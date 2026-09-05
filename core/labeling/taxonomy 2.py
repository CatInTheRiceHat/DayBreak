"""
Layer 1.5 - content taxonomy (v1).

Maps a video's existing `LabelSet` (the 16 wellbeing/risk dimensions) plus a light,
deterministic scan of its raw text into a small, demo-friendly classification the
feed can reason about:

    content_category  - one of CONTENT_CATEGORIES
    wellness_score    - how "healthy / wellness" the content is        (0-1)
    positivity_score  - how positive / uplifting the content feels     (0-1)
    conflict_score    - how conflict / outrage / comparison heavy      (0-1)
    safety_risk       - worst-case wellbeing/safety risk               (0-1)
    perspective_topic - named topic when this is perspective content   (str|None)

This is intentionally rule-based and zero-network: it reuses the keyword scorer's
LabelSet and adds a few extra keyword groups for signals the base scorer does not
cover well yet (offline "touch grass" activities, diverse perspectives, and
explicitly harmful mental-health / graphic content that must be blocked).

The taxonomy is *derived at read time* and surfaced in the feed payload; it does
not add columns to the database, so it can never drift from the scorer. Prompt 2
(the balanced algorithm) consumes `content_category` to build the healthy mix.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import LabelSet, clamp01

SCHEMA_VERSION = "v1"

# Content categories
# healthy      - wellness / self-improvement / calming advice / "touch grass"
# positive     - generally uplifting, kind, feel-good (not explicitly wellness)
# regular      - normal entertainment: comedy, trends, music, sports, games, DIY
# perspective  - low-conflict diverse perspectives / calm real-world topics
# reduced      - downrank: rage-bait, comparison-heavy, toxic argument, doomscroll
# blocked      - filter out: graphic/triggering, self-harm/ED/trauma, harassment
CONTENT_CATEGORIES: tuple[str, ...] = (
    "healthy",
    "positive",
    "regular",
    "perspective",
    "reduced",
    "blocked",
)

# Categories Prompt 2 will treat as the "healthy mix" target (40-60%).
HEALTHY_CATEGORIES: frozenset[str] = frozenset({"healthy", "positive"})

# Decision thresholds (tunable by editing data, not logic)
# Blocking is reserved for genuinely harmful / graphic content. Generic outrage or
# drama is high-risk but NOT blocked - it becomes "reduced" (downranked) instead.
BLOCK_HARMFUL_HITS = 0.60       # self-harm/ED/graphic signal at/above this -> blocked
BLOCK_AGE_RISK = 0.70           # age-safety/graphic risk at/above this -> blocked
REDUCE_CONFLICT = 0.45          # conflict_score at/above this -> reduced
PERSPECTIVE_FLOOR = 0.40        # perspective signal at/above this -> perspective
HEALTHY_FLOOR = 0.45            # wellness_score at/above this -> healthy
POSITIVE_FLOOR = 0.40           # positivity_score at/above this -> positive

# Phrases that flip a harmful keyword into safe / supportive context
# ("suicide prevention", "recovering from an eating disorder", "ED awareness").
_SAFE_CONTEXT = (
    "prevention", "awareness", "recovery", "recovering", "overcoming", "overcome",
    "healing", "heal from", "support", "hotline", "helpline", "survivor",
    "how to help", "warning signs", "reach out", "you are not alone",
)

# Offline / "touch grass" + self-improvement activity signals that the base
# scorer under-weights. These strongly raise wellness_score.
_ACTIVITY_PATTERNS = (
    "walk", "walking", "go for a walk", "touch grass", "step outside", "fresh air",
    "drink water", "hydrate", "stay hydrated", "stretch", "stretching",
    "journal", "journaling", "gratitude", "habit", "habits", "routine",
    "productivity", "productive", "study with me", "focus", "goal setting",
    "motivation", "motivated", "self improvement", "self-improvement",
    "self care", "self-care", "snack", "screen break", "take a break",
    "creative", "create something", "make something", "diy", "craft",
)

# Friendship / kindness / connection signals (healthy + positive).
_CONNECTION_PATTERNS = (
    "friend", "friends", "friendship", "kindness", "be kind", "kind to",
    "compliment", "thank you", "wholesome", "together", "community", "support each other",
)

_CONFLICT_PATTERNS = (
    "rage bait", "ragebait", "rage-bait", "bullying", "harassment", "harassing",
    "toxic argument", "toxic debate", "toxic comments", "comment war",
    "internet fight", "online fight", "doomscroll", "doomscrolling", "hate watch",
    "dogpile", "pile on", "callout drama", "public shaming",
)

# Motivation / encouragement / pep-talk signals. A motivational pep talk reads as
# uplifting and belongs in the healthy mix, not generic "regular" entertainment, so
# these feed positivity (strongly) and wellness (lightly).
_UPLIFT_PATTERNS = (
    "pep talk", "motivation", "motivational", "motivated", "motivate",
    "encouragement", "encourage", "inspiring", "inspire", "inspirational",
    "uplifting", "you got this", "keep going", "believe in yourself",
    "cheer you on", "choose awesome", "be awesome", "brighter", "you matter",
)

# Low-conflict diverse-perspective signals. Each tuple is (topic, [phrases]).
_PERSPECTIVE_TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("different perspectives", (
        "different perspective", "different perspectives", "another perspective",
        "other point of view", "see it differently", "both sides", "two sides",
        "open mind", "open-minded", "open minded", "respectful conversation",
        "respectful debate", "civil conversation", "common ground", "where i disagree but",
    )),
    ("cultures", (
        "different culture", "other cultures", "around the world", "traditions",
        "what it's like in", "growing up in", "day in the life in",
    )),
    ("lived experience", (
        "what it's like to", "a day in the life of", "i interviewed",
        "people explain", "asked strangers", "humans of",
    )),
)

# Explicitly harmful / graphic / triggering content that must be blocked unless it
# is clearly supportive/preventative (see _SAFE_CONTEXT).
_HARMFUL_PATTERNS = (
    "self harm", "self-harm", "selfharm", "suicide", "suicidal", "kill myself",
    "end it all", "want to die", "cutting myself", "self injury",
    "anorexia", "bulimia", "pro ana", "pro-ana", "pro mia", "thinspo", "bonespo",
    "eating disorder tips", "how to starve", "starve yourself", "lose weight fast tips",
    "graphic", "gore", "gory", "gruesome", "disturbing footage", "nsfw",
    "trauma dump", "trauma-dump", "triggering content", "panic attack live",
)


def _hit_score(text: str, patterns, per_hit: float = 0.5, *, safe_aware: bool = False) -> tuple[float, int]:
    """Density score for a keyword group: each occurrence adds `per_hit` (clamped).

    When `safe_aware`, an occurrence is ignored if a supportive/preventative phrase
    appears nearby, so recovery/awareness content is not penalized.
    """
    hits = 0
    for pat in patterns:
        start = 0
        while True:
            idx = text.find(pat, start)
            if idx == -1:
                break
            if not (safe_aware and _in_safe_context(text, idx)):
                hits += 1
            start = idx + len(pat)
    return clamp01(hits * per_hit), hits


def _in_safe_context(text: str, idx: int) -> bool:
    window = text[max(0, idx - 48): idx + 48]
    return any(marker in window for marker in _SAFE_CONTEXT)


def _meta_text(meta: dict | None) -> str:
    if not meta:
        return ""
    parts = [
        str(meta.get("title") or ""),
        str(meta.get("description") or ""),
        str(meta.get("channel_title") or meta.get("channel") or ""),
        str(meta.get("source_query") or ""),
        str(meta.get("source_category") or meta.get("topic") or meta.get("category") or ""),
    ]
    tags = meta.get("tags")
    if isinstance(tags, (list, tuple)):
        parts.append(" ".join(str(t) for t in tags))
    elif tags:
        parts.append(str(tags))
    return " ".join(parts).lower()


def _detect_perspective(text: str) -> tuple[float, str | None]:
    best_score = 0.0
    best_topic: str | None = None
    for topic, phrases in _PERSPECTIVE_TOPICS:
        score, hits = _hit_score(text, phrases, per_hit=0.5)
        if hits and score > best_score:
            best_score = score
            best_topic = topic
    return best_score, best_topic


@dataclass(frozen=True)
class ContentTaxonomy:
    content_category: str
    wellness_score: float
    positivity_score: float
    conflict_score: float
    safety_risk: float
    perspective_topic: str | None

    def to_dict(self) -> dict:
        return {
            "content_category": self.content_category,
            "wellness_score": round(self.wellness_score, 4),
            "positivity_score": round(self.positivity_score, 4),
            "conflict_score": round(self.conflict_score, 4),
            "safety_risk": round(self.safety_risk, 4),
            "perspective_topic": self.perspective_topic,
        }


def classify_content(labels: LabelSet, meta: dict | None = None) -> ContentTaxonomy:
    """Derive the content taxonomy for one labeled video.

    `labels` is the required wellbeing/risk LabelSet. `meta` is the optional raw row
    (title/description/tags/topic...) used for the extra keyword signals; when omitted,
    classification falls back to the LabelSet dimensions alone.
    """
    text = _meta_text(meta)

    activity_score, _ = _hit_score(text, _ACTIVITY_PATTERNS, per_hit=0.34)
    connection_score, _ = _hit_score(text, _CONNECTION_PATTERNS, per_hit=0.34)
    uplift_score, _ = _hit_score(text, _UPLIFT_PATTERNS, per_hit=0.34)
    conflict_text_score, _ = _hit_score(text, _CONFLICT_PATTERNS, per_hit=0.45)
    perspective_score, perspective_topic = _detect_perspective(text)
    harmful_score, _ = _hit_score(text, _HARMFUL_PATTERNS, per_hit=0.6, safe_aware=True)

    # Derived 0-1 scores
    wellness_score = clamp01(
        0.28 * labels.calm
        + 0.20 * labels.self_love
        + 0.18 * labels.reflection_value
        + 0.14 * labels.prosocial
        + 0.12 * labels.educational
        + 0.55 * activity_score
        + 0.25 * connection_score
        + 0.15 * uplift_score
    )
    positivity_score = clamp01(
        0.32 * labels.prosocial
        + 0.28 * labels.self_love
        + 0.24 * labels.calm
        + 0.10 * labels.novelty
        + 0.30 * connection_score
        + 0.20 * activity_score
        + 0.30 * uplift_score
        - 0.50 * labels.overall_risk
    )

    conflict_components = (labels.ragebait, labels.shame_or_humiliation_risk, labels.comparison_risk)
    peak = max(conflict_components)
    avg = sum(conflict_components) / len(conflict_components)
    conflict_score = clamp01(0.7 * peak + 0.3 * avg + conflict_text_score)

    safety_risk = clamp01(max(labels.overall_risk, labels.age_safety_risk, harmful_score))

    # Category decision (priority order)
    if harmful_score >= BLOCK_HARMFUL_HITS or labels.age_safety_risk >= BLOCK_AGE_RISK:
        category = "blocked"
    elif conflict_score >= REDUCE_CONFLICT:
        category = "reduced"
    elif perspective_score >= PERSPECTIVE_FLOOR:
        category = "perspective"
    elif wellness_score >= HEALTHY_FLOOR:
        category = "healthy"
    elif positivity_score >= POSITIVE_FLOOR:
        category = "positive"
    else:
        category = "regular"

    # perspective_topic is only meaningful for perspective content
    topic = perspective_topic if category == "perspective" else None

    return ContentTaxonomy(
        content_category=category,
        wellness_score=wellness_score,
        positivity_score=positivity_score,
        conflict_score=conflict_score,
        safety_risk=safety_risk,
        perspective_topic=topic,
    )


def is_healthy_category(category: str) -> bool:
    """True for categories that count toward the Prompt-2 healthy mix target."""
    return category in HEALTHY_CATEGORIES
