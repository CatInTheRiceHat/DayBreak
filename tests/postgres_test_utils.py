"""Safety boundary and fixtures for opt-in PostgreSQL integration tests.

This module never falls back to ``DATABASE_URL``.  Its setup is destructive to
the research tables in the explicitly supplied disposable test database, so it
requires both a dedicated URL and an affirmative opt-in flag.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = (
    PROJECT_ROOT / "migrations/015_research_sessions_and_events.sql",
    PROJECT_ROOT / "migrations/016_research_feed_policies.sql",
    PROJECT_ROOT / "migrations/017_intentional_break_loop.sql",
)
OPT_IN_HELP = (
    "set TEST_POSTGRES_DATABASE_URL to a disposable test database and "
    "ALLOW_POSTGRES_INTEGRATION_TESTS=1"
)
_TEST_NAME = re.compile(r"(?:^|[_-])(test|testing|ci)(?:[_-]|$)", re.IGNORECASE)
_PRODUCTION_NAME = re.compile(r"(?:^|[_-])(prod|production|live)(?:[_-]|$)", re.IGNORECASE)
_PRODUCTION_HOST = re.compile(r"(?:^|[.-])(prod|production|live)(?:[.-]|$)", re.IGNORECASE)


class PostgresIntegrationSafetyError(RuntimeError):
    """The requested PostgreSQL target did not pass the destructive-test guard."""


@dataclass(frozen=True)
class DatabaseIdentity:
    host: str
    port: int
    database: str

    @property
    def comparable(self) -> tuple[str, int, str]:
        return (self.host.lower(), self.port, self.database.lower())

    @property
    def sanitized(self) -> str:
        return f"{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True)
class PostgresTestConfig:
    url: str
    identity: DatabaseIdentity
    unmarked_identity_override: bool


@dataclass(frozen=True)
class PostgresHarness:
    config: PostgresTestConfig
    version: str
    version_number: int
    current_user: str
    legacy: dict[str, str]
    migrations_executed: tuple[str, ...]


def postgres_skip_reason(environ: Mapping[str, str] | None = None) -> str | None:
    source = os.environ if environ is None else environ
    if not source.get("TEST_POSTGRES_DATABASE_URL"):
        return f"PostgreSQL integration suite is not configured: {OPT_IN_HELP}"
    if source.get("ALLOW_POSTGRES_INTEGRATION_TESTS") != "1":
        return (
            "PostgreSQL integration mutations are disabled: "
            "set ALLOW_POSTGRES_INTEGRATION_TESTS=1 with TEST_POSTGRES_DATABASE_URL"
        )
    return None


def _identity_from_url(url: str) -> DatabaseIdentity:
    try:
        from psycopg2.extensions import parse_dsn

        parsed = parse_dsn(url)
        host = parsed.get("host") or "localhost"
        port = int(parsed.get("port") or 5432)
        database = parsed.get("dbname") or ""
    except Exception as exc:
        raise PostgresIntegrationSafetyError(
            "TEST_POSTGRES_DATABASE_URL is not a valid PostgreSQL connection URL"
        ) from exc
    if not database:
        raise PostgresIntegrationSafetyError(
            "TEST_POSTGRES_DATABASE_URL must identify a database explicitly"
        )
    return DatabaseIdentity(host=host, port=port, database=database)


def _known_runtime_identities(source: Mapping[str, str]) -> list[tuple[str, DatabaseIdentity]]:
    identities = []
    for name in ("DATABASE_URL", "PRODUCTION_DATABASE_URL", "PILOT_DATABASE_URL"):
        value = source.get(name)
        if not value:
            continue
        try:
            identities.append((name, _identity_from_url(value)))
        except PostgresIntegrationSafetyError:
            # A malformed unrelated runtime value cannot make a safe test URL less safe.
            continue
    return identities


def load_postgres_test_config(
    environ: Mapping[str, str] | None = None,
) -> PostgresTestConfig:
    source = os.environ if environ is None else environ
    reason = postgres_skip_reason(source)
    if reason:
        raise PostgresIntegrationSafetyError(reason)

    url = source["TEST_POSTGRES_DATABASE_URL"]
    identity = _identity_from_url(url)
    for name, runtime_identity in _known_runtime_identities(source):
        if identity.comparable == runtime_identity.comparable:
            raise PostgresIntegrationSafetyError(
                f"refusing PostgreSQL integration target because it matches {name} "
                f"at {identity.sanitized}"
            )

    has_test_marker = bool(_TEST_NAME.search(identity.database))
    looks_production = bool(
        _PRODUCTION_NAME.search(identity.database) or _PRODUCTION_HOST.search(identity.host)
    )
    override = source.get("ALLOW_UNMARKED_POSTGRES_TEST_DATABASE") == "1"
    if (not has_test_marker or looks_production) and not override:
        raise PostgresIntegrationSafetyError(
            "refusing PostgreSQL integration target without an explicit test database "
            "name; use a name containing test/testing/ci, or additionally set "
            "ALLOW_UNMARKED_POSTGRES_TEST_DATABASE=1 for a verified disposable target"
        )
    return PostgresTestConfig(
        url=url,
        identity=identity,
        unmarked_identity_override=override,
    )


def connect_postgres(config: PostgresTestConfig):
    import psycopg2
    from psycopg2.extras import register_uuid

    conn = psycopg2.connect(config.url)
    register_uuid(conn_or_curs=conn)
    return conn


def _drop_research_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            DROP TABLE IF EXISTS
                public.research_session_checkouts,
                public.research_session_items,
                public.research_feed_items,
                public.research_events,
                public.research_sessions,
                public.research_participants
            CASCADE
            """
        )
    conn.commit()


def _apply_migration(conn, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def _insert_legacy_fixture(conn) -> dict[str, str]:
    from psycopg2.extras import Json

    values = {
        "participant_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "second_session_id": str(uuid.uuid4()),
        "event_zero_id": str(uuid.uuid4()),
        "event_four_id": str(uuid.uuid4()),
        "feed_request_id": str(uuid.uuid4()),
    }
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.research_participants "
            "(id, access_token_hash, assigned_condition) VALUES (%s, %s, 'balanced')",
            (values["participant_id"], f"legacy-hash-{uuid.uuid4()}"),
        )
        for session_id in (values["session_id"], values["second_session_id"]):
            cur.execute(
                """
                INSERT INTO public.research_sessions (
                    id, participant_id, feed_condition, application_version,
                    feed_policy_version, feed_seed, status
                ) VALUES (%s, %s, 'balanced', 'legacy-pilot-v0',
                          'balanced-v1', %s, 'completed')
                """,
                (session_id, values["participant_id"], f"legacy-seed-{uuid.uuid4()}"),
            )
        event_rows = (
            (values["event_zero_id"], 0, "session_started", None, {}),
            (
                values["event_four_id"],
                4,
                "post_impression",
                "legacy-post-1",
                {"legacy": True, "nested": {"source": "migration-fixture"}},
            ),
        )
        for event_id, sequence, event_type, post_id, metadata in event_rows:
            cur.execute(
                """
                INSERT INTO public.research_events (
                    id, session_id, participant_id, sequence_number, event_type,
                    post_id, content_category, feed_condition, client_timestamp, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'balanced',
                          '2026-08-01T12:00:00+00:00', %s)
                """,
                (
                    event_id,
                    values["session_id"],
                    values["participant_id"],
                    sequence,
                    event_type,
                    post_id,
                    "positive" if post_id else None,
                    Json(metadata),
                ),
            )
        cur.execute(
            """
            INSERT INTO public.research_feed_items (
                feed_request_id, session_id, participant_id, post_id, feed_position,
                content_category, feed_policy_version, selection_bucket, selection_reason
            ) VALUES (%s, %s, %s, 'legacy-post-1', 0, 'positive', 'balanced-v1',
                      'healthy', 'healthy_category_target')
            """,
            (
                values["feed_request_id"],
                values["session_id"],
                values["participant_id"],
            ),
        )
    conn.commit()
    return values


@pytest.fixture(scope="session")
def postgres_harness() -> PostgresHarness:
    config = load_postgres_test_config()
    print(f"\nPostgreSQL integration target: {config.identity.sanitized} (credentials hidden)")
    control = connect_postgres(config)
    locked = False
    try:
        with control.cursor() as cur:
            cur.execute(
                "SELECT current_database(), current_user, version(), "
                "current_setting('server_version_num')::integer"
            )
            actual_database, current_user, version, version_number = cur.fetchone()
            if str(actual_database).lower() != config.identity.database.lower():
                raise PostgresIntegrationSafetyError(
                    "connected database identity differs from the guarded URL identity"
                )
            cur.execute(
                "SELECT pg_try_advisory_lock(hashtext(%s))",
                ("daybreak-intentional-break-postgres-integration-v1",),
            )
            locked = bool(cur.fetchone()[0])
            if not locked:
                raise PostgresIntegrationSafetyError(
                    "another DayBreak PostgreSQL integration run owns the test database lock"
                )
        control.commit()
        print(f"PostgreSQL server version: {version}")

        _drop_research_tables(control)
        _apply_migration(control, MIGRATIONS[0])
        _apply_migration(control, MIGRATIONS[1])
        legacy = _insert_legacy_fixture(control)
        _apply_migration(control, MIGRATIONS[2])
        yield PostgresHarness(
            config=config,
            version=version,
            version_number=version_number,
            current_user=current_user,
            legacy=legacy,
            migrations_executed=tuple(path.name for path in MIGRATIONS),
        )
    finally:
        try:
            control.rollback()
            if locked:
                _drop_research_tables(control)
                with control.cursor() as cur:
                    cur.execute(
                        "SELECT pg_advisory_unlock(hashtext(%s))",
                        ("daybreak-intentional-break-postgres-integration-v1",),
                    )
                control.commit()
        finally:
            control.close()


@pytest.fixture
def postgres_connection(postgres_harness: PostgresHarness):
    conn = connect_postgres(postgres_harness.config)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def delete_test_participants(config: PostgresTestConfig, *participant_ids: str) -> None:
    if not participant_ids:
        return
    conn = connect_postgres(config)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.research_participants WHERE id = ANY(%s::uuid[])",
                (list(participant_ids),),
            )
        conn.commit()
    finally:
        conn.close()


def reserved_items(prefix: str, count: int = 5) -> list[dict]:
    return [
        {
            "post_id": f"{prefix}-post-{position}",
            "content_category": "positive" if position % 2 else "healthy",
            "source_type": "research_feed",
            "source_reference": f"{prefix}-source-{position}",
            "feed_policy_version": "balanced-v1",
            "selection_bucket": "healthy",
            "selection_reason": "healthy_category_target",
            "ranking_snapshot": {"score": count - position, "position": position},
            "provenance_metadata": {"fixture": prefix, "position": position},
        }
        for position in range(1, count + 1)
    ]
