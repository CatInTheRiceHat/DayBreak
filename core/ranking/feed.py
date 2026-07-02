"""
Shared, pure feed builder (v1).

`build_feed` takes raw video rows (plain dicts, as read from either SQLite or
Postgres), applies the shared safe-feed ranking, and returns mode-specific
explanations over the same broad video pool. No DB or network here, so both API
files (api.py / api/index.py) and the unit tests call the exact same logic.
"""

from __future__ import annotations

from collections import Counter
import json
import secrets

from ..feed_captions import (
    build_display_channel,
    build_display_hashtags,
    build_display_title,
    build_short_description,
)
from ..feed_integrity import INTEGRITY_MIN_SCORE, normalize_integrity_flags, resolve_feed_integrity
from ..labeling.schema import LabelSet, SCORING_VERSION
from ..labeling.metadata_scoring import (
    score_metadata,
    parse_duration_seconds,
    _normalize_tags,
)
from ..labeling.explain import build_reasons
from ..labeling.taxonomy import classify_content, is_healthy_category
from ..language_filter import (
    ALLOWED_LANGUAGE_PREFIXES,
    ALLOWED_REGION,
    BLOCKED_LANGUAGE_CODES,
    LANGUAGE_POLICY,
    verdict as language_verdict,
)
from ..public_signals.ranking import PublicSignalContext
from .modes import (
    HEALTHY_TARGET_MAX_RATIO,
    HEALTHY_TARGET_MIN_RATIO,
    POPULAR_MIN_SCORE,
    is_valid_mode,
    popular_passes_min_score,
    rank_videos,
)

_THUMB = "https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
_EMBED = "https://www.youtube-nocookie.com/embed/{vid}"
_WATCH = "https://www.youtube.com/watch?v={vid}"

# Cap tags surfaced to the client — enough to be useful, not a debug dump.
_MAX_API_TAGS = 15
_MAX_SEED_LENGTH = 96


def _labels_for_row(row: dict) -> LabelSet:
    """Reuse stored v1 scores when present and current; otherwise score on the fly."""
    stored = row.get("chrysalis_scores")
    version = row.get("scoring_version")
    if stored and version == SCORING_VERSION:
        if isinstance(stored, str):
            try:
                stored = json.loads(stored)
            except (ValueError, TypeError):
                stored = None
        if isinstance(stored, dict):
            return LabelSet.from_dict(stored)
    return score_metadata(row)


def label_row(row: dict) -> LabelSet:
    """Public helper (used by the backfill script): label one raw video row."""
    return _labels_for_row(row)


def build_feed(
    rows: list[dict],
    mode: str,
    k: int = 12,
    public_signal_context: PublicSignalContext | None = None,
    public_signal_override: bool = False,
    shuffle_seed: str | None = None,
    offset: int = 0,
    exclude_ids: list[str] | set[str] | None = None,
) -> list[dict]:
    """
    Returns a list of API-ready items for `mode`:
      { youtube_id, title, source, description, thumbnail, embed_url, watch_url,
        duration_seconds, tags, channel_id, category_id, source_category,
        source_query, short_description, display_description,
        chrysalis_scores, ranking_reason, safety_reason, concern_reason, mode_fit,
        public_signal, source_safety_status, public_signal_effect,
        public_signal_reason }
    Empty input (or an unknown mode) yields an empty list. New metadata fields are
    null/empty for older rows that predate richer extraction.

    Pagination: pass the video ids already shown to the user as ``exclude_ids``
    and the feed serves the next balanced page over the not-yet-seen pool, so
    pages never repeat a video (see ``build_feed_payload`` for the metadata).
    """
    items, _debug = _build_feed_result(
        rows,
        mode,
        k=k,
        public_signal_context=public_signal_context,
        public_signal_override=public_signal_override,
        shuffle_seed=shuffle_seed,
        offset=offset,
        exclude_ids=exclude_ids,
    )
    return items


def build_feed_payload(
    rows: list[dict],
    mode: str,
    k: int = 12,
    public_signal_context: PublicSignalContext | None = None,
    public_signal_override: bool = False,
    shuffle_seed: str | None = None,
    offset: int = 0,
    exclude_ids: list[str] | set[str] | None = None,
) -> dict:
    """Build one feed page plus pagination metadata.

    Pagination is ``exclude_ids``-based: the caller accumulates the ids already
    shown and passes them back, and each request returns the next balanced page
    over the remaining eligible pool. The response carries:
      * ``returned_count``      — items in this page
      * ``eligible_pool_count`` — total videos that pass every safety/language
                                  filter (stable across pages)
      * ``has_more``            — whether another non-empty page exists
      * ``next_offset`` / ``next_cursor`` — informational cursor for the client
    ``offset`` is informational only; the page contents are driven by
    ``exclude_ids`` so per-page content-mix balancing is preserved.
    """
    resolved_seed = normalize_shuffle_seed(shuffle_seed) or new_shuffle_seed()
    items, debug = _build_feed_result(
        rows,
        mode,
        k=k,
        public_signal_context=public_signal_context,
        public_signal_override=public_signal_override,
        shuffle_seed=resolved_seed,
        offset=offset,
        exclude_ids=exclude_ids,
    )
    payload = {"count": len(items), "items": items, **debug}
    payload["debug"] = dict(debug)
    return payload


def new_shuffle_seed() -> str:
    return secrets.token_urlsafe(12)


def normalize_shuffle_seed(seed: str | None) -> str | None:
    value = str(seed or "").strip()
    if not value:
        return None
    return value[:_MAX_SEED_LENGTH]


def _build_feed_result(
    rows: list[dict],
    mode: str,
    k: int = 12,
    public_signal_context: PublicSignalContext | None = None,
    public_signal_override: bool = False,
    shuffle_seed: str | None = None,
    offset: int = 0,
    exclude_ids: list[str] | set[str] | None = None,
) -> tuple[list[dict], dict]:
    exclude_set = {str(v).strip() for v in (exclude_ids or []) if str(v).strip()}
    if not is_valid_mode(mode) or not rows:
        return [], _debug_metadata(
            [], [], k,
            shuffle_seed=shuffle_seed,
            offset=offset,
            eligible_pool_count=0,
            has_more=False,
        )

    candidates: list[dict] = []
    seen_video_ids: set[str] = set()
    popular_below_threshold = 0
    language_filtered = 0
    region_filtered = 0
    blocked_status_filtered = 0
    for row in rows:
        video_id = _row_video_id(row)
        if not video_id or video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)
        # Never serve rows an admin/cleanup already marked blocked (belt-and-suspenders;
        # the SQL loader already filters status='active', but legacy rows may not).
        if str(row.get("status") or "").strip().lower() == "blocked":
            blocked_status_filtered += 1
            continue
        # English-only / US-focused demo policy: drop non-English + non-US rows here so
        # old database rows can never leak into the feed, even if ingestion missed them.
        language_decision = language_verdict(row)
        if not language_decision["allowed"]:
            if language_decision["language_reason"]:
                language_filtered += 1
            if language_decision["region_blocked"]:
                region_filtered += 1
            continue
        # Guard the load path: drop weak popular rows (incl. legacy rows ingested
        # before the threshold existed) so they never reach the feed. Search-lane
        # rows are exempt — only most_popular is gated.
        if not popular_passes_min_score(
            row.get("source_type"), row.get("popularity_score")
        ):
            popular_below_threshold += 1
            continue
        labels = _labels_for_row(row)
        integrity = resolve_feed_integrity(row, labels.to_dict())
        taxonomy = classify_content(labels, row)
        candidates.append({
            "_row": row,
            "labels": labels,
            "taxonomy": taxonomy,
            "content_category": taxonomy.content_category,
            "topic": row.get("source_category") or row.get("topic") or row.get("category"),
            "source_category": row.get("source_category") or row.get("topic") or row.get("category"),
            "source_query": row.get("source_query") or "",
            "source_type": row.get("source_type") or "search",
            "popularity_score": row.get("popularity_score"),
            "ingest_score": row.get("ingest_score"),
            "integrity_score": integrity["integrity_score"],
            "integrity_flags": integrity["integrity_flags"],
            "production_style": integrity["production_style"],
            "creator_scale": integrity["creator_scale"],
            "video_id": video_id,
            "channel_id": row.get("channel_id") or "",
            "channel_title": row.get("channel_title") or row.get("channel") or "",
        })

    # Full eligible pool (everything that clears every safety / integrity /
    # public-signal gate). Used only to size the pool and decide ``has_more`` —
    # the page itself is ranked from the not-yet-seen slice below so per-page
    # content-mix balancing (target 40-60% healthy at size ``k``) is preserved.
    eligible_all = rank_videos(
        candidates,
        mode,
        k=len(candidates),
        public_signal_context=public_signal_context,
        public_signal_override=public_signal_override,
        shuffle_seed=shuffle_seed,
    )
    eligible_ids = [str(cand.get("video_id") or "") for cand in eligible_all]
    eligible_pool_count = len(eligible_ids)
    eligible_remaining = sum(1 for vid in eligible_ids if vid not in exclude_set)

    remaining_candidates = (
        [cand for cand in candidates if cand["video_id"] not in exclude_set]
        if exclude_set else candidates
    )
    ranked = rank_videos(
        remaining_candidates,
        mode,
        k=k,
        public_signal_context=public_signal_context,
        public_signal_override=public_signal_override,
        shuffle_seed=shuffle_seed,
    )
    has_more = eligible_remaining > len(ranked)

    items: list[dict] = []
    for cand in ranked:
        row = cand["_row"]
        labels = cand["labels"]
        # Reasons are mode-specific, so always compute for the requested mode.
        reasons = build_reasons(labels, mode)
        vid = _row_video_id(row)
        tags = _normalize_tags(row.get("tags"))[:_MAX_API_TAGS]
        raw_title = row.get("title") or ""
        raw_channel = row.get("channel_title") or row.get("channel") or "Chrysalis"
        raw_description = row.get("description") or ""
        short_description = (
            row.get("short_description")
            or row.get("display_description")
            or build_short_description(raw_description)
        )
        display_title = row.get("display_title") or build_display_title(raw_title)
        display_channel = row.get("display_channel") or build_display_channel(raw_channel)
        display_hashtags = _display_hashtags_for_row(row, raw_title, raw_description)
        source_type = str(cand.get("source_type") or row.get("source_type") or "search").strip().lower()
        is_popular = source_type == "most_popular"
        popularity_badge = "Popular" if is_popular else None
        taxonomy = cand.get("taxonomy") or classify_content(labels, row)
        taxonomy_fields = taxonomy.to_dict()
        recommendation_lane = cand.get("recommendation_lane") or _recommendation_lane_for_category(
            taxonomy_fields["content_category"]
        )
        ranking_reason = _with_taxonomy_reason(
            reasons["ranking_reason"],
            taxonomy_fields["content_category"],
            recommendation_lane,
        )
        items.append({
            "youtube_id": vid,
            "title": raw_title,
            "display_title": display_title,
            "displayTitle": display_title,
            "source": display_channel,
            "channel_title": raw_channel,
            "display_channel": display_channel,
            "displayChannel": display_channel,
            "description": raw_description,
            "short_description": short_description,
            "shortDescription": short_description,
            "display_description": short_description,
            "displayDescription": short_description,
            "display_hashtags": display_hashtags,
            "displayHashtags": display_hashtags,
            "thumbnail": (
                row.get("thumbnail_url") or row.get("thumbnail")
                or (_THUMB.format(vid=vid) if vid else None)
            ),
            "embed_url": row.get("embed_url") or (_EMBED.format(vid=vid) if vid else None),
            "watch_url": row.get("watch_url") or (_WATCH.format(vid=vid) if vid else None),
            "duration_seconds": parse_duration_seconds(
                row.get("duration_seconds") if row.get("duration_seconds") is not None
                else row.get("duration")
            ),
            "tags": tags,
            "channel_id": row.get("channel_id") or "",
            "category_id": row.get("category_id") or row.get("category") or None,
            "source_category": row.get("source_category") or row.get("topic") or row.get("category") or None,
            "source_query": row.get("source_query") or None,
            "source_type": source_type,
            "is_popular": is_popular,
            "isPopular": is_popular,
            "popularity_badge": popularity_badge,
            "popularityBadge": popularity_badge,
            "content_category": taxonomy_fields["content_category"],
            "contentCategory": taxonomy_fields["content_category"],
            "wellness_score": taxonomy_fields["wellness_score"],
            "wellnessScore": taxonomy_fields["wellness_score"],
            "positivity_score": taxonomy_fields["positivity_score"],
            "positivityScore": taxonomy_fields["positivity_score"],
            "conflict_score": taxonomy_fields["conflict_score"],
            "conflictScore": taxonomy_fields["conflict_score"],
            "safety_risk": taxonomy_fields["safety_risk"],
            "safetyRisk": taxonomy_fields["safety_risk"],
            "perspective_topic": taxonomy_fields["perspective_topic"],
            "perspectiveTopic": taxonomy_fields["perspective_topic"],
            "recommendation_lane": recommendation_lane,
            "recommendationLane": recommendation_lane,
            "chrysalis_scores": labels.to_dict(),
            "ranking_reason": ranking_reason,
            "rankingReason": ranking_reason,
            "safety_reason": reasons["safety_reason"],
            "concern_reason": reasons["concern_reason"],
            "mode_fit": round(cand["mode_fit"], 4),
            "integrity_score": round(float(cand.get("integrity_score") or 0.0), 4),
            "integrityScore": round(float(cand.get("integrity_score") or 0.0), 4),
            "feed_validity_score": round(float(cand.get("integrity_score") or 0.0), 4),
            "feedValidityScore": round(float(cand.get("integrity_score") or 0.0), 4),
            "integrity_flags": normalize_integrity_flags(cand.get("integrity_flags")),
            "integrityFlags": normalize_integrity_flags(cand.get("integrity_flags")),
            "production_style": cand.get("production_style") or "unknown",
            "productionStyle": cand.get("production_style") or "unknown",
            "creator_scale": cand.get("creator_scale") or "unknown",
            "creatorScale": cand.get("creator_scale") or "unknown",
            "public_signal": cand.get("public_signal"),
            "source_safety_status": cand.get("source_safety_status", "neutral"),
            "public_signal_effect": cand.get("public_signal_effect", "none"),
            "public_signal_reason": cand.get("public_signal_reason"),
        })
    return items, _debug_metadata(
        candidates,
        ranked,
        k,
        shuffle_seed=shuffle_seed,
        offset=offset,
        eligible_pool_count=eligible_pool_count,
        has_more=has_more,
        popular_below_threshold=popular_below_threshold,
        language_filtered=language_filtered,
        region_filtered=region_filtered,
        blocked_status_filtered=blocked_status_filtered,
    )


def _debug_metadata(
    candidates: list[dict],
    ranked: list[dict],
    k: int,
    *,
    shuffle_seed: str | None,
    offset: int = 0,
    eligible_pool_count: int = 0,
    has_more: bool = False,
    popular_below_threshold: int = 0,
    language_filtered: int = 0,
    region_filtered: int = 0,
    blocked_status_filtered: int = 0,
) -> dict:
    integrity_scores = [
        float(item.get("integrity_score"))
        for item in ranked
        if item.get("integrity_score") is not None
    ]
    flag_counts: Counter[str] = Counter()
    for item in candidates:
        flags = normalize_integrity_flags(item.get("integrity_flags"))
        flag_counts.update(flags["negative"])
        flag_counts.update(flags["positive"])
    ranked_content_counts = _counts_for(ranked, "content_category")
    candidate_content_counts = _counts_for(candidates, "content_category")
    healthy_count = sum(
        count for category, count in ranked_content_counts.items()
        if is_healthy_category(category)
    )
    ranked_count = len(ranked)
    reduced_or_blocked_candidates = sum(
        count for category, count in candidate_content_counts.items()
        if category in {"reduced", "blocked"}
    )
    reduced_or_blocked_ranked = sum(
        count for category, count in ranked_content_counts.items()
        if category in {"reduced", "blocked"}
    )

    returned_count = len(ranked)
    safe_offset = max(0, int(offset))
    return {
        "shuffle_seed": shuffle_seed,
        "real_count": len(ranked),
        "template_count": max(0, int(k) - len(ranked)),
        # ── Pagination / infinite-scroll contract ──────────────────────────
        "returned_count": returned_count,
        "eligible_pool_count": eligible_pool_count,
        "has_more": bool(has_more),
        "next_offset": safe_offset + returned_count,
        "next_cursor": str(safe_offset + returned_count) if has_more else None,
        "average_integrity_score": (
            round(sum(integrity_scores) / len(integrity_scores), 4)
            if integrity_scores else 0.0
        ),
        "category_counts": dict(_counts_for(ranked, "source_category", "topic", "category")),
        "content_category_counts": dict(ranked_content_counts),
        "candidate_content_category_counts": dict(candidate_content_counts),
        "recommendation_lane_counts": dict(_counts_for(ranked, "recommendation_lane")),
        "healthy_content_ratio": round(healthy_count / ranked_count, 4) if ranked_count else 0.0,
        "healthy_content_target": {
            "min": HEALTHY_TARGET_MIN_RATIO,
            "max": HEALTHY_TARGET_MAX_RATIO,
        },
        "reduced_or_blocked_filtered_count": max(
            0,
            reduced_or_blocked_candidates - reduced_or_blocked_ranked,
        ),
        "language_policy": LANGUAGE_POLICY,
        "allowed_language_prefixes": list(ALLOWED_LANGUAGE_PREFIXES),
        "allowed_region": ALLOWED_REGION,
        "language_filtered_count": language_filtered,
        "region_or_origin_filtered_count": region_filtered,
        "blocked_or_deleted_count": blocked_status_filtered,
        # retained for back-compat with earlier debug consumers
        "region_filtered_count": region_filtered,
        "blocked_language_codes": list(BLOCKED_LANGUAGE_CODES),
        "source_query_counts": dict(_counts_for(ranked, "source_query")),
        "source_type_counts": dict(_counts_for(ranked, "source_type")),
        "popular_min_score": POPULAR_MIN_SCORE,
        "popular_below_threshold_filtered_count": popular_below_threshold,
        "production_style_counts": dict(_counts_for(ranked, "production_style")),
        "creator_scale_counts": dict(_counts_for(ranked, "creator_scale")),
        "integrity_flag_counts": dict(sorted(flag_counts.items())),
        "low_integrity_filtered_count": sum(
            1
            for item in candidates
            if item.get("integrity_score") is not None
            and float(item["integrity_score"]) < INTEGRITY_MIN_SCORE
        ),
    }


def _counts_for(items: list[dict], *fields: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        value = None
        for field in fields:
            raw = item.get(field)
            if raw:
                value = str(raw)
                break
        counts[value or "unknown"] += 1
    return counts


def _display_hashtags_for_row(row: dict, title: str, description: str) -> list[str]:
    raw = row.get("display_hashtags") or row.get("displayHashtags")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = [raw]
    if isinstance(raw, list):
        tags = [str(tag).strip() for tag in raw if str(tag).strip()]
        return tags[:3]
    return build_display_hashtags(title, description)


def _recommendation_lane_for_category(category: str) -> str:
    if is_healthy_category(category):
        return "healthy_mix"
    if category == "perspective":
        return "perspective_mix"
    if category == "reduced":
        return "reduced_filler"
    return "regular_mix"


def _with_taxonomy_reason(reason: str, category: str, lane: str) -> str:
    if lane == "healthy_mix":
        extra = " It also supports the feed's positive, mentally healthy mix."
    elif lane == "regular_mix":
        extra = " It also keeps the feed feeling fun and normal."
    elif lane == "perspective_mix":
        extra = " It also adds a low-conflict different perspective."
    elif category == "reduced":
        extra = " It was deprioritized because Chrysalis saw higher conflict signals."
    else:
        extra = ""
    return f"{reason}{extra}"


def _row_video_id(row: dict) -> str:
    return str(
        row.get("video_id")
        or row.get("youtube_id")
        or row.get("youtube_video_id")
        or row.get("id")
        or ""
    ).strip()
