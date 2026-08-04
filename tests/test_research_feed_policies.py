from collections import Counter

from core.ranking.research_policies import (
    BALANCED_POLICY_VERSION,
    REGULAR_POLICY_VERSION,
    apply_research_policy,
    build_research_feed_payload,
    target_bucket_counts,
)


def item(index, category, *, creator=None):
    return {
        "youtube_id": f"post-{category}-{index}",
        "content_category": category,
        "channel_id": creator or f"creator-{index}",
        "channel_title": creator or f"Creator {index}",
        "title": f"Post {index}",
        "mode_fit": 0.5,
        "chrysalis_scores": {"calm": 0.5},
    }


def balanced_inventory():
    rows = [item(i, "regular") for i in range(16)]
    rows += [item(i, "healthy") for i in range(10)]
    rows += [item(i, "positive") for i in range(10)]
    rows += [item(i, "perspective") for i in range(6)]
    return rows


def max_run(values):
    longest = current = 0
    previous = object()
    for value in values:
        current = current + 1 if value == previous else 1
        longest = max(longest, current)
        previous = value
    return longest


def test_regular_v1_preserves_existing_order_without_new_quota():
    source = [item(0, "healthy"), item(1, "healthy"), item(2, "regular")]
    result = apply_research_policy(
        source,
        policy_version=REGULAR_POLICY_VERSION,
        k=3,
        seed="unused-by-regular",
    )

    assert [row["youtube_id"] for row in result] == [row["youtube_id"] for row in source]
    assert all(row["feed_policy_version"] == "regular-v1" for row in result)
    assert all(row["selection_reason"] == "existing_chrysalis_rank" for row in result)


def test_balanced_v1_approaches_60_30_10_bucket_targets():
    result = apply_research_policy(
        balanced_inventory(),
        policy_version=BALANCED_POLICY_VERSION,
        k=10,
        seed="policy-seed",
    )

    assert Counter(row["selection_bucket"] for row in result) == {
        "normal": 6,
        "healthy": 3,
        "diversity": 1,
    }
    assert target_bucket_counts(10) == {"normal": 6, "healthy": 3, "diversity": 1}


def test_balanced_v1_avoids_more_than_two_consecutive_categories_when_possible():
    result = apply_research_policy(
        balanced_inventory(),
        policy_version=BALANCED_POLICY_VERSION,
        k=12,
        seed="category-spread",
    )
    assert max_run([row["content_category"] for row in result]) <= 2


def test_balanced_v1_reduces_recent_creator_repetition_when_alternatives_exist():
    rows = []
    for category in ("regular", "healthy", "perspective"):
        rows.extend(item(i, category, creator="repeated") for i in range(5))
        rows.extend(item(i + 20, category, creator=f"unique-{category}-{i}") for i in range(5))
    result = apply_research_policy(
        rows,
        policy_version=BALANCED_POLICY_VERSION,
        k=10,
        seed="creator-spread",
    )
    creators = [row["channel_id"] for row in result]

    assert max_run(creators) == 1
    assert creators.count("repeated") <= 3


def test_balanced_v1_deduplicates_posts():
    duplicate = item(0, "regular")
    rows = balanced_inventory() + [duplicate, dict(duplicate)]
    result = apply_research_policy(
        rows,
        policy_version=BALANCED_POLICY_VERSION,
        k=30,
        seed="dedupe",
    )
    ids = [row["post_id"] for row in result]
    assert len(ids) == len(set(ids))


def test_balanced_v1_falls_back_when_healthy_or_perspective_inventory_is_short():
    rows = [item(i, "regular") for i in range(10)] + [item(20, "healthy")]
    result = apply_research_policy(
        rows,
        policy_version=BALANCED_POLICY_VERSION,
        k=10,
        seed="short-inventory",
    )

    assert len(result) == 10
    assert sum(row["selection_bucket"] == "healthy" for row in result) == 1
    assert any(row["selection_reason"] == "inventory_fallback" for row in result)


def test_balanced_v1_returns_fewer_posts_when_total_inventory_is_short():
    result = apply_research_policy(
        [item(0, "regular"), item(1, "healthy")],
        policy_version=BALANCED_POLICY_VERSION,
        k=12,
        seed="tiny",
    )
    assert len(result) == 2


def test_balanced_v1_is_deterministic_for_a_seed_and_changes_across_seeds():
    rows = balanced_inventory()
    first = apply_research_policy(rows, policy_version=BALANCED_POLICY_VERSION, k=12, seed="a")
    repeated = apply_research_policy(rows, policy_version=BALANCED_POLICY_VERSION, k=12, seed="a")
    changed = apply_research_policy(rows, policy_version=BALANCED_POLICY_VERSION, k=12, seed="b")

    first_ids = [row["post_id"] for row in first]
    assert first_ids == [row["post_id"] for row in repeated]
    assert first_ids != [row["post_id"] for row in changed]


def test_unknown_and_missing_categories_are_safe_normal_candidates():
    rows = [item(0, "unknown"), {**item(1, "regular"), "content_category": None}]
    result = apply_research_policy(
        rows,
        policy_version=BALANCED_POLICY_VERSION,
        k=2,
        seed="unknown",
    )
    assert len(result) == 2
    assert all(row["selection_bucket"] == "normal" for row in result)


def test_research_payload_hides_seed_and_private_ranking_scores():
    rows = [{
        "video_id": "calm-1",
        "title": "Calm journaling walk",
        "description": "Take a gentle walk, drink water, stretch and journal with gratitude.",
        "channel_id": "creator-1",
        "channel_title": "Creator One",
        "source_category": "wellness",
        "source_query": "wellness seed",
        "source_type": "search",
        "integrity_score": 0.8,
        "tags": ["journal", "walk"],
    }]
    payload = build_research_feed_payload(
        rows,
        policy_version=BALANCED_POLICY_VERSION,
        k=1,
        seed="private-server-seed",
    )

    assert "shuffle_seed" not in payload
    assert payload["items"][0]["feed_policy_version"] == "balanced-v1"
    assert "chrysalis_scores" not in payload["items"][0]
    assert "mode_fit" not in payload["items"][0]
    assert "integrity_score" not in payload["items"][0]
