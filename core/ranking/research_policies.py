"""Versioned, deterministic research-feed policies.

The public/product feed remains owned by ``build_feed_payload``. Research
policies consume that same safe, categorized inventory and add only the
versioned experimental selection/provenance described here.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter

from .feed import build_feed_payload


REGULAR_POLICY_VERSION = "regular-v1"
BALANCED_POLICY_VERSION = "balanced-v1"
POLICY_VERSION_BY_CONDITION = {
    "regular": REGULAR_POLICY_VERSION,
    "balanced": BALANCED_POLICY_VERSION,
}
SUPPORTED_POLICY_VERSIONS = frozenset(POLICY_VERSION_BY_CONDITION.values())

BALANCED_TARGETS = {
    "normal": 0.60,
    "healthy": 0.30,
    "diversity": 0.10,
}
HEALTHY_CATEGORIES = frozenset({"healthy", "positive"})

_PRIVATE_ITEM_FIELDS = frozenset({
    "chrysalis_scores",
    "mode_fit",
    "integrity_score",
    "integrityScore",
    "feed_validity_score",
    "feedValidityScore",
    "integrity_flags",
    "integrityFlags",
    "wellness_score",
    "wellnessScore",
    "positivity_score",
    "positivityScore",
    "conflict_score",
    "conflictScore",
    "safety_risk",
    "safetyRisk",
})


def policy_version_for_condition(condition: str) -> str:
    try:
        return POLICY_VERSION_BY_CONDITION[condition]
    except KeyError as exc:
        raise ValueError("Unsupported research feed condition") from exc


def build_research_feed_payload(
    rows: list[dict],
    *,
    policy_version: str,
    k: int = 12,
    seed: str,
    exclude_ids: list[str] | set[str] | None = None,
    public_signal_context=None,
) -> dict:
    """Build one research window without exposing the private server seed.

    ``regular-v1`` delegates to the existing product builder at the requested
    size. ``balanced-v1`` asks that same builder for a wider eligible candidate
    window, then applies the explicit 60/30/10 research selector.
    """
    safe_k = max(0, int(k))
    if policy_version not in SUPPORTED_POLICY_VERSIONS:
        raise ValueError("Unsupported research feed policy version")

    candidate_k = safe_k
    if policy_version == BALANCED_POLICY_VERSION:
        candidate_k = min(len(rows), max(safe_k, safe_k * 5))

    base = build_feed_payload(
        rows,
        "flutter-feed",
        k=candidate_k,
        public_signal_context=public_signal_context,
        shuffle_seed=seed,
        exclude_ids=exclude_ids,
    )
    selected = apply_research_policy(
        base.get("items") or [],
        policy_version=policy_version,
        k=safe_k,
        seed=seed,
    )
    public_items = [_public_item(item) for item in selected]
    eligible_pool_count = int(base.get("eligible_pool_count") or 0)
    excluded_count = len({str(value) for value in (exclude_ids or []) if str(value)})
    eligible_remaining = max(0, eligible_pool_count - excluded_count)
    returned_count = len(public_items)
    return {
        "count": returned_count,
        "items": public_items,
        "returned_count": returned_count,
        "eligible_pool_count": eligible_pool_count,
        "has_more": eligible_remaining > returned_count,
        "next_offset": excluded_count + returned_count,
        "policy_version": policy_version,
    }


def apply_research_policy(
    items: list[dict],
    *,
    policy_version: str,
    k: int,
    seed: str,
) -> list[dict]:
    """Select and annotate an auditable research feed window."""
    target = min(max(0, int(k)), len(_dedupe(items)))
    if policy_version == REGULAR_POLICY_VERSION:
        return [
            _with_provenance(
                item,
                position=position,
                policy_version=policy_version,
                bucket="normal",
                reason="existing_chrysalis_rank",
            )
            for position, item in enumerate(_dedupe(items)[:target])
        ]
    if policy_version != BALANCED_POLICY_VERSION:
        raise ValueError("Unsupported research feed policy version")
    return _balanced_window(_dedupe(items), target=target, seed=seed)


def target_bucket_counts(size: int) -> dict[str, int]:
    """Largest-remainder allocation for the balanced 60/30/10 targets."""
    size = max(0, int(size))
    exact = {bucket: size * ratio for bucket, ratio in BALANCED_TARGETS.items()}
    counts = {bucket: math.floor(value) for bucket, value in exact.items()}
    remaining = size - sum(counts.values())
    priority = {"normal": 0, "healthy": 1, "diversity": 2}
    order = sorted(
        exact,
        key=lambda bucket: (-(exact[bucket] - counts[bucket]), priority[bucket]),
    )
    for bucket in order[:remaining]:
        counts[bucket] += 1
    return counts


def _balanced_window(items: list[dict], *, target: int, seed: str) -> list[dict]:
    if target == 0:
        return []
    ordered = sorted(items, key=lambda item: _seed_key(seed, _post_id(item)))
    buckets = {"normal": [], "healthy": [], "diversity": []}
    for item in ordered:
        buckets[_selection_bucket(item)].append(item)

    schedule = _smooth_bucket_schedule(target_bucket_counts(target))
    selected: list[dict] = []
    selected_ids: set[str] = set()
    reasons: list[tuple[str, str]] = []
    for desired_bucket in schedule:
        candidate, actual_bucket = _take_candidate(
            buckets,
            desired_bucket=desired_bucket,
            selected=selected,
            selected_ids=selected_ids,
        )
        if candidate is None:
            break
        selected.append(candidate)
        selected_ids.add(_post_id(candidate))
        reasons.append((
            actual_bucket,
            _target_reason(actual_bucket) if actual_bucket == desired_bucket else "inventory_fallback",
        ))

    # A malformed or unexpectedly categorized pool may leave a scheduled slot
    # empty. Fill once from every remaining item; never retry indefinitely.
    while len(selected) < target:
        candidate, actual_bucket = _take_candidate(
            buckets,
            desired_bucket=None,
            selected=selected,
            selected_ids=selected_ids,
        )
        if candidate is None:
            break
        selected.append(candidate)
        selected_ids.add(_post_id(candidate))
        reasons.append((actual_bucket, "inventory_fallback"))

    return [
        _with_provenance(
            item,
            position=position,
            policy_version=BALANCED_POLICY_VERSION,
            bucket=reasons[position][0],
            reason=reasons[position][1],
        )
        for position, item in enumerate(selected)
    ]


def _smooth_bucket_schedule(counts: dict[str, int]) -> list[str]:
    total = sum(counts.values())
    used: Counter[str] = Counter()
    priority = {"normal": 0, "healthy": 1, "diversity": 2}
    schedule: list[str] = []
    for position in range(total):
        available = [bucket for bucket, count in counts.items() if used[bucket] < count]
        bucket = max(
            available,
            key=lambda name: (
                counts[name] * (position + 1) / total - used[name],
                -priority[name],
            ),
        )
        schedule.append(bucket)
        used[bucket] += 1
    return schedule


def _take_candidate(
    buckets: dict[str, list[dict]],
    *,
    desired_bucket: str | None,
    selected: list[dict],
    selected_ids: set[str],
) -> tuple[dict | None, str | None]:
    bucket_order = [desired_bucket] if desired_bucket else []
    bucket_order.extend(name for name in ("normal", "healthy", "diversity") if name != desired_bucket)
    choices: list[tuple[tuple, int, int, str, dict]] = []
    for bucket_rank, bucket in enumerate(bucket_order):
        if bucket is None:
            continue
        for index, item in enumerate(buckets[bucket]):
            if _post_id(item) in selected_ids:
                continue
            choices.append((_candidate_penalty(item, selected), bucket_rank, index, bucket, item))
        if choices and bucket == desired_bucket:
            break
    if not choices:
        return None, None
    _penalty, _bucket_rank, index, bucket, item = min(
        choices,
        key=lambda choice: (choice[0], choice[1], choice[2]),
    )
    buckets[bucket].pop(index)
    return item, bucket


def _candidate_penalty(item: dict, selected: list[dict]) -> tuple[int, int, int]:
    category = _category(item)
    creator = _creator(item)
    third_category = int(
        len(selected) >= 2
        and _category(selected[-1]) == category
        and _category(selected[-2]) == category
    )
    recent_creators = {_creator(value) for value in selected[-4:]}
    all_creators = {_creator(value) for value in selected}
    return (
        third_category,
        int(creator in recent_creators),
        int(creator in all_creators),
    )


def _selection_bucket(item: dict) -> str:
    category = _category(item)
    if category in HEALTHY_CATEGORIES:
        return "healthy"
    if category == "perspective":
        return "diversity"
    return "normal"


def _target_reason(bucket: str) -> str:
    return {
        "normal": "normal_interest_target",
        "healthy": "healthy_category_target",
        "diversity": "perspective_variety_target",
    }[bucket]


def _with_provenance(
    item: dict,
    *,
    position: int,
    policy_version: str,
    bucket: str,
    reason: str,
) -> dict:
    return {
        **item,
        "post_id": _post_id(item),
        "feed_position": position,
        "feed_policy_version": policy_version,
        "selection_bucket": bucket,
        "selection_reason": reason,
    }


def _public_item(item: dict) -> dict:
    return {key: value for key, value in item.items() if key not in _PRIVATE_ITEM_FIELDS}


def _dedupe(items: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for item in items:
        post_id = _post_id(item)
        if not post_id or post_id in seen:
            continue
        seen.add(post_id)
        result.append(dict(item))
    return result


def _post_id(item: dict) -> str:
    return str(item.get("post_id") or item.get("youtube_id") or item.get("video_id") or item.get("id") or "")


def _category(item: dict) -> str:
    value = str(item.get("content_category") or item.get("contentCategory") or "").strip().lower()
    return value or "unknown"


def _creator(item: dict) -> str:
    value = str(item.get("channel_id") or item.get("channel_title") or item.get("source") or "").strip().lower()
    return value or f"unknown:{_post_id(item)}"


def _seed_key(seed: str, post_id: str) -> tuple[str, str]:
    digest = hashlib.sha256(f"{seed}|balanced-v1|{post_id}".encode("utf-8")).hexdigest()
    return digest, post_id
