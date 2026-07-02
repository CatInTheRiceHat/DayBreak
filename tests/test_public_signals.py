"""
Tests for the optional Public Signal Scanner layer.

These tests use only deterministic stub/sample records. No public web search or
scraping is involved.
"""

import sqlite3

from core.labeling.schema import LabelSet, SCORING_VERSION
from core.public_signals.provider import StubPublicSignalProvider
from core.public_signals.storage import load_cached_context_sqlite
from core.public_signals.ranking import PublicSignalContext
from core.public_signals.schema import ChannelSafetyRecord, PublicSignalRecord, expiry_iso, iso_utc
from core.ranking.feed import build_feed


def _labels(**overrides):
    base = {
        "prosocial": 0.75,
        "calm": 0.55,
        "educational": 0.5,
        "self_love": 0.35,
        "diversity": 0.2,
        "novelty": 0.35,
        "reflection_value": 0.4,
        "comparison_risk": 0.05,
        "appearance_focus": 0.05,
        "shame_or_humiliation_risk": 0.05,
        "ragebait": 0.05,
        "overstimulation": 0.05,
        "consumerism": 0.05,
        "age_safety_risk": 0.05,
        "misinformation_risk": 0.05,
        "overall_risk": 0.08,
        "confidence": 0.92,
    }
    base.update(overrides)
    return LabelSet(**base).to_dict()


def _row(video_id, channel_id, labels=None, title=None):
    return {
        "video_id": video_id,
        "title": title or f"Calm sample {video_id}",
        "description": "A gentle reflective video with low-stimulation framing.",
        "channel_id": channel_id,
        "channel_title": f"Channel {channel_id}",
        "topic": "education",
        "chrysalis_scores": labels or _labels(),
        "scoring_version": SCORING_VERSION,
    }


def _signal(target_type, target_id, concern, confidence=0.8, review=False):
    return PublicSignalRecord(
        target_type=target_type,
        target_id=target_id,
        concern_score=concern,
        support_score=0.05,
        confidence=confidence,
        main_concerns=["appearance comparison", "shame-based framing"] if concern else [],
        evidence_count=4 if concern else 0,
        source_quality="mixed",
        recency="recent",
        requires_human_review=review,
        summary="Fictional sample public context.",
        last_checked=iso_utc(),
        expires_at=expiry_iso(review),
    )


def test_stub_record_serializes_to_public_shape():
    provider = StubPublicSignalProvider()
    record = provider.scan_channel("fictional-comparison-lab", "Fictional Lab")
    data = record.to_public_dict()
    assert set(data) == {
        "target_type",
        "target_id",
        "concern_score",
        "support_score",
        "confidence",
        "main_concerns",
        "supportive_signals",
        "evidence_count",
        "source_quality",
        "recency",
        "requires_human_review",
        "summary",
        "last_checked",
        "expires_at",
    }
    assert data["target_type"] == "channel"
    assert data["target_id"] == "fictional-comparison-lab"
    assert data["source_quality"] in {"weak", "mixed", "strong"}


def test_missing_public_signal_data_stays_neutral():
    feed = build_feed([_row("v1", "neutral-channel")], "flutter-feed", k=3)
    assert len(feed) == 1
    assert feed[0]["public_signal"] is None
    assert feed[0]["source_safety_status"] == "neutral"
    assert feed[0]["public_signal_effect"] == "none"
    assert feed[0]["public_signal_reason"] is None


def test_cached_public_signal_read_does_not_create_tables():
    conn = sqlite3.connect(":memory:")
    context = load_cached_context_sqlite(conn, [_row("v1", "neutral-channel")])
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    conn.close()

    assert context == PublicSignalContext.empty()
    assert "public_signal_records" not in tables
    assert "channel_safety_records" not in tables


def test_medium_concern_changes_ranking_order():
    context = PublicSignalContext(
        channel_signals={
            "medium-source": _signal("channel", "medium-source", concern=0.5),
        }
    )
    rows = [
        _row("v1", "medium-source"),
        _row("v2", "neutral-source"),
    ]
    feed = build_feed(rows, "flutter-feed", k=2, public_signal_context=context)
    assert [item["youtube_id"] for item in feed] == ["v2", "v1"]
    affected = next(item for item in feed if item["youtube_id"] == "v1")
    assert affected["public_signal_effect"] == "stricter_scoring"
    assert affected["public_signal_reason"]


def test_do_not_recommend_channels_are_excluded_unless_overridden():
    safety = ChannelSafetyRecord(
        channel_id="review-hold",
        status="do_not_recommend",
        requires_human_review=True,
        reason="Source has an active review hold.",
        last_checked=iso_utc(),
        review_after=expiry_iso(True),
        expires_at=expiry_iso(True),
    )
    context = PublicSignalContext(channel_safety={"review-hold": safety})
    rows = [
        _row("blocked", "review-hold"),
        _row("allowed", "neutral-source"),
    ]

    feed = build_feed(rows, "flutter-feed", k=3, public_signal_context=context)
    assert {item["youtube_id"] for item in feed} == {"allowed"}

    override_feed = build_feed(
        rows,
        "flutter-feed",
        k=3,
        public_signal_context=context,
        public_signal_override=True,
    )
    assert {item["youtube_id"] for item in override_feed} == {"allowed", "blocked"}


def test_severe_public_signal_plus_internal_risk_is_excluded():
    risky_labels = _labels(
        comparison_risk=0.2,
        appearance_focus=0.2,
        shame_or_humiliation_risk=0.2,
        ragebait=0.2,
        overall_risk=0.55,
    )
    context = PublicSignalContext(
        channel_signals={
            "severe-source": _signal("channel", "severe-source", concern=0.95, confidence=0.95, review=True),
        }
    )
    feed = build_feed(
        [_row("severe", "severe-source", labels=risky_labels), _row("ok", "neutral-source")],
        "flutter-feed",
        k=3,
        public_signal_context=context,
    )
    assert {item["youtube_id"] for item in feed} == {"ok"}


def test_cautious_source_low_risk_video_is_allowed_with_explanation():
    context = PublicSignalContext(
        channel_signals={
            "cautious-source": _signal("channel", "cautious-source", concern=0.95, confidence=0.95, review=True),
        }
    )
    feed = build_feed([_row("gentle", "cautious-source")], "flutter-feed", k=3, public_signal_context=context)
    assert len(feed) == 1
    item = feed[0]
    assert item["youtube_id"] == "gentle"
    assert item["public_signal_effect"] == "allowed_low_video_risk"
    assert "video-level scan was low-risk" in item["public_signal_reason"]
    assert item["source_safety_status"] == "caution"
