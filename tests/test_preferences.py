import sqlite3

from core.preferences import (
    DEFAULT_LANGUAGE,
    DEFAULT_REGION,
    ensure_sqlite_preferences_table,
    get_preferences,
    normalize_language_code,
    normalize_region_code,
    upsert_preferences,
)
from integrations import youtube_extractor, youtube_service
from integrations.youtube_ingest import SourceQuerySpec, fetch_youtube_candidates


def test_sqlite_preferences_default_and_upsert_normalize_values():
    conn = sqlite3.connect(":memory:")
    try:
        ensure_sqlite_preferences_table(conn)

        defaulted = get_preferences(conn, backend="sqlite", session_id="anon-1")
        assert defaulted["preferred_language"] == DEFAULT_LANGUAGE
        assert defaulted["region_code"] == DEFAULT_REGION
        assert defaulted["has_completed_language_setup"] is False

        saved = upsert_preferences(
            conn,
            backend="sqlite",
            session_id="anon-1",
            preferred_language="ES",
            region_code="mx",
            use_approx_location=True,
            has_completed_language_setup=True,
        )
        assert saved["preferred_language"] == "es"
        assert saved["region_code"] == "MX"
        assert saved["use_approx_location"] is True
        assert saved["has_completed_language_setup"] is True

        updated = upsert_preferences(
            conn,
            backend="sqlite",
            session_id="anon-1",
            preferred_language="zh-hant",
            region_code="tw",
        )
        assert updated["id"] == saved["id"]
        assert updated["preferred_language"] == "zh-Hant"
        assert updated["region_code"] == "TW"
    finally:
        conn.close()


def test_preference_code_normalizers_fall_back_to_safe_defaults():
    assert normalize_language_code("zh-hans") == "zh-Hans"
    assert normalize_language_code("not a language") == DEFAULT_LANGUAGE
    assert normalize_region_code("gb") == "GB"
    assert normalize_region_code("usa") == DEFAULT_REGION


def test_youtube_ingest_search_uses_language_and_region_preferences():
    seen_search_params = []
    seen_popular_params = []

    def fake_youtube(endpoint: str, params: dict) -> dict:
        if endpoint == "search":
            seen_search_params.append(params)
            return {"items": []}
        if endpoint == "videos" and params.get("chart") == "mostPopular":
            seen_popular_params.append(params)
            return {"items": []}
        raise AssertionError(f"Unexpected endpoint: {endpoint} {params}")

    candidates, skipped = fetch_youtube_candidates(
        api_key="test-key",
        queries=[SourceQuerySpec("music/culture", "new music review")],
        relevance_language="zh-hans",
        region_code="tw",
        request_json=fake_youtube,
    )

    assert candidates == []
    assert skipped == 0
    # search.list targets locale via relevanceLanguage + regionCode
    assert seen_search_params[0]["relevanceLanguage"] == "zh-Hans"
    assert seen_search_params[0]["regionCode"] == "TW"
    # mostPopular (chart) lane targets locale via hl + regionCode — NOT relevanceLanguage
    assert seen_popular_params, "popular lane should issue mostPopular requests"
    for params in seen_popular_params:
        assert params["chart"] == "mostPopular"
        assert params["hl"] == "zh-Hans"
        assert params["regionCode"] == "TW"
        assert "relevanceLanguage" not in params
        assert "videoCategoryId" in params


def test_youtube_service_chart_request_uses_hl_not_relevance_language(monkeypatch):
    calls = []

    def fake_request(endpoint: str, params: dict) -> dict:
        calls.append((endpoint, dict(params)))
        return {"items": [{"id": "video-1"}]}

    youtube_service._cache.clear()
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(youtube_service, "_api_request", fake_request)

    ids = youtube_service.fetch_videos_by_topic(
        "education",
        relevance_language="zh-hans",
        region_code="tw",
    )

    assert ids == ["video-1"]
    assert calls[0][0] == "videos"
    assert calls[0][1]["hl"] == "zh-Hans"
    assert calls[0][1]["regionCode"] == "TW"
    assert "relevanceLanguage" not in calls[0][1]
    assert youtube_service.get_all_topics_cache_status()["education@zh-Hans/TW"]["count"] == 1


def test_youtube_extractor_chart_request_uses_hl_not_relevance_language(monkeypatch):
    calls = []

    def fake_request(endpoint: str, params: dict) -> dict:
        calls.append((endpoint, dict(params)))
        return {"items": [{"id": "video-2"}]}

    monkeypatch.setattr(youtube_extractor, "YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(youtube_extractor, "_yt_request", fake_request)

    ids = youtube_extractor._fetch_ids_by_topic(
        "music",
        relevance_language="es",
        region_code="mx",
    )

    assert ids == ["video-2"]
    assert calls[0][0] == "videos"
    assert calls[0][1]["hl"] == "es"
    assert calls[0][1]["regionCode"] == "MX"
    assert "relevanceLanguage" not in calls[0][1]
