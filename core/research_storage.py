"""Storage primitives for anonymous Chrysalis research sessions.

The module supports the project's two existing backends: SQLite for local work
and PostgreSQL in production. It owns server-generated ids/timestamps, token
hashing, participant-level condition assignment, and idempotent event inserts.
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
import uuid
from datetime import datetime, timedelta, timezone

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

INTENTIONAL_BREAK_VERSION = "intentional_break_v1"
INTENTIONAL_BREAK_POLICY_VERSION = "balanced-v1"
INTENTIONAL_BREAK_PLAN_VERSION = "intentional-break-plan-v1"
INTENTIONAL_BREAK_STATES = frozenset({
    "planned", "active", "checkout", "cooldown", "completed", "cancelled",
})
INTENTIONAL_BREAK_NONTERMINAL_STATES = (
    "planned", "active", "checkout", "cooldown",
)
INTENTIONAL_BREAK_INTENTIONS = frozenset({
    "relax", "learn", "inspired", "catch_up", "quick_break",
})
INTENTIONAL_BREAK_VIDEO_COUNTS = frozenset({5, 10, 20, 40})
INTENTIONAL_BREAK_WORTHWHILE_VALUES = frozenset({
    "yes", "mostly", "not_really", "prefer_not_to_answer",
})
INTENTIONAL_BREAK_CONTROL_VALUES = frozenset({
    1, 2, 3, 4, 5, "prefer_not_to_answer",
})
INTENTIONAL_BREAK_MOOD_VALUES = frozenset({
    "better", "same", "worse", "prefer_not_to_answer",
})
INTENTIONAL_BREAK_OVERRIDE_REASONS = frozenset({
    "change_plan", "opened_automatically", "want_another_session", "other",
})
INTENTIONAL_BREAK_CONTENT_CATEGORIES = frozenset({
    "healthy", "positive", "regular", "perspective", "reduced", "blocked", "unknown",
})
INTENTIONAL_BREAK_SELECTION_BUCKETS = frozenset({"normal", "healthy", "diversity"})
INTENTIONAL_BREAK_SELECTION_REASONS = frozenset({
    "existing_chrysalis_rank",
    "normal_interest_target",
    "healthy_category_target",
    "perspective_variety_target",
    "inventory_fallback",
})
INTENTIONAL_BREAK_CLIENT_EVENT_TYPES = frozenset({
    "post_impression",
    "post_viewed",
    "post_liked",
    "post_unliked",
    "post_skipped",
    "post_reported",
    "break_prompt_shown",
    "break_prompt_accepted",
    "break_prompt_dismissed",
})
INTENTIONAL_BREAK_POST_EVENT_TYPES = frozenset(
    event_type
    for event_type in INTENTIONAL_BREAK_CLIENT_EVENT_TYPES
    if event_type.startswith("post_")
)
INTENTIONAL_BREAK_ERROR_CODES = frozenset({
    "participant_not_found",
    "participant_inactive",
    "session_not_found",
    "session_not_owned",
    "existing_nonterminal_session",
    "invalid_transition",
    "invalid_plan",
    "invalid_reserved_batch",
    "event_not_allowed",
    "event_provenance_invalid",
    "checkout_invalid",
    "cooldown_not_ready",
    "override_not_started",
    "override_pause_active",
    "idempotency_conflict",
})


class ResearchStorageError(Exception):
    """Base error for a rejected research storage operation."""


class ResearchNotFoundError(ResearchStorageError):
    """Participant or session does not exist for the supplied credential."""


class ResearchConflictError(ResearchStorageError):
    """Operation conflicts with the current session state or sequence."""


class IntentionalBreakStorageError(ResearchStorageError):
    """Stable, API-mappable rejection from the intentional-break storage path."""

    def __init__(self, code: str, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.error_code = code
        self.details = details or {}


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


def _sqlite_columns(conn, table_name: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def _sqlite_add_column(conn, table_name: str, column_name: str, definition: str) -> None:
    if column_name not in _sqlite_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _create_sqlite_research_events_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE research_events (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
            participant_id TEXT NOT NULL REFERENCES research_participants(id) ON DELETE CASCADE,
            sequence_number INTEGER NOT NULL CHECK (sequence_number >= 0),
            server_sequence_number INTEGER CHECK (
                server_sequence_number IS NULL OR server_sequence_number >= 0
            ),
            client_event_id TEXT,
            client_sequence_number INTEGER CHECK (
                client_sequence_number IS NULL OR client_sequence_number >= 0
            ),
            event_type TEXT NOT NULL CHECK (event_type IN (
                'session_plan_created', 'session_started',
                'session_finished_early', 'session_boundary_reached',
                'checkout_submitted', 'cooldown_started', 'cooldown_completed',
                'cooldown_override_started', 'cooldown_overridden',
                'session_cancelled', 'post_impression', 'post_viewed',
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
            client_timestamp TEXT,
            server_timestamp TEXT NOT NULL,
            received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            event_authority TEXT CHECK (
                event_authority IS NULL OR event_authority IN ('server', 'client')
            ),
            metadata TEXT NOT NULL DEFAULT '{}',
            CHECK (event_type NOT LIKE 'post_%' OR post_id IS NOT NULL),
            UNIQUE (session_id, sequence_number)
        )
        """
    )


def _upgrade_sqlite_research_events(conn) -> None:
    """Rebuild the leaf event table to widen its event-type check safely."""
    if "server_sequence_number" in _sqlite_columns(conn, "research_events"):
        return

    conn.commit()
    try:
        conn.execute("BEGIN")
        conn.execute("ALTER TABLE research_events RENAME TO research_events_legacy_017")
        _create_sqlite_research_events_table(conn)
        conn.execute(
            """
            INSERT INTO research_events (
                id, session_id, participant_id, sequence_number,
                server_sequence_number, client_event_id, client_sequence_number,
                event_type, post_id, content_category, feed_condition,
                client_timestamp, server_timestamp, received_at, event_authority,
                metadata
            )
            SELECT
                id, session_id, participant_id, sequence_number,
                sequence_number, NULL, NULL,
                event_type, post_id, content_category, feed_condition,
                client_timestamp, server_timestamp, server_timestamp, NULL,
                metadata
            FROM research_events_legacy_017
            """
        )
        conn.execute("DROP TABLE research_events_legacy_017")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def ensure_sqlite_research_tables(conn) -> None:
    """Create or upgrade the local SQLite mirror of migrations 015 through 017."""
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
            created_at TEXT NOT NULL,
            journey_version TEXT CHECK (
                journey_version IS NULL OR (
                    journey_version = 'intentional_break_v1'
                    AND feed_condition = 'balanced'
                    AND feed_policy_version IS NOT NULL
                    AND feed_policy_version = 'balanced-v1'
                )
            ),
            journey_state TEXT CHECK (
                journey_version IS NULL OR (
                    journey_state IS NOT NULL AND journey_state IN
                    ('planned', 'active', 'checkout', 'cooldown', 'completed', 'cancelled')
                )
            ),
            intention TEXT CHECK (
                journey_version IS NULL OR (
                    intention IS NOT NULL AND intention IN
                    ('relax', 'learn', 'inspired', 'catch_up', 'quick_break')
                )
            ),
            planned_video_count INTEGER CHECK (
                journey_version IS NULL OR (
                    planned_video_count IS NOT NULL AND planned_video_count IN (5, 10, 20, 40)
                )
            ),
            estimated_duration_seconds INTEGER CHECK (
                journey_version IS NULL OR (
                    estimated_duration_seconds IS NOT NULL
                    AND estimated_duration_seconds = planned_video_count * 30
                )
            ),
            suggested_cooldown_seconds INTEGER CHECK (
                journey_version IS NULL OR (
                    suggested_cooldown_seconds IS NOT NULL
                    AND suggested_cooldown_seconds BETWEEN 300 AND 7200
                    AND suggested_cooldown_seconds % 300 = 0
                    AND suggested_cooldown_seconds = planned_video_count * 60
                )
            ),
            selected_cooldown_seconds INTEGER CHECK (
                selected_cooldown_seconds IS NULL OR (
                    selected_cooldown_seconds BETWEEN 300 AND 7200
                    AND selected_cooldown_seconds % 300 = 0
                )
            ),
            plan_version TEXT CHECK (
                journey_version IS NULL OR (plan_version IS NOT NULL AND length(plan_version) > 0)
            ),
            plan_created_at TEXT CHECK (
                journey_version IS NULL OR plan_created_at IS NOT NULL
            ),
            session_started_at TEXT,
            finish_reason TEXT CHECK (
                finish_reason IS NULL OR finish_reason IN ('boundary_reached', 'finished_early')
            ),
            highest_reached_position INTEGER CHECK (
                journey_version IS NULL OR (
                    highest_reached_position IS NOT NULL
                    AND highest_reached_position BETWEEN 0 AND planned_video_count
                )
            ),
            boundary_reached_at TEXT,
            checkout_entered_at TEXT,
            cooldown_started_at TEXT,
            cooldown_ends_at TEXT CHECK (
                cooldown_started_at IS NULL OR cooldown_ends_at IS NULL
                OR (
                    julianday(cooldown_started_at) IS NOT NULL
                    AND julianday(cooldown_ends_at) IS NOT NULL
                    AND julianday(cooldown_ends_at) >= julianday(cooldown_started_at)
                )
            ),
            cooldown_outcome TEXT CHECK (
                cooldown_outcome IS NULL OR cooldown_outcome IN ('completed', 'overridden')
            ),
            cooldown_completed_at TEXT,
            override_started_at TEXT,
            override_available_at TEXT CHECK (
                override_started_at IS NULL OR override_available_at IS NULL
                OR (
                    julianday(override_started_at) IS NOT NULL
                    AND julianday(override_available_at) IS NOT NULL
                    AND julianday(override_available_at) >= julianday(override_started_at)
                )
            ),
            override_reason TEXT CHECK (
                override_reason IS NULL OR override_reason IN (
                    'change_plan', 'opened_automatically', 'want_another_session', 'other'
                )
            ),
            previous_session_id TEXT REFERENCES research_sessions(id) ON DELETE SET NULL,
            cancelled_at TEXT,
            next_server_sequence_number INTEGER NOT NULL DEFAULT 0
                CHECK (next_server_sequence_number >= 0),
            retain_until TEXT
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

        """
    )
    _sqlite_add_column(conn, "research_sessions", "feed_policy_version", "TEXT")
    _sqlite_add_column(conn, "research_sessions", "feed_seed", "TEXT")
    conn.execute(
        "UPDATE research_sessions SET feed_policy_version = CASE feed_condition "
        "WHEN 'regular' THEN 'regular-v1' ELSE 'balanced-v1' END "
        "WHERE feed_policy_version IS NULL"
    )
    conn.execute(
        "UPDATE research_sessions SET feed_seed = lower(hex(randomblob(24))) "
        "WHERE feed_seed IS NULL"
    )

    session_columns = {
        "journey_version": """TEXT CHECK (
            journey_version IS NULL OR (
                journey_version = 'intentional_break_v1'
                AND feed_condition = 'balanced'
                AND feed_policy_version IS NOT NULL
                AND feed_policy_version = 'balanced-v1'
            )
        )""",
        "journey_state": """TEXT CHECK (
            journey_version IS NULL OR (
                journey_state IS NOT NULL AND journey_state IN
                ('planned', 'active', 'checkout', 'cooldown', 'completed', 'cancelled')
            )
        )""",
        "intention": """TEXT CHECK (
            journey_version IS NULL OR (
                intention IS NOT NULL AND intention IN
                ('relax', 'learn', 'inspired', 'catch_up', 'quick_break')
            )
        )""",
        "planned_video_count": """INTEGER CHECK (
            journey_version IS NULL OR (
                planned_video_count IS NOT NULL AND planned_video_count IN (5, 10, 20, 40)
            )
        )""",
        "estimated_duration_seconds": """INTEGER CHECK (
            journey_version IS NULL OR (
                estimated_duration_seconds IS NOT NULL
                AND estimated_duration_seconds = planned_video_count * 30
            )
        )""",
        "suggested_cooldown_seconds": """INTEGER CHECK (
            journey_version IS NULL OR (
                suggested_cooldown_seconds IS NOT NULL
                AND suggested_cooldown_seconds BETWEEN 300 AND 7200
                AND suggested_cooldown_seconds % 300 = 0
                AND suggested_cooldown_seconds = planned_video_count * 60
            )
        )""",
        "selected_cooldown_seconds": """INTEGER CHECK (
            selected_cooldown_seconds IS NULL OR (
                selected_cooldown_seconds BETWEEN 300 AND 7200
                AND selected_cooldown_seconds % 300 = 0
            )
        )""",
        "plan_version": """TEXT CHECK (
            journey_version IS NULL OR (plan_version IS NOT NULL AND length(plan_version) > 0)
        )""",
        "plan_created_at": "TEXT CHECK (journey_version IS NULL OR plan_created_at IS NOT NULL)",
        "session_started_at": "TEXT",
        "finish_reason": """TEXT CHECK (
            finish_reason IS NULL OR finish_reason IN ('boundary_reached', 'finished_early')
        )""",
        "highest_reached_position": """INTEGER CHECK (
            journey_version IS NULL OR (
                highest_reached_position IS NOT NULL
                AND highest_reached_position BETWEEN 0 AND planned_video_count
            )
        )""",
        "boundary_reached_at": "TEXT",
        "checkout_entered_at": "TEXT",
        "cooldown_started_at": "TEXT",
        "cooldown_ends_at": """TEXT CHECK (
            cooldown_started_at IS NULL OR cooldown_ends_at IS NULL
            OR (
                julianday(cooldown_started_at) IS NOT NULL
                AND julianday(cooldown_ends_at) IS NOT NULL
                AND julianday(cooldown_ends_at) >= julianday(cooldown_started_at)
            )
        )""",
        "cooldown_outcome": """TEXT CHECK (
            cooldown_outcome IS NULL OR cooldown_outcome IN ('completed', 'overridden')
        )""",
        "cooldown_completed_at": "TEXT",
        "override_started_at": "TEXT",
        "override_available_at": """TEXT CHECK (
            override_started_at IS NULL OR override_available_at IS NULL
            OR (
                julianday(override_started_at) IS NOT NULL
                AND julianday(override_available_at) IS NOT NULL
                AND julianday(override_available_at) >= julianday(override_started_at)
            )
        )""",
        "override_reason": """TEXT CHECK (
            override_reason IS NULL OR override_reason IN (
                'change_plan', 'opened_automatically', 'want_another_session', 'other'
            )
        )""",
        "previous_session_id": "TEXT REFERENCES research_sessions(id) ON DELETE SET NULL",
        "cancelled_at": "TEXT",
        "next_server_sequence_number": (
            "INTEGER NOT NULL DEFAULT 0 CHECK (next_server_sequence_number >= 0)"
        ),
        "retain_until": "TEXT",
    }
    for column_name, definition in session_columns.items():
        _sqlite_add_column(conn, "research_sessions", column_name, definition)

    conn.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_research_sessions_id_participant_unique
            ON research_sessions (id, participant_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_research_sessions_one_nonterminal_intentional_break
            ON research_sessions (participant_id)
            WHERE journey_version = 'intentional_break_v1'
              AND journey_state IN ('planned', 'active', 'checkout', 'cooldown');
        CREATE INDEX IF NOT EXISTS idx_research_sessions_previous_session
            ON research_sessions (previous_session_id) WHERE previous_session_id IS NOT NULL;

        CREATE TABLE IF NOT EXISTS research_session_items (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            participant_id TEXT NOT NULL REFERENCES research_participants(id) ON DELETE CASCADE,
            post_id TEXT NOT NULL,
            session_position INTEGER NOT NULL CHECK (session_position >= 1),
            content_category TEXT NOT NULL CHECK (content_category IN (
                'healthy', 'positive', 'regular', 'perspective', 'reduced',
                'blocked', 'unknown'
            )),
            feed_policy_version TEXT NOT NULL CHECK (feed_policy_version = 'balanced-v1'),
            selection_bucket TEXT NOT NULL
                CHECK (selection_bucket IN ('normal', 'healthy', 'diversity')),
            selection_reason TEXT NOT NULL CHECK (selection_reason IN (
                'existing_chrysalis_rank', 'normal_interest_target',
                'healthy_category_target', 'perspective_variety_target',
                'inventory_fallback'
            )),
            ranking_snapshot TEXT NOT NULL DEFAULT '{}',
            provenance_metadata TEXT NOT NULL DEFAULT '{}',
            reserved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            first_issued_at TEXT,
            first_impressed_at TEXT,
            first_viewed_at TEXT,
            FOREIGN KEY (session_id, participant_id)
                REFERENCES research_sessions(id, participant_id) ON DELETE CASCADE,
            UNIQUE (session_id, session_position),
            UNIQUE (session_id, post_id)
        );

        CREATE INDEX IF NOT EXISTS idx_research_session_items_participant_session
            ON research_session_items (participant_id, session_id);

        CREATE TABLE IF NOT EXISTS research_session_checkouts (
            session_id TEXT PRIMARY KEY,
            participant_id TEXT NOT NULL REFERENCES research_participants(id) ON DELETE CASCADE,
            worthwhile_answer TEXT NOT NULL CHECK (worthwhile_answer IN (
                'yes', 'mostly', 'not_really', 'prefer_not_to_answer'
            )),
            perceived_control_answer NOT NULL CHECK (
                (typeof(perceived_control_answer) = 'integer'
                    AND perceived_control_answer BETWEEN 1 AND 5)
                OR perceived_control_answer = 'prefer_not_to_answer'
            ),
            mood_answer TEXT NOT NULL CHECK (mood_answer IN (
                'better', 'same', 'worse', 'prefer_not_to_answer'
            )),
            checkout_version TEXT NOT NULL CHECK (length(checkout_version) > 0),
            submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id, participant_id)
                REFERENCES research_sessions(id, participant_id) ON DELETE CASCADE
        );
        """
    )

    if not _sqlite_columns(conn, "research_events"):
        _create_sqlite_research_events_table(conn)
    else:
        _upgrade_sqlite_research_events(conn)

    conn.executescript(
        """
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
        CREATE UNIQUE INDEX IF NOT EXISTS idx_research_events_canonical_session_sequence
            ON research_events (session_id, server_sequence_number)
            WHERE server_sequence_number IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_research_events_client_event_id
            ON research_events (client_event_id) WHERE client_event_id IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_research_events_server_lifecycle_once
            ON research_events (session_id, event_type)
            WHERE event_authority = 'server' AND event_type IN (
                'session_plan_created', 'session_started',
                'session_finished_early', 'session_boundary_reached',
                'checkout_submitted', 'cooldown_started', 'cooldown_completed',
                'cooldown_override_started', 'cooldown_overridden', 'session_cancelled'
            );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_research_events_server_finish_once
            ON research_events (session_id)
            WHERE event_authority = 'server'
              AND event_type IN ('session_finished_early', 'session_boundary_reached');
        CREATE UNIQUE INDEX IF NOT EXISTS idx_research_events_server_cooldown_outcome_once
            ON research_events (session_id)
            WHERE event_authority = 'server'
              AND event_type IN ('cooldown_completed', 'cooldown_overridden');
        CREATE INDEX IF NOT EXISTS idx_research_feed_items_session_created
            ON research_feed_items (session_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_research_feed_items_session_post
            ON research_feed_items (session_id, post_id);
        """
    )
    conn.execute(
        """
        UPDATE research_sessions
        SET next_server_sequence_number = max(
            next_server_sequence_number,
            coalesce((
                SELECT max(server_sequence_number) + 1
                FROM research_events
                WHERE research_events.session_id = research_sessions.id
            ), 0)
        )
        """
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


# Intentional Break Loop storage. These operations deliberately do not share
# transition code with the legacy session path above: journey_state is the v1
# authority, while status/started_at remain compatibility fields.

_JOURNEY_SESSION_COLUMNS = (
    "id",
    "participant_id",
    "journey_version",
    "journey_state",
    "intention",
    "planned_video_count",
    "estimated_duration_seconds",
    "suggested_cooldown_seconds",
    "selected_cooldown_seconds",
    "highest_reached_position",
    "finish_reason",
    "plan_version",
    "plan_created_at",
    "session_started_at",
    "boundary_reached_at",
    "checkout_entered_at",
    "cooldown_started_at",
    "cooldown_ends_at",
    "cooldown_outcome",
    "cooldown_completed_at",
    "override_started_at",
    "override_available_at",
    "override_reason",
    "previous_session_id",
    "completed_at",
    "cancelled_at",
    "feed_condition",
    "feed_policy_version",
    "next_server_sequence_number",
    "status",
    "created_at",
)


def _intentional_backend(conn, backend: str | None) -> str:
    if backend in {"sqlite", "postgres"}:
        return backend
    module_name = conn.__class__.__module__.lower()
    return "sqlite" if "sqlite" in module_name else "postgres"


def _intentional_now(now: datetime | str | None) -> datetime:
    value = now or utc_now()
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise IntentionalBreakStorageError("invalid_plan", "Invalid server timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise IntentionalBreakStorageError("invalid_plan", "Server time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _as_utc_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_object(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(value)


def _begin_intentional_transaction(conn, backend: str):
    try:
        if backend == "sqlite":
            if conn.in_transaction:
                conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            return conn.cursor()
        cur = conn.cursor()
        cur.execute("BEGIN")
        return cur
    except Exception as exc:
        raise IntentionalBreakStorageError(
            "invalid_transition", "Unable to begin storage transaction"
        ) from exc


def _participant_for_journey(cur, *, backend: str, participant_id: str) -> dict:
    ph = _placeholder(backend)
    lock = " FOR UPDATE" if backend == "postgres" else ""
    cur.execute(
        f"SELECT id, status FROM research_participants WHERE id = {ph}{lock}",
        (participant_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise IntentionalBreakStorageError("participant_not_found", "Participant not found")
    if row[1] != "active":
        raise IntentionalBreakStorageError("participant_inactive", "Participant is not active")
    return {"participant_id": str(row[0]), "status": row[1]}


def _row_to_journey_session(row) -> dict:
    return dict(zip(_JOURNEY_SESSION_COLUMNS, row, strict=True))


def _select_journey_session(
    cur,
    *,
    backend: str,
    session_id: str,
    participant_id: str,
    lock: bool = True,
) -> dict:
    ph = _placeholder(backend)
    lock_sql = " FOR UPDATE" if lock and backend == "postgres" else ""
    cur.execute(
        f"SELECT {', '.join(_JOURNEY_SESSION_COLUMNS)} FROM research_sessions "
        f"WHERE id = {ph}{lock_sql}",
        (session_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise IntentionalBreakStorageError("session_not_found", "Session not found")
    session = _row_to_journey_session(row)
    if str(session["participant_id"]) != str(participant_id):
        raise IntentionalBreakStorageError("session_not_owned", "Session is not owned by participant")
    if session["journey_version"] != INTENTIONAL_BREAK_VERSION:
        raise IntentionalBreakStorageError(
            "invalid_transition", "Session is not an Intentional Break Loop journey"
        )
    session["id"] = str(session["id"])
    session["participant_id"] = str(session["participant_id"])
    if session["previous_session_id"] is not None:
        session["previous_session_id"] = str(session["previous_session_id"])
    return session


def _checkout_row(cur, *, backend: str, session_id: str):
    ph = _placeholder(backend)
    cur.execute(
        f"SELECT worthwhile_answer, perceived_control_answer, mood_answer, "
        f"checkout_version, submitted_at FROM research_session_checkouts "
        f"WHERE session_id = {ph}",
        (session_id,),
    )
    return cur.fetchone()


def _journey_snapshot(cur, *, backend: str, session: dict, now: datetime) -> dict:
    checkout = _checkout_row(cur, backend=backend, session_id=session["id"])
    cooldown_ends_at = _as_utc_datetime(session["cooldown_ends_at"])
    remaining = None
    if session["journey_state"] == "cooldown" and cooldown_ends_at is not None:
        remaining = max(0, math.ceil((cooldown_ends_at - now).total_seconds()))
    elif session["journey_state"] == "completed" and cooldown_ends_at is not None:
        remaining = 0
    return {
        "session_id": session["id"],
        "participant_id": session["participant_id"],
        "journey_version": session["journey_version"],
        "journey_state": session["journey_state"],
        "intention": session["intention"],
        "planned_video_count": int(session["planned_video_count"]),
        "estimated_duration_seconds": int(session["estimated_duration_seconds"]),
        "suggested_cooldown_seconds": int(session["suggested_cooldown_seconds"]),
        "selected_cooldown_seconds": int(session["selected_cooldown_seconds"]),
        "highest_reached_position": int(session["highest_reached_position"]),
        "finish_reason": session["finish_reason"],
        "checkout_status": "submitted" if checkout else (
            "required" if session["journey_state"] == "checkout" else "not_submitted"
        ),
        "checkout_submitted": checkout is not None,
        "checkout_version": checkout[3] if checkout else None,
        "plan_version": session["plan_version"],
        "plan_created_at": _serialize_timestamp(session["plan_created_at"]),
        "session_started_at": _serialize_timestamp(session["session_started_at"]),
        "boundary_reached_at": _serialize_timestamp(session["boundary_reached_at"]),
        "checkout_entered_at": _serialize_timestamp(session["checkout_entered_at"]),
        "cooldown_started_at": _serialize_timestamp(session["cooldown_started_at"]),
        "cooldown_ends_at": _serialize_timestamp(session["cooldown_ends_at"]),
        "cooldown_remaining_seconds": remaining,
        "cooldown_outcome": session["cooldown_outcome"],
        "cooldown_completed_at": _serialize_timestamp(session["cooldown_completed_at"]),
        "override_started_at": _serialize_timestamp(session["override_started_at"]),
        "override_available_at": _serialize_timestamp(session["override_available_at"]),
        "override_reason": session["override_reason"],
        "previous_session_id": session["previous_session_id"],
        "completed_at": _serialize_timestamp(session["completed_at"]),
        "cancelled_at": _serialize_timestamp(session["cancelled_at"]),
        "feed_condition": session["feed_condition"],
        "feed_policy_version": session["feed_policy_version"],
    }


def _lifecycle_event(cur, *, backend: str, session_id: str, event_type: str):
    ph = _placeholder(backend)
    cur.execute(
        f"SELECT id, server_sequence_number, server_timestamp, metadata "
        f"FROM research_events WHERE session_id = {ph} AND event_type = {ph} "
        f"AND event_authority = 'server'",
        (session_id, event_type),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "event_id": str(row[0]),
        "server_sequence_number": int(row[1]),
        "server_timestamp": _serialize_timestamp(row[2]),
        "metadata": _json_object(row[3]),
    }


def _require_idempotency_key(value, *, code: str = "idempotency_conflict") -> str:
    key = str(value or "").strip()
    if not key or len(key) > 200:
        raise IntentionalBreakStorageError(code, "A valid idempotency key is required")
    return key


def _allocate_and_insert_canonical_event(
    cur,
    *,
    backend: str,
    session: dict,
    participant_id: str,
    event_type: str,
    authority: str,
    occurred_at: datetime,
    metadata: dict,
    post_id: str | None = None,
    content_category: str | None = None,
    client_event_id: str | None = None,
    client_sequence_number: int | None = None,
    client_timestamp=None,
) -> dict:
    ph = _placeholder(backend)
    cur.execute(
        f"UPDATE research_sessions SET next_server_sequence_number = "
        f"next_server_sequence_number + 1 WHERE id = {ph} AND participant_id = {ph} "
        f"RETURNING next_server_sequence_number - 1",
        (session["id"], participant_id),
    )
    allocated = cur.fetchone()
    if allocated is None:
        raise IntentionalBreakStorageError("session_not_found", "Session disappeared")
    server_sequence_number = int(allocated[0])
    event_id = str(uuid.uuid4())
    cur.execute(
        f"INSERT INTO research_events ("
        f"id, session_id, participant_id, sequence_number, server_sequence_number, "
        f"client_event_id, client_sequence_number, event_type, post_id, content_category, "
        f"feed_condition, client_timestamp, server_timestamp, received_at, event_authority, metadata"
        f") VALUES ({', '.join([ph] * 16)})",
        (
            event_id,
            session["id"],
            participant_id,
            server_sequence_number,
            server_sequence_number,
            client_event_id,
            client_sequence_number,
            event_type,
            post_id,
            content_category,
            session["feed_condition"],
            _db_timestamp(backend, client_timestamp),
            _db_timestamp(backend, occurred_at),
            _db_timestamp(backend, occurred_at),
            authority,
            _json_value(backend, metadata),
        ),
    )
    session["next_server_sequence_number"] = server_sequence_number + 1
    return {
        "event_id": event_id,
        "client_event_id": client_event_id,
        "server_sequence_number": server_sequence_number,
        "server_timestamp": occurred_at.isoformat(),
    }


def _command_replay(
    cur,
    *,
    backend: str,
    session: dict,
    event_type: str,
    idempotency_key: str,
    material: dict,
):
    existing = _lifecycle_event(
        cur, backend=backend, session_id=session["id"], event_type=event_type
    )
    if existing is None:
        return None
    stored = existing["metadata"]
    if stored.get("idempotency_key") != idempotency_key:
        return False
    if stored.get("material", {}) != material:
        raise IntentionalBreakStorageError(
            "idempotency_conflict", "Idempotency key was reused with different inputs"
        )
    return existing


def _normalize_reserved_items(items: list[dict], planned_video_count: int) -> list[dict]:
    if not isinstance(items, (list, tuple)) or len(items) != planned_video_count:
        raise IntentionalBreakStorageError(
            "invalid_reserved_batch",
            "Reserved batch must contain exactly the planned number of items",
        )
    normalized = []
    seen_posts = set()
    for position, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            raise IntentionalBreakStorageError(
                "invalid_reserved_batch", "Each reserved item must be an object"
            )
        post_id = str(raw.get("post_id") or "").strip()
        if not post_id or post_id in seen_posts:
            raise IntentionalBreakStorageError(
                "invalid_reserved_batch", "Reserved post ids must be present and unique"
            )
        seen_posts.add(post_id)
        category = raw.get("content_category") or "unknown"
        policy = raw.get("feed_policy_version")
        bucket = raw.get("selection_bucket")
        reason = raw.get("selection_reason")
        ranking_snapshot = raw.get("ranking_snapshot")
        provenance = raw.get("provenance_metadata")
        if not isinstance(ranking_snapshot, dict) or not isinstance(provenance, dict):
            raise IntentionalBreakStorageError(
                "invalid_reserved_batch", "Ranking and provenance metadata must be objects"
            )
        try:
            json.dumps(ranking_snapshot, separators=(",", ":"), sort_keys=True)
            json.dumps(provenance, separators=(",", ":"), sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise IntentionalBreakStorageError(
                "invalid_reserved_batch", "Reserved metadata must be JSON serializable"
            ) from exc
        source_type = raw.get("source_type") or provenance.get("source_type")
        source_reference = (
            raw.get("source_reference")
            or raw.get("source_ref")
            or raw.get("feed_request_id")
            or provenance.get("source_reference")
            or provenance.get("source_ref")
            or provenance.get("feed_request_id")
        )
        source_type = str(source_type or "").strip()
        source_reference = str(source_reference or "").strip()
        source_requires_reference = source_type.lower() in {
            "feed", "feed_request", "ranked_feed", "research_feed",
        }
        if not source_type or (source_requires_reference and not source_reference):
            raise IntentionalBreakStorageError(
                "invalid_reserved_batch", "Reserved item source provenance is required"
            )
        if (
            not isinstance(category, str)
            or category not in INTENTIONAL_BREAK_CONTENT_CATEGORIES
            or policy != INTENTIONAL_BREAK_POLICY_VERSION
            or not isinstance(bucket, str)
            or bucket not in INTENTIONAL_BREAK_SELECTION_BUCKETS
            or not isinstance(reason, str)
            or reason not in INTENTIONAL_BREAK_SELECTION_REASONS
        ):
            raise IntentionalBreakStorageError(
                "invalid_reserved_batch", "Reserved item policy provenance is invalid"
            )
        canonical_provenance = dict(provenance)
        canonical_provenance["source_type"] = source_type
        if source_reference:
            canonical_provenance["source_reference"] = source_reference
        if raw.get("feed_request_id"):
            canonical_provenance["feed_request_id"] = str(raw["feed_request_id"])
        normalized.append({
            "post_id": post_id,
            "session_position": position,
            "content_category": category,
            "feed_policy_version": policy,
            "selection_bucket": bucket,
            "selection_reason": reason,
            "ranking_snapshot": ranking_snapshot,
            "provenance_metadata": canonical_provenance,
        })
    return normalized


def _plan_fingerprint(
    *,
    intention: str,
    planned_video_count: int,
    selected_cooldown_seconds: int,
    reserved_items: list[dict],
    previous_session_id: str | None,
) -> str:
    encoded = json.dumps({
        "intention": intention,
        "planned_video_count": planned_video_count,
        "selected_cooldown_seconds": selected_cooldown_seconds,
        "reserved_items": reserved_items,
        "previous_session_id": previous_session_id,
    }, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_plan_values(
    intention: str, planned_video_count: int, selected_cooldown_seconds: int
) -> None:
    if not isinstance(intention, str) or intention not in INTENTIONAL_BREAK_INTENTIONS:
        raise IntentionalBreakStorageError("invalid_plan", "Unsupported intention")
    if (
        isinstance(planned_video_count, bool)
        or not isinstance(planned_video_count, int)
        or planned_video_count not in INTENTIONAL_BREAK_VIDEO_COUNTS
    ):
        raise IntentionalBreakStorageError("invalid_plan", "Unsupported planned video count")
    if (
        isinstance(selected_cooldown_seconds, bool)
        or not isinstance(selected_cooldown_seconds, int)
        or selected_cooldown_seconds < 300
        or selected_cooldown_seconds > 7200
        or selected_cooldown_seconds % 300
    ):
        raise IntentionalBreakStorageError("invalid_plan", "Unsupported selected cooldown")


def _reconcile_cooldown_in_transaction(
    cur, *, backend: str, session: dict, now: datetime
) -> dict:
    if session["journey_state"] != "cooldown":
        return session
    cooldown_ends_at = _as_utc_datetime(session["cooldown_ends_at"])
    if cooldown_ends_at is None:
        raise IntentionalBreakStorageError("invalid_transition", "Cooldown end time is missing")
    if now < cooldown_ends_at:
        return session
    _allocate_and_insert_canonical_event(
        cur,
        backend=backend,
        session=session,
        participant_id=session["participant_id"],
        event_type="cooldown_completed",
        authority="server",
        occurred_at=now,
        metadata={"completion_mode": "natural"},
    )
    ph = _placeholder(backend)
    cur.execute(
        f"UPDATE research_sessions SET journey_state = 'completed', status = 'completed', "
        f"cooldown_outcome = 'completed', cooldown_completed_at = {ph}, completed_at = {ph} "
        f"WHERE id = {ph} AND journey_state = 'cooldown'",
        (
            _db_timestamp(backend, now),
            _db_timestamp(backend, now),
            session["id"],
        ),
    )
    if cur.rowcount != 1:
        raise IntentionalBreakStorageError("invalid_transition", "Cooldown state changed")
    session.update({
        "journey_state": "completed",
        "status": "completed",
        "cooldown_outcome": "completed",
        "cooldown_completed_at": now,
        "completed_at": now,
    })
    return session


def get_current_intentional_break_journey(
    conn,
    *,
    participant_id: str,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict | None:
    """Return and, when due, lazily reconcile the participant's current journey."""
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        ph = _placeholder(backend)
        lock = " FOR UPDATE" if backend == "postgres" else ""
        states = ", ".join([ph] * len(INTENTIONAL_BREAK_NONTERMINAL_STATES))
        cur.execute(
            f"SELECT {', '.join(_JOURNEY_SESSION_COLUMNS)} FROM research_sessions "
            f"WHERE participant_id = {ph} AND journey_version = {ph} "
            f"AND journey_state IN ({states}) ORDER BY plan_created_at DESC LIMIT 1{lock}",
            (
                participant_id,
                INTENTIONAL_BREAK_VERSION,
                *INTENTIONAL_BREAK_NONTERMINAL_STATES,
            ),
        )
        row = cur.fetchone()
        if row is None:
            conn.commit()
            return None
        session = _row_to_journey_session(row)
        session["id"] = str(session["id"])
        session["participant_id"] = str(session["participant_id"])
        if session["previous_session_id"] is not None:
            session["previous_session_id"] = str(session["previous_session_id"])
        _reconcile_cooldown_in_transaction(
            cur, backend=backend, session=session, now=current_time
        )
        result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError(
            "invalid_transition", "Unable to read current journey"
        ) from exc


def create_intentional_break_plan(
    conn,
    *,
    participant_id: str,
    intention: str,
    planned_video_count: int,
    selected_cooldown_seconds: int,
    reserved_items: list[dict] | None = None,
    plan_idempotency_key: str | None = None,
    ordered_reserved_items: list[dict] | None = None,
    reserved_item_payload: list[dict] | None = None,
    idempotency_key: str | None = None,
    previous_session_id: str | None = None,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict:
    """Create one complete, stable planned batch in a single transaction."""
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    key = _require_idempotency_key(plan_idempotency_key or idempotency_key)
    _validate_plan_values(intention, planned_video_count, selected_cooldown_seconds)
    supplied_items = reserved_items
    if supplied_items is None:
        supplied_items = ordered_reserved_items
    if supplied_items is None:
        supplied_items = reserved_item_payload
    normalized_items = _normalize_reserved_items(supplied_items, planned_video_count)
    previous_id = str(previous_session_id) if previous_session_id is not None else None
    fingerprint = _plan_fingerprint(
        intention=intention,
        planned_video_count=planned_video_count,
        selected_cooldown_seconds=selected_cooldown_seconds,
        reserved_items=normalized_items,
        previous_session_id=previous_id,
    )
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        ph = _placeholder(backend)

        cur.execute(
            f"SELECT e.session_id, e.metadata FROM research_events e "
            f"JOIN research_sessions s ON s.id = e.session_id "
            f"WHERE e.participant_id = {ph} AND e.event_type = 'session_plan_created' "
            f"AND e.event_authority = 'server' AND s.journey_version = {ph}",
            (participant_id, INTENTIONAL_BREAK_VERSION),
        )
        for replay_session_id, metadata_value in cur.fetchall():
            metadata = _json_object(metadata_value)
            if metadata.get("idempotency_key") != key:
                continue
            if metadata.get("plan_fingerprint") != fingerprint:
                raise IntentionalBreakStorageError(
                    "idempotency_conflict",
                    "Plan idempotency key was reused with different inputs",
                )
            replay_session = _select_journey_session(
                cur,
                backend=backend,
                session_id=str(replay_session_id),
                participant_id=participant_id,
            )
            result = _journey_snapshot(
                cur, backend=backend, session=replay_session, now=current_time
            )
            conn.commit()
            return result

        if previous_id is not None:
            previous = _select_journey_session(
                cur,
                backend=backend,
                session_id=previous_id,
                participant_id=participant_id,
            )
            if previous["journey_state"] != "completed":
                raise IntentionalBreakStorageError(
                    "invalid_plan", "Previous session must be completed"
                )

        states = ", ".join([ph] * len(INTENTIONAL_BREAK_NONTERMINAL_STATES))
        cur.execute(
            f"SELECT id FROM research_sessions WHERE participant_id = {ph} "
            f"AND journey_version = {ph} AND journey_state IN ({states}) LIMIT 1",
            (
                participant_id,
                INTENTIONAL_BREAK_VERSION,
                *INTENTIONAL_BREAK_NONTERMINAL_STATES,
            ),
        )
        existing = cur.fetchone()
        if existing is not None:
            existing_session = _select_journey_session(
                cur,
                backend=backend,
                session_id=str(existing[0]),
                participant_id=participant_id,
            )
            raise IntentionalBreakStorageError(
                "existing_nonterminal_session",
                "Participant already has a nonterminal journey",
                details={
                    "journey": _journey_snapshot(
                        cur, backend=backend, session=existing_session, now=current_time
                    )
                },
            )

        session_id = str(uuid.uuid4())
        estimated_duration = planned_video_count * 30
        suggested_cooldown = min(
            7200, max(300, math.ceil((estimated_duration * 2) / 300) * 300)
        )
        compatibility_time = _db_timestamp(backend, current_time)
        cur.execute(
            f"INSERT INTO research_sessions ("
            f"id, participant_id, feed_condition, feed_policy_version, feed_seed, "
            f"application_version, status, started_at, created_at, journey_version, "
            f"journey_state, intention, planned_video_count, estimated_duration_seconds, "
            f"suggested_cooldown_seconds, selected_cooldown_seconds, plan_version, "
            f"plan_created_at, highest_reached_position, previous_session_id, "
            f"next_server_sequence_number"
            f") VALUES ({', '.join([ph] * 21)})",
            (
                session_id,
                participant_id,
                "balanced",
                INTENTIONAL_BREAK_POLICY_VERSION,
                secrets.token_urlsafe(24),
                INTENTIONAL_BREAK_PLAN_VERSION,
                "active",
                compatibility_time,
                compatibility_time,
                INTENTIONAL_BREAK_VERSION,
                "planned",
                intention,
                planned_video_count,
                estimated_duration,
                suggested_cooldown,
                selected_cooldown_seconds,
                INTENTIONAL_BREAK_PLAN_VERSION,
                compatibility_time,
                0,
                previous_id,
                0,
            ),
        )
        session = _select_journey_session(
            cur,
            backend=backend,
            session_id=session_id,
            participant_id=participant_id,
        )
        for item in normalized_items:
            cur.execute(
                f"INSERT INTO research_session_items ("
                f"id, session_id, participant_id, post_id, session_position, "
                f"content_category, feed_policy_version, selection_bucket, selection_reason, "
                f"ranking_snapshot, provenance_metadata, reserved_at"
                f") VALUES ({', '.join([ph] * 12)})",
                (
                    str(uuid.uuid4()),
                    session_id,
                    participant_id,
                    item["post_id"],
                    item["session_position"],
                    item["content_category"],
                    item["feed_policy_version"],
                    item["selection_bucket"],
                    item["selection_reason"],
                    _json_value(backend, item["ranking_snapshot"]),
                    _json_value(backend, item["provenance_metadata"]),
                    compatibility_time,
                ),
            )
        _allocate_and_insert_canonical_event(
            cur,
            backend=backend,
            session=session,
            participant_id=participant_id,
            event_type="session_plan_created",
            authority="server",
            occurred_at=current_time,
            metadata={
                "idempotency_key": key,
                "plan_fingerprint": fingerprint,
                "planned_video_count": planned_video_count,
                "plan_version": INTENTIONAL_BREAK_PLAN_VERSION,
            },
        )
        result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError(
            "invalid_reserved_batch", "Unable to create the reserved plan atomically"
        ) from exc


def cancel_intentional_break_plan(
    conn,
    *,
    participant_id: str,
    session_id: str,
    idempotency_key: str,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict:
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    key = _require_idempotency_key(idempotency_key)
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        session = _select_journey_session(
            cur, backend=backend, session_id=session_id, participant_id=participant_id
        )
        replay = _command_replay(
            cur,
            backend=backend,
            session=session,
            event_type="session_cancelled",
            idempotency_key=key,
            material={},
        )
        if replay:
            result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
            conn.commit()
            return result
        if session["journey_state"] != "planned":
            raise IntentionalBreakStorageError(
                "invalid_transition", "Only a planned session may be cancelled"
            )
        _allocate_and_insert_canonical_event(
            cur,
            backend=backend,
            session=session,
            participant_id=participant_id,
            event_type="session_cancelled",
            authority="server",
            occurred_at=current_time,
            metadata={"idempotency_key": key, "material": {}},
        )
        ph = _placeholder(backend)
        cur.execute(
            f"UPDATE research_sessions SET journey_state = 'cancelled', cancelled_at = {ph} "
            f"WHERE id = {ph} AND journey_state = 'planned'",
            (_db_timestamp(backend, current_time), session_id),
        )
        if cur.rowcount != 1:
            raise IntentionalBreakStorageError("invalid_transition", "Session state changed")
        session.update({"journey_state": "cancelled", "cancelled_at": current_time})
        result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError("invalid_transition", "Unable to cancel plan") from exc


def _validate_reserved_batch_for_start(
    cur, *, backend: str, session: dict, participant_id: str
) -> None:
    ph = _placeholder(backend)
    cur.execute(
        f"SELECT participant_id, session_position FROM research_session_items "
        f"WHERE session_id = {ph} ORDER BY session_position",
        (session["id"],),
    )
    rows = cur.fetchall()
    count = int(session["planned_video_count"])
    if len(rows) != count:
        raise IntentionalBreakStorageError(
            "invalid_reserved_batch", "Reserved batch size no longer matches the plan"
        )
    if [int(row[1]) for row in rows] != list(range(1, count + 1)):
        raise IntentionalBreakStorageError(
            "invalid_reserved_batch", "Reserved positions are not contiguous"
        )
    if any(str(row[0]) != str(participant_id) for row in rows):
        raise IntentionalBreakStorageError(
            "invalid_reserved_batch", "Reserved item ownership is invalid"
        )


def start_intentional_break_session(
    conn,
    *,
    participant_id: str,
    session_id: str,
    idempotency_key: str,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict:
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    key = _require_idempotency_key(idempotency_key)
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        session = _select_journey_session(
            cur, backend=backend, session_id=session_id, participant_id=participant_id
        )
        replay = _command_replay(
            cur,
            backend=backend,
            session=session,
            event_type="session_started",
            idempotency_key=key,
            material={},
        )
        if replay:
            result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
            conn.commit()
            return result
        if session["journey_state"] != "planned":
            raise IntentionalBreakStorageError(
                "invalid_transition", "Only a planned session may be started"
            )
        _validate_reserved_batch_for_start(
            cur, backend=backend, session=session, participant_id=participant_id
        )
        event_metadata = {"idempotency_key": key, "material": {}}
        if session["previous_session_id"]:
            previous = _select_journey_session(
                cur,
                backend=backend,
                session_id=session["previous_session_id"],
                participant_id=participant_id,
            )
            previous_completed_at = _as_utc_datetime(previous["completed_at"])
            if previous["journey_state"] == "completed" and previous_completed_at is not None:
                event_metadata.update({
                    "previous_session_id": previous["id"],
                    "previous_cooldown_outcome": previous["cooldown_outcome"],
                    "seconds_since_previous_session_completed": max(
                        0, int((current_time - previous_completed_at).total_seconds())
                    ),
                })
        _allocate_and_insert_canonical_event(
            cur,
            backend=backend,
            session=session,
            participant_id=participant_id,
            event_type="session_started",
            authority="server",
            occurred_at=current_time,
            metadata=event_metadata,
        )
        ph = _placeholder(backend)
        cur.execute(
            f"UPDATE research_sessions SET journey_state = 'active', "
            f"session_started_at = {ph} WHERE id = {ph} AND journey_state = 'planned'",
            (_db_timestamp(backend, current_time), session_id),
        )
        if cur.rowcount != 1:
            raise IntentionalBreakStorageError("invalid_transition", "Session state changed")
        session.update({"journey_state": "active", "session_started_at": current_time})
        result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError("invalid_transition", "Unable to start session") from exc


def read_intentional_break_items(
    conn,
    *,
    participant_id: str,
    session_id: str,
    start_position: int | None = None,
    requested_limit: int | None = None,
    cursor: int | str | None = None,
    limit: int | None = None,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict:
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    raw_start = start_position if start_position is not None else (cursor if cursor is not None else 1)
    raw_limit = requested_limit if requested_limit is not None else limit
    try:
        first_position = int(raw_start)
        page_limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise IntentionalBreakStorageError("invalid_plan", "Invalid item page") from exc
    if first_position < 1 or page_limit < 1 or page_limit > 100:
        raise IntentionalBreakStorageError("invalid_plan", "Invalid item page")
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        session = _select_journey_session(
            cur, backend=backend, session_id=session_id, participant_id=participant_id
        )
        if session["journey_state"] != "active":
            raise IntentionalBreakStorageError(
                "invalid_transition", "Reserved items are available only while active"
            )
        planned_total = int(session["planned_video_count"])
        ph = _placeholder(backend)
        upper_bound = min(planned_total, first_position + page_limit - 1)
        cur.execute(
            f"UPDATE research_session_items SET first_issued_at = {ph} "
            f"WHERE session_id = {ph} AND participant_id = {ph} "
            f"AND session_position BETWEEN {ph} AND {ph} AND first_issued_at IS NULL",
            (
                _db_timestamp(backend, current_time),
                session_id,
                participant_id,
                first_position,
                upper_bound,
            ),
        )
        cur.execute(
            f"SELECT id, post_id, session_position, content_category, feed_policy_version, "
            f"selection_bucket, selection_reason, ranking_snapshot, provenance_metadata, "
            f"reserved_at, first_issued_at, first_impressed_at, first_viewed_at "
            f"FROM research_session_items WHERE session_id = {ph} AND participant_id = {ph} "
            f"AND session_position BETWEEN {ph} AND {ph} "
            f"ORDER BY session_position LIMIT {ph}",
            (session_id, participant_id, first_position, planned_total, page_limit),
        )
        items = []
        for row in cur.fetchall():
            items.append({
                "item_id": str(row[0]),
                "post_id": row[1],
                "global_position": int(row[2]),
                "session_position": int(row[2]),
                "content_category": row[3],
                "feed_policy_version": row[4],
                "selection_bucket": row[5],
                "selection_reason": row[6],
                "ranking_snapshot": _json_object(row[7]),
                "provenance_metadata": _json_object(row[8]),
                "reserved_at": _serialize_timestamp(row[9]),
                "first_issued_at": _serialize_timestamp(row[10]),
                "first_impressed_at": _serialize_timestamp(row[11]),
                "first_viewed_at": _serialize_timestamp(row[12]),
            })
        next_position = items[-1]["global_position"] + 1 if items else first_position
        has_more = bool(items) and next_position <= planned_total
        result = {
            "items": items,
            "planned_total": planned_total,
            "next_position": next_position if has_more else None,
            "next_cursor": next_position if has_more else None,
            "has_more": has_more,
        }
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError("invalid_transition", "Unable to read items") from exc


def _normalize_client_timestamp(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise IntentionalBreakStorageError("event_not_allowed", "Invalid client timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise IntentionalBreakStorageError(
            "event_not_allowed", "Client timestamp must include a timezone"
        )
    return value.astimezone(timezone.utc)


def _normalize_client_event(event: dict) -> dict:
    if not isinstance(event, dict):
        raise IntentionalBreakStorageError("event_not_allowed", "Client event must be an object")
    raw_id = event.get("client_event_id") or event.get("event_id")
    try:
        client_event_id = str(uuid.UUID(str(raw_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise IntentionalBreakStorageError(
            "event_not_allowed", "Client event id must be a UUID"
        ) from exc
    event_type = str(event.get("event_type") or "")
    if event_type not in INTENTIONAL_BREAK_CLIENT_EVENT_TYPES:
        raise IntentionalBreakStorageError("event_not_allowed", "Unsupported client event type")
    post_id = event.get("post_id")
    if event_type in INTENTIONAL_BREAK_POST_EVENT_TYPES:
        post_id = str(post_id or "").strip()
        if not post_id:
            raise IntentionalBreakStorageError("event_not_allowed", "Post id is required")
    elif post_id is not None:
        post_id = str(post_id)
    diagnostic = event.get("client_sequence_number")
    if diagnostic is None:
        diagnostic = event.get("client_diagnostic_sequence_number")
    if diagnostic is None:
        diagnostic = event.get("sequence_number")
    if diagnostic is not None and (
        isinstance(diagnostic, bool) or not isinstance(diagnostic, int) or diagnostic < 0
    ):
        raise IntentionalBreakStorageError(
            "event_not_allowed", "Client diagnostic sequence must be non-negative"
        )
    metadata = event.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise IntentionalBreakStorageError("event_not_allowed", "Event metadata must be an object")
    try:
        json.dumps(metadata, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise IntentionalBreakStorageError("event_not_allowed", "Event metadata is invalid") from exc
    if event_type == "post_impression":
        ratio = metadata.get("visibility_ratio")
        visible_ms = metadata.get("visible_ms")
        if (
            isinstance(ratio, bool)
            or not isinstance(ratio, (int, float))
            or ratio < 0.6
            or isinstance(visible_ms, bool)
            or not isinstance(visible_ms, (int, float))
            or visible_ms < 1000
        ):
            raise IntentionalBreakStorageError(
                "event_not_allowed",
                "Post impression does not meet the meaningful-impression threshold",
            )
    return {
        "client_event_id": client_event_id,
        "client_sequence_number": diagnostic,
        "event_type": event_type,
        "post_id": post_id,
        "client_timestamp": _normalize_client_timestamp(event.get("client_timestamp")),
        "metadata": dict(metadata),
    }


def _reserved_item_for_event(
    cur, *, backend: str, session_id: str, participant_id: str, post_id: str
) -> dict:
    ph = _placeholder(backend)
    cur.execute(
        f"SELECT post_id, session_position, content_category, feed_policy_version, "
        f"selection_bucket, selection_reason, ranking_snapshot, provenance_metadata "
        f"FROM research_session_items WHERE session_id = {ph} "
        f"AND participant_id = {ph} AND post_id = {ph}",
        (session_id, participant_id, post_id),
    )
    row = cur.fetchone()
    if row is None:
        raise IntentionalBreakStorageError(
            "event_provenance_invalid", "Post was not reserved for this session"
        )
    return {
        "post_id": row[0],
        "session_position": int(row[1]),
        "content_category": row[2],
        "feed_policy_version": row[3],
        "selection_bucket": row[4],
        "selection_reason": row[5],
        "ranking_snapshot": _json_object(row[6]),
        "provenance_metadata": _json_object(row[7]),
    }


def _server_derived_event_metadata(event: dict, item: dict | None) -> dict:
    metadata = dict(event["metadata"])
    if item is None:
        return metadata
    metadata.update({
        "session_position": item["session_position"],
        "feed_position": item["session_position"],
        "feed_policy_version": item["feed_policy_version"],
        "selection_bucket": item["selection_bucket"],
        "selection_reason": item["selection_reason"],
        "ranking_snapshot": item["ranking_snapshot"],
        "provenance_metadata": item["provenance_metadata"],
    })
    return metadata


def _existing_client_event(cur, *, backend: str, client_event_id: str):
    ph = _placeholder(backend)
    cur.execute(
        f"SELECT id, session_id, participant_id, server_sequence_number, event_type, "
        f"post_id, content_category, client_sequence_number, client_timestamp, "
        f"server_timestamp, metadata FROM research_events WHERE client_event_id = {ph}",
        (client_event_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "event_id": str(row[0]),
        "session_id": str(row[1]),
        "participant_id": str(row[2]),
        "server_sequence_number": int(row[3]),
        "event_type": row[4],
        "post_id": row[5],
        "content_category": row[6],
        "client_sequence_number": row[7],
        "client_timestamp": _serialize_timestamp(row[8]),
        "server_timestamp": _serialize_timestamp(row[9]),
        "metadata": _json_object(row[10]),
    }


def _client_event_material_matches(
    existing: dict,
    *,
    session_id: str,
    participant_id: str,
    event: dict,
    content_category: str | None,
    metadata: dict,
) -> bool:
    return all((
        existing["session_id"] == str(session_id),
        existing["participant_id"] == str(participant_id),
        existing["event_type"] == event["event_type"],
        existing["post_id"] == event["post_id"],
        existing["content_category"] == content_category,
        existing["client_sequence_number"] == event["client_sequence_number"],
        existing["client_timestamp"] == _serialize_timestamp(event["client_timestamp"]),
        existing["metadata"] == metadata,
    ))


def append_intentional_break_client_events(
    conn,
    *,
    participant_id: str,
    session_id: str,
    events: list[dict] | None = None,
    client_events: list[dict] | None = None,
    ordered_client_event_payloads: list[dict] | None = None,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict:
    """Append client events in supplied order using canonical server sequences."""
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    supplied = events if events is not None else client_events
    if supplied is None:
        supplied = ordered_client_event_payloads
    if not isinstance(supplied, (list, tuple)) or not supplied:
        raise IntentionalBreakStorageError("event_not_allowed", "At least one event is required")
    normalized_events = [_normalize_client_event(event) for event in supplied]
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        session = _select_journey_session(
            cur, backend=backend, session_id=session_id, participant_id=participant_id
        )
        accepted = []
        duplicates = []
        lifecycle_events = []
        for event in normalized_events:
            item = None
            if event["event_type"] in INTENTIONAL_BREAK_POST_EVENT_TYPES:
                item = _reserved_item_for_event(
                    cur,
                    backend=backend,
                    session_id=session_id,
                    participant_id=participant_id,
                    post_id=event["post_id"],
                )
            derived_metadata = _server_derived_event_metadata(event, item)
            existing = _existing_client_event(
                cur, backend=backend, client_event_id=event["client_event_id"]
            )
            if existing is not None:
                if not _client_event_material_matches(
                    existing,
                    session_id=session_id,
                    participant_id=participant_id,
                    event=event,
                    content_category=item["content_category"] if item else None,
                    metadata=derived_metadata,
                ):
                    raise IntentionalBreakStorageError(
                        "idempotency_conflict",
                        "Client event id was reused with different data",
                    )
                duplicate_result = {
                    "event_id": existing["event_id"],
                    "client_event_id": event["client_event_id"],
                    "server_sequence_number": existing["server_sequence_number"],
                    "server_timestamp": existing["server_timestamp"],
                    "duplicate": True,
                }
                accepted.append(duplicate_result)
                duplicates.append(event["client_event_id"])
                continue

            state = session["journey_state"]
            if state == "completed":
                raise IntentionalBreakStorageError(
                    "event_not_allowed", "Completed sessions accept only exact event replays"
                )
            if state in {"planned", "cancelled"} or session["session_started_at"] is None:
                raise IntentionalBreakStorageError(
                    "event_not_allowed", "Session has not started or no longer accepts events"
                )
            if state in {"checkout", "cooldown"} and event["event_type"] not in INTENTIONAL_BREAK_POST_EVENT_TYPES:
                raise IntentionalBreakStorageError(
                    "event_not_allowed", "Only delayed post events are accepted after feed exit"
                )
            inserted = _allocate_and_insert_canonical_event(
                cur,
                backend=backend,
                session=session,
                participant_id=participant_id,
                event_type=event["event_type"],
                authority="client",
                occurred_at=current_time,
                metadata=derived_metadata,
                post_id=event["post_id"],
                content_category=item["content_category"] if item else None,
                client_event_id=event["client_event_id"],
                client_sequence_number=event["client_sequence_number"],
                client_timestamp=event["client_timestamp"],
            )
            inserted["duplicate"] = False
            accepted.append(inserted)

            if item is None:
                continue
            ph = _placeholder(backend)
            timestamp_column = None
            if event["event_type"] == "post_impression":
                timestamp_column = "first_impressed_at"
            elif event["event_type"] == "post_viewed":
                timestamp_column = "first_viewed_at"
            first_timestamp_written = False
            if timestamp_column:
                cur.execute(
                    f"UPDATE research_session_items SET {timestamp_column} = {ph} "
                    f"WHERE session_id = {ph} AND participant_id = {ph} AND post_id = {ph} "
                    f"AND {timestamp_column} IS NULL",
                    (
                        _db_timestamp(backend, current_time),
                        session_id,
                        participant_id,
                        item["post_id"],
                    ),
                )
                first_timestamp_written = cur.rowcount == 1
            if event["event_type"] != "post_impression":
                continue
            position = item["session_position"]
            cur.execute(
                f"UPDATE research_sessions SET highest_reached_position = CASE "
                f"WHEN highest_reached_position < {ph} THEN {ph} "
                f"ELSE highest_reached_position END WHERE id = {ph}",
                (position, position, session_id),
            )
            session["highest_reached_position"] = max(
                int(session["highest_reached_position"]), position
            )
            if (
                first_timestamp_written
                and position == int(session["planned_video_count"])
                and session["journey_state"] == "active"
            ):
                boundary_event = _allocate_and_insert_canonical_event(
                    cur,
                    backend=backend,
                    session=session,
                    participant_id=participant_id,
                    event_type="session_boundary_reached",
                    authority="server",
                    occurred_at=current_time,
                    metadata={"session_position": position},
                )
                lifecycle_events.append(boundary_event)
                cur.execute(
                    f"UPDATE research_sessions SET journey_state = 'checkout', "
                    f"finish_reason = 'boundary_reached', boundary_reached_at = {ph}, "
                    f"checkout_entered_at = {ph} WHERE id = {ph} AND journey_state = 'active'",
                    (
                        _db_timestamp(backend, current_time),
                        _db_timestamp(backend, current_time),
                        session_id,
                    ),
                )
                if cur.rowcount != 1:
                    raise IntentionalBreakStorageError(
                        "invalid_transition", "Boundary state changed"
                    )
                session.update({
                    "journey_state": "checkout",
                    "finish_reason": "boundary_reached",
                    "boundary_reached_at": current_time,
                    "checkout_entered_at": current_time,
                })
        result = {
            "accepted": accepted,
            "duplicates": duplicates,
            "lifecycle_events": lifecycle_events,
            "journey": _journey_snapshot(
                cur, backend=backend, session=session, now=current_time
            ),
        }
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError("event_not_allowed", "Unable to append events") from exc


def finish_intentional_break_early(
    conn,
    *,
    participant_id: str,
    session_id: str,
    idempotency_key: str,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict:
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    key = _require_idempotency_key(idempotency_key)
    material = {}
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        session = _select_journey_session(
            cur, backend=backend, session_id=session_id, participant_id=participant_id
        )
        replay = _command_replay(
            cur,
            backend=backend,
            session=session,
            event_type="session_finished_early",
            idempotency_key=key,
            material=material,
        )
        if replay:
            result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
            conn.commit()
            return result
        if session["journey_state"] != "active" or session["finish_reason"] == "boundary_reached":
            raise IntentionalBreakStorageError(
                "invalid_transition", "Only an active pre-boundary session may finish early"
            )
        highest_meaningful_position = int(session["highest_reached_position"])
        _allocate_and_insert_canonical_event(
            cur,
            backend=backend,
            session=session,
            participant_id=participant_id,
            event_type="session_finished_early",
            authority="server",
            occurred_at=current_time,
            metadata={
                "idempotency_key": key,
                "material": material,
                "highest_meaningful_position": highest_meaningful_position,
            },
        )
        ph = _placeholder(backend)
        cur.execute(
            f"UPDATE research_sessions SET journey_state = 'checkout', "
            f"finish_reason = 'finished_early', checkout_entered_at = {ph} "
            f"WHERE id = {ph} AND journey_state = 'active'",
            (
                _db_timestamp(backend, current_time),
                session_id,
            ),
        )
        if cur.rowcount != 1:
            raise IntentionalBreakStorageError("invalid_transition", "Session state changed")
        session.update({
            "journey_state": "checkout",
            "finish_reason": "finished_early",
            "checkout_entered_at": current_time,
        })
        result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError(
            "invalid_transition", "Unable to finish the session early"
        ) from exc


def _validate_checkout_answers(worthwhile, perceived_control, mood, checkout_version) -> None:
    if (
        not isinstance(worthwhile, str)
        or worthwhile not in INTENTIONAL_BREAK_WORTHWHILE_VALUES
        or isinstance(perceived_control, bool)
        or not isinstance(perceived_control, (int, str))
        or perceived_control not in INTENTIONAL_BREAK_CONTROL_VALUES
        or not isinstance(mood, str)
        or mood not in INTENTIONAL_BREAK_MOOD_VALUES
        or not str(checkout_version or "").strip()
    ):
        raise IntentionalBreakStorageError(
            "checkout_invalid", "All checkout answers and a checkout version are required"
        )


def submit_intentional_break_checkout(
    conn,
    *,
    participant_id: str,
    session_id: str,
    worthwhile_answer=None,
    perceived_control_answer=None,
    mood_answer=None,
    checkout_version: str,
    submission_idempotency_key: str | None = None,
    worthwhile=None,
    perceived_control=None,
    mood=None,
    idempotency_key: str | None = None,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict:
    """Store the sole checkout and start its server-timed cooldown atomically."""
    worthwhile_value = worthwhile_answer if worthwhile_answer is not None else worthwhile
    control_value = (
        perceived_control_answer
        if perceived_control_answer is not None
        else perceived_control
    )
    mood_value = mood_answer if mood_answer is not None else mood
    _validate_checkout_answers(
        worthwhile_value, control_value, mood_value, checkout_version
    )
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    key = _require_idempotency_key(submission_idempotency_key or idempotency_key)
    material = {
        "worthwhile_answer": worthwhile_value,
        "perceived_control_answer": control_value,
        "mood_answer": mood_value,
        "checkout_version": checkout_version,
    }
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        session = _select_journey_session(
            cur, backend=backend, session_id=session_id, participant_id=participant_id
        )
        replay = _command_replay(
            cur,
            backend=backend,
            session=session,
            event_type="checkout_submitted",
            idempotency_key=key,
            material=material,
        )
        if replay:
            result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
            conn.commit()
            return result
        if _checkout_row(cur, backend=backend, session_id=session_id) is not None:
            raise IntentionalBreakStorageError(
                "checkout_invalid", "Checkout has already been submitted"
            )
        if session["journey_state"] != "checkout":
            raise IntentionalBreakStorageError(
                "invalid_transition", "Checkout is allowed only from checkout state"
            )
        ph = _placeholder(backend)
        database_control = (
            _json_value(backend, control_value) if backend == "postgres" else control_value
        )
        cur.execute(
            f"INSERT INTO research_session_checkouts ("
            f"session_id, participant_id, worthwhile_answer, perceived_control_answer, "
            f"mood_answer, checkout_version, submitted_at"
            f") VALUES ({', '.join([ph] * 7)})",
            (
                session_id,
                participant_id,
                worthwhile_value,
                database_control,
                mood_value,
                checkout_version,
                _db_timestamp(backend, current_time),
            ),
        )
        checkout_event = _allocate_and_insert_canonical_event(
            cur,
            backend=backend,
            session=session,
            participant_id=participant_id,
            event_type="checkout_submitted",
            authority="server",
            occurred_at=current_time,
            metadata={"idempotency_key": key, "material": material},
        )
        cooldown_ends_at = current_time + timedelta(
            seconds=int(session["selected_cooldown_seconds"])
        )
        cooldown_event = _allocate_and_insert_canonical_event(
            cur,
            backend=backend,
            session=session,
            participant_id=participant_id,
            event_type="cooldown_started",
            authority="server",
            occurred_at=current_time,
            metadata={
                "selected_cooldown_seconds": int(session["selected_cooldown_seconds"]),
                "checkout_event_id": checkout_event["event_id"],
            },
        )
        cur.execute(
            f"UPDATE research_sessions SET journey_state = 'cooldown', "
            f"cooldown_started_at = {ph}, cooldown_ends_at = {ph} "
            f"WHERE id = {ph} AND journey_state = 'checkout'",
            (
                _db_timestamp(backend, current_time),
                _db_timestamp(backend, cooldown_ends_at),
                session_id,
            ),
        )
        if cur.rowcount != 1:
            raise IntentionalBreakStorageError("invalid_transition", "Session state changed")
        session.update({
            "journey_state": "cooldown",
            "cooldown_started_at": current_time,
            "cooldown_ends_at": cooldown_ends_at,
        })
        result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
        result["checkout_event"] = checkout_event
        result["cooldown_event"] = cooldown_event
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError(
            "checkout_invalid", "Unable to submit checkout"
        ) from exc


def reconcile_intentional_break_cooldown(
    conn,
    *,
    participant_id: str,
    session_id: str,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict:
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        session = _select_journey_session(
            cur, backend=backend, session_id=session_id, participant_id=participant_id
        )
        _reconcile_cooldown_in_transaction(
            cur, backend=backend, session=session, now=current_time
        )
        result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError(
            "invalid_transition", "Unable to reconcile cooldown"
        ) from exc


def start_intentional_break_override(
    conn,
    *,
    participant_id: str,
    session_id: str,
    idempotency_key: str,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict:
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    key = _require_idempotency_key(idempotency_key)
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        session = _select_journey_session(
            cur, backend=backend, session_id=session_id, participant_id=participant_id
        )
        if session["journey_state"] == "cooldown":
            _reconcile_cooldown_in_transaction(
                cur, backend=backend, session=session, now=current_time
            )
        if session["journey_state"] == "completed" and session["cooldown_outcome"] == "completed":
            result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
            conn.commit()
            return result
        replay = _command_replay(
            cur,
            backend=backend,
            session=session,
            event_type="cooldown_override_started",
            idempotency_key=key,
            material={},
        )
        if replay or (
            session["journey_state"] == "cooldown" and session["override_started_at"] is not None
        ):
            result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
            conn.commit()
            return result
        if session["journey_state"] != "cooldown":
            raise IntentionalBreakStorageError(
                "invalid_transition", "Override may start only during cooldown"
            )
        available_at = current_time + timedelta(seconds=15)
        _allocate_and_insert_canonical_event(
            cur,
            backend=backend,
            session=session,
            participant_id=participant_id,
            event_type="cooldown_override_started",
            authority="server",
            occurred_at=current_time,
            metadata={"idempotency_key": key, "material": {}},
        )
        ph = _placeholder(backend)
        cur.execute(
            f"UPDATE research_sessions SET override_started_at = {ph}, "
            f"override_available_at = {ph} WHERE id = {ph} AND journey_state = 'cooldown' "
            f"AND override_started_at IS NULL",
            (
                _db_timestamp(backend, current_time),
                _db_timestamp(backend, available_at),
                session_id,
            ),
        )
        if cur.rowcount != 1:
            raise IntentionalBreakStorageError("invalid_transition", "Override state changed")
        session.update({
            "override_started_at": current_time,
            "override_available_at": available_at,
        })
        result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError(
            "invalid_transition", "Unable to start cooldown override"
        ) from exc


def confirm_intentional_break_override(
    conn,
    *,
    participant_id: str,
    session_id: str,
    reason_code: str,
    confirmation_idempotency_key: str | None = None,
    idempotency_key: str | None = None,
    backend: str | None = None,
    now: datetime | str | None = None,
) -> dict:
    backend = _intentional_backend(conn, backend)
    current_time = _intentional_now(now)
    key = _require_idempotency_key(confirmation_idempotency_key or idempotency_key)
    material = {"reason_code": reason_code}
    cur = _begin_intentional_transaction(conn, backend)
    try:
        _participant_for_journey(cur, backend=backend, participant_id=participant_id)
        session = _select_journey_session(
            cur, backend=backend, session_id=session_id, participant_id=participant_id
        )
        replay = _command_replay(
            cur,
            backend=backend,
            session=session,
            event_type="cooldown_overridden",
            idempotency_key=key,
            material=material,
        )
        if replay:
            result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
            conn.commit()
            return result
        if session["journey_state"] == "cooldown":
            _reconcile_cooldown_in_transaction(
                cur, backend=backend, session=session, now=current_time
            )
        if session["journey_state"] == "completed" and session["cooldown_outcome"] == "completed":
            result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
            conn.commit()
            return result
        if session["journey_state"] != "cooldown":
            raise IntentionalBreakStorageError(
                "invalid_transition", "Override may be confirmed only during cooldown"
            )
        if session["override_started_at"] is None or session["override_available_at"] is None:
            raise IntentionalBreakStorageError(
                "override_not_started", "Cooldown override has not been started"
            )
        available_at = _as_utc_datetime(session["override_available_at"])
        if current_time < available_at:
            raise IntentionalBreakStorageError(
                "override_pause_active",
                "Cooldown override pause is still active",
                details={"override_available_at": available_at.isoformat()},
            )
        if (
            not isinstance(reason_code, str)
            or reason_code not in INTENTIONAL_BREAK_OVERRIDE_REASONS
        ):
            raise IntentionalBreakStorageError(
                "event_not_allowed", "Unsupported override reason"
            )
        _allocate_and_insert_canonical_event(
            cur,
            backend=backend,
            session=session,
            participant_id=participant_id,
            event_type="cooldown_overridden",
            authority="server",
            occurred_at=current_time,
            metadata={"idempotency_key": key, "material": material},
        )
        ph = _placeholder(backend)
        cur.execute(
            f"UPDATE research_sessions SET journey_state = 'completed', status = 'completed', "
            f"override_reason = {ph}, cooldown_outcome = 'overridden', "
            f"cooldown_completed_at = {ph}, completed_at = {ph} "
            f"WHERE id = {ph} AND journey_state = 'cooldown'",
            (
                reason_code,
                _db_timestamp(backend, current_time),
                _db_timestamp(backend, current_time),
                session_id,
            ),
        )
        if cur.rowcount != 1:
            raise IntentionalBreakStorageError("invalid_transition", "Cooldown state changed")
        session.update({
            "journey_state": "completed",
            "status": "completed",
            "override_reason": reason_code,
            "cooldown_outcome": "overridden",
            "cooldown_completed_at": current_time,
            "completed_at": current_time,
        })
        result = _journey_snapshot(cur, backend=backend, session=session, now=current_time)
        conn.commit()
        return result
    except IntentionalBreakStorageError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise IntentionalBreakStorageError(
            "invalid_transition", "Unable to confirm cooldown override"
        ) from exc
