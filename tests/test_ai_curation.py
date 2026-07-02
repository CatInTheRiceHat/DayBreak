"""Tests for the AI-assisted channel curation import/upsert workflow.

Model: AI inserts labeled rows (added_by='ai', review_status='unreviewed') into
the EXISTING trust tables; a human later removes/disables exceptions. AI must
never overwrite a human's review/disable decision, and a trusted whitelist must
never bypass safety/language filters (enforced at the ingestion gate, tested in
tests/test_trusted_channels.py).
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_CLI = _REPO_ROOT / "scripts" / "import_ai_channel_curation.py"

from core.trust_registry import (
    AI_REVIEW_STATUS_DEFAULT,
    AI_TRUST_STATUSES,
    ensure_trust_tables_sqlite,
    load_approved_trusted_channels,
    load_blocked_channel_ids,
    upsert_ai_channel_curation,
    validate_ai_curation_row,
)
from integrations.youtube_ingest import (
    SourceQuerySpec,
    ingest_youtube_videos_sqlite,
    load_active_feed_video_rows_sqlite,
)

NOW = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def _ytvideo(vid, title, channel_id, default_language="en"):
    return {
        "id": vid,
        "snippet": {
            "title": title,
            "description": "A calm, prosocial study and wellbeing explainer.",
            "channelId": channel_id, "channelTitle": channel_id, "categoryId": "27",
            "publishedAt": "2026-06-13T12:00:00Z", "tags": ["calm", "study"],
            "defaultLanguage": default_language,
            "thumbnails": {"high": {"url": f"https://i.ytimg.com/vi/{vid}/hq.jpg"}},
        },
        "contentDetails": {"duration": "PT1M10S"},
        "statistics": {"viewCount": "40000", "likeCount": "3000", "commentCount": "200"},
        "status": {"embeddable": True, "privacyStatus": "public", "uploadStatus": "processed"},
    }


def _fake_transport(*, channel_videos=None, search_videos=None):
    """search by channelId → that channel's ids; search by q → search ids;
    videos by id → metadata; mostPopular → empty."""
    channel_videos = channel_videos or {}
    search_videos = search_videos or {}
    by_id = {v["id"]: v for vs in channel_videos.values() for v in vs}
    by_id.update({v["id"]: v for v in search_videos.values()})
    calls = {"search_channel": []}

    def fake(endpoint, params):
        if endpoint == "search" and params.get("channelId"):
            ch = params["channelId"]
            calls["search_channel"].append(ch)
            return {"items": [{"id": {"videoId": v["id"]}} for v in channel_videos.get(ch, [])]}
        if endpoint == "search":
            return {"items": [{"id": {"videoId": vid}} for vid in search_videos]}
        if endpoint == "videos" and params.get("chart") == "mostPopular":
            return {"items": []}
        if endpoint == "videos":
            ids = str(params["id"]).split(",")
            return {"items": [by_id[i] for i in ids if i in by_id]}
        raise AssertionError(f"unexpected endpoint {endpoint} {params}")

    return fake, calls


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_trust_tables_sqlite(conn)
    return conn


def _trusted_row(conn, channel_id):
    return conn.execute(
        "SELECT * FROM trusted_youtube_channels WHERE channel_id=?", (channel_id,)
    ).fetchone()


def _blocked_row(conn, channel_id):
    return conn.execute(
        "SELECT * FROM blocked_youtube_channels WHERE channel_id=?", (channel_id,)
    ).fetchone()


# ── Validation ───────────────────────────────────────────────────────────────

def test_trust_status_vocabulary():
    assert set(AI_TRUST_STATUSES) == {"trusted", "blocked", "pending", "rejected"}
    assert AI_REVIEW_STATUS_DEFAULT == "unreviewed"


def test_validate_rejects_unknown_trust_status():
    with pytest.raises(ValueError):
        validate_ai_curation_row({"channel_id": "UC1", "trust_status": "whitelist",
                                  "confidence_score": 0.5})


def test_validate_rejects_out_of_range_confidence():
    for bad in (-0.1, 1.5, "high", None):
        with pytest.raises(ValueError):
            validate_ai_curation_row({"channel_id": "UC1", "trust_status": "trusted",
                                      "confidence_score": bad})


def test_validate_requires_channel_id():
    with pytest.raises(ValueError):
        validate_ai_curation_row({"trust_status": "trusted", "confidence_score": 0.5})


def test_validate_defaults_active_by_status():
    trusted = validate_ai_curation_row({"channel_id": "UC1", "trust_status": "trusted",
                                        "confidence_score": 0.8})
    assert trusted["active"] is True and trusted["platform"] == "youtube"
    pending = validate_ai_curation_row({"channel_id": "UC2", "trust_status": "pending",
                                        "confidence_score": 0.8})
    rejected = validate_ai_curation_row({"channel_id": "UC3", "trust_status": "rejected",
                                         "confidence_score": 0.8})
    assert pending["active"] is False and rejected["active"] is False


# ── Upsert: trusted / blocked routing ────────────────────────────────────────

def test_ai_trusted_insert_lands_in_trusted_table_and_is_eligible():
    conn = _conn()
    res = upsert_ai_channel_curation(
        conn, channel_id="UCwell", channel_title="Wellness", source_type="wellness",
        trust_status="trusted", confidence_score=0.86, reason="calm teen-safe wellness",
    )
    assert res["action"] == "inserted"
    row = _trusted_row(conn, "UCwell")
    assert row["added_by"] == "ai"
    assert row["status"] == "approved"
    assert row["trust_status"] == "trusted"
    assert row["active"] == 1
    assert row["review_status"] == "unreviewed"
    assert abs(row["ai_confidence"] - 0.86) < 1e-9
    assert row["ai_reason"] == "calm teen-safe wellness"
    # eligible for the trusted lane
    assert "UCwell" in {c.channel_id for c in load_approved_trusted_channels(conn)}


def test_ai_blocked_insert_lands_in_blocked_table_and_excludes():
    conn = _conn()
    res = upsert_ai_channel_curation(
        conn, channel_id="UCspam", channel_title="Spam", source_type="spam",
        trust_status="blocked", confidence_score=0.91, reason="reposted engagement bait",
    )
    assert res["action"] == "inserted"
    row = _blocked_row(conn, "UCspam")
    assert row["added_by"] == "ai"
    assert row["trust_status"] == "blocked"
    assert row["active"] == 1
    assert "UCspam" in load_blocked_channel_ids(conn)


def test_pending_and_rejected_are_inactive_and_not_eligible():
    conn = _conn()
    upsert_ai_channel_curation(conn, channel_id="UCpend", trust_status="pending",
                               confidence_score=0.5, reason="needs a human look")
    upsert_ai_channel_curation(conn, channel_id="UCrej", trust_status="rejected",
                               confidence_score=0.5, reason="not a fit")
    assert _trusted_row(conn, "UCpend")["active"] == 0
    assert _trusted_row(conn, "UCrej")["active"] == 0
    eligible = {c.channel_id for c in load_approved_trusted_channels(conn)}
    assert "UCpend" not in eligible and "UCrej" not in eligible


# ── Upsert: idempotency + human-decision protection ──────────────────────────

def test_upsert_is_idempotent_no_duplicate_rows():
    conn = _conn()
    upsert_ai_channel_curation(conn, channel_id="UCx", trust_status="trusted",
                               confidence_score=0.7, source_type="wellness", reason="r1")
    res2 = upsert_ai_channel_curation(conn, channel_id="UCx", trust_status="trusted",
                                      confidence_score=0.8, source_type="education", reason="r2")
    assert res2["action"] == "updated"
    count = conn.execute("SELECT COUNT(*) FROM trusted_youtube_channels WHERE channel_id='UCx'").fetchone()[0]
    assert count == 1
    row = _trusted_row(conn, "UCx")
    assert abs(row["ai_confidence"] - 0.8) < 1e-9   # AI may update ai_confidence
    assert row["ai_reason"] == "r2"                  # …and ai_reason
    assert row["source_group"] == "education"        # …and source_type/category


def test_inactive_human_disabled_row_not_reactivated_by_default():
    conn = _conn()
    upsert_ai_channel_curation(conn, channel_id="UCdis", trust_status="trusted",
                               confidence_score=0.7, reason="ok")
    # human disables the row in Supabase
    conn.execute("UPDATE trusted_youtube_channels SET active=0 WHERE channel_id='UCdis'")
    conn.commit()
    # AI re-imports as trusted (active default true) — must NOT reactivate
    upsert_ai_channel_curation(conn, channel_id="UCdis", trust_status="trusted",
                               confidence_score=0.9, reason="still ok")
    assert _trusted_row(conn, "UCdis")["active"] == 0
    assert "UCdis" not in {c.channel_id for c in load_approved_trusted_channels(conn)}


def test_force_reactivate_flag_reactivates():
    conn = _conn()
    upsert_ai_channel_curation(conn, channel_id="UCf", trust_status="trusted",
                               confidence_score=0.7, reason="ok")
    conn.execute("UPDATE trusted_youtube_channels SET active=0 WHERE channel_id='UCf'")
    conn.commit()
    upsert_ai_channel_curation(conn, channel_id="UCf", trust_status="trusted",
                               confidence_score=0.9, reason="ok", force_reactivate=True)
    assert _trusted_row(conn, "UCf")["active"] == 1


def test_human_reviewed_fields_not_overwritten_by_ai():
    conn = _conn()
    upsert_ai_channel_curation(conn, channel_id="UCh", trust_status="trusted",
                               confidence_score=0.6, reason="ai says ok")
    # human reviews + annotates
    conn.execute(
        "UPDATE trusted_youtube_channels SET review_status='reviewed', reviewed_by='elaine', "
        "review_notes='checked, keep', status='approved' WHERE channel_id='UCh'"
    )
    conn.commit()
    # AI re-imports with a different opinion
    upsert_ai_channel_curation(conn, channel_id="UCh", trust_status="rejected",
                               confidence_score=0.95, reason="ai changed its mind")
    row = _trusted_row(conn, "UCh")
    # human review fields preserved
    assert row["review_status"] == "reviewed"
    assert row["reviewed_by"] == "elaine"
    assert row["review_notes"] == "checked, keep"
    assert row["status"] == "approved"          # human decision not overwritten
    # but AI metadata still refreshed
    assert abs(row["ai_confidence"] - 0.95) < 1e-9
    assert row["ai_reason"] == "ai changed its mind"


# ── End-to-end ingestion integration (requirement #4) ────────────────────────

def _seed_and_ingest(tmp_path, *, curations, channel_videos=None, search_videos=None):
    db = tmp_path / "feed.db"
    conn = sqlite3.connect(db)
    ensure_trust_tables_sqlite(conn)
    for c in curations:
        upsert_ai_channel_curation(conn, **c)
    conn.close()
    fake, calls = _fake_transport(channel_videos=channel_videos, search_videos=search_videos)
    ingest_youtube_videos_sqlite(
        db_path=db, api_key="k",
        queries=[SourceQuerySpec("study/productivity", "focus")],
        request_json=fake, now=NOW,
    )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rows = load_active_feed_video_rows_sqlite(conn)
    finally:
        conn.close()
    return rows, calls


def test_ai_trusted_active_channel_is_queried_and_ingested(tmp_path):
    rows, calls = _seed_and_ingest(
        tmp_path,
        curations=[dict(channel_id="UC_ai", channel_title="AI Trusted", source_type="wellness",
                        trust_status="trusted", confidence_score=0.8, reason="calm wellness")],
        channel_videos={"UC_ai": [_ytvideo("aiv", "Calm grounding reflection focus", "UC_ai")]},
    )
    assert "UC_ai" in calls["search_channel"]                      # trusted lane queried it
    trusted = [r for r in rows if r["source_type"] == "trusted_channel"]
    assert {r["video_id"] for r in trusted} == {"aiv"}


def test_ai_blocked_active_channel_excluded_end_to_end(tmp_path):
    rows, _ = _seed_and_ingest(
        tmp_path,
        curations=[dict(channel_id="UC_evil", trust_status="blocked", source_type="spam",
                        confidence_score=0.9, reason="reposted bait")],
        # the search lane surfaces a video that belongs to the blocked channel
        search_videos={"s1": _ytvideo("s1", "Calm focus tips", "UC_evil")},
    )
    assert all(r["channel_id"] != "UC_evil" for r in rows)
    assert all(r["video_id"] != "s1" for r in rows)


def test_pending_and_rejected_channels_are_not_queried(tmp_path):
    _, calls = _seed_and_ingest(
        tmp_path,
        curations=[
            dict(channel_id="UC_pend", trust_status="pending", confidence_score=0.5, reason="?"),
            dict(channel_id="UC_rej", trust_status="rejected", confidence_score=0.5, reason="no"),
        ],
        channel_videos={
            "UC_pend": [_ytvideo("pv", "pending vid", "UC_pend")],
            "UC_rej": [_ytvideo("rv", "rejected vid", "UC_rej")],
        },
    )
    assert "UC_pend" not in calls["search_channel"]
    assert "UC_rej" not in calls["search_channel"]


def test_ai_trusted_whitelist_does_not_bypass_language_filter(tmp_path):
    # Trusted + active, but the video is non-English → still rejected by the gate.
    rows, calls = _seed_and_ingest(
        tmp_path,
        curations=[dict(channel_id="UC_w", trust_status="trusted", source_type="news",
                        confidence_score=0.85, reason="trusted but mixed-language")],
        channel_videos={"UC_w": [
            _ytvideo("eng", "A calm grounding reflection for focus", "UC_w", "en"),
            _ytvideo("hin", "नमस्ते आज हम ध्यान करना सीखेंगे रोज़ अभ्यास", "UC_w", "hi"),
        ]},
    )
    assert "UC_w" in calls["search_channel"]                       # it was eligible…
    ids = {r["video_id"] for r in rows}
    assert "eng" in ids                                            # English kept
    assert "hin" not in ids                                        # foreign rejected despite whitelist


# ── Postgres upsert branching (fake conn — no real Postgres in CI) ───────────

class _FakePGCursor:
    def __init__(self, store):
        self.store = store

    def execute(self, sql, params=None):
        verb = sql.strip().split()[0].upper()
        self.store["log"].append((verb, sql, params))

    def fetchone(self):
        return self.store["existing"]

    def close(self):
        pass


class _FakePGConn:
    def __init__(self, existing=None):
        self.store = {"log": [], "existing": existing}
        self.committed = False

    def cursor(self):
        return _FakePGCursor(self.store)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def test_postgres_upsert_insert_path_labels_ai():
    conn = _FakePGConn(existing=None)
    res = upsert_ai_channel_curation(conn, backend="postgres", channel_id="UCp",
                                     trust_status="trusted", confidence_score=0.7,
                                     source_type="news", reason="r")
    assert res["action"] == "inserted"
    inserts = [(s, p) for (verb, s, p) in conn.store["log"] if verb == "INSERT"]
    assert inserts and "trusted_youtube_channels" in inserts[0][0]
    assert "ai" in inserts[0][1]              # added_by='ai' is in the value tuple
    assert conn.committed


def test_postgres_upsert_human_review_only_touches_ai_fields():
    # existing row: (active, review_status, reviewed_by)
    conn = _FakePGConn(existing=(True, "reviewed", "elaine"))
    upsert_ai_channel_curation(conn, backend="postgres", channel_id="UCp",
                               trust_status="rejected", confidence_score=0.95,
                               reason="ai changed mind")
    updates = [s for (verb, s, p) in conn.store["log"] if verb == "UPDATE"]
    assert updates, "expected an UPDATE"
    u = updates[0].lower().replace(" ", "")
    assert "ai_confidence=%s" in u            # AI signal refreshed
    assert "active=%s" not in u               # human decision untouched
    assert "status=%s" not in u and "trust_status=%s" not in u


# ── CLI script (subprocess, real sqlite) ─────────────────────────────────────

def _run_cli(*args):
    return subprocess.run([sys.executable, str(_CLI), *args],
                          capture_output=True, text=True, cwd=str(_REPO_ROOT))


def test_cli_imports_valid_rows_and_skips_invalid(tmp_path):
    data = [
        {"platform": "youtube", "channel_id": "UCcli", "channel_title": "CLI Wellness",
         "channel_url": "https://youtube.com/channel/UCcli", "trust_status": "trusted",
         "source_type": "wellness", "confidence_score": 0.8, "reason": "calm advice"},
        {"channel_id": "UCspamcli", "trust_status": "blocked", "source_type": "spam",
         "confidence_score": 0.9, "reason": "bait"},
        {"channel_id": "UCbad", "trust_status": "whitelist", "confidence_score": 0.5},  # invalid status
        {"channel_id": "UCbadconf", "trust_status": "trusted", "confidence_score": 2.0},  # bad confidence
    ]
    jf = tmp_path / "ai.json"
    jf.write_text(json.dumps(data))
    db = tmp_path / "feed.db"
    out = _run_cli("--backend", "sqlite", "--db-path", str(db), "--input", str(jf))
    assert out.returncode == 0, out.stderr
    assert "inserted=2" in out.stdout
    assert "skipped=2" in out.stdout

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    t = conn.execute("SELECT * FROM trusted_youtube_channels WHERE channel_id='UCcli'").fetchone()
    b = conn.execute("SELECT * FROM blocked_youtube_channels WHERE channel_id='UCspamcli'").fetchone()
    conn.close()
    assert t["added_by"] == "ai" and t["trust_status"] == "trusted" and t["active"] == 1
    assert b["added_by"] == "ai" and b["trust_status"] == "blocked"


def test_cli_dry_run_makes_no_changes(tmp_path):
    data = [{"channel_id": "UCdry", "trust_status": "trusted", "confidence_score": 0.7, "reason": "x"}]
    jf = tmp_path / "ai.json"
    jf.write_text(json.dumps(data))
    db = tmp_path / "feed.db"
    out = _run_cli("--backend", "sqlite", "--db-path", str(db), "--input", str(jf), "--dry-run")
    assert out.returncode == 0, out.stderr
    assert "DRY RUN" in out.stdout and "no database changes" in out.stdout
    # the row must NOT have been written
    conn = sqlite3.connect(db)
    try:
        present = conn.execute(
            "SELECT COUNT(*) FROM trusted_youtube_channels WHERE channel_id='UCdry'"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        present = 0  # table may not even exist on a pure dry run
    conn.close()
    assert present == 0


def test_cli_fails_safely_on_missing_input(tmp_path):
    out = _run_cli("--backend", "sqlite", "--input", str(tmp_path / "nope.json"))
    assert out.returncode != 0
    assert "not found" in (out.stdout + out.stderr).lower()


def test_cli_never_prints_database_url(tmp_path, monkeypatch):
    # postgres backend with a bogus URL should fail without echoing the URL.
    data = [{"channel_id": "UCx", "trust_status": "trusted", "confidence_score": 0.5}]
    jf = tmp_path / "ai.json"
    jf.write_text(json.dumps(data))
    env = dict(os.environ, DATABASE_URL="postgresql://secretuser:secretpw@db.example/secretdb")
    out = subprocess.run(
        [sys.executable, str(_CLI), "--backend", "postgres", "--input", str(jf)],
        capture_output=True, text=True, cwd=str(_REPO_ROOT), env=env,
    )
    combined = out.stdout + out.stderr
    assert "secretpw" not in combined and "secretuser" not in combined
    assert "secretdb" not in combined
