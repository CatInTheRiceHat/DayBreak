"""Lightweight source-reputation scoring (Part D of the trust-source system).

Produces a 0–1 reputation score (and a coarse tier) for a YouTube source from a
handful of human-reviewable signals. This is **metadata / a small ranking nudge
only** — it deliberately does NOT live on the safety path:

  * The only way to reach 0.0 is a hard block (`is_blocked`).
  * A high reputation never relaxes a safety/relevance gate. Every candidate,
    trusted or not, still goes through ``_candidate_from_video_item`` (blocked
    terms, language filter, duration, integrity, relevance) and through feed
    ranking. Reputation cannot bypass any of that.

Keeping the function pure (no DB, no network) makes it trivially testable and
safe to call from both ingestion and ranking.
"""

from __future__ import annotations

# Tier labels, ordered worst → best. "blocked" is reserved for hard-blocked
# sources and is never produced by the numeric score alone.
REPUTATION_TIERS: tuple[str, ...] = ("blocked", "low", "medium", "high")

# Reputation contributed by trust status / tier (the human-review signal).
_STATUS_WEIGHT: dict[str, float] = {
    "approved": 0.45,
    "needs_review": 0.15,
    "candidate": 0.10,
    "experimental": 0.10,
    "disabled": 0.0,
    "rejected": 0.0,
}
_TIER_WEIGHT: dict[str, float] = {
    "institutional": 0.30,
    "established_creator": 0.20,
    "candidate": 0.08,
    "experimental": 0.05,
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def source_reputation_score(
    *,
    status: str | None = None,
    trust_tier: str | None = None,
    is_blocked: bool = False,
    source_group_match: bool = False,
    english_us: bool = True,
    recent_activity: bool = True,
    block_rate: float = 0.0,
    clickbait: float = 0.0,
    integrity_history: float = 0.6,
    foreign_language_leak: bool = False,
    ragebait: bool = False,
    gossip_drama: bool = False,
    misinformation: bool = False,
) -> float:
    """Return a 0–1 reputation score for a source.

    A hard block short-circuits to 0.0. Otherwise positive signals (approval,
    institutional tier, English/US metadata, recent activity, good integrity
    history, source-group match) add up and negative signals (high block rate,
    clickbait, ragebait, foreign-language leakage, gossip/drama, misinformation)
    subtract, with the total clamped to [0, 1].
    """
    if is_blocked:
        return 0.0

    score = 0.0
    # ── positive signals ──────────────────────────────────────────────────
    score += _STATUS_WEIGHT.get((status or "").strip().lower(), 0.0)
    score += _TIER_WEIGHT.get((trust_tier or "").strip().lower(), 0.0)
    if source_group_match:
        score += 0.05
    if english_us:
        score += 0.07
    if recent_activity:
        score += 0.05
    # Integrity history (0..1) contributes a small, proportional amount.
    score += 0.10 * _clamp01(integrity_history)

    # ── negative signals ──────────────────────────────────────────────────
    score -= 0.30 * _clamp01(block_rate)
    score -= 0.15 * _clamp01(clickbait)
    if foreign_language_leak:
        score -= 0.20
    if ragebait:
        score -= 0.20
    if gossip_drama:
        score -= 0.12
    if misinformation:
        score -= 0.25

    return _clamp01(score)


def reputation_tier(score: float, *, is_blocked: bool = False) -> str:
    """Map a reputation score to a coarse tier label."""
    if is_blocked:
        return "blocked"
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"
