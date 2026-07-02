"""
Shared feed ranking (v2).

All reels modes draw from the same safe, broad video pool. Mode-specific behavior
lives in the reflection/explanation layer, not in separate content pools. Ranking
therefore applies one shared safety gate, one shared relevance score, then balances
source metadata so no single ingestion query or category dominates the feed.
"""

from __future__ import annotations

import hashlib
import math
import os

from .. import algorithm as _alg  # reuse calculate_gini for the diversity proxy
from ..feed_integrity import DEFAULT_INTEGRITY_SCORE, INTEGRITY_MIN_SCORE
from ..labeling.schema import LabelSet
from ..labeling.taxonomy import HEALTHY_CATEGORIES, classify_content, is_healthy_category
from ..public_signals.ranking import PublicSignalContext, evaluate_public_signal

MODES = ("daily-dew", "metamorphosis", "flutter-feed")


def is_valid_mode(mode: str) -> bool:
    return mode in MODE_PROFILES


SHARED_FEED_CAPS = {
    "overall_risk": 0.65,
    "comparison_risk": 0.65,
    "appearance_focus": 0.65,
    "shame_or_humiliation_risk": 0.45,
    "ragebait": 0.45,
    "age_safety_risk": 0.65,
    "misinformation_risk": 0.65,
    "overstimulation": 0.85,
}
SHARED_MIN_CONFIDENCE = 0.12

# --- Popular / trending lane policy -----------------------------------------
# Maximum additive boost a video's capped popularity_score can add to its
# mode_fit. Kept deliberately small: a healthy-signal gap (e.g. a ~0.4 higher
# calm score) moves mode_fit more than this cap, so popularity tilts *ties*
# toward familiar content but never lets one viral hit outrank a genuinely
# calmer/safer/healthier video. That, plus the per-mode budget below, is what
# keeps the feed from collapsing into a pure popularity ranking.
POPULARITY_BOOST_CAP = 0.04

# How many popular-lane picks may appear in the final feed for each mode.
#   daily-dew     → a small taste (calm, grounding mode)
#   metamorphosis → very few, and only when low-risk (see guard below)
#   flutter-feed  → unlimited (closest to a normal feed)
POPULAR_BUDGET_BY_MODE: dict[str, int | None] = {
    "daily-dew": 2,
    "metamorphosis": 2,
    "flutter-feed": None,
}
# Metamorphosis is the strictest mode: only surface popular picks whose overall
# risk is at/below this floor, regardless of the per-mode budget.
METAMORPHOSIS_POPULAR_MAX_RISK = 0.2


def _resolve_popular_min_score() -> float:
    """Read POPULAR_MIN_SCORE from the env, defaulting to 0.75 on absent/invalid."""
    raw = os.environ.get("POPULAR_MIN_SCORE")
    if raw is None or not raw.strip():
        return 0.75
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.75


# Minimum popularity_score a "most_popular" candidate must reach to be eligible
# for the feed. Weak trending picks below this floor are dropped both at
# extraction and at feed-load time. Search-lane candidates are *exempt* — niche
# / high-quality search results are allowed to be low-popularity. Configurable
# via the POPULAR_MIN_SCORE env var; defaults to 0.75.
POPULAR_MIN_SCORE = _resolve_popular_min_score()


# --- Healthier-feed mix policy ----------------------------------------------
# The final feed should still feel like normal short-form video: a substantial
# wellness/positive lane, but never an all-wellness lecture reel when regular
# safe entertainment is available.
HEALTHY_TARGET_MIN_RATIO = 0.40
HEALTHY_TARGET_MAX_RATIO = 0.60
PERSPECTIVE_MIN_FEED_SIZE = 6
REGULAR_MIN_FEED_SIZE = 4

TAXONOMY_SCORE_ADJUSTMENTS = {
    "healthy": 0.06,
    "positive": 0.05,
    "perspective": 0.025,
    "regular": 0.0,
    "reduced": -0.35,
    "blocked": -1.0,
}


def _is_popular(item: dict) -> bool:
    return str(item.get("source_type") or "").strip().lower() == "most_popular"


def popular_passes_min_score(source_type, popularity_score) -> bool:
    """True if a candidate clears the popular-lane popularity floor.

    Only ``most_popular`` candidates are gated; every other source type (search)
    always passes, since search results may be legitimately low-popularity.
    Reads ``POPULAR_MIN_SCORE`` at call time so env / test overrides take effect.
    """
    if str(source_type or "").strip().lower() != "most_popular":
        return True
    score = _safe_score(popularity_score)
    return (score if score is not None else 0.0) >= POPULAR_MIN_SCORE


# Each profile:
#   pos:  weights over positive dims
#   risk: weights over risk dims (subtracted)
#   caps: hard upper bounds — exceed any → gated out
#   min_pos: hard lower bounds on positive dims → below any → gated out
#   min_any_pos: at least one named positive dim must meet a floor
#   min_confidence: confidence floor
#
# clip-fit hook (future): Daily Dew / Metamorphosis are short, clip-style feeds, so
# long-form videos (duration_seconds ≥ ~20 min, see _LONG_DURATION_S in
# core/labeling/metadata_scoring.py) are a weaker fit. A later pass can fold a soft
# clip-fit factor into score_for_mode (e.g. a small mode_fit multiplier for
# non-clip-like durations) — kept out of v1 so duration stays a scoring-only signal
# and never hard-gates a video purely for being long.
MODE_PROFILES: dict[str, dict] = {
    # Calm, grounding, low-risk. Strict on comparison / overstimulation / overall risk.
    "daily-dew": {
        "pos": {
            "calm": 0.30, "prosocial": 0.22, "self_love": 0.20,
            "reflection_value": 0.18, "educational": 0.07, "diversity": 0.03,
        },
        "risk": {
            "comparison_risk": 0.9, "overstimulation": 0.8, "overall_risk": 0.8,
            "appearance_focus": 0.8, "ragebait": 0.7, "shame_or_humiliation_risk": 0.7,
            "consumerism": 0.4, "age_safety_risk": 0.6, "misinformation_risk": 0.4,
        },
        "caps": {
            "comparison_risk": 0.3, "appearance_focus": 0.3, "ragebait": 0.3,
            "overstimulation": 0.3, "shame_or_humiliation_risk": 0.3, "overall_risk": 0.4,
        },
        "min_pos": {},
        "min_any_pos": {
            "dims": ("calm", "prosocial", "self_love", "reflection_value", "educational"),
            "floor": 0.3,
        },
        "min_confidence": 0.25,
    },
    # Strictest. Only very-calm, very-low-risk real videos pass; novelty is penalized.
    # The frontend keeps synthetic pause cards primary; the backend supplies only a few.
    "metamorphosis": {
        "pos": {
            "calm": 0.50, "reflection_value": 0.20, "self_love": 0.15,
            "prosocial": 0.15, "educational": 0.05,
        },
        "risk": {
            "overstimulation": 1.0, "overall_risk": 1.0, "ragebait": 0.9,
            "comparison_risk": 0.9, "appearance_focus": 0.9, "shame_or_humiliation_risk": 0.9,
            "consumerism": 0.7, "age_safety_risk": 0.9, "misinformation_risk": 0.7,
            "novelty": 0.5,  # downrank addictive novelty/intensity
        },
        "caps": {
            "overall_risk": 0.2, "overstimulation": 0.2, "comparison_risk": 0.2,
            "appearance_focus": 0.2, "ragebait": 0.2, "shame_or_humiliation_risk": 0.2,
        },
        "min_pos": {"calm": 0.5},
        "min_any_pos": {},
        "min_confidence": 0.3,
    },
    # More variety/novelty allowed, but still downranks shame/comparison/ragebait/
    # appearance/overall risk. Closest to a normal feed.
    "flutter-feed": {
        "pos": {
            "prosocial": 0.18, "novelty": 0.18, "educational": 0.15, "calm": 0.15,
            "self_love": 0.12, "reflection_value": 0.12, "diversity": 0.10,
        },
        "risk": {
            "comparison_risk": 0.7, "ragebait": 0.7, "shame_or_humiliation_risk": 0.7,
            "appearance_focus": 0.6, "overall_risk": 0.6, "age_safety_risk": 0.6,
            "misinformation_risk": 0.5, "overstimulation": 0.5, "consumerism": 0.4,
        },
        "caps": {
            "overall_risk": 0.7, "comparison_risk": 0.6, "ragebait": 0.6,
            "appearance_focus": 0.6, "shame_or_humiliation_risk": 0.6, "overstimulation": 0.7,
        },
        "min_pos": {},
        "min_any_pos": {},
        "min_confidence": 0.15,
    },
}


def score_for_mode(labels: LabelSet, mode: str) -> float:
    """0–1 fit of a labeled video for a mode. Higher = better fit."""
    profile = MODE_PROFILES[mode]
    pos_w = profile["pos"]
    risk_w = profile["risk"]

    value = sum(w * getattr(labels, d, 0.0) for d, w in pos_w.items())
    risk = sum(w * getattr(labels, d, 0.0) for d, w in risk_w.items())

    norm = sum(pos_w.values()) or 1.0
    return _alg_clamp((value - risk) / norm)


def score_for_shared_feed(labels: LabelSet, ingest_score: float | None = None) -> float:
    """Shared 0-1 relevance score used for every reels mode's video source."""
    value = (
        0.18 * labels.prosocial
        + 0.17 * labels.educational
        + 0.16 * labels.novelty
        + 0.14 * labels.calm
        + 0.12 * labels.reflection_value
        + 0.10 * labels.self_love
        + 0.08 * labels.diversity
    )
    risk = (
        0.32 * labels.overall_risk
        + 0.18 * labels.ragebait
        + 0.16 * labels.shame_or_humiliation_risk
        + 0.12 * labels.comparison_risk
        + 0.10 * labels.appearance_focus
        + 0.08 * labels.misinformation_risk
        + 0.06 * labels.age_safety_risk
        + 0.04 * labels.overstimulation
    )
    label_score = _alg_clamp(value - risk + 0.35)
    if ingest_score is None:
        return label_score
    return _alg_clamp((0.62 * label_score) + (0.38 * ingest_score))


def passes_shared_feed_gate(labels: LabelSet) -> bool:
    """Shared safe/relevant filter used by all modes before balancing."""
    if labels.confidence < SHARED_MIN_CONFIDENCE:
        return False
    for dim, cap in SHARED_FEED_CAPS.items():
        if getattr(labels, dim, 0.0) > cap:
            return False
    return True


def passes_gate(labels: LabelSet, mode: str) -> bool:
    """Compatibility wrapper: all modes now use the same video-source gate."""
    if not is_valid_mode(mode):
        return False
    return passes_shared_feed_gate(labels)


def rank_videos(
    items: list[dict],
    mode: str,
    k: int = 12,
    public_signal_context: PublicSignalContext | None = None,
    public_signal_override: bool = False,
    shuffle_seed: str | None = None,
) -> list[dict]:
    """
    Shared gate → shared score → source balancing. Each input item must carry a
    `labels` LabelSet; returned items are annotated with `mode_fit` for API
    compatibility. Public-signal context can downrank, request review, or exclude
    only when the context policy requires it.
    """
    if not is_valid_mode(mode):
        return []

    scored: list[dict] = []
    for item in items:
        labels = item.get("labels")
        if not isinstance(labels, LabelSet):
            labels = LabelSet.from_dict(labels or {})
        if not passes_shared_feed_gate(labels):
            continue
        taxonomy_fields = _taxonomy_fields(item, labels)
        content_category = taxonomy_fields["content_category"]
        if content_category == "blocked":
            continue
        # Metamorphosis only tolerates popular-lane picks when they are genuinely
        # low-risk — popularity must never relax this mode's calm guarantee.
        if (
            mode == "metamorphosis"
            and _is_popular(item)
            and getattr(labels, "overall_risk", 0.0) > METAMORPHOSIS_POPULAR_MAX_RISK
        ):
            continue
        integrity_score = _safe_score(item.get("integrity_score"))
        if integrity_score is None:
            integrity_score = DEFAULT_INTEGRITY_SCORE
        if integrity_score < INTEGRITY_MIN_SCORE:
            continue

        public_eval = evaluate_public_signal(
            item,
            labels,
            context=public_signal_context,
            public_signal_override=public_signal_override,
        )
        if not public_eval.allowed:
            continue

        annotated = dict(item)
        annotated["labels"] = labels
        annotated["integrity_score"] = round(integrity_score, 4)
        # Capped popularity boost: small additive nudge from the precomputed
        # popularity_score (views/likes/comments/freshness), bounded by
        # POPULARITY_BOOST_CAP so it can break ties toward familiar content but
        # never override the core safety/relevance ranking.
        popularity = _safe_score(item.get("popularity_score")) or 0.0
        base_mode_fit = (
            (0.90 * score_for_shared_feed(labels, _safe_score(item.get("ingest_score"))))
            + (0.10 * integrity_score)
            + public_eval.score_delta
            + TAXONOMY_SCORE_ADJUSTMENTS.get(content_category, 0.0)
        )
        annotated["mode_fit"] = _alg_clamp(base_mode_fit + POPULARITY_BOOST_CAP * popularity)
        annotated.update(taxonomy_fields)
        annotated["recommendation_lane"] = _recommendation_lane(content_category)
        annotated.update(public_eval.to_item_fields())
        scored.append(annotated)

    balanced = _balance_source_metadata(scored, shuffle_seed=shuffle_seed)
    popular_budgeted = _select_with_popular_budget(balanced, mode, len(balanced))
    return _balance_content_mix(popular_budgeted, k, shuffle_seed=shuffle_seed)


def _select_with_popular_budget(ordered: list[dict], mode: str, k: int) -> list[dict]:
    """Take the top ``k`` while capping how many popular-lane picks appear.

    Preserves the balanced ordering; once a mode's popular budget is spent,
    further popular items are skipped and their slots go to the next eligible
    (non-popular) candidates. A mode with an unlimited budget (flutter-feed) is
    a plain top-k.
    """
    budget = POPULAR_BUDGET_BY_MODE.get(mode)
    if budget is None:
        return ordered[:k]

    result: list[dict] = []
    popular_used = 0
    for item in ordered:
        if len(result) >= k:
            break
        if _is_popular(item):
            if popular_used >= budget:
                continue
            popular_used += 1
        result.append(item)
    return result


def _balance_content_mix(
    ordered: list[dict],
    k: int,
    *,
    shuffle_seed: str | None = None,
) -> list[dict]:
    """Select a healthier short-form mix from already-scored safe candidates.

    The selector uses taxonomy lanes instead of ML: target 40%-60% healthy
    (healthy + positive) when inventory allows, reserve room for safe regular
    content, include a low-conflict perspective lane occasionally, and use reduced
    content only as a last-resort filler.
    """
    target = min(max(int(k), 0), len(ordered))
    if target == 0:
        return []

    buckets = _content_buckets(ordered)
    healthy_items = buckets["healthy"] + buckets["positive"]
    regular_items = buckets["regular"]
    perspective_items = buckets["perspective"]
    other_items = buckets["other"]
    reduced_items = buckets["reduced"]
    safe_nonhealthy_count = len(regular_items) + len(perspective_items) + len(other_items)
    nonhealthy_count = safe_nonhealthy_count + len(reduced_items)

    healthy_min = math.ceil(target * HEALTHY_TARGET_MIN_RATIO)
    healthy_max = max(healthy_min, math.floor(target * HEALTHY_TARGET_MAX_RATIO))
    desired_healthy = min(len(healthy_items), max(healthy_min, round(target * 0.5)))

    if nonhealthy_count < target - desired_healthy:
        desired_healthy = min(len(healthy_items), target - nonhealthy_count)
    desired_healthy = min(desired_healthy, healthy_max)
    if len(healthy_items) < healthy_min:
        desired_healthy = len(healthy_items)

    nonhealthy_slots = target - desired_healthy
    required_regular = 1 if target >= REGULAR_MIN_FEED_SIZE and regular_items else 0
    required_perspective = 1 if target >= PERSPECTIVE_MIN_FEED_SIZE and perspective_items else 0
    required_nonhealthy = required_regular + required_perspective
    if nonhealthy_slots < required_nonhealthy:
        shift = min(desired_healthy, required_nonhealthy - nonhealthy_slots)
        desired_healthy -= shift
        nonhealthy_slots += shift

    selected: list[dict] = []
    selected.extend(_take_round_robin(
        {"healthy": buckets["healthy"], "positive": buckets["positive"]},
        desired_healthy,
        shuffle_seed=shuffle_seed,
    ))

    selected.extend(_take_first(regular_items, min(required_regular, nonhealthy_slots)))
    nonhealthy_slots = target - len(selected)
    selected.extend(_take_first(perspective_items, min(required_perspective, nonhealthy_slots)))
    nonhealthy_slots = target - len(selected)

    used_ids = {_item_identity(item) for item in selected}
    remaining_regular = _without_ids(regular_items, used_ids)
    remaining_perspective = _without_ids(perspective_items, used_ids)
    remaining_other = _without_ids(other_items, used_ids)
    remaining_reduced = _without_ids(reduced_items, used_ids)

    selected.extend(_take_round_robin(
        {
            "regular": remaining_regular,
            "perspective": remaining_perspective,
            "other": remaining_other,
        },
        nonhealthy_slots,
        shuffle_seed=shuffle_seed,
    ))

    if len(selected) < target:
        used_ids = {_item_identity(item) for item in selected}
        selected.extend(_take_round_robin(
            {
                "healthy": _without_ids(buckets["healthy"], used_ids),
                "positive": _without_ids(buckets["positive"], used_ids),
                "regular": _without_ids(regular_items, used_ids),
                "perspective": _without_ids(perspective_items, used_ids),
                "other": _without_ids(other_items, used_ids),
            },
            target - len(selected),
            shuffle_seed=shuffle_seed,
        ))

    if len(selected) < target:
        used_ids = {_item_identity(item) for item in selected}
        selected.extend(_take_first(_without_ids(remaining_reduced, used_ids), target - len(selected)))

    return _spread_content_categories(selected[:target], shuffle_seed=shuffle_seed)


def _content_buckets(items: list[dict]) -> dict[str, list[dict]]:
    buckets = {
        "healthy": [],
        "positive": [],
        "regular": [],
        "perspective": [],
        "reduced": [],
        "other": [],
    }
    for item in items:
        category = _content_category(item)
        if category in buckets:
            buckets[category].append(item)
        elif is_healthy_category(category):
            buckets["healthy"].append(item)
        else:
            buckets["other"].append(item)
    return buckets


def _take_first(items: list[dict], limit: int) -> list[dict]:
    if limit <= 0:
        return []
    return list(items[:limit])


def _take_round_robin(
    buckets: dict[str, list[dict]],
    limit: int,
    *,
    shuffle_seed: str | None,
) -> list[dict]:
    if limit <= 0:
        return []
    local = {key: list(value) for key, value in buckets.items() if value}
    order = _ordered_bucket_keys(local, salt="content_take", shuffle_seed=shuffle_seed)
    result: list[dict] = []
    while len(result) < limit and any(local.values()):
        for key in order:
            if len(result) >= limit:
                break
            if local.get(key):
                result.append(local[key].pop(0))
    return result


def _spread_content_categories(items: list[dict], *, shuffle_seed: str | None) -> list[dict]:
    if len(items) <= 2:
        return sorted(items, key=lambda item: _feed_sort_key(item, shuffle_seed))

    buckets: dict[str, list[dict]] = {}
    for item in items:
        buckets.setdefault(_content_category(item), []).append(item)

    order = _ordered_bucket_keys(buckets, salt="content_category", shuffle_seed=shuffle_seed)
    order_index = {value: index for index, value in enumerate(order)}
    result: list[dict] = []
    while any(buckets[value] for value in order):
        last_category = _content_category(result[-1]) if result else None
        choices = [
            value for value in order
            if buckets[value] and value != last_category
        ]
        if not choices:
            choices = [value for value in order if buckets[value]]
        pick = sorted(choices, key=lambda value: (-len(buckets[value]), order_index[value]))[0]
        result.append(buckets[pick].pop(0))
    return result


def _ordered_bucket_keys(
    buckets: dict[str, list[dict]],
    *,
    salt: str,
    shuffle_seed: str | None,
) -> list[str]:
    return sorted(
        buckets,
        key=lambda value: _bucket_sort_key(
            value,
            buckets[value],
            salt=salt,
            shuffle_seed=shuffle_seed,
        ),
    )


def _without_ids(items: list[dict], used_ids: set[str]) -> list[dict]:
    return [item for item in items if _item_identity(item) not in used_ids]


def _balance_source_metadata(items: list[dict], *, shuffle_seed: str | None = None) -> list[dict]:
    """
    Round-robin source categories, with query/style/scale spread inside each
    category. Production style and creator scale are diversity metadata, not
    polish gates.
    """
    if len(items) <= 2:
        return sorted(items, key=lambda item: _feed_sort_key(item, shuffle_seed))

    category_buckets: dict[str, list[dict]] = {}
    for item in sorted(items, key=lambda item: _feed_sort_key(item, shuffle_seed)):
        category = _source_value(item, "source_category", "topic", "category")
        category_buckets.setdefault(category, []).append(item)

    for category, bucket in category_buckets.items():
        category_buckets[category] = _spread_source_queries(bucket, shuffle_seed=shuffle_seed)

    category_order = sorted(
        category_buckets,
        key=lambda category: _bucket_sort_key(
            category,
            category_buckets[category],
            salt="category",
            shuffle_seed=shuffle_seed,
        ),
    )

    result: list[dict] = []
    while any(category_buckets[category] for category in category_order):
        for category in category_order:
            if category_buckets[category]:
                result.append(category_buckets[category].pop(0))
    return result


def _spread_source_queries(items: list[dict], *, shuffle_seed: str | None = None) -> list[dict]:
    if len(items) <= 2:
        return _spread_style_and_scale(items, shuffle_seed=shuffle_seed)

    query_buckets: dict[str, list[dict]] = {}
    for item in sorted(items, key=lambda item: _feed_sort_key(item, shuffle_seed)):
        query = _source_value(item, "source_query")
        query_buckets.setdefault(query, []).append(item)

    for query, bucket in query_buckets.items():
        query_buckets[query] = _spread_style_and_scale(bucket, shuffle_seed=shuffle_seed)

    query_order = sorted(
        query_buckets,
        key=lambda query: _bucket_sort_key(
            query,
            query_buckets[query],
            salt="query",
            shuffle_seed=shuffle_seed,
        ),
    )

    result: list[dict] = []
    while any(query_buckets[query] for query in query_order):
        for query in query_order:
            if query_buckets[query]:
                result.append(query_buckets[query].pop(0))
    return result


def _spread_style_and_scale(items: list[dict], *, shuffle_seed: str | None = None) -> list[dict]:
    balanced = _spread_metadata_field(
        items,
        "production_style",
        salt="production_style",
        shuffle_seed=shuffle_seed,
    )
    return _spread_metadata_field(
        balanced,
        "creator_scale",
        salt="creator_scale",
        shuffle_seed=shuffle_seed,
    )


def _spread_metadata_field(
    items: list[dict],
    field: str,
    *,
    salt: str,
    shuffle_seed: str | None = None,
) -> list[dict]:
    if len(items) <= 2:
        return sorted(items, key=lambda item: _feed_sort_key(item, shuffle_seed))

    buckets: dict[str, list[dict]] = {}
    for item in sorted(items, key=lambda item: _feed_sort_key(item, shuffle_seed)):
        value = _source_value(item, field)
        buckets.setdefault(value, []).append(item)

    order = sorted(
        buckets,
        key=lambda value: _bucket_sort_key(
            value,
            buckets[value],
            salt=salt,
            shuffle_seed=shuffle_seed,
        ),
    )

    result: list[dict] = []
    while any(buckets[value] for value in order):
        for value in order:
            if buckets[value]:
                result.append(buckets[value].pop(0))
    return result


def _feed_sort_key(item: dict, shuffle_seed: str | None = None) -> tuple[float, float]:
    if not shuffle_seed:
        return (-round(_item_score(item), 2), _stable_random_value("item", _item_identity(item)))
    return (
        _stable_random_value("item", _item_identity(item), shuffle_seed=shuffle_seed),
        -round(_item_score(item), 2),
    )


def _bucket_sort_key(
    value: str,
    items: list[dict],
    *,
    salt: str,
    shuffle_seed: str | None,
) -> tuple[float, float]:
    random_value = _stable_random_value(salt, value, shuffle_seed=shuffle_seed)
    score_value = -max(_item_score(item) for item in items)
    if not shuffle_seed:
        return (score_value, random_value)
    return (random_value, score_value)


def _item_score(item: dict) -> float:
    return float(item.get("mode_fit") or item.get("ingest_score") or 0.0)


def _source_value(item: dict, *fields: str) -> str:
    for field in fields:
        value = str(item.get(field) or "").strip().lower()
        if value:
            return value
    return "_"


def _taxonomy_fields(item: dict, labels: LabelSet) -> dict:
    taxonomy = item.get("taxonomy")
    if hasattr(taxonomy, "to_dict"):
        fields = taxonomy.to_dict()
    else:
        fields = classify_content(labels, item).to_dict()

    explicit_category = str(item.get("content_category") or "").strip().lower()
    if explicit_category:
        fields["content_category"] = explicit_category
    for field in ("wellness_score", "positivity_score", "conflict_score", "safety_risk"):
        explicit_score = _safe_score(item.get(field))
        if explicit_score is not None:
            fields[field] = round(explicit_score, 4)
    if item.get("perspective_topic"):
        fields["perspective_topic"] = item.get("perspective_topic")
    return fields


def _content_category(item: dict) -> str:
    category = str(item.get("content_category") or "").strip().lower()
    if not category:
        return "regular"
    if category in HEALTHY_CATEGORIES:
        return category
    if category in {"regular", "perspective", "reduced", "blocked"}:
        return category
    return "regular"


def _recommendation_lane(category: str) -> str:
    if is_healthy_category(category):
        return "healthy_mix"
    if category == "perspective":
        return "perspective_mix"
    if category == "reduced":
        return "reduced_filler"
    return "regular_mix"


def _item_identity(item: dict) -> str:
    return str(item.get("video_id") or item.get("youtube_id") or item.get("id") or "")


def _safe_score(value) -> float | None:
    try:
        if value is None:
            return None
        return _alg_clamp(float(value))
    except (TypeError, ValueError):
        return None


def _feed_random_seed() -> str:
    return os.environ.get("CHRYSALIS_FEED_RANDOM_SEED") or "chrysalis-default-feed-seed"


def _stable_random_value(*parts: str, shuffle_seed: str | None = None) -> float:
    raw = "|".join((str(shuffle_seed or _feed_random_seed()), *parts))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return int(digest, 16) / float(0xFFFFFFFFFFFF)


def _alg_clamp(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return float(v)


# Touch the import so linters don't flag it; the diversity proxy below uses it.
def topic_gini(topics: list[str]) -> float:
    """Diversity proxy over a list of topics (0 = uniform spread … 1 = all one topic)."""
    if not topics:
        return 0.0
    counts: dict[str, int] = {}
    for t in topics:
        counts[t] = counts.get(t, 0) + 1
    return float(_alg.calculate_gini(list(counts.values())))
