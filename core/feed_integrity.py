"""
Deterministic feed integrity scoring.

This layer is deliberately not a production-value score. Low-budget, awkward,
casual, niche, or small-creator videos should remain eligible when they are safe
and analyzable. The score only gates obvious spam, unsafe content, broken
metadata, misleading metadata, and content-farm/reupload patterns.
"""

from __future__ import annotations

from collections.abc import Iterable
import json
import re

from .labeling.metadata_scoring import _normalize_tags, parse_duration_seconds
from .labeling.schema import LabelSet, clamp01

INTEGRITY_MIN_SCORE = 0.38
DEFAULT_INTEGRITY_SCORE = 0.72

PRODUCTION_STYLES = {"polished", "casual", "amateur", "low_budget", "chaotic", "unknown"}
CREATOR_SCALES = {"small", "mid", "large", "unknown"}

NEGATIVE_FLAGS = {
    "clickbait_spam",
    "keyword_stuffing",
    "low_effort",
    "misleading_title",
    "bad_metadata",
    "likely_reupload",
    "unsafe_or_ragebait",
    "irrelevant_to_broad_pool",
}
POSITIVE_FLAGS = {
    "clear_explainer",
    "authentic_vlog",
    "thoughtful_commentary",
    "creative_original",
    "wholesome_or_prosocial",
    "useful_context",
    "strong_storytelling",
    "good_production",
}

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9']+")
_HASHTAG_RE = re.compile(r"#[a-z0-9_]+", re.IGNORECASE)

_SCAM_SPAM_TERMS = (
    "free money", "cash app giveaway", "crypto giveaway", "telegram crypto",
    "whatsapp investment", "guaranteed profit", "double your money",
    "make money fast", "investment scheme", "forex signals", "free robux",
    "gift card generator", "account hack", "password hack",
)
_ADULT_GAMBLING_TERMS = (
    "18+", "nsfw", "porn", "sex tape", "onlyfans", "nude", "casino",
    "gambling", "betting", "parlay", "sportsbook",
)
_HATE_EXTREMISM_TERMS = (
    "hate speech", "white power", "racial slur", "extremist propaganda",
    "terrorist propaganda", "neo-nazi", "kkk rally",
)
_VIOLENT_SHOCK_TERMS = (
    "graphic violence", "gore", "beheading", "execution video",
    "shooting footage", "dead body", "blood everywhere", "violent shock",
)
_UNSAFE_CHALLENGE_TERMS = (
    "blackout challenge", "choking challenge", "train surfing",
    "dangerous challenge", "do not try this", "unsafe stunt",
)
_RAGEBAIT_TERMS = (
    "you won't believe", "destroyed", "humiliated", "caught in 4k",
    "this will make you angry", "ragebait", "owned by", "exposed and",
)
_MISLEADING_TERMS = (
    "not clickbait", "doctors hate", "secret cure", "they don't want you to know",
    "what they're hiding", "miracle cure", "fake news proof",
)
_REUPLOAD_TERMS = (
    "reupload", "tiktok compilation", "reaction compilation", "clips compilation",
    "no copyright", "full movie", "full episode", "stolen clip", "viral tiktoks",
)


def score_feed_integrity(
    meta: dict,
    *,
    labels: dict | LabelSet | None = None,
) -> dict:
    title = str(meta.get("title") or "").strip()
    description = str(meta.get("description") or "").strip()
    short_description = str(meta.get("short_description") or meta.get("display_description") or "").strip()
    channel = str(meta.get("channel_title") or meta.get("channel") or "").strip()
    tags = _normalize_tags(meta.get("tags"))
    thumbnail = str(meta.get("thumbnail_url") or meta.get("thumbnail") or "").strip()
    video_id = str(meta.get("video_id") or meta.get("youtube_id") or meta.get("youtube_video_id") or "").strip()
    duration_seconds = parse_duration_seconds(
        meta.get("duration_seconds") if meta.get("duration_seconds") is not None else meta.get("duration")
    )
    view_count = _coerce_int(meta.get("view_count"))

    text = " ".join([title, description, short_description, channel, " ".join(tags)]).lower()
    title_l = title.lower()
    score = DEFAULT_INTEGRITY_SCORE
    negative: set[str] = set()
    positive: set[str] = set()

    has_title = _has_meaningful_text(title, min_tokens=2)
    has_any_description = _has_meaningful_text(description or short_description, min_tokens=3)

    if not video_id:
        score -= 0.40
        negative.add("bad_metadata")
    if not has_title:
        score -= 0.36
        negative.add("bad_metadata")
    if not has_title and not has_any_description:
        score -= 0.20
        negative.add("irrelevant_to_broad_pool")
    elif not has_any_description and len(tags) < 2:
        # Missing captions are common on valid Shorts; this is only a light
        # analyzability nudge, not a polish filter.
        score -= 0.06
    if not thumbnail:
        score -= 0.04

    if _has_any(text, _SCAM_SPAM_TERMS):
        score -= 0.44
        negative.add("clickbait_spam")
    if _has_any(text, _ADULT_GAMBLING_TERMS):
        score -= 0.48
        negative.add("unsafe_or_ragebait")
    if _has_any(text, _HATE_EXTREMISM_TERMS):
        score -= 0.52
        negative.add("unsafe_or_ragebait")
    if _has_any(text, _VIOLENT_SHOCK_TERMS):
        score -= 0.48
        negative.add("unsafe_or_ragebait")
    if _has_any(text, _UNSAFE_CHALLENGE_TERMS):
        score -= 0.44
        negative.add("unsafe_or_ragebait")
    if _has_any(text, _MISLEADING_TERMS):
        score -= 0.26
        negative.add("misleading_title")
    if _has_any(text, _REUPLOAD_TERMS):
        score -= 0.24
        negative.add("likely_reupload")

    ragebait_hits = sum(1 for term in _RAGEBAIT_TERMS if term in text)
    if ragebait_hits >= 2 or _label_value(labels, "ragebait") >= 0.75:
        score -= 0.30
        negative.add("unsafe_or_ragebait")

    if _looks_keyword_stuffed(title, description, tags):
        score -= 0.25
        negative.add("keyword_stuffing")

    if duration_seconds is not None and duration_seconds <= 3 and not has_any_description:
        score -= 0.18
        negative.add("low_effort")

    if title and (_caps_ratio(title) > 0.72 or title.count("!") >= 4) and not _has_clear_context(text):
        score -= 0.12
        negative.add("misleading_title")

    if _has_any(text, ("explained", "how to", "guide", "tutorial", "breakdown", "context")):
        positive.add("clear_explainer")
    if _has_any(text, ("vlog", "day in my life", "storytime", "with me", "grwm", "life update")):
        positive.add("authentic_vlog")
    if _has_any(text, ("commentary", "essay", "thoughtful", "perspective", "review", "analysis")):
        positive.add("thoughtful_commentary")
    if _has_any(text, ("original", "creative", "diy", "sketch", "art", "made this", "behind the scenes")):
        positive.add("creative_original")
    if _has_any(text, ("wholesome", "kind", "community", "helpful", "support", "uplifting")):
        positive.add("wholesome_or_prosocial")
    if _has_any(text, ("source", "context", "background", "details", "what happened", "why it matters")):
        positive.add("useful_context")
    if _has_any(text, ("story", "journey", "lesson learned", "documentary", "before and after")):
        positive.add("strong_storytelling")
    if thumbnail and has_title and (has_any_description or duration_seconds is not None):
        positive.add("good_production")

    score += min(0.16, 0.035 * len(positive))
    if _label_value(labels, "overall_risk") >= 0.75:
        score -= 0.18
        negative.add("unsafe_or_ragebait")

    score = round(clamp01(score), 4)
    return {
        "integrity_score": score,
        "integrity_flags": _flags_dict(negative, positive),
        "production_style": infer_production_style(meta, title=title, text=text, view_count=view_count),
        "creator_scale": infer_creator_scale(view_count),
    }


def resolve_feed_integrity(row: dict, labels: dict | LabelSet | None = None) -> dict:
    computed = score_feed_integrity(row, labels=labels)
    raw_score = row.get("integrity_score")
    if raw_score is None:
        raw_score = row.get("feed_validity_score")
    stored_score = _coerce_score(raw_score)
    stored_flags = normalize_integrity_flags(row.get("integrity_flags"))
    style = normalize_production_style(row.get("production_style")) or computed["production_style"]
    scale = normalize_creator_scale(row.get("creator_scale")) or computed["creator_scale"]

    flags = stored_flags if stored_flags["negative"] or stored_flags["positive"] else computed["integrity_flags"]
    score = stored_score if stored_score is not None else computed["integrity_score"]
    return {
        "integrity_score": round(clamp01(score), 4),
        "integrity_flags": flags,
        "production_style": style,
        "creator_scale": scale,
    }


def normalize_integrity_flags(raw) -> dict:
    if raw is None:
        return _flags_dict(set(), set())
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return _flags_dict(set(), set())
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = [raw]

    negative: set[str] = set()
    positive: set[str] = set()
    if isinstance(raw, dict):
        negative.update(_coerce_flag_iterable(raw.get("negative") or raw.get("negative_flags")))
        positive.update(_coerce_flag_iterable(raw.get("positive") or raw.get("positive_flags")))
        # Accept flat legacy booleans, e.g. {"keyword_stuffing": true}.
        for key, value in raw.items():
            if not value:
                continue
            if key in NEGATIVE_FLAGS:
                negative.add(key)
            elif key in POSITIVE_FLAGS:
                positive.add(key)
    elif isinstance(raw, Iterable) and not isinstance(raw, (bytes, bytearray)):
        for flag in _coerce_flag_iterable(raw):
            if flag in POSITIVE_FLAGS:
                positive.add(flag)
            else:
                negative.add(flag)

    return _flags_dict(negative, positive)


def infer_production_style(
    meta: dict,
    *,
    title: str | None = None,
    text: str | None = None,
    view_count: int | None = None,
) -> str:
    title = str(title if title is not None else meta.get("title") or "").strip()
    text = text if text is not None else " ".join([
        title,
        str(meta.get("description") or ""),
        str(meta.get("short_description") or ""),
        str(meta.get("channel_title") or meta.get("channel") or ""),
        " ".join(_normalize_tags(meta.get("tags"))),
    ]).lower()
    view_count = view_count if view_count is not None else _coerce_int(meta.get("view_count"))

    if _has_any(text, ("chaotic", "unhinged", "random moments", "messy vlog", "no plan")) or title.count("!") >= 3:
        return "chaotic"
    if _has_any(text, ("low budget", "no budget", "filmed on phone", "phone vlog", "home video", "bedroom vlog")):
        return "low_budget"
    if _has_any(text, ("vlog", "day in my life", "storytime", "with me", "life update", "grwm", "casual")):
        return "casual"
    if _has_any(text, ("my first", "amateur", "beginner", "trying to", "homemade")):
        return "amateur"
    if _has_any(text, ("official", "documentary", "studio", "interview", "explained", "trailer", "news")):
        return "polished"
    if view_count is not None and view_count < 5000 and len(_tokens(title)) <= 6:
        return "amateur"
    return "unknown"


def infer_creator_scale(view_count: int | None) -> str:
    if view_count is None:
        return "unknown"
    if view_count < 5000:
        return "small"
    if view_count < 100000:
        return "mid"
    return "large"


def normalize_production_style(value) -> str | None:
    style = str(value or "").strip().lower()
    return style if style in PRODUCTION_STYLES else None


def normalize_creator_scale(value) -> str | None:
    scale = str(value or "").strip().lower()
    return scale if scale in CREATOR_SCALES else None


def _flags_dict(negative: set[str], positive: set[str]) -> dict:
    negative = {flag for flag in negative if flag}
    positive = {flag for flag in positive if flag}
    return {
        "negative": sorted(negative),
        "positive": sorted(positive),
        "needs_review": bool(negative & {"unsafe_or_ragebait", "clickbait_spam", "misleading_title"}),
    }


def _coerce_flag_iterable(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, Iterable) or isinstance(raw, (bytes, bytearray)):
        return []
    return [str(item).strip().lower() for item in raw if str(item).strip()]


def _coerce_score(value) -> float | None:
    try:
        if value is None:
            return None
        return clamp01(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_int(value) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_meaningful_text(value: str, *, min_tokens: int) -> bool:
    tokens = [token for token in _tokens(value) if len(token) > 1]
    return len(tokens) >= min_tokens


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall((value or "").lower())


def _has_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def _looks_keyword_stuffed(title: str, description: str, tags: list[str]) -> bool:
    title_tokens = [token for token in _tokens(title) if len(token) > 2]
    if len(title_tokens) >= 12 and len(set(title_tokens)) / len(title_tokens) < 0.55:
        return True
    if title.count("|") >= 3 or title.count(",") >= 6:
        return True
    hashtags = _HASHTAG_RE.findall(description or "")
    if len(hashtags) > 10:
        return True
    normalized_tags = [tag.lower().strip() for tag in tags if tag.strip()]
    if len(normalized_tags) > 18 and len(set(normalized_tags)) / len(normalized_tags) < 0.7:
        return True
    return False


def _caps_ratio(value: str) -> float:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for char in letters if char.isupper()) / len(letters)


def _has_clear_context(text: str) -> bool:
    return _has_any(text, ("explained", "guide", "tutorial", "vlog", "review", "story", "news", "recipe"))


def _label_value(labels: dict | LabelSet | None, name: str) -> float:
    if labels is None:
        return 0.0
    if isinstance(labels, LabelSet):
        return clamp01(getattr(labels, name, 0.0))
    if isinstance(labels, dict):
        return clamp01(labels.get(name, 0.0))
    return 0.0
