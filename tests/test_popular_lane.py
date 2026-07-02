"""Tests for the YouTube "popular seed lane".

Covers extraction (videos.list chart=mostPopular with hl+regionCode, never
search.list/relevanceLanguage), mixing caps, source_type persistence, the capped
popularity ranking boost, and per-mode popular policy (Daily Dew ≤2, Flutter
Feed normal, Metamorphosis low-risk only).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from core.labeling.schema import SCORING_VERSION
from core.ranking.feed import build_feed_payload
from core.ranking.modes import POPULARITY_BOOST_CAP
from integrations.youtube_ingest import (
    MOST_POPULAR_CATEGORIES,
    SourceQuerySpec,
    fetch_most_popular_candidates,
    fetch_youtube_candidates,
    ingest_youtube_videos_sqlite,
    load_active_feed_video_rows_sqlite,
)

NOW = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def _video(video_id: str, title: str, *, views="20000", likes="1500", comments="120") -> dict:
    return {
        "id": video_id,
        "snippet": {
            "title": title,
            "description": (
                "Short wholesome wellbeing tips for study focus, digital wellness, "
                "confidence, and healthy phone habits."
            ),
            "channelId": f"channel-{video_id}",
            "channelTitle": "Wellness Lab",
            "categoryId": "27",
            "publishedAt": "2026-06-13T12:00:00Z",
            "tags": ["wellness", "study", "focus", "calm"],
            "thumbnails": {"high": {"url": f"https://i.ytimg.com/vi/{video_id}/hq.jpg"}},
        },
        "contentDetails": {"duration": "PT1M10S"},
        "statistics": {"viewCount": views, "likeCount": likes, "commentCount": comments},
        "status": {"embeddable": True, "privacyStatus": "public", "uploadStatus": "processed"},
    }


def _make_fake(*, search_ids, popular_per_category=2):
    """Fake YouTube transport: search.list returns ids; mostPopular returns videos."""
    calls = {"search": [], "popular": [], "metadata": []}

    def fake(endpoint: str, params: dict):
        if endpoint == "search":
            calls["search"].append(dict(params))
            return {"items": [{"id": {"videoId": vid}} for vid in search_ids]}
        if endpoint == "videos" and params.get("chart") == "mostPopular":
            calls["popular"].append(dict(params))
            cat = params["videoCategoryId"]
            items = [
                _video(f"pop_{cat}_{n}", "Calm wholesome trending explainer reset",
                       views="8000000", likes="350000", comments="20000")
                for n in range(popular_per_category)
            ]
            return {"items": items}
        if endpoint == "videos":
            calls["metadata"].append(dict(params))
            ids = str(params["id"]).split(",")
            return {"items": [_video(i, "Student focus calm study reset tips") for i in ids]}
        raise AssertionError(f"unexpected endpoint: {endpoint} {params}")

    return fake, calls


def test_popular_lane_uses_chart_hl_region_not_relevance_language():
    fake, calls = _make_fake(search_ids=["s1", "s2", "s3", "s4"])
    candidates, _ = fetch_youtube_candidates(
        api_key="k",
        queries=[SourceQuerySpec("study/productivity", "focus tips")],
        relevance_language="zh-hans",
        region_code="tw",
        request_json=fake,
        now=NOW,
    )

    assert calls["popular"], "popular lane should issue mostPopular requests"
    for params in calls["popular"]:
        assert params["chart"] == "mostPopular"
        assert params["hl"] == "zh-Hans"          # normalized
        assert params["regionCode"] == "TW"
        assert "videoCategoryId" in params
        assert "relevanceLanguage" not in params   # chart endpoint must not use it

    # metadata videos.list (by id) localizes with hl + regionCode too
    for params in calls["metadata"]:
        assert params["hl"] == "zh-Hans"
        assert params["regionCode"] == "TW"

    types = {c.source_type for c in candidates}
    assert "most_popular" in types and "search" in types


def test_mix_is_not_one_hundred_percent_popular():
    # Large search harvest → popular share stays a minority (~<=33% with the floor).
    fake, _ = _make_fake(search_ids=[f"s{i}" for i in range(12)], popular_per_category=3)
    candidates, _ = fetch_youtube_candidates(
        api_key="k",
        queries=[SourceQuerySpec("study/productivity", "focus tips")],
        request_json=fake,
        now=NOW,
    )
    n_total = len(candidates)
    n_popular = sum(1 for c in candidates if c.source_type == "most_popular")
    assert n_popular >= 1
    assert n_popular < n_total                      # never 100% popular
    assert n_popular / n_total <= 0.34


def test_fetch_most_popular_excludes_ids_and_tags_source_type():
    fake, _ = _make_fake(search_ids=[])
    first_cat = MOST_POPULAR_CATEGORIES[0][1]
    exclude = {f"pop_{first_cat}_0"}
    candidates, _ = fetch_most_popular_candidates(
        request=fake, relevance_language="en", region_code="US",
        now=NOW, exclude_ids=exclude,
    )
    ids = {c.youtube_video_id for c in candidates}
    assert f"pop_{first_cat}_0" not in ids          # excluded id dropped
    assert candidates and all(c.source_type == "most_popular" for c in candidates)
    assert all(c.popularity_score > 0 for c in candidates)


def test_source_type_and_popularity_persist_in_sqlite(tmp_path):
    fake, _ = _make_fake(search_ids=["s1", "s2"])
    db = tmp_path / "feed.db"
    ingest_youtube_videos_sqlite(
        db_path=db, api_key="k",
        queries=[SourceQuerySpec("study/productivity", "focus tips")],
        request_json=fake, now=NOW,
    )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rows = load_active_feed_video_rows_sqlite(conn)
    finally:
        conn.close()
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r["source_type"]] = by_type.get(r["source_type"], 0) + 1
    assert by_type.get("most_popular", 0) >= 1
    assert by_type.get("search", 0) >= 1
    assert all(r["popularity_score"] is not None for r in rows)


# --- ranking layer ----------------------------------------------------------

def _row(video_id, source_type, *, popularity, risk=0.05, calm=0.85):
    return {
        "video_id": video_id, "youtube_video_id": video_id,
        "title": f"Calm grounding reflection {video_id}",
        "description": "A calm, prosocial, reflective moment for studying and self care.",
        "channel_title": f"Ch-{video_id}", "channel_id": f"c-{video_id}",
        "source_category": "popular/news" if source_type == "most_popular" else "wellness",
        "source_query": "trending" if source_type == "most_popular" else "calm tips",
        "source_type": source_type, "popularity_score": popularity,
        "view_count": 1000, "published_at": "2026-06-14T10:00:00Z", "duration_seconds": 60,
        "chrysalis_scores": {
            "calm": calm, "prosocial": 0.7, "self_love": 0.6, "reflection_value": 0.7,
            "educational": 0.4, "novelty": 0.2, "diversity": 0.5, "overall_risk": risk,
            "comparison_risk": 0.05, "appearance_focus": 0.05, "ragebait": 0.02,
            "shame_or_humiliation_risk": 0.02, "age_safety_risk": 0.05,
            "misinformation_risk": 0.05, "overstimulation": 0.1, "consumerism": 0.1,
            "confidence": 0.6,
        },
        "scoring_version": SCORING_VERSION,
    }


def _items(mode, rows, k=10):
    return build_feed_payload(rows, mode, k=k, shuffle_seed="fixed")["items"]


def test_daily_dew_caps_popular_at_two():
    rows = [_row(f"s{i}", "search", popularity=0.2) for i in range(6)]
    rows += [_row(f"p{i}", "most_popular", popularity=0.95) for i in range(6)]
    items = _items("daily-dew", rows)
    assert sum(1 for it in items if it["is_popular"]) <= 2


def test_flutter_feed_allows_popular_normally():
    rows = [_row(f"s{i}", "search", popularity=0.2) for i in range(6)]
    rows += [_row(f"p{i}", "most_popular", popularity=0.95) for i in range(6)]
    items = _items("flutter-feed", rows)
    assert sum(1 for it in items if it["is_popular"]) > 2


def test_metamorphosis_excludes_high_risk_popular():
    # Low-risk search + high-risk popular. The popular ones must not appear.
    rows = [_row(f"s{i}", "search", popularity=0.2, risk=0.05) for i in range(6)]
    rows += [_row(f"p{i}", "most_popular", popularity=0.95, risk=0.4) for i in range(6)]
    items = _items("metamorphosis", rows)
    assert all(not it["is_popular"] for it in items)


def test_metamorphosis_allows_low_risk_popular_but_capped():
    rows = [_row(f"s{i}", "search", popularity=0.2, risk=0.02) for i in range(6)]
    rows += [_row(f"p{i}", "most_popular", popularity=0.95, risk=0.02) for i in range(6)]
    items = _items("metamorphosis", rows)
    assert 0 < sum(1 for it in items if it["is_popular"]) <= 2


def test_popularity_boost_is_capped_and_cannot_dominate():
    # A maximally-popular but lower-calm video vs. a calmer, less-popular one.
    calmer = _row("calmer", "search", popularity=0.0, calm=0.95)
    viral = _row("viral", "most_popular", popularity=1.0, calm=0.55)
    items = _items("daily-dew", [calmer, viral], k=2)
    fits = {it["youtube_id"]: it["mode_fit"] for it in items}
    # The capped boost (<= POPULARITY_BOOST_CAP) cannot lift the viral video over
    # the genuinely calmer one in a calm-first mode.
    assert fits["calmer"] > fits["viral"]
    assert POPULARITY_BOOST_CAP <= 0.05


def test_popular_items_carry_badge_fields():
    rows = [_row("p0", "most_popular", popularity=0.9), _row("s0", "search", popularity=0.1)]
    items = _items("flutter-feed", rows)
    popular = [it for it in items if it["youtube_id"] == "p0"][0]
    search = [it for it in items if it["youtube_id"] == "s0"][0]
    assert popular["is_popular"] is True
    assert popular["popularity_badge"] == "Popular"
    assert popular["source_type"] == "most_popular"
    assert search["is_popular"] is False
    assert search["popularity_badge"] is None


# --- Popular minimum-score threshold (POPULAR_MIN_SCORE, default 0.75) --------

def _payload(mode, rows, k=10):
    return build_feed_payload(rows, mode, k=k, shuffle_seed="fixed")


def test_low_score_popular_excluded_from_feed():
    # Old/weak popular rows (popularity < 0.75) must not surface, even though they
    # were "inserted" into the row pool. Search rows remain.
    rows = [_row(f"s{i}", "search", popularity=0.2) for i in range(4)]
    rows += [_row(f"weakpop{i}", "most_popular", popularity=0.2) for i in range(4)]
    items = _items("flutter-feed", rows)
    ids = {it["youtube_id"] for it in items}
    assert ids == {"s0", "s1", "s2", "s3"}
    assert all(not it["is_popular"] for it in items)


def test_high_score_popular_still_included():
    rows = [_row(f"s{i}", "search", popularity=0.2) for i in range(4)]
    rows += [_row("strongpop", "most_popular", popularity=0.9)]
    items = _items("flutter-feed", rows)
    assert any(it["youtube_id"] == "strongpop" and it["is_popular"] for it in items)


def test_low_score_search_videos_are_not_filtered():
    # Search lane is exempt from the popularity floor — niche/high-quality search
    # results may legitimately be low-popularity.
    rows = [_row(f"s{i}", "search", popularity=0.0) for i in range(4)]
    items = _items("flutter-feed", rows)
    assert {it["youtube_id"] for it in items} == {"s0", "s1", "s2", "s3"}


def test_threshold_is_exactly_at_boundary_inclusive():
    # popularity == POPULAR_MIN_SCORE (0.75) passes (>=), 0.74 fails.
    rows = [_row("s0", "search", popularity=0.2)]
    rows += [_row("at_floor", "most_popular", popularity=0.75)]
    rows += [_row("below_floor", "most_popular", popularity=0.74)]
    ids = {it["youtube_id"] for it in _items("flutter-feed", rows)}
    assert "at_floor" in ids
    assert "below_floor" not in ids


def test_debug_reports_popular_min_score():
    rows = [_row("s0", "search", popularity=0.2)]
    rows += [_row("weakpop", "most_popular", popularity=0.1)]
    payload = _payload("flutter-feed", rows)
    assert payload["popular_min_score"] == 0.75
    assert payload["popular_below_threshold_filtered_count"] == 1
    assert "source_type_counts" in payload


def test_daily_dew_still_caps_popular_at_two_with_threshold():
    # Strong popular (>= 0.75) still capped at 2 for daily-dew.
    rows = [_row(f"s{i}", "search", popularity=0.2) for i in range(6)]
    rows += [_row(f"p{i}", "most_popular", popularity=0.95) for i in range(6)]
    items = _items("daily-dew", rows)
    assert sum(1 for it in items if it["is_popular"]) <= 2


def test_extraction_filters_weak_popular(monkeypatch):
    # With an unreachable floor, no most_popular candidate survives extraction;
    # search candidates are untouched.
    monkeypatch.setattr("core.ranking.modes.POPULAR_MIN_SCORE", 2.0)
    fake, _ = _make_fake(search_ids=[f"s{i}" for i in range(6)], popular_per_category=3)
    candidates, _ = fetch_youtube_candidates(
        api_key="k",
        queries=[SourceQuerySpec("study/productivity", "focus tips")],
        request_json=fake,
        now=NOW,
    )
    types = {c.source_type for c in candidates}
    assert "most_popular" not in types
    assert "search" in types
