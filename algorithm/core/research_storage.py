"""Storage primitives for anonymous Chrysalis research sessions.

The module supports the project's two existing backends: SQLite for local work
and PostgreSQL in production. It owns server-generated ids/timestamps, token
hashing, participant-level condition assignment, and idempotent event inserts.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone

from core.ranking.research_policies import policy_version_for_condition


FEED_CONDITIONS = ("regular", "balanced")
PARTICIPANT_STATUSES = ("active", "withdrawn", "deletion_requested")
SESSION_STATUSES = ("active", "completed", "withdrawn", "deletion_requested")

ALLOWED_EVENT_TYPES = frozenset({
    "session_started",
    "post_impression",
    "post_viewed",
    "post_liked",
    "post_unliked",
    "post_skipped",
    "post_reported",
    "break_prompt_shown",
    "break_prompt_accepted",
    "break_prompt_dismissed",
    "session_completed",
})


class ResearchStorageError(Exception):
    """Base error for a rejected research storage operation."""


class ResearchNotFoundError(ResearchStorageError):
    """Participant or session does not exist for the supplied credential."""


class ResearchConflictError(ResearchStorageError):
    """Operation conflicts with the current session state or sequence."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_access_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_access_token() -> str:
    return secrets.token_urlsafe(32)


def _placeholder(backend: str) -> str:
    return "%s" if backend == "postgres" else "?"


def _json_value(backend: str, value: dict):
    if backend == "postgres":
        from psycopg2.extras import Json
        return Json(value)
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _serialize_timestamp(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _db_timestamp(backend: str, value):
    """Use native datetimes in Postgres and explicit ISO strings in SQLite."""
    return value if backend == "postgres" else _serialize_timestamp(value)


def ensure_sqlite_research_tables(conn) -> None:
    """Create the local SQLite mirror of migrations 015 and 016."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS research_participants (
            id TEXT PRIMARY KEY,
            access_token_hash TEXT NOT NULL UNIQUE,
            assigned_condition TEXT NOT NULL CHECK (assigned_condition IN ('regular', 'balanced')),
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'withdrawn', 'deletion_requested')),
            created_at TEXT NOT NULL,
            withdrawn_at TEXT,
            deletion_requested_at TEXT
        );

        CREATE TABLE IF NOT EXISTS research_sessions (
            id TEXT PRIMARY KEY,
            participant_id TEXT NOT NULL REFERENCES research_participants(id) ON DELETE CASCADE,
            feed_condition TEXT NOT NULL CHECK (feed_condition IN ('regular', 'balanced')),
            feed_policy_version TEXT NOT NULL
                CHECK (feed_policy_version IN ('regular-v1', 'balanced-v1')),
            feed_seed TEXT NOT NULL,
            application_version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'completed', 'withdrawn', 'deletion_requested')),
            started_at TEXT NOT NULL,
            completed_at TEXT,
            withdrawn_at TEXT,
            deletion_requested_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS research_events (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
            participant_id TEXT NOT NULL REFERENCES research_participants(id) ON DELETE CASCADE,
            sequence_number INTEGER NOT NULL CHECK (sequence_number >= 0),
            event_type TEXT NOT NULL CHECK (event_type IN (
                'session_started', 'post_impression', 'post_viewed',
                'post_liked', 'post_unliked', 'post_skipped', 'post_reported',
                'break_prompt_shown', 'break_prompt_accepted',
                'break_prompt_dismissed', 'session_completed'
            )),
            post_id TEXT,
            content_category TEXT CHECK (
                content_category IS NULL OR content_category IN
                ('healthy', 'positive', 'regular', 'perspective', 'reduced',
                 'blocked', 'unknown')
            ),
            feed_condition TEXT NOT NULL CHECK (feed_condition IN ('regular', 'balanced')),
            client_timestamp TEXT NOT NULL,
            server_timestamp TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            CHECK (event_type NOT LIKE 'post_%' OR post_id IS NOT NULL),
            UNIQUE (session_id, sequence_number)
        );

        CREATE TABLE IF NOT EXISTS research_feed_items (
            id TEXT PRIMARY KEY,
            feed_request_id TEXT NOT NULL,
            session_id TEXT NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
            participant_id TEXT NOT NULL REFERENCES research_participants(id) ON DELETE CASCADE,
            post_id TEXT NOT NULL,
            feed_position INTEGER NOT NULL CHECK (feed_position >= 0),
            content_category TEXT NOT NULL CHECK (content_category IN (
                'healthy', 'positive', 'regular', 'perspective', 'reduced',
                'blocked', 'unknown'
            )),
            feed_policy_version TEXT NOT NULL
                CHECK (feed_policy_version IN ('regular-v1', 'balanced-v1')),
            selection_bucket TEXT NOT NULL
                CHECK (selection_bucket IN ('normal', 'healthy', 'diversity')),
            selection_reason TEXT NOT NULL CHECK (selection_reason IN (
                'existing_chrysalis_rank', 'normal_interest_target',
                'healthy_category_target', 'perspective_variety_target',
                'inventory_fallback'
            )),
            created_at TEXT NOT NULL,
            UNIQUE (feed_request_id, post_id),
            UNIQUE (feed_request_id, feed_position)
        );

        CREATE INDEX IF NOT EXISTS idx_research_sessions_participant_started
            ON research_sessions (participant_id, started_at DESC);
        CREATE INDEX IF NOT EXISTS idx_research_sessions_condition_status
            ON research_sessions (feed_condition, status);
        CREATE INDEX IF NOT EXISTS idx_research_events_session_sequence
            ON research_events (session_id, sequence_number);
        CREATE INDEX IF NOT EXISTS idx_research_events_type_server_time
            ON research_events (event_type, server_timestamp);
        CREATE INDEX IF NOT EXISTS idx_research_events_post
            ON research_events (post_id) WHERE post_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_research_feed_items_session_created
            ON research_feed_items (session_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_research_feed_items_session_post
            ON research_feed_items (session_id, post_id);
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(research_sessions)")}
    if "feed_policy_version" not in columns:
        conn.execute("ALTER TABLE research_sessions ADD COLUMN feed_policy_version TEXT")
    if "feed_seed" not in columns:
        conn.execute("ALTER TABLE research_sessions ADD COLUMN feed_seed TEXT")
    conn.execute(
        "UPDATE research_sessions SET feed_policy_version = CASE feed_condition "
        "WHEN 'regular' THEN 'regular-v1' ELSE 'balanced-v1' END "
        "WHERE feed_policy_version IS NULL"
    )
    conn.execute(
        "UPDATE research_sessions SET feed_seed = lower(hex(randomblob(24))) "
        "WHERE feed_seed IS NULL"
    )
    conn.commit()


def create_participant(conn, *, backend: str, condition: str | None = None) -> dict:
    """Create one anonymous participant and return its one-time bearer token."""
    assigned = condition or secrets.choice(FEED_CONDITIONS)
    if assigned not in FEED_CONDITIONS:
        raise ValueError("Unsupported feed condition")

    participant_id = str(uuid.uuid4())
    access_token = generate_access_token()
    created_at = utc_now()
    ph = _placeholder(backend)
    conn.cursor().execute(
        f"INSERT INTO research_participants "
        f"(id, access_token_hash, assigned_condition, status, created_at) "
        f"VALUES ({ph}, {ph}, {ph}, 'active', {ph})",
        (participant_id, hash_access_token(access_token), assigned, _db_timestamp(backend, created_at)),
    )
    conn.commit()
    return {
        "participant_id": participant_id,
        "access_token": access_token,
        "assigned_condition": assigned,
        "status": "active",
        "created_at": created_at.isoformat(),
    }


def authenticate_participant(conn, *, backend: str, access_token: str) -> dict:
    if not access_token:
        raise ResearchNotFoundError("Missing participant credential")
    ph = _placeholder(backend)
    cur = conn.cursor()
    cur.execute(
        f"SELECT id, assigned_condition, status, created_at "
        f"FROM research_participants WHERE access_token_hash = {ph}",
        (hash_access_token(access_token),),
    )
    row = cur.fetchone()
    if row is None:
        raise ResearchNotFoundError("Unknown participant credential")
    return {
        "participant_id": str(row[0]),
        "assigned_condition": row[1],
        "status": row[2],
        "created_at": _serialize_timestamp(row[3]),
    }


def start_session(
    conn,
    *,
    backend: str,
    participant: dict,
    application_version: str,
    client_timestamp: datetime,
) -> dict:
    if participant["status"] != "active":
        raise ResearchConflictError("Participant is not active")

    session_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    started_at = utc_now()
    condition = participant["assigned_condition"]
    policy_version = policy_version_for_condition(condition)
    feed_seed = secrets.token_urlsafe(24)
    participant_id = participant["participant_id"]
    ph = _placeholder(backend)
    cur = conn.cursor()
    try:
        cur.execute(
            f"INSERT INTO research_sessions "
            f"(id, participant_id, feed_condition, feed_policy_version, feed_seed, "
            f"application_version, status, started_at, created_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'active', {ph}, {ph})",
            (
                session_id,
                participant_id,
                condition,
                policy_version,
                feed_seed,
                application_version,
                _db_timestamp(backend, started_at),
                _db_timestamp(backend, started_at),
            ),
        )
        cur.execute(
            f"INSERT INTO research_events "
            f"(id, session_id, participant_id, sequence_number, event_type, post_id, "
            f"content_category, feed_condition, client_timestamp, server_timestamp, metadata) "
            f"VALUES ({ph}, {ph}, {ph}, 0, 'session_started', NULL, NULL, {ph}, {ph}, {ph}, {ph})",
            (
                event_id,
                session_id,
                participant_id,
                condition,
                _db_timestamp(backend, client_timestamp),
                _db_timestamp(backend, started_at),
                _json_value(backend, {
                    "application_version": application_version,
                    "feed_policy_version": policy_version,
                }),
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "session_id": session_id,
        "participant_id": participant_id,
        "feed_condition": condition,
        "feed_policy_version": policy_version,
        "application_version": application_version,
        "status": "active",
        "started_at": started_at.isoformat(),
        "completed_at": None,
        "session_started_event_id": event_id,
        "next_sequence_number": 1,
    }


def get_session(conn, *, backend: str, participant_id: str, session_id: str) -> dict:
    ph = _placeholder(backend)
    cur = conn.cursor()
    cur.execute(
        f"SELECT id, participant_id, feed_condition, feed_policy_version, application_version, status, "
        f"started_at, completed_at, withdrawn_at, deletion_requested_at "
        f"FROM research_sessions WHERE id = {ph} AND participant_id = {ph}",
        (session_id, participant_id),
    )
    row = cur.fetchone()
    if row is None:
        raise ResearchNotFoundError("Research session not found")
    return {
        "session_id": str(row[0]),
        "participant_id": str(row[1]),
        "feed_condition": row[2],
        "feed_policy_version": row[3],
        "application_version": row[4],
        "status": row[5],
        "started_at": _serialize_timestamp(row[6]),
        "completed_at": _serialize_timestamp(row[7]),
        "withdrawn_at": _serialize_timestamp(row[8]),
        "deletion_requested_at": _serialize_timestamp(row[9]),
    }


def get_feed_session(conn, *, backend: str, participant_id: str, session_id: str) -> dict:
    """Return public session fields plus the private server-only feed seed."""
    session = get_session(
        conn,
        backend=backend,
        participant_id=participant_id,
        session_id=session_id,
    )
    ph = _placeholder(backend)
    cur = conn.cursor()
    cur.execute(
        f"SELECT feed_seed FROM research_sessions WHERE id = {ph} AND participant_id = {ph}",
        (session_id, participant_id),
    )
    row = cur.fetchone()
    if row is None or not row[0]:
        raise ResearchNotFoundError("Research session feed policy is unavailable")
    return {**session, "feed_seed": row[0]}


def record_feed_items(
    conn,
    *,
    backend: str,
    participant_id: str,
    session_id: str,
    feed_request_id: str,
    items: list[dict],
) -> None:
    """Persist authoritative provenance for one issued research feed window."""
    created_at = utc_now()
    ph = _placeholder(backend)
    cur = conn.cursor()
    try:
        for item in items:
            cur.execute(
                f"INSERT INTO research_feed_items "
                f"(id, feed_request_id, session_id, participant_id, post_id, feed_position, "
                f"content_category, feed_policy_version, selection_bucket, selection_reason, created_at) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                (
                    str(uuid.uuid4()),
                    feed_request_id,
                    session_id,
                    participant_id,
                    str(item["post_id"]),
                    int(item["feed_position"]),
                    item.get("content_category") or "unknown",
                    item["feed_policy_version"],
                    item["selection_bucket"],
                    item["selection_reason"],
                    _db_timestamp(backend, created_at),
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _issued_post_provenance(
    conn,
    *,
    backend: str,
    participant_id: str,
    session_id: str,
    feed_request_id: str,
    post_id: str,
) -> dict:
    ph = _placeholder(backend)
    cur = conn.cursor()
    cur.execute(
        f"SELECT feed_position, content_category, feed_policy_version, "
        f"selection_bucket, selection_reason FROM research_feed_items "
        f"WHERE feed_request_id = {ph} AND session_id = {ph} "
        f"AND participant_id = {ph} AND post_id = {ph}",
        (feed_request_id, session_id, participant_id, post_id),
    )
    row = cur.fetchone()
    if row is None:
        raise ResearchConflictError("Post provenance does not match an issued research feed item")
    return {
        "feed_request_id": feed_request_id,
        "feed_position": int(row[0]),
        "content_category": row[1],
        "feed_policy_version": row[2],
        "selection_bucket": row[3],
        "selection_reason": row[4],
    }


def _event_with_server_provenance(
    conn,
    *,
    backend: str,
    participant_id: str,
    session_id: str,
    event: dict,
) -> dict:
    if not str(event.get("event_type") or "").startswith("post_"):
        return event
    metadata = dict(event.get("metadata") or {})
    feed_request_id = str(metadata.get("feed_request_id") or "")
    if not feed_request_id:
        raise ResearchConflictError("Issued feed provenance is required for post events")
    provenance = _issued_post_provenance(
        conn,
        backend=backend,
        participant_id=participant_id,
        session_id=session_id,
        feed_request_id=feed_request_id,
        post_id=str(event.get("post_id") or ""),
    )
    metadata.update({
        "feed_request_id": provenance["feed_request_id"],
        "feed_position": provenance["feed_position"],
        "feed_policy_version": provenance["feed_policy_version"],
        "selection_bucket": provenance["selection_bucket"],
        "selection_reason": provenance["selection_reason"],
    })
    return {
        **event,
        "content_category": provenance["content_category"],
        "metadata": metadata,
    }


def _event_exists(conn, *, backend: str, event_id: str) -> bool:
    ph = _placeholder(backend)
    cur = conn.cursor()
    cur.execute(f"SELECT 1 FROM research_events WHERE id = {ph}", (event_id,))
    return cur.fetchone() is not None


def insert_event_batch(
    conn,
    *,
    backend: str,
    participant_id: str,
    session_id: str,
    events: list[dict],
) -> dict:
    session = get_session(
        conn,
        backend=backend,
        participant_id=participant_id,
        session_id=session_id,
    )
    if session["status"] != "active":
        raise ResearchConflictError("Research session is not active")

    ph = _placeholder(backend)
    accepted: list[dict] = []
    duplicates: list[str] = []
    cur = conn.cursor()
    try:
        for event in events:
            event = _event_with_server_provenance(
                conn,
                backend=backend,
                participant_id=participant_id,
                session_id=session_id,
                event=event,
            )
            event_id = str(event["event_id"])
            server_timestamp = utc_now()
            cur.execute(
                f"INSERT INTO research_events "
                f"(id, session_id, participant_id, sequence_number, event_type, post_id, "
                f"content_category, feed_condition, client_timestamp, server_timestamp, metadata) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}) "
                f"ON CONFLICT (id) DO NOTHING",
                (
                    event_id,
                    session_id,
                    participant_id,
                    int(event["sequence_number"]),
                    event["event_type"],
                    event.get("post_id"),
                    event.get("content_category"),
                    session["feed_condition"],
                    _db_timestamp(backend, event["client_timestamp"]),
                    _db_timestamp(backend, server_timestamp),
                    _json_value(backend, event.get("metadata") or {}),
                ),
            )
            if cur.rowcount == 0:
                duplicates.append(event_id)
                continue
            accepted.append({
                "event_id": event_id,
                "server_timestamp": server_timestamp.isoformat(),
            })
        conn.commit()
    except Exception as exc:
        conn.rollback()
        message = str(exc).lower()
        if "sequence" in message or "unique" in message:
            raise ResearchConflictError("Event sequence number already exists") from exc
        raise

    return {"accepted": accepted, "duplicates": duplicates}


def complete_session(
    conn,
    *,
    backend: str,
    participant_id: str,
    session_id: str,
    event: dict,
) -> dict:
    session = get_session(
        conn,
        backend=backend,
        participant_id=participant_id,
        session_id=session_id,
    )
    event_id = str(event["event_id"])
    if session["status"] == "completed":
        if _event_exists(conn, backend=backend, event_id=event_id):
            return {**session, "duplicate": True}
        raise ResearchConflictError("Research session is already completed")
    if session["status"] != "active":
        raise ResearchConflictError("Research session is not active")

    completed_at = utc_now()
    ph = _placeholder(backend)
    cur = conn.cursor()
    try:
        cur.execute(
            f"INSERT INTO research_events "
            f"(id, session_id, participant_id, sequence_number, event_type, post_id, "
            f"content_category, feed_condition, client_timestamp, server_timestamp, metadata) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, 'session_completed', NULL, NULL, {ph}, {ph}, {ph}, {ph})",
            (
                event_id,
                session_id,
                participant_id,
                int(event["sequence_number"]),
                session["feed_condition"],
                _db_timestamp(backend, event["client_timestamp"]),
                _db_timestamp(backend, completed_at),
                _json_value(backend, event.get("metadata") or {}),
            ),
        )
        cur.execute(
            f"UPDATE research_sessions SET status = 'completed', completed_at = {ph} "
            f"WHERE id = {ph} AND participant_id = {ph} AND status = 'active'",
            (_db_timestamp(backend, completed_at), session_id, participant_id),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        message = str(exc).lower()
        if "sequence" in message or "unique" in message:
            raise ResearchConflictError("Completion event conflicts with an existing event") from exc
        raise

    return {
        **session,
        "status": "completed",
        "completed_at": completed_at.isoformat(),
        "duplicate": False,
    }
