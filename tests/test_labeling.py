"""
Tests for the Chrysalis v1 video labeling + mode ranking system.

Verifies the core product guarantees with small hand-built metadata samples:
  - calm/grounding content scores well and survives the shared safe-feed gate
  - ragebait/shame content scores high-risk and is gated out everywhere
  - all modes draw from the same real-video source pool
  - the shared feed keeps source variety while filtering high-risk items
  - explanations only surface a concern when a real risk is present
"""

import pytest

from core.labeling.metadata_scoring import score_metadata, parse_duration_seconds
from core.labeling.explain import build_reasons
from core.ranking.modes import passes_gate, score_for_mode, rank_videos
from core.ranking.feed import build_feed, build_feed_payload


# ── Sample metadata ─────────────────────────────────────────────────────────
CALM = {
    "video_id": "calm1",
    "title": "Calm rain sounds for a gentle mental reset",
    "description": "Slow breathing, gratitude journaling, and soothing nature ambience.",
    "channel_title": "Quiet Forest",
    "topic": "music",
}
GRATITUDE = {
    "video_id": "calm2",
    "title": "One kind thought before you scroll — a gratitude reflection",
    "description": "A gentle reminder about self compassion and kindness.",
    "channel_title": "Soft Light",
    "topic": "education",
}
RAGEBAIT = {
    "video_id": "rage1",
    "title": "She got EXPOSED and DESTROYED!! you won't believe the drama",
    "description": "Cringe glow up, rating people, body check — pure drama.",
    "channel_title": "DramaDaily",
    "topic": "entertainment",
}
HYPER = {
    "video_id": "hyper1",
    "title": "INSANE extreme challenge gone wrong!!! shocking chaos",
    "description": "Non-stop wild rapid fire stunts, loudest craziest moments.",
    "channel_title": "MaxHype",
    "topic": "gaming",
}
LEARN = {
    "video_id": "learn1",
    "title": "How to study effectively — a calm explained guide",
    "description": "Learn a gentle study routine with reflection and breaks.",
    "channel_title": "StudyWithMe",
    "topic": "education",
}
NEUTRAL_LOW_RISK = {
    "video_id": "neutral1",
    "title": "One day or day one",
    "description": (
        "A plain update with ordinary details about a routine upload, including "
        "schedule notes, location context, simple production notes, and general "
        "background text for metadata confidence."
    ),
    "channel_title": "Neutral Channel",
    "topic": "entertainment",
}


# ── Scoring ──────────────────────────────────────────────────────────────────
def test_calm_scores_high_calm_low_risk():
    labels = score_metadata(CALM)
    assert labels.calm >= 0.6
    assert labels.overall_risk < 0.3
    assert labels.confidence > 0.3


def test_ragebait_scores_high_risk():
    labels = score_metadata(RAGEBAIT)
    assert labels.ragebait >= 0.3
    assert labels.shame_or_humiliation_risk >= 0.3
    assert labels.comparison_risk >= 0.2 or labels.appearance_focus >= 0.3
    assert labels.overall_risk >= 0.5


def test_negation_aware_scoring():
    meta = {"title": "Overcoming body image struggles with self compassion",
            "description": "healing and self love", "topic": "education"}
    labels = score_metadata(meta)
    # "body" appears but is negated by "overcoming"; self_love should dominate.
    assert labels.self_love >= 0.3
    assert labels.appearance_focus < 0.34


def test_title_matches_are_weighted_more_than_description():
    labels = score_metadata({
        "title": "Calm",
        "description": "",
        "channel_title": "Sample",
        "topic": "entertainment",
    })
    assert labels.calm >= 0.6


# ── Mode ranking ─────────────────────────────────────────────────────────────
def test_shared_gate_keeps_calm_and_blocks_ragebait():
    calm = score_metadata(CALM)
    rage = score_metadata(RAGEBAIT)
    assert passes_gate(calm, "daily-dew")
    assert not passes_gate(rage, "daily-dew")
    assert score_for_mode(calm, "daily-dew") > score_for_mode(rage, "daily-dew")


def test_shared_gate_allows_neutral_low_risk_content():
    neutral = score_metadata(NEUTRAL_LOW_RISK)
    assert neutral.confidence >= 0.25
    assert neutral.overall_risk < 0.3
    assert passes_gate(neutral, "daily-dew")
    assert passes_gate(neutral, "metamorphosis")
    assert passes_gate(neutral, "flutter-feed")


def test_ragebait_gated_out_of_every_mode():
    rage = score_metadata(RAGEBAIT)
    for mode in ("daily-dew", "metamorphosis", "flutter-feed"):
        assert not passes_gate(rage, mode), f"ragebait should fail {mode}"


def test_all_modes_use_same_shared_video_gate():
    calm = score_metadata(CALM)
    hyper = score_metadata(HYPER)
    for mode in ("daily-dew", "metamorphosis", "flutter-feed"):
        assert passes_gate(calm, mode)
        assert not passes_gate(hyper, mode)


def test_shared_feed_keeps_variety_filters_risk():
    items = [
        {"labels": score_metadata(CALM), "topic": "music"},
        {"labels": score_metadata(LEARN), "topic": "education"},
        {"labels": score_metadata(GRATITUDE), "topic": "education"},
        {"labels": score_metadata(RAGEBAIT), "topic": "entertainment"},
        {"labels": score_metadata(HYPER), "topic": "gaming"},
    ]
    ranked = rank_videos(items, "flutter-feed", k=12)
    topics = [it["topic"] for it in ranked]
    # high-risk items dropped
    assert "entertainment" not in topics  # ragebait gone
    # variety preserved across the survivors
    assert len(set(topics)) >= 2


def test_source_metadata_balancing_limits_dominant_categories_and_queries():
    rows = []
    for index in range(6):
        rows.append({
            "video_id": f"game-{index}",
            "title": "A calm educational guide with a creative idea",
            "description": "Learn one useful thing in a low-risk, reflective format.",
            "source_category": "gaming",
            "source_query": "gaming highlights" if index % 2 else "cozy gaming",
        })
    for index in range(2):
        rows.append({
            "video_id": f"travel-{index}",
            "title": "A calm educational guide with a creative idea",
            "description": "Learn one useful thing in a low-risk, reflective format.",
            "source_category": "travel",
            "source_query": "travel vlog city guide",
        })
        rows.append({
            "video_id": f"food-{index}",
            "title": "A calm educational guide with a creative idea",
            "description": "Learn one useful thing in a low-risk, reflective format.",
            "source_category": "food",
            "source_query": "food recipes street food",
        })

    feed = build_feed(rows, "flutter-feed", k=6)
    categories = [item["source_category"] for item in feed]
    queries = [item["source_query"] for item in feed]
    assert max(categories.count(category) for category in set(categories)) <= 2
    assert max(queries.count(query) for query in set(queries)) <= 2


def test_integrity_gate_filters_spam_but_keeps_safe_amateur_content():
    rows = [
        {
            "video_id": "safe-amateur",
            "title": "My awkward phone vlog about tiny clay frogs",
            "description": "Low budget day in my life making a little pottery shelf at home.",
            "source_category": "lifestyle/vlogs",
            "source_query": "day in my life lifestyle vlog",
            "integrity_score": 0.58,
            "integrity_flags": {"negative": [], "positive": ["authentic_vlog"]},
            "production_style": "low_budget",
            "creator_scale": "small",
        },
        {
            "video_id": "polished-explainer",
            "title": "A useful explainer about pottery tools",
            "description": "A clear guide with simple context for beginners.",
            "source_category": "education/explainers",
            "source_query": "science history explained",
            "integrity_score": 0.86,
            "integrity_flags": {"negative": [], "positive": ["clear_explainer"]},
            "production_style": "polished",
            "creator_scale": "mid",
        },
        {
            "video_id": "spam",
            "title": "FREE MONEY CRYPTO GIVEAWAY TELEGRAM CRYPTO!!!!",
            "description": "Guaranteed profit. Double your money with my telegram crypto bot.",
            "source_category": "internet culture",
            "source_query": "internet culture memes explained",
            "integrity_score": 0.12,
            "integrity_flags": {"negative": ["clickbait_spam"], "positive": []},
            "production_style": "chaotic",
            "creator_scale": "large",
        },
    ]

    feed = build_feed(rows, "flutter-feed", k=10)
    ids = {item["youtube_id"] for item in feed}
    assert "safe-amateur" in ids
    assert "polished-explainer" in ids
    assert "spam" not in ids


def test_production_style_and_creator_scale_are_balanced_not_gated():
    rows = []
    for index in range(4):
        rows.append({
            "video_id": f"polished-{index}",
            "title": "A calm educational guide with a creative idea",
            "description": "Learn one useful thing in a low-risk, reflective format.",
            "source_category": "education/explainers",
            "source_query": "science history explained",
            "integrity_score": 0.82,
            "integrity_flags": {"negative": [], "positive": ["clear_explainer"]},
            "production_style": "polished",
            "creator_scale": "large",
        })
        rows.append({
            "video_id": f"casual-{index}",
            "title": "A calm casual vlog with a creative idea",
            "description": "A low-budget but safe day in my life update.",
            "source_category": "education/explainers",
            "source_query": "science history explained",
            "integrity_score": 0.68,
            "integrity_flags": {"negative": [], "positive": ["authentic_vlog"]},
            "production_style": "casual",
            "creator_scale": "small",
        })

    feed = build_feed(rows, "flutter-feed", k=6)
    styles = {item["production_style"] for item in feed}
    scales = {item["creator_scale"] for item in feed}
    assert {"polished", "casual"} <= styles
    assert {"large", "small"} <= scales


def test_feed_payload_includes_integrity_debug_metadata():
    rows = [
        dict(CALM, integrity_score=0.82, production_style="polished", creator_scale="mid"),
        dict(LEARN, integrity_score=0.72, production_style="casual", creator_scale="small"),
        dict(
            RAGEBAIT,
            integrity_score=0.12,
            integrity_flags={"negative": ["unsafe_or_ragebait"], "positive": []},
            production_style="chaotic",
            creator_scale="large",
        ),
    ]

    payload = build_feed_payload(rows, "flutter-feed", k=5)
    assert payload["real_count"] == len(payload["items"])
    assert payload["template_count"] == max(0, 5 - len(payload["items"]))
    assert payload["average_integrity_score"] > 0
    assert payload["low_integrity_filtered_count"] == 1
    assert payload["category_counts"]
    assert payload["production_style_counts"]
    assert payload["creator_scale_counts"]
    assert payload["integrity_flag_counts"]["unsafe_or_ragebait"] == 1
    assert payload["shuffle_seed"]


def test_feed_payload_uses_seeded_shuffle_and_removes_duplicates():
    rows = []
    categories = ["travel", "food", "gaming", "music/culture"]
    styles = ["polished", "casual", "amateur", "low_budget"]
    scales = ["large", "small", "mid", "small"]
    for index in range(16):
        rows.append({
            "video_id": f"seeded-{index}",
            "title": "A calm educational guide with a creative idea",
            "description": "Learn one useful thing in a low-risk, reflective format.",
            "source_category": categories[index % len(categories)],
            "source_query": f"{categories[index % len(categories)]} broad query",
            "integrity_score": 0.72,
            "integrity_flags": {"negative": [], "positive": ["useful_context"]},
            "production_style": styles[index % len(styles)],
            "creator_scale": scales[index % len(scales)],
        })
    rows.append(dict(rows[3], title="Duplicate row should not appear twice"))

    first = build_feed_payload(rows, "flutter-feed", k=12, shuffle_seed="seed-a")
    second = build_feed_payload(rows, "flutter-feed", k=12, shuffle_seed="seed-a")
    third = build_feed_payload(rows, "flutter-feed", k=12, shuffle_seed="seed-b")

    first_ids = [item["youtube_id"] for item in first["items"]]
    third_ids = [item["youtube_id"] for item in third["items"]]
    assert first["shuffle_seed"] == "seed-a"
    assert first_ids == [item["youtube_id"] for item in second["items"]]
    assert first_ids != third_ids
    assert len(first_ids) == len(set(first_ids))
    assert first["template_count"] == 0
    assert max(first["category_counts"].values()) <= 3


def test_feed_payload_generates_new_seed_when_seed_is_omitted():
    rows = [dict(CALM), dict(LEARN)]
    first = build_feed_payload(rows, "flutter-feed", k=2)
    second = build_feed_payload(rows, "flutter-feed", k=2)
    assert first["shuffle_seed"]
    assert second["shuffle_seed"]
    assert first["shuffle_seed"] != second["shuffle_seed"]


# ── Explanations ─────────────────────────────────────────────────────────────
def test_concern_reason_only_when_risk_present():
    calm = score_metadata(CALM)
    rage = score_metadata(RAGEBAIT)
    assert build_reasons(calm, "daily-dew")["concern_reason"] is None
    assert build_reasons(rage, "flutter-feed")["concern_reason"] is not None
    # ranking_reason always present
    assert build_reasons(calm, "daily-dew")["ranking_reason"]


# ── Feed builder (end-to-end shape) ──────────────────────────────────────────
def test_build_feed_shape_and_gating():
    rows = [CALM, GRATITUDE, RAGEBAIT, HYPER, LEARN, NEUTRAL_LOW_RISK]
    feed = build_feed(rows, "daily-dew", k=12)
    ids = {it["youtube_id"] for it in feed}
    assert "rage1" not in ids and "hyper1" not in ids
    assert "calm1" in ids
    item = feed[0]
    for key in ("youtube_id", "title", "thumbnail", "chrysalis_scores",
                "display_title", "displayTitle", "display_channel", "displayChannel",
                "display_hashtags", "displayHashtags",
                "source_category", "source_query",
                "ranking_reason", "safety_reason", "concern_reason", "mode_fit",
                "public_signal", "source_safety_status", "public_signal_effect",
                "public_signal_reason"):
        assert key in item


def test_all_modes_share_video_ids_but_change_explanation_copy():
    daily = build_feed([CALM], "daily-dew", k=12)
    metamorphosis = build_feed([CALM], "metamorphosis", k=12)
    flutter = build_feed([CALM], "flutter-feed", k=12)
    assert {item["youtube_id"] for item in daily} == {"calm1"}
    assert {item["youtube_id"] for item in metamorphosis} == {"calm1"}
    assert {item["youtube_id"] for item in flutter} == {"calm1"}
    assert daily[0]["ranking_reason"] != metamorphosis[0]["ranking_reason"]


def test_build_feed_unknown_mode_is_empty():
    assert build_feed([CALM], "nope", k=12) == []


# ── Richer metadata: duration parsing ────────────────────────────────────────
def test_parse_duration_seconds_safe():
    assert parse_duration_seconds("PT1M30S") == 90
    assert parse_duration_seconds("PT1H2M3S") == 3723
    assert parse_duration_seconds("PT45S") == 45
    assert parse_duration_seconds("PT2H") == 7200
    # numeric passthrough (already seconds)
    assert parse_duration_seconds(90) == 90
    assert parse_duration_seconds("90") == 90
    # junk / empty → None, never raises
    for bad in (None, "", "garbage", "P", "PT", True, -5):
        assert parse_duration_seconds(bad) is None


# ── Richer metadata: tags influence scoring (but don't dominate) ──────────────
def test_risky_tags_increase_risk_dims():
    meta = {
        "title": "a quiet afternoon update",
        "description": "just sharing some ordinary notes about the day",
        "tags": ["glow up", "drama", "exposed", "cringe", "am i pretty"],
        "topic": "entertainment",
    }
    labels = score_metadata(meta)
    assert labels.appearance_focus > 0.0
    assert labels.ragebait > 0.0
    assert labels.shame_or_humiliation_risk > 0.0
    assert labels.comparison_risk > 0.0


def test_positive_tags_increase_positive_dims():
    meta = {
        "title": "a quiet afternoon update",
        "description": "just sharing some ordinary notes about the day",
        "tags": ["gratitude", "study", "calm", "art", "kindness", "reflection"],
        "topic": "entertainment",
    }
    labels = score_metadata(meta)
    assert labels.reflection_value > 0.0
    assert labels.educational > 0.0
    assert labels.calm > 0.0
    assert labels.novelty > 0.0
    assert labels.prosocial > 0.0


def test_tags_do_not_dominate_title_description():
    # Same keyword in the title vs. only in tags → title contributes strictly more.
    in_title = score_metadata({
        "title": "gratitude gratitude gratitude reflection",
        "description": "",
        "topic": "education",
    })
    in_tags = score_metadata({
        "title": "ordinary update",
        "description": "",
        "tags": ["gratitude", "gratitude", "gratitude", "reflection"],
        "topic": "education",
    })
    assert in_title.reflection_value > in_tags.reflection_value


def test_tags_accept_json_string():
    import json
    meta = {
        "title": "ordinary update",
        "description": "",
        "tags": json.dumps(["calm", "gratitude"]),
        "topic": "entertainment",
    }
    labels = score_metadata(meta)
    assert labels.calm > 0.0
    assert labels.reflection_value > 0.0


# ── Richer metadata: duration heuristics ──────────────────────────────────────
def test_short_risky_video_nudges_overstimulation():
    risky = {
        "title": "INSANE wild chaotic rapid fire drama",
        "description": "non-stop shocking exposed cringe",
        "topic": "entertainment",
    }
    long_risky = dict(risky, duration_seconds=600)
    short_risky = dict(risky, duration_seconds=20)
    assert score_metadata(short_risky).overstimulation >= score_metadata(long_risky).overstimulation


def test_short_calm_video_not_penalized():
    calm_short = dict(CALM, duration_seconds=20)
    calm_long = dict(CALM, duration_seconds=600)
    # A short calm clip must not gain overstimulation just for being short.
    assert score_metadata(calm_short).overstimulation == score_metadata(calm_long).overstimulation
    assert passes_gate(score_metadata(calm_short), "daily-dew")


def test_missing_metadata_does_not_crash():
    bare = {"title": "calm rain", "topic": "music"}  # no tags/duration/thumbnail
    labels = score_metadata(bare)
    assert labels.calm >= 0.0
    # explicit Nones must also be safe
    nulls = {"title": "calm rain", "tags": None, "duration_seconds": None,
             "thumbnail_url": None, "topic": "music"}
    assert score_metadata(nulls).calm >= 0.0


# ── Richer metadata: API serialization ────────────────────────────────────────
def test_build_feed_includes_new_fields():
    row = dict(
        CALM,
        title=(
            "A calm rain reset with a very very long YouTube title that would "
            "otherwise take over the whole reel #calm #rain #study #focus"
        ),
        channel_title="A Very Long Channel Name That Should Not Break The Reel Card",
        short_description="A compact calm caption for the card.",
        tags=["calm", "gratitude"],
        duration_seconds=300,
        thumbnail_url="https://example.com/t.jpg",
        channel_id="UC123",
        category_id="10",
    )
    feed = build_feed([row], "daily-dew", k=12)
    assert feed, "calm video should survive Daily Dew"
    item = feed[0]
    for key in (
        "duration_seconds",
        "tags",
        "channel_id",
        "category_id",
        "thumbnail",
        "short_description",
        "shortDescription",
        "display_description",
        "displayDescription",
        "integrity_score",
        "integrityScore",
        "feed_validity_score",
        "feedValidityScore",
        "integrity_flags",
        "integrityFlags",
        "production_style",
        "productionStyle",
        "creator_scale",
        "creatorScale",
    ):
        assert key in item
    assert item["duration_seconds"] == 300
    assert item["tags"] == ["calm", "gratitude"]
    assert item["channel_id"] == "UC123"
    assert item["category_id"] == "10"
    assert item["thumbnail"] == "https://example.com/t.jpg"
    assert item["description"] == CALM["description"]
    assert item["title"] == row["title"]
    assert item["channel_title"] == row["channel_title"]
    assert "#" not in item["display_title"]
    assert len(item["display_title"]) <= 82
    assert len(item["display_channel"]) <= 30
    assert item["source"] == item["display_channel"]
    assert item["display_hashtags"] == ["#calm", "#rain", "#study"]
    assert item["short_description"] == "A compact calm caption for the card."
    assert item["displayDescription"] == "A compact calm caption for the card."


def test_build_feed_generates_short_description_fallback_for_old_rows():
    raw = (
        "A gentle study reset with a calm timer and one reflection question for "
        "the afternoon. Subscribe for more study resets. https://example.com"
    )
    row = dict(CALM, description=raw)
    feed = build_feed([row], "flutter-feed", k=12)
    assert feed
    item = feed[0]
    assert item["description"] == raw
    assert "Subscribe" not in item["short_description"]
    assert "https://example.com" not in item["short_description"]
    assert item["display_description"] == item["short_description"]


def test_build_feed_old_rows_without_new_fields():
    # Rows from a pre-metadata DB (no tags/duration/thumbnail) still build a feed.
    feed = build_feed([CALM, GRATITUDE], "daily-dew", k=12)
    assert feed
    item = feed[0]
    assert item["tags"] == []
    assert item["duration_seconds"] is None
    assert item["channel_id"] == ""
    # thumbnail falls back to the derived YouTube URL
    assert item["thumbnail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
