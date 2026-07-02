from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from core.language_filter import verdict
from core.ranking.feed import build_feed, build_feed_payload
from integrations.youtube_ingest import (
    DEFAULT_SOURCE_BUCKETS,
    RELEVANCE_TERMS,
    SourceQuerySpec,
    _relevance_score,
    configured_source_queries,
    ingest_youtube_videos_sqlite,
    load_active_feed_video_rows_sqlite,
)


NOW = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def _video(
    video_id: str,
    title: str,
    duration: str = "PT1M20S",
    views: str = "12000",
    description: str | None = None,
) -> dict:
    return {
        "id": video_id,
        "snippet": {
            "title": title,
            "description": description or (
                "Short student wellbeing tips for study focus, digital wellness, "
                "confidence, and healthy phone habits."
            ),
            "channelId": f"channel-{video_id}",
            "channelTitle": "Student Wellness Lab",
            "categoryId": "27",
            "publishedAt": "2026-06-13T12:00:00Z",
            "tags": ["student", "study", "focus", "digital wellness"],
            "thumbnails": {"high": {"url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"}},
        },
        "contentDetails": {"duration": duration},
        "statistics": {"viewCount": views},
        "status": {
            "embeddable": True,
            "privacyStatus": "public",
            "uploadStatus": "processed",
        },
    }


def _fake_youtube(endpoint: str, params: dict) -> dict:
    if endpoint == "search":
        return {
            "items": [
                {"id": {"videoId": "calm1"}},
                {"id": {"videoId": "focus2"}},
                {"id": {"videoId": "bad3"}},
                {"id": {"videoId": "long4"}},
                {"id": {"videoId": "calm1"}},  # duplicate from the same search page
            ]
        }
    if endpoint == "videos" and params.get("chart") == "mostPopular":
        # Popular seed lane — keep this fixture focused on the search path.
        return {"items": []}
    if endpoint == "videos":
        ids = str(params["id"]).split(",")
        all_items = {
            "calm1": _video(
                "calm1",
                "Student focus tips for a calm study reset",
                description=(
                    "Short student wellbeing tips for study focus, digital wellness, "
                    "confidence, and healthy phone habits. Subscribe for more resets! "
                    "Links below: https://example.com #study #focus #productivity #school"
                ),
            ),
            "focus2": _video("focus2", "AI literacy for students in 60 seconds", "PT58S", "22000"),
            "bad3": _video("bad3", "Free money crypto giveaway telegram crypto", "PT45S", "90000"),
            "long4": _video("long4", "Student focus tips full workshop", "PT6M", "5000"),
        }
        return {"items": [all_items[video_id] for video_id in ids if video_id in all_items]}
    raise AssertionError(f"Unexpected endpoint: {endpoint}")


def test_youtube_ingest_stores_filtered_real_videos_without_duplicate_inserts(tmp_path):
    db_path = tmp_path / "feed.db"

    first = ingest_youtube_videos_sqlite(
        db_path=db_path,
        api_key="test-key",
        queries=[SourceQuerySpec("study/productivity", "student focus tips")],
        max_results_per_query=10,
        days_back=7,
        request_json=_fake_youtube,
        now=NOW,
    )
    assert first.added == 2
    assert first.updated == 0
    assert first.skipped >= 3

    second = ingest_youtube_videos_sqlite(
        db_path=db_path,
        api_key="test-key",
        queries=[SourceQuerySpec("study/productivity", "student focus tips")],
        max_results_per_query=10,
        days_back=7,
        request_json=_fake_youtube,
        now=NOW,
    )
    assert second.added == 0
    assert second.updated == 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = load_active_feed_video_rows_sqlite(conn)
    finally:
        conn.close()

    assert {row["video_id"] for row in rows} == {"focus2", "calm1"}
    assert {row["source_category"] for row in rows} == {"study/productivity"}
    assert {row["source_query"] for row in rows} == {"student focus tips"}
    raw_calm = next(row for row in rows if row["video_id"] == "calm1")
    assert "Subscribe for more resets" in raw_calm["description"]
    assert "Subscribe" not in raw_calm["short_description"]
    assert "https://example.com" not in raw_calm["short_description"]
    assert raw_calm["display_title"] == "Student focus tips for a calm study reset"
    assert raw_calm["display_channel"] == "Student Wellness Lab"
    assert raw_calm["display_hashtags"]
    assert raw_calm["integrity_score"] >= 0.38
    assert raw_calm["integrity_flags"]
    assert raw_calm["production_style"] in {"polished", "casual", "amateur", "low_budget", "chaotic", "unknown"}
    assert raw_calm["creator_scale"] in {"small", "mid", "large", "unknown"}
    assert rows[0]["ingest_score"] >= rows[1]["ingest_score"]
    assert all(row["embed_url"].startswith("https://www.youtube-nocookie.com/embed/") for row in rows)
    assert all(row["thumbnail_url"].endswith("/hqdefault.jpg") for row in rows)

    feed = build_feed(rows, "flutter-feed", k=10)
    assert {item["youtube_id"] for item in feed} == {"calm1", "focus2"}
    assert all(item["embed_url"].startswith("https://www.youtube-nocookie.com/embed/") for item in feed)
    assert all(item["source_category"] == "study/productivity" for item in feed)
    calm_card = next(item for item in feed if item["youtube_id"] == "calm1")
    assert calm_card["description"] == raw_calm["description"]
    assert calm_card["title"] == raw_calm["title"]
    assert calm_card["display_title"] == raw_calm["display_title"]
    assert calm_card["source"] == raw_calm["display_channel"]
    assert calm_card["display_hashtags"] == ["#study", "#focus", "#productivity"]
    assert calm_card["short_description"] == raw_calm["short_description"]
    assert calm_card["displayDescription"] == raw_calm["short_description"]
    assert calm_card["integrity_score"] >= 0.38
    assert calm_card["feed_validity_score"] == calm_card["integrity_score"]
    assert calm_card["production_style"] == raw_calm["production_style"]
    assert calm_card["creator_scale"] == raw_calm["creator_scale"]

    mode_sets = {
        mode: {item["youtube_id"] for item in build_feed(rows, mode, k=10)}
        for mode in ("flutter-feed", "daily-dew", "metamorphosis")
    }
    assert all(video_ids == {"calm1", "focus2"} for video_ids in mode_sets.values())


def test_default_youtube_source_buckets_match_broad_feed_brief():
    categories = {spec.source_category for spec in DEFAULT_SOURCE_BUCKETS}
    assert categories == {
        "news/current events",
        "opinion/commentary",
        "travel",
        "food",
        "cute animals",
        "fashion/aesthetic",
        "gaming",
        "comedy",
        "internet culture",
        "AI/technology",
        "pop culture",
        "sports",
        "wellness/mental health",
        "positivity/self care",
        "emotional wellness",
        "mindfulness/calm",
        "study/productivity",
        "lifestyle/vlogs",
        "education/explainers",
        "music/culture",
    }
    assert configured_source_queries("news/current events=current events explained")[0] == (
        "news/current events",
        "current events explained",
    )


# ── Positive / self-care expansion (more uplifting content, still balanced) ───

NEW_POSITIVE_BUCKETS = (
    SourceQuerySpec("positivity/self care", "uplifting self care positive mindset tips"),
    SourceQuerySpec("emotional wellness", "emotional wellness healthy habits advice"),
    SourceQuerySpec("mindfulness/calm", "mindfulness calm reset tips"),
)


def test_new_positive_buckets_do_not_self_block_language_filter():
    # Every default query — including the new positivity/self-care ones — must
    # pass the English-only filter. A self-blocking query would ingest nothing.
    for spec in DEFAULT_SOURCE_BUCKETS:
        decision = verdict({"source_query": spec.source_query, "source_category": spec.source_category})
        assert decision["allowed"], (spec, decision)
    for spec in NEW_POSITIVE_BUCKETS:
        assert spec in DEFAULT_SOURCE_BUCKETS
        assert verdict({"source_query": spec.source_query, "source_category": spec.source_category})["allowed"]


def test_configured_queries_include_positivity_buckets():
    configured = configured_source_queries("")  # empty -> defaults, deterministic
    for spec in NEW_POSITIVE_BUCKETS:
        assert spec in configured
    # The broad Gen-Z mix is preserved (not replaced by wellness).
    categories = {spec.source_category for spec in configured}
    for general in ("comedy", "food", "gaming", "fashion/aesthetic", "sports",
                    "music/culture", "cute animals", "news/current events"):
        assert general in categories
    # Only a small number of new wellness-adjacent lanes were added (2–3).
    wellnessish = {"wellness/mental health", "positivity/self care",
                   "emotional wellness", "mindfulness/calm", "study/productivity"}
    assert len(categories & wellnessish) <= 5
    assert len(categories - wellnessish) >= 10  # general lanes still dominate the list


def test_relevance_terms_include_positive_vocabulary():
    for term in ("self care", "self-care", "positivity", "positive mindset",
                 "uplifting", "encouragement", "confidence", "gratitude",
                 "kindness", "resilience", "mindfulness", "calm", "healthy habits",
                 "emotional wellness", "wholesome", "feel good", "reset",
                 "reflection", "self improvement", "personal growth"):
        assert term in RELEVANCE_TERMS, term


def _rel(title, description="", tags=None, *, category="positivity/self care",
         query="uplifting self care positive mindset tips"):
    return _relevance_score(
        title=title, description=description, tags=tags or [], query=query,
        source_category=category, published_at="2026-06-13T12:00:00Z",
        duration_seconds=80, view_count=12000, labels={}, now=NOW, days_back=7,
    )


def test_positive_terms_boost_relevance_without_overpowering():
    uplifting = _rel(
        "A gentle gratitude and self care reset for calm confidence",
        "mindfulness kindness resilience healthy habits positive mindset",
    )
    bland = _rel("random clip", "nothing in particular here",
                 category="custom", query="custom")
    # Uplifting content ranks clearly above contentless content…
    assert uplifting > bland
    # …but the keyword score is clamped, so wellness never runs away to a 1.0
    # that would crowd every slot.
    assert uplifting < 1.0
    # A regular non-wellness video still scores meaningfully — the new terms add
    # signal, they don't zero out everything else.
    comedy = _rel("clean comedy sketch standup bit", "funny short skit",
                  category="comedy", query="clean comedy sketch standup")
    assert comedy > 0.1


def test_feed_stays_balanced_and_not_all_wellness():
    from tests.test_balanced_feed_algorithm import _healthy, _regular

    # Wellness-heavy candidate pool (as the new positive lanes would produce)
    # plus regular Gen-Z content.
    rows = [_healthy(i) for i in range(12)]
    rows += [_regular(i, category=c) for i, c in
             enumerate(["comedy", "gaming", "sports", "food", "music", "travel"])]

    payload = build_feed_payload(rows, "flutter-feed", k=10, shuffle_seed="balance")
    categories = [item["content_category"] for item in payload["items"]]

    # Regular content still appears — the feed did not collapse into all-wellness.
    assert "regular" in categories
    # Healthy ratio holds inside the Chrysalis target band despite the heavy pool.
    assert 0.4 <= payload["healthy_content_ratio"] <= 0.6
