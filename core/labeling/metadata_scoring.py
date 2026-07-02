"""
Layer 1 — cheap metadata scorer (v1).

Rule-based, deterministic, zero network/LLM. Reads whatever metadata is available
(title, description, tags, channel title, category/topic, duration, thumbnail) and
produces a normalized `LabelSet`.

This is intentionally simple and structured: each dimension is driven by a list of
keyword/phrase patterns in `POSITIVE_PATTERNS` / `RISK_PATTERNS`, so the signal can be
tuned by editing data, not logic. It does not need to be perfect — only structured and
easy to improve. Deeper layers (thumbnail vision, LLM) refine this later.
"""

from __future__ import annotations

import json
import re

from .schema import (
    LabelSet,
    POSITIVE_DIMS,
    RISK_DIMS,
    clamp01,
)

# Phrases that, when they appear shortly BEFORE a matched keyword, flip its meaning
# ("overcoming body image issues" should not read as appearance pressure).
_NEGATION_PREFIXES = (
    "overcoming", "overcome", "recovering from", "recovery from", "healing from",
    "stop", "no more", "quitting", "letting go of", "unlearning", "beyond",
)

# ── Positive signal patterns, keyed by the dimension they raise ──────────────
POSITIVE_PATTERNS: dict[str, list[str]] = {
    "calm": [
        "calm", "calming", "relax", "relaxing", "soothing", "slow", "gentle",
        "breathe", "breathing", "meditat", "mindful", "asmr", "ambient", "lo-fi",
        "lofi", "nature", "rain", "ocean", "forest", "mental reset", "unwind",
        "wind down", "cozy", "peaceful", "stillness",
    ],
    "prosocial": [
        "kindness", "kind", "community", "together", "support", "help", "helping",
        "volunteer", "donate", "charity", "friendship", "friends", "empathy",
        "compassion", "wholesome", "uplifting", "give back", "good news",
    ],
    "educational": [
        "how to", "tutorial", "learn", "learning", "explain", "explained",
        "guide", "study", "study with me", "lesson", "education", "course",
        "science", "history", "documentary", "facts", "deep dive", "breakdown",
    ],
    "self_love": [
        "self love", "self-love", "self care", "self-care", "self compassion",
        "self worth", "you are enough", "affirmation", "confidence without comparison",
        "be yourself", "self acceptance", "worthy", "self esteem", "gentle reminder",
    ],
    "reflection_value": [
        "reflection", "reflect", "journal", "journaling", "gratitude", "grateful",
        "thankful", "perspective", "intention", "values", "meaning", "philosophy",
        "lessons learned", "thoughtful", "growth", "notice", "pause and",
    ],
    "novelty": [
        "you've never", "never seen", "rare", "unusual", "unexpected", "first time",
        "experiment", "what happens if", "weird", "obscure", "hidden gem",
        "creative", "art", "diy", "make", "build", "design",
    ],
}

# ── Risk signal patterns, keyed by the dimension they raise ──────────────────
RISK_PATTERNS: dict[str, list[str]] = {
    "comparison_risk": [
        "rating people", "rate my", "rate me", "hot or not", "ranking people",
        "who is prettier", "out of 10", "vs everyone", "am i pretty", "tier list of people",
        "richest", "compared to", "better than you", "leveling up", "status",
    ],
    "appearance_focus": [
        "glow up", "glow-up", "transformation", "before and after", "before & after",
        "body check", "body checking", "what i eat in a day", "snatched", "abs",
        "weight loss", "lose weight", "diet", "skincare routine", "my body",
        "perfect body", "summer body", "get ready with me to look",
    ],
    "shame_or_humiliation_risk": [
        "exposed", "exposing", "humiliat", "embarrass", "called out", "destroyed",
        "owned", "wrecked", "cringe", "ratio'd", "publicly shamed", "caught in 4k",
        "you won't believe what she did", "clowned",
    ],
    "ragebait": [
        "you won't believe", "gone wrong", "triggered", "rant", "worst", "hate",
        "outrage", "controversial", "drama", "beef", "exposed the truth", "destroyed",
        "owning", "clapback", "this will make you angry", "infuriating",
    ],
    "overstimulation": [
        "insane", "crazy", "extreme", "fastest", "loudest", "epic fail compilation",
        "tiktok compilation", "satisfying", "overload", "hyper", "chaotic", "!!!",
        "shocking", "wild", "non stop", "non-stop", "rapid fire",
    ],
    "consumerism": [
        "haul", "luxury", "designer", "unboxing", "shopping spree", "rich life",
        "expensive", "billionaire", "millionaire lifestyle", "what i bought",
        "must have", "tiktok made me buy", "amazon finds", "flexing", "net worth",
    ],
    "age_safety_risk": [
        "challenge gone", "dangerous", "do not try", "prank", "18+", "graphic",
        "disturbing", "nsfw", "risky", "stunt",
    ],
    "misinformation_risk": [
        "they don't want you to know", "the truth about", "conspiracy", "hoax",
        "secret cure", "doctors hate", "exposed the lie", "fake news", "miracle",
        "what they're hiding", "wake up",
    ],
}

# Risk dimensions that also contribute to overstimulation pressure when present.
_TOKEN_RE = re.compile(r"[a-z0-9']+")

# Duration thresholds (seconds). Shorts/snackable clips are more prone to
# compulsive scrolling; very long videos are not penalized but are flagged as
# less clip-like for Daily Dew / Reels (see the clip-fit hook in core/ranking).
_SHORT_DURATION_S = 60          # ≤ ~1 min → snackable
_LONG_DURATION_S = 20 * 60      # ≥ ~20 min → long-form, not clip-like

# Tags are weighted noticeably lower than title/description: they are creator-
# supplied, noisy, and easily stuffed, so a tag match must never outweigh a real
# title/description match. (Main blob uses per_hit=0.34; title is doubled.)
_TAG_PER_HIT = 0.12

# ISO 8601 duration as returned by YouTube contentDetails.duration, e.g. "PT1H2M3S".
_ISO8601_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def parse_duration_seconds(value) -> int | None:
    """
    Safely normalize a video duration into integer seconds.

    Accepts:
      • YouTube ISO 8601 strings ("PT1M30S" → 90, "PT1H2M3S" → 3723)
      • plain int/float/numeric strings (already seconds)
    Returns None on empty/None/unparseable input. Never raises — the scorer must
    tolerate older rows and junk metadata.
    """
    if value is None:
        return None
    # Numeric passthrough (already seconds).
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value >= 0 else None

    s = str(value).strip()
    if not s:
        return None

    # Plain numeric string (e.g. "90").
    if s.isdigit():
        return int(s)

    m = _ISO8601_DURATION_RE.match(s.upper())
    if not m:
        return None
    parts = m.groupdict()
    if not any(parts.values()):
        return None
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _normalize_tags(raw) -> list[str]:
    """Coerce stored tags (list, JSON-encoded string, or None) into a list of strings."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(t) for t in raw]
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                decoded = json.loads(s)
                if isinstance(decoded, list):
                    return [str(t) for t in decoded]
            except (ValueError, TypeError):
                pass
        # Fall back to treating the whole string as a single tag blob.
        return [s] if s else []
    return [str(raw)]


def _count_hits(text: str, patterns: list[str]) -> int:
    """Count negation-aware keyword hits for one pattern list."""
    hits = 0
    for pat in patterns:
        start = 0
        while True:
            idx = text.find(pat, start)
            if idx == -1:
                break
            context = text[max(0, idx - 32): idx]
            if not any(neg in context for neg in _NEGATION_PREFIXES):
                hits += 1
            start = idx + len(pat)
    return hits


def _score_group(text: str, patterns: list[str], per_hit: float = 0.34) -> float:
    """Density-based 0–1 score: each matching phrase occurrence adds `per_hit`."""
    return clamp01(_count_hits(text, patterns) * per_hit)


def _normalize_category(meta: dict) -> str:
    """Best-effort category/topic string for light category nudges."""
    return str(meta.get("category") or meta.get("topic") or "").lower()


def score_metadata(meta: dict) -> LabelSet:
    """
    Score a single video's metadata into a normalized LabelSet.

    `meta` keys used (all optional):
      • title, description       — primary text signal (title weighted most)
      • tags (list|JSON str)     — secondary signal, weighted *below* title/description
      • channel_title / channel  — weak text signal
      • category / topic         — weak category prior
      • duration_seconds / duration (ISO 8601 or seconds) — light overstimulation/
        clip-fit heuristic
      • thumbnail / thumbnail_url — surfaced in the API only (no image AI yet)
    Missing fields simply contribute no signal and lower confidence.
    """
    title = str(meta.get("title") or "")
    description = str(meta.get("description") or "")

    tags = _normalize_tags(meta.get("tags"))
    tags_text = " ".join(tags).lower()

    channel = str(meta.get("channel_title") or meta.get("channel") or "")
    category = _normalize_category(meta)

    # future hook: meta.get("thumbnail"/"thumbnail_url") is intentionally NOT scored
    # yet. A later Layer-2 pass can OCR/vision-analyze the thumbnail; for now it is
    # passed through to the API (see core/ranking/feed.py) untouched.

    # Title carries the strongest signal, so weight it by repeating it. Tags are
    # deliberately excluded here and scored separately at a lower weight below, so
    # creator-supplied tags can nudge but never dominate title/description.
    blob = " ".join([title, title, description, channel, category]).lower()

    labels = LabelSet()

    # Positive dimensions: main text first, then a smaller tag-only contribution.
    for dim in POSITIVE_DIMS:
        if dim == "diversity":
            continue  # diversity is contextual — set at ranking time, not per-video
        patterns = POSITIVE_PATTERNS.get(dim, [])
        score = _score_group(blob, patterns)
        if tags_text:
            score = clamp01(score + _score_group(tags_text, patterns, per_hit=_TAG_PER_HIT))
        setattr(labels, dim, score)

    # Category nudges (cheap priors)
    if category in ("education",):
        labels.educational = clamp01(labels.educational + 0.35)
    if category in ("music",):
        labels.calm = clamp01(labels.calm + 0.1)

    # Risk dimensions (overall_risk computed after): main text + smaller tag signal.
    for dim in RISK_DIMS:
        if dim == "overall_risk":
            continue
        patterns = RISK_PATTERNS.get(dim, [])
        score = _score_group(blob, patterns)
        if tags_text:
            score = clamp01(score + _score_group(tags_text, patterns, per_hit=_TAG_PER_HIT))
        setattr(labels, dim, score)

    # Exclamation-mark / all-caps overstimulation nudge from the title
    bangs = title.count("!")
    if bangs >= 2:
        labels.overstimulation = clamp01(labels.overstimulation + 0.2)
    letters = [c for c in title if c.isalpha()]
    if len(letters) >= 8:
        caps_ratio = sum(c.isupper() for c in letters) / len(letters)
        if caps_ratio > 0.6:
            labels.overstimulation = clamp01(labels.overstimulation + 0.15)
            labels.ragebait = clamp01(labels.ragebait + 0.1)

    # Duration heuristic (light): very short/snackable clips amplify overstimulation
    # ONLY when another risk signal is already present — a calm short stays calm and
    # is never penalized for being short. Medium clips are neutral; very long videos
    # are not penalized here.
    #   clip-fit hook: long-form (≥ _LONG_DURATION_S) is less "clip-like" and so a
    #   weaker fit for Daily Dew / Reels. That is a *ranking* concern, handled (later)
    #   in core/ranking/modes.py, not a per-video risk — so no penalty is applied here.
    duration_s = parse_duration_seconds(
        meta.get("duration_seconds") if meta.get("duration_seconds") is not None
        else meta.get("duration")
    )
    if duration_s is not None and duration_s <= _SHORT_DURATION_S:
        existing_risk = max(
            getattr(labels, d) for d in RISK_DIMS if d != "overall_risk"
        )
        if existing_risk > 0.2:
            labels.overstimulation = clamp01(labels.overstimulation + 0.15)

    # overall_risk: max-biased aggregate so one strong risk dominates, with a
    # contribution from the average so multiple moderate risks add up.
    component_risks = [getattr(labels, d) for d in RISK_DIMS if d != "overall_risk"]
    if component_risks:
        peak = max(component_risks)
        avg = sum(component_risks) / len(component_risks)
        labels.overall_risk = clamp01(0.7 * peak + 0.3 * avg)

    # Confidence: scales with how much usable text we had (short/empty → low).
    text_tokens = len(_TOKEN_RE.findall(f"{title} {description} {tags_text}"))
    text_conf = clamp01(text_tokens / 40.0)          # ~40 tokens → full text confidence
    any_signal = max(
        [getattr(labels, d) for d in POSITIVE_DIMS] +
        [getattr(labels, d) for d in RISK_DIMS]
    )
    # Confident when we either have plenty of text or a clear signal; floor of 0.2
    # whenever there's any text at all so totally-unscored items can be deprioritized.
    base = 0.2 if text_tokens > 0 else 0.0
    labels.confidence = clamp01(max(base, 0.55 * text_conf + 0.6 * any_signal))

    return labels.clamped()
