"""Regression tests for GET /api/cron/extract (api/index.py).

The cron used to write to a standalone legacy ``videos`` table that does not
exist in production Supabase, raising
``psycopg2.errors.UndefinedTable: relation "videos" does not exist``.

These tests exercise the *real* Postgres ingestion code path (the same SQL
strings production runs) with only the network (YouTube API) and the psycopg2
driver faked, and assert that the cron now:

  * writes into ``feed_videos`` (the table GET /api/feed/{mode} reads), and
  * never issues a read/write against the legacy ``videos`` table except the
    guarded, non-fatal ``to_regclass`` diagnostic, and
  * preserves language/region targeting end to end.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import integrations.youtube_ingest as youtube_ingest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_api_index():
    """Load api/index.py by file path (it is not an importable package)."""
    spec = importlib.util.spec_from_file_location(
        "chrysalis_api_index", ROOT / "api" / "index.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _video(video_id: str, title: str) -> dict:
    return {
        "id": video_id,
        "snippet": {
            "title": title,
            "description": (
                "Short student wellbeing tips for study focus, digital wellness, "
                "confidence, and healthy phone habits."
            ),
            "channelId": f"channel-{video_id}",
            "channelTitle": "Student Wellness Lab",
            "categoryId": "27",
            "publishedAt": "2026-06-13T12:00:00Z",
            "tags": ["student", "study", "focus"],
            "thumbnails": {"high": {"url": f"https://i.ytimg.com/vi/{video_id}/hq.jpg"}},
        },
        "contentDetails": {"duration": "PT1M10S"},
        "statistics": {"viewCount": "12000"},
        "status": {
            "embeddable": True,
            "privacyStatus": "public",
            "uploadStatus": "processed",
        },
    }


class _FakeCursor:
    def __init__(self, log: list[str]):
        self._log = log
        self._last = ""

    def execute(self, sql, params=None):
        self._last = sql
        self._log.append(sql)

    def fetchone(self):
        s = self._last.lower()
        if "to_regclass" in s:
            return (None,)  # legacy `videos` table is absent (production state)
        if "select 1 from feed_videos" in s:
            return None  # treat every candidate as new
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class _FakeConn:
    def __init__(self):
        self.sql_log: list[str] = []
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return _FakeCursor(self.sql_log)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_cron_extract_writes_feed_videos_and_avoids_legacy_videos(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.delenv("CRON_SECRET", raising=False)

    captured: list[tuple[str, dict]] = []

    def fake_request_factory(api_key):
        def request(endpoint: str, params: dict):
            captured.append((endpoint, dict(params)))
            if endpoint == "search":
                return {"items": [{"id": {"videoId": "calm1"}}, {"id": {"videoId": "focus2"}}]}
            if endpoint == "videos" and params.get("chart") == "mostPopular":
                return {"items": []}
            if endpoint == "videos":
                ids = str(params["id"]).split(",")
                return {"items": [_video(i, "Student focus tips for a calm reset") for i in ids]}
            raise AssertionError(f"unexpected endpoint: {endpoint}")

        return request

    # Fake only the network layer — the real ingest/Postgres SQL still runs.
    monkeypatch.setattr(youtube_ingest, "_youtube_request_json", fake_request_factory)

    index = _load_api_index()
    fake_conn = _FakeConn()
    monkeypatch.setattr(index, "get_db", lambda: fake_conn)

    # Call the endpoint function directly (avoids needing httpx/TestClient).
    # 1. No UndefinedTable error; endpoint returns cleanly.
    body = index.cron_extract(
        authorization=None,
        relevance_language="fr",
        region_code="FR",
    )

    # 3/4. Cron reports + actually targets the feed_videos table.
    assert body["table"] == "feed_videos"
    assert body["ok"] is True
    assert body["added"] >= 1  # candidates upserted

    executed = [s.lower() for s in fake_conn.sql_log]
    assert any("feed_videos" in s for s in executed)
    assert fake_conn.committed

    # 8. No reference to the legacy `videos` table except the guarded diagnostic.
    legacy_hits = [
        s
        for s in executed
        if "videos" in s and "feed_videos" not in s and "to_regclass" not in s
    ]
    assert legacy_hits == [], legacy_hits

    # 7. The safe, non-fatal legacy-table guard ran.
    assert any("to_regclass" in s for s in executed)

    # 6. Language/region preserved: search.list -> relevanceLanguage + regionCode;
    #    videos.list -> hl + regionCode.
    search_params = [p for ep, p in captured if ep == "search"]
    videos_params = [p for ep, p in captured if ep == "videos"]
    assert search_params and videos_params
    for p in search_params:
        assert p["relevanceLanguage"] == "fr"
        assert p["regionCode"] == "FR"
    for p in videos_params:
        assert p["hl"] == "fr"
        assert p["regionCode"] == "FR"


def test_cron_extract_defaults_to_en_us(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.delenv("CRON_SECRET", raising=False)

    captured: list[tuple[str, dict]] = []

    def fake_request_factory(api_key):
        def request(endpoint: str, params: dict):
            captured.append((endpoint, dict(params)))
            if endpoint == "search":
                return {"items": [{"id": {"videoId": "calm1"}}]}
            if endpoint == "videos" and params.get("chart") == "mostPopular":
                return {"items": []}
            if endpoint == "videos":
                ids = str(params["id"]).split(",")
                return {"items": [_video(i, "Student focus tips reset") for i in ids]}
            raise AssertionError(endpoint)

        return request

    monkeypatch.setattr(youtube_ingest, "_youtube_request_json", fake_request_factory)

    index = _load_api_index()
    monkeypatch.setattr(index, "get_db", lambda: _FakeConn())

    body = index.cron_extract(authorization=None)
    assert body["table"] == "feed_videos"

    search_params = [p for ep, p in captured if ep == "search"]
    videos_params = [p for ep, p in captured if ep == "videos"]
    assert all(p["relevanceLanguage"] == "en" and p["regionCode"] == "US" for p in search_params)
    assert all(p["hl"] == "en" and p["regionCode"] == "US" for p in videos_params)
