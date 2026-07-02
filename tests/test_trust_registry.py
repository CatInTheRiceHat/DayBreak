"""Tests for the trust-source registry: trusted channels, blocked channels, and
the candidate review queue (Parts A/B/C), sqlite-backed for the local demo.

Core principle under test: AI does not decide trust. Only rows a human has set to
status='approved' are eligible for ingestion; candidates and rejected/disabled
rows are not; blocked channels are tracked separately.
"""

from __future__ import annotations

import sqlite3

from core.trust_registry import (
    BLOCKED_REASONS,
    CANDIDATE_REVIEW_STATUSES,
    TRUST_TIERS,
    TRUSTED_SOURCE_GROUPS,
    TRUSTED_STATUSES,
    add_channel_candidate_sqlite,
    block_channel_sqlite,
    ensure_trust_tables_sqlite,
    load_approved_trusted_channels,
    load_approved_trusted_channels_postgres,
    load_blocked_channel_ids,
    load_blocked_channel_ids_postgres,
    load_channel_candidates,
    upsert_trusted_channel_sqlite,
)


# ── Minimal psycopg-style fakes (no real Postgres in the test env) ───────────

class _FakePGCursor:
    def __init__(self, rows, *, missing=False):
        self._rows = rows
        self._missing = missing

    def execute(self, sql, params=None):
        if self._missing:
            raise RuntimeError('relation "trusted_youtube_channels" does not exist')

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _FakePGConn:
    def __init__(self, rows=(), *, missing=False):
        self._rows = list(rows)
        self._missing = missing
        self.rolled_back = False

    def cursor(self):
        return _FakePGCursor(self._rows, missing=self._missing)

    def rollback(self):
        self.rolled_back = True


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_ensure_creates_all_three_tables():
    conn = _conn()
    ensure_trust_tables_sqlite(conn)
    names = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"trusted_youtube_channels", "blocked_youtube_channels",
            "youtube_channel_candidates"} <= names


def test_load_approved_returns_only_approved_channels():
    conn = _conn()
    ensure_trust_tables_sqlite(conn)
    upsert_trusted_channel_sqlite(conn, channel_id="UC_app", channel_title="Approved News",
                                  source_group="trusted/news", trust_tier="institutional",
                                  status="approved", approved_by="elaine")
    upsert_trusted_channel_sqlite(conn, channel_id="UC_cand", channel_title="Pending",
                                  source_group="trusted/science", trust_tier="candidate",
                                  status="candidate")
    upsert_trusted_channel_sqlite(conn, channel_id="UC_rej", channel_title="Rejected",
                                  source_group="trusted/news", trust_tier="experimental",
                                  status="rejected")
    upsert_trusted_channel_sqlite(conn, channel_id="UC_dis", channel_title="Disabled",
                                  source_group="trusted/news", trust_tier="institutional",
                                  status="disabled")

    approved = load_approved_trusted_channels(conn)
    ids = {c.channel_id for c in approved}
    assert ids == {"UC_app"}
    assert approved[0].source_group == "trusted/news"
    assert approved[0].trust_tier == "institutional"


def test_load_blocked_channel_ids():
    conn = _conn()
    ensure_trust_tables_sqlite(conn)
    block_channel_sqlite(conn, channel_id="UC_bad", channel_title="Rage Central",
                         reason="ragebait", blocked_by="elaine")
    block_channel_sqlite(conn, channel_id="UC_spam", channel_title="Repost Farm",
                         reason="spam_or_repost", blocked_by="elaine")
    assert load_blocked_channel_ids(conn) == {"UC_bad", "UC_spam"}


def test_candidates_are_queued_but_not_a_source_of_approved_channels():
    conn = _conn()
    ensure_trust_tables_sqlite(conn)
    add_channel_candidate_sqlite(conn, channel_id="UC_new", channel_title="Maybe Good",
                                 suggested_source_group="trusted/education",
                                 discovery_source="search_lane", review_status="new")
    # Candidate is visible in the review queue…
    cands = load_channel_candidates(conn)
    assert {c["channel_id"] for c in cands} == {"UC_new"}
    # …but is NOT returned as an approved trusted channel (no auto-promotion).
    assert load_approved_trusted_channels(conn) == []


def test_empty_or_missing_tables_do_not_crash():
    # Fresh connection, trust tables never created → loaders return empties.
    conn = _conn()
    assert load_approved_trusted_channels(conn) == []
    assert load_blocked_channel_ids(conn) == set()
    assert load_channel_candidates(conn) == []


def test_postgres_loaders_graceful_when_tables_missing():
    # Production may not have run migration 011 yet — loaders must degrade to
    # empty (and roll back the aborted txn), never crash the cron (Part G).
    conn = _FakePGConn(missing=True)
    assert load_approved_trusted_channels_postgres(conn) == []
    assert conn.rolled_back
    conn2 = _FakePGConn(missing=True)
    assert load_blocked_channel_ids_postgres(conn2) == set()
    assert conn2.rolled_back


def test_postgres_loader_parses_approved_rows():
    # Row order matches the loader's SELECT:
    # channel_id, channel_title, channel_handle, channel_url,
    # source_group, trust_tier, status, notes, risk_notes
    rows = [("UC_a", "Approved News", "@news", "https://x", "trusted/news",
             "institutional", "approved", None, None)]
    channels = load_approved_trusted_channels_postgres(_FakePGConn(rows))
    assert len(channels) == 1
    assert channels[0].channel_id == "UC_a"
    assert channels[0].source_group == "trusted/news"
    assert channels[0].trust_tier == "institutional"


def test_postgres_blocked_loader_returns_id_set():
    rows = [("UC_bad",), ("UC_spam",)]
    assert load_blocked_channel_ids_postgres(_FakePGConn(rows)) == {"UC_bad", "UC_spam"}


def test_migration_011_defines_all_three_tables_and_gating():
    import pathlib

    sql = (pathlib.Path(__file__).resolve().parent.parent
           / "migrations" / "011_trusted_sources.sql").read_text().lower()
    # All three tables present…
    for table in ("trusted_youtube_channels", "blocked_youtube_channels",
                  "youtube_channel_candidates"):
        assert f"create table if not exists public.{table}" in sql
    # …the columns ingestion depends on…
    for col in ("channel_id", "source_group", "trust_tier", "status", "reason",
                "review_status"):
        assert col in sql
    # …the approved-status gate + review-status vocab are enforced.
    assert "'approved'" in sql and "'rejected'" in sql
    assert "'new'" in sql and "'stale'" in sql
    # operator-only: RLS enabled on every table
    assert sql.count("enable row level security") == 3
    # hardening: trust_tier CHECK + idempotent updated_at trigger on all 3 tables
    assert "trusted_trust_tier_chk" in sql
    assert "set_updated_at" in sql
    assert sql.count("drop trigger if exists") == 3


def test_recommended_constant_values_present():
    assert "trusted/news" in TRUSTED_SOURCE_GROUPS
    assert "trusted/mental_health" in TRUSTED_SOURCE_GROUPS
    assert {"institutional", "established_creator", "candidate", "experimental"} <= set(TRUST_TIERS)
    assert {"candidate", "approved", "rejected", "needs_review", "disabled"} <= set(TRUSTED_STATUSES)
    assert {"foreign_language_leak", "ragebait", "misinformation", "manual_block"} <= set(BLOCKED_REASONS)
    assert {"new", "needs_review", "approved", "rejected", "stale"} <= set(CANDIDATE_REVIEW_STATUSES)
