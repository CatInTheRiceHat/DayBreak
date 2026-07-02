"""Tests for the balanced healthier feed algorithm."""

from core.labeling.taxonomy import HEALTHY_CATEGORIES
from core.ranking.feed import build_feed_payload
from scripts.seed_demo_videos import seed_database


def _row(video_id: str, title: str, description: str, *, source_category: str, tags=None) -> dict:
    return {
        "video_id": video_id,
        "title": title,
        "description": description,
        "channel_title": f"Channel {video_id}",
        "source_category": source_category,
        "source_query": f"{source_category} seed",
        "source_type": "search",
        "duration_seconds": 72,
        "view_count": 12000,
        "tags": tags or [],
        "integrity_score": 0.78,
        "integrity_flags": {"negative": [], "positive": ["useful_context"]},
    }


def _healthy(index: int) -> dict:
    return _row(
        f"healthy-{index}",
        f"Calm journaling walk reset {index}",
        (
            "A gentle self care reminder to journal, drink water, stretch, "
            "take a short walk outside, and notice one thing you are grateful for."
        ),
        source_category="wellness",
        tags=["journal", "walk", "gratitude", "self care"],
    )


def _regular(index: int, category: str = "comedy") -> dict:
    return _row(
        f"regular-{category}-{index}",
        f"Harmless {category} short video {index}",
        (
            "A normal low-risk short-form clip with ordinary jokes, trends, "
            "sports, music, school, games, and lifestyle context for a fun feed."
        ),
        source_category=category,
        tags=[category, "fun", "shorts"],
    )


def _perspective(index: int) -> dict:
    return _row(
        f"perspective-{index}",
        f"Two people share different perspectives {index}",
        (
            "A calm respectful conversation where people see it differently, "
            "listen with an open mind, and find common ground without fighting."
        ),
        source_category="perspectives",
        tags=["different perspectives", "open minded", "common ground"],
    )


def _blocked() -> dict:
    return _row(
        "blocked-harm",
        "Graphic self harm and suicide vlog",
        "Disturbing footage with self-harm, suicidal content, and triggering content.",
        source_category="harmful",
        tags=["self harm", "suicide", "graphic"],
    )


def _reduced(index: int) -> dict:
    return _row(
        f"reduced-{index}",
        f"Doomscrolling bullying argument {index}",
        (
            "A toxic argument full of bullying, harassment, comment war, "
            "callout drama, and doomscrolling conflict."
        ),
        source_category="drama",
        tags=["doomscrolling", "bullying", "harassment"],
    )


def _payload(rows: list[dict], k: int = 10) -> dict:
    return build_feed_payload(rows, "flutter-feed", k=k, shuffle_seed="balanced-test")


def _max_run(values: list[str]) -> int:
    longest = 0
    current = 0
    last = None
    for value in values:
        current = current + 1 if value == last else 1
        longest = max(longest, current)
        last = value
    return longest


def test_balanced_feed_targets_healthy_ratio_when_inventory_allows():
    rows = [_healthy(i) for i in range(10)]
    rows += [_regular(i, category="comedy") for i in range(5)]
    rows += [_regular(i, category="sports") for i in range(5)]
    rows += [_perspective(i) for i in range(2)]

    payload = _payload(rows, k=10)
    categories = [item["content_category"] for item in payload["items"]]
    healthy_count = sum(1 for category in categories if category in HEALTHY_CATEGORIES)

    assert 4 <= healthy_count <= 6
    assert 0.4 <= payload["healthy_content_ratio"] <= 0.6
    assert payload["healthy_content_target"] == {"min": 0.4, "max": 0.6}


def test_regular_content_still_appears_in_the_healthier_feed():
    rows = [_healthy(i) for i in range(8)]
    rows += [_regular(i, category="music") for i in range(4)]
    rows += [_regular(i, category="games") for i in range(4)]

    payload = _payload(rows, k=8)
    categories = [item["content_category"] for item in payload["items"]]

    assert "regular" in categories
    assert any(item["recommendation_lane"] == "regular_mix" for item in payload["items"])


def test_blocked_harmful_content_is_filtered_from_feed():
    rows = [_healthy(i) for i in range(5)]
    rows += [_regular(i, category="comedy") for i in range(5)]
    rows.append(_blocked())

    payload = _payload(rows, k=8)
    ids = {item["youtube_id"] for item in payload["items"]}

    assert "blocked-harm" not in ids
    assert payload["candidate_content_category_counts"]["blocked"] == 1
    assert payload["reduced_or_blocked_filtered_count"] >= 1


def test_reduced_conflict_content_is_downranked_when_safe_alternatives_exist():
    rows = [_healthy(i) for i in range(6)]
    rows += [_regular(i, category="lifestyle") for i in range(6)]
    rows += [_reduced(i) for i in range(4)]

    payload = _payload(rows, k=8)
    categories = [item["content_category"] for item in payload["items"]]

    assert "reduced" not in categories
    assert payload["candidate_content_category_counts"]["reduced"] == 4


def test_content_categories_are_mixed_without_repeating_one_lane():
    rows = [_healthy(i) for i in range(8)]
    rows += [_regular(i, category="comedy") for i in range(4)]
    rows += [_regular(i, category="sports") for i in range(4)]
    rows += [_perspective(i) for i in range(3)]

    payload = _payload(rows, k=12)
    categories = [item["content_category"] for item in payload["items"]]

    assert len(set(categories)) >= 3
    assert _max_run(categories) <= 2


def test_low_conflict_perspective_content_appears_occasionally():
    rows = [_healthy(i) for i in range(8)]
    rows += [_regular(i, category="music") for i in range(8)]
    rows.append(_perspective(0))

    payload = _payload(rows, k=8)

    assert any(item["content_category"] == "perspective" for item in payload["items"])
    perspective = next(item for item in payload["items"] if item["content_category"] == "perspective")
    assert perspective["perspective_topic"]
    assert perspective["recommendation_lane"] == "perspective_mix"


def test_healthy_ratio_holds_for_realistic_feed_sizes():
    rows = [_healthy(i) for i in range(80)]
    rows += [_regular(i, category="comedy") for i in range(20)]
    rows += [_regular(i, category="sports") for i in range(20)]
    rows += [_regular(i, category="music") for i in range(20)]
    rows += [_regular(i, category="games") for i in range(20)]
    rows += [_perspective(i) for i in range(12)]

    for k in (10, 20, 50):
        payload = _payload(rows, k=k)
        categories = [item["content_category"] for item in payload["items"]]
        healthy_count = sum(1 for category in categories if category in HEALTHY_CATEGORIES)

        assert payload["count"] == k
        assert 0.4 <= healthy_count / k <= 0.6
        assert 0.4 <= payload["healthy_content_ratio"] <= 0.6
        assert "regular" in categories
        assert "perspective" in categories
        assert _max_run(categories) <= 2


def test_real_feed_endpoint_payload_exposes_taxonomy_debug_fields(tmp_path, monkeypatch):
    import api as local_api

    db_path = tmp_path / "chrysalis-feed.db"
    result = seed_database(str(db_path), reset=True)
    assert result["inserted"] == 12
    assert result["seed_rows_total"] == 12
    monkeypatch.setattr(local_api, "DB_PATH", str(db_path))

    payload = local_api.chrysalis_feed("flutter-feed", k=12, seed="balanced-api-test")
    assert payload["count"] == 12
    assert payload["debug"]["shuffle_seed"] == "balanced-api-test"

    required_item_fields = {
        "content_category",
        "contentCategory",
        "wellness_score",
        "wellnessScore",
        "positivity_score",
        "positivityScore",
        "conflict_score",
        "conflictScore",
        "safety_risk",
        "safetyRisk",
        "recommendation_lane",
        "recommendationLane",
        "ranking_reason",
        "rankingReason",
    }
    for item in payload["items"]:
        assert required_item_fields <= set(item)

    required_debug_fields = {
        "healthy_content_ratio",
        "healthy_content_target",
        "candidate_content_category_counts",
        "recommendation_lane_counts",
        "reduced_or_blocked_filtered_count",
        "content_category_counts",
    }
    assert required_debug_fields <= set(payload["debug"])

    categories = {item["content_category"] for item in payload["items"]}
    assert {"healthy", "positive", "regular", "perspective"} <= categories
