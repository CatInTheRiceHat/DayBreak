"""Guard tests for the trust-source SQL operator assets (hardening pass).

These can't run against a real Postgres in CI, so they assert the *contract* of
the smoke-test script and the seed template — enough to catch drift, accidental
destructive edits, or a seed file that stopped using placeholders.
"""

from __future__ import annotations

import pathlib

MIGRATIONS = pathlib.Path(__file__).resolve().parent.parent / "migrations"
SMOKE = MIGRATIONS / "011_trusted_sources_smoke_test.sql"
SEED = MIGRATIONS / "seed_trusted_youtube_channels.example.sql"
DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs" / "trust_sources_operations.md"

TABLES = ("trusted_youtube_channels", "blocked_youtube_channels", "youtube_channel_candidates")


def test_smoke_test_file_exists_and_covers_all_three_tables():
    assert SMOKE.exists()
    sql = SMOKE.read_text().lower()
    for table in TABLES:
        assert table in sql, table


def test_smoke_test_verifies_rls_and_no_policies():
    sql = SMOKE.read_text().lower()
    assert "relrowsecurity" in sql           # RLS enabled check
    assert "pg_policies" in sql               # no-public-policy check


def test_smoke_test_checks_status_and_trust_tier_constraints():
    sql = SMOKE.read_text().lower()
    assert "check_violation" in sql
    assert "bogus_status" in sql              # invalid status rejected
    assert "not_a_tier" in sql                # invalid trust_tier rejected


def test_smoke_test_checks_approved_only_selection():
    sql = SMOKE.read_text().lower()
    assert "where status = 'approved'" in sql
    # proves candidate/rejected/disabled are excluded from ingestion selection
    for excluded in ("candidate", "rejected", "disabled"):
        assert excluded in sql


def test_smoke_test_is_non_destructive():
    sql = SMOKE.read_text().lower()
    assert "rollback" in sql                  # rolls back its test rows
    # must not contain destructive schema/data ops
    for danger in ("drop table", "truncate", "delete from", "drop schema"):
        assert danger not in sql, danger


def test_seed_template_is_placeholders_only():
    assert SEED.exists()
    sql = SEED.read_text()
    low = sql.lower()
    assert "uc_replace_me" in low                       # placeholder ids
    assert "do not run" in low                            # explicit warning
    assert "insert into public.trusted_youtube_channels" in low
    assert "'approved'" in low                            # approved examples
    assert "on conflict (channel_id) do nothing" in low   # safe to re-run


def test_ops_docs_cover_quota_and_checklist():
    assert DOCS.exists()
    doc = DOCS.read_text().lower()
    assert "max_trusted_channels_per_run" in doc
    assert "3" in doc and "quota" in doc                 # start-small + quota guidance
    assert "checklist" in doc
