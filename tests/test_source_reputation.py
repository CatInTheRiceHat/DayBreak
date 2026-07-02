"""Tests for the lightweight source-reputation scoring helper (Part D).

Reputation is *metadata / a small ranking nudge only*. It must never be able to
turn an unsafe source into a safe one — the only way a reputation reaches 0 here
is a hard block, and a high reputation does not relax any safety gate (those live
in the ingestion candidate gate + feed ranking, not here).
"""

from __future__ import annotations

from core.source_reputation import REPUTATION_TIERS, reputation_tier, source_reputation_score


def test_blocked_channel_scores_zero_and_blocked_tier():
    score = source_reputation_score(is_blocked=True, status="approved", trust_tier="institutional")
    assert score == 0.0
    assert reputation_tier(score, is_blocked=True) == "blocked"


def test_approved_institutional_source_scores_high():
    score = source_reputation_score(
        status="approved",
        trust_tier="institutional",
        source_group_match=True,
        english_us=True,
        recent_activity=True,
        block_rate=0.0,
        clickbait=0.0,
        integrity_history=0.85,
    )
    assert score >= 0.8
    assert reputation_tier(score) == "high"


def test_negative_signals_pull_score_down():
    good = source_reputation_score(status="approved", trust_tier="established_creator",
                                   english_us=True, integrity_history=0.8)
    bad = source_reputation_score(
        status="approved", trust_tier="established_creator",
        english_us=True, integrity_history=0.8,
        ragebait=True, foreign_language_leak=True, gossip_drama=True,
        clickbait=0.9, block_rate=0.6,
    )
    assert bad < good
    assert bad <= 0.45


def test_unreviewed_candidate_scores_below_approved():
    candidate = source_reputation_score(status="candidate", trust_tier="candidate")
    approved = source_reputation_score(status="approved", trust_tier="established_creator")
    assert candidate < approved


def test_score_is_always_clamped_0_1():
    # Pile on every positive signal — still <= 1.0.
    hi = source_reputation_score(
        status="approved", trust_tier="institutional", source_group_match=True,
        english_us=True, recent_activity=True, block_rate=0.0, clickbait=0.0,
        integrity_history=1.0,
    )
    # Pile on every negative signal (but not blocked) — still >= 0.0.
    lo = source_reputation_score(
        status="rejected", trust_tier="experimental", source_group_match=False,
        english_us=False, recent_activity=False, block_rate=1.0, clickbait=1.0,
        integrity_history=0.0, ragebait=True, foreign_language_leak=True,
        gossip_drama=True, misinformation=True,
    )
    assert 0.0 <= lo <= hi <= 1.0


def test_reputation_tier_thresholds():
    assert reputation_tier(0.85) == "high"
    assert reputation_tier(0.55) == "medium"
    assert reputation_tier(0.2) == "low"
    assert set(REPUTATION_TIERS) == {"blocked", "low", "medium", "high"}
