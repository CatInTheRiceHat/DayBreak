import sqlite3
import uuid

import pytest

from core.research_storage import ensure_sqlite_research_tables


NOW = "2026-08-05T12:00:00+00:00"
LATER = "2026-08-05T12:05:00+00:00"


def connection(tmp_path):
    conn = sqlite3.connect(tmp_path / f"intentional-{uuid.uuid4()}.db")
    ensure_sqlite_research_tables(conn)
    return conn


def insert_participant(conn, participant_id=None):
    participant_id = participant_id or str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO research_participants (
            id, access_token_hash, assigned_condition, status, created_at
        ) VALUES (?, ?, 'balanced', 'active', ?)
        """,
        (participant_id, f"hash-{participant_id}", NOW),
    )
    return participant_id


def insert_intentional_session(
    conn,
    participant_id,
    *,
    session_id=None,
    journey_state="planned",
    planned_video_count=5,
    selected_cooldown_seconds=300,
    previous_session_id=None,
    **overrides,
):
    session_id = session_id or str(uuid.uuid4())
    values = {
        "id": session_id,
        "participant_id": participant_id,
        "feed_condition": "balanced",
        "feed_policy_version": "balanced-v1",
        "feed_seed": f"seed-{session_id}",
        "application_version": "schema-test",
        # Kept for compatibility only; journey_state is authoritative for v1.
        "status": "completed" if journey_state == "completed" else "active",
        "started_at": NOW,
        "created_at": NOW,
        "journey_version": "intentional_break_v1",
        "journey_state": journey_state,
        "intention": "quick_break",
        "planned_video_count": planned_video_count,
        "estimated_duration_seconds": planned_video_count * 30,
        "suggested_cooldown_seconds": planned_video_count * 60,
        "selected_cooldown_seconds": selected_cooldown_seconds,
        "plan_version": "intentional-break-plan-v1",
        "plan_created_at": NOW,
        "highest_reached_position": 0,
        "previous_session_id": previous_session_id,
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    conn.execute(
        f"INSERT INTO research_sessions ({columns}) VALUES ({placeholders})",
        tuple(values.values()),
    )
    return session_id


def insert_item(conn, participant_id, session_id, *, position=1, post_id="post-1"):
    item_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO research_session_items (
            id, session_id, participant_id, post_id, session_position,
            content_category, feed_policy_version, selection_bucket,
            selection_reason, reserved_at
        ) VALUES (?, ?, ?, ?, ?, 'positive', 'balanced-v1', 'healthy',
                  'healthy_category_target', ?)
        """,
        (item_id, session_id, participant_id, post_id, position, NOW),
    )
    return item_id


def insert_checkout(
    conn,
    participant_id,
    session_id,
    *,
    worthwhile="yes",
    control=3,
    mood="same",
):
    conn.execute(
        """
        INSERT INTO research_session_checkouts (
            session_id, participant_id, worthwhile_answer,
            perceived_control_answer, mood_answer, checkout_version, submitted_at
        ) VALUES (?, ?, ?, ?, ?, 'checkout-v1', ?)
        """,
        (session_id, participant_id, worthwhile, control, mood, NOW),
    )


def insert_event(
    conn,
    participant_id,
    session_id,
    *,
    sequence_number,
    event_type="session_plan_created",
    server_sequence_number=None,
    client_event_id=None,
    client_sequence_number=None,
    event_authority=None,
):
    event_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO research_events (
            id, session_id, participant_id, sequence_number,
            server_sequence_number, client_event_id, client_sequence_number,
            event_type, feed_condition, client_timestamp, server_timestamp,
            received_at, event_authority, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'balanced', NULL, ?, ?, ?, '{}')
        """,
        (
            event_id,
            session_id,
            participant_id,
            sequence_number,
            server_sequence_number,
            client_event_id,
            client_sequence_number,
            event_type,
            NOW,
            NOW,
            event_authority,
        ),
    )
    return event_id


def test_legacy_sessions_remain_valid_and_do_not_enter_journey_uniqueness(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    for session_id in ("legacy-1", "legacy-2"):
        conn.execute(
            """
            INSERT INTO research_sessions (
                id, participant_id, feed_condition, feed_policy_version, feed_seed,
                application_version, status, started_at, created_at
            ) VALUES (?, ?, 'balanced', 'balanced-v1', ?, 'legacy', 'active', ?, ?)
            """,
            (session_id, participant_id, f"seed-{session_id}", NOW, NOW),
        )

    insert_intentional_session(conn, participant_id)

    assert conn.execute(
        "SELECT count(*) FROM research_sessions WHERE participant_id = ?",
        (participant_id,),
    ).fetchone()[0] == 3


def test_planned_session_and_previous_completed_session_linkage(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    previous_id = insert_intentional_session(
        conn,
        participant_id,
        journey_state="completed",
        completed_at=LATER,
        cooldown_outcome="completed",
        cooldown_completed_at=LATER,
    )
    current_id = insert_intentional_session(
        conn,
        participant_id,
        previous_session_id=previous_id,
    )

    assert conn.execute(
        "SELECT previous_session_id FROM research_sessions WHERE id = ?", (current_id,)
    ).fetchone()[0] == previous_id
    conn.execute("DELETE FROM research_sessions WHERE id = ?", (previous_id,))
    assert conn.execute(
        "SELECT previous_session_id FROM research_sessions WHERE id = ?", (current_id,)
    ).fetchone()[0] is None


@pytest.mark.parametrize("planned_video_count", [0, 6, 15, 41])
def test_unsupported_planned_counts_are_rejected(tmp_path, planned_video_count):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_intentional_session(
            conn, participant_id, planned_video_count=planned_video_count
        )


def test_frozen_estimated_duration_is_enforced(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_intentional_session(conn, participant_id, estimated_duration_seconds=151)


@pytest.mark.parametrize("selected_cooldown_seconds", [0, 301, 7500])
def test_invalid_cooldown_increments_and_ranges_are_rejected(
    tmp_path, selected_cooldown_seconds
):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_intentional_session(
            conn,
            participant_id,
            selected_cooldown_seconds=selected_cooldown_seconds,
        )


def test_one_nonterminal_intentional_break_session_per_participant(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    insert_intentional_session(conn, participant_id, journey_state="active")

    with pytest.raises(sqlite3.IntegrityError):
        insert_intentional_session(conn, participant_id, journey_state="cooldown")


def test_participant_may_have_multiple_completed_intentional_break_sessions(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    insert_intentional_session(conn, participant_id, journey_state="completed")
    insert_intentional_session(conn, participant_id, journey_state="completed")

    assert conn.execute(
        "SELECT count(*) FROM research_sessions WHERE participant_id = ?",
        (participant_id,),
    ).fetchone()[0] == 2


def test_session_item_position_and_membership_constraints(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    session_id = insert_intentional_session(conn, participant_id)

    with pytest.raises(sqlite3.IntegrityError):
        insert_item(conn, participant_id, session_id, position=0)

    insert_item(conn, participant_id, session_id, position=1, post_id="post-1")
    with pytest.raises(sqlite3.IntegrityError):
        insert_item(conn, participant_id, session_id, position=1, post_id="post-2")
    with pytest.raises(sqlite3.IntegrityError):
        insert_item(conn, participant_id, session_id, position=2, post_id="post-1")


def test_same_post_can_appear_in_different_sessions(tmp_path):
    conn = connection(tmp_path)
    first_participant = insert_participant(conn)
    second_participant = insert_participant(conn)
    first_session = insert_intentional_session(conn, first_participant)
    second_session = insert_intentional_session(conn, second_participant)

    insert_item(conn, first_participant, first_session, post_id="shared-post")
    insert_item(conn, second_participant, second_session, post_id="shared-post")

    assert conn.execute(
        "SELECT count(*) FROM research_session_items WHERE post_id = 'shared-post'"
    ).fetchone()[0] == 2


def test_session_item_requires_session_owner_and_cascades(tmp_path):
    conn = connection(tmp_path)
    owner_id = insert_participant(conn)
    other_id = insert_participant(conn)
    session_id = insert_intentional_session(conn, owner_id)

    with pytest.raises(sqlite3.IntegrityError):
        insert_item(conn, other_id, session_id)

    insert_item(conn, owner_id, session_id)
    conn.execute("DELETE FROM research_sessions WHERE id = ?", (session_id,))
    assert conn.execute("SELECT count(*) FROM research_session_items").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("worthwhile", "control", "mood"),
    [
        ("yes", 1, "better"),
        ("mostly", 5, "same"),
        ("prefer_not_to_answer", "prefer_not_to_answer", "prefer_not_to_answer"),
    ],
)
def test_valid_checkout_answers_are_accepted(tmp_path, worthwhile, control, mood):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    session_id = insert_intentional_session(conn, participant_id)
    insert_checkout(
        conn,
        participant_id,
        session_id,
        worthwhile=worthwhile,
        control=control,
        mood=mood,
    )

    assert conn.execute("SELECT count(*) FROM research_session_checkouts").fetchone()[0] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("worthwhile", "maybe"),
        ("control", 0),
        ("control", 6),
        ("control", "3"),
        ("mood", "mixed"),
    ],
)
def test_invalid_checkout_answers_are_rejected(tmp_path, field, value):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    session_id = insert_intentional_session(conn, participant_id)
    answers = {"worthwhile": "yes", "control": 3, "mood": "same", field: value}

    with pytest.raises(sqlite3.IntegrityError):
        insert_checkout(conn, participant_id, session_id, **answers)


def test_checkout_is_one_to_one_owner_checked_and_cascades(tmp_path):
    conn = connection(tmp_path)
    owner_id = insert_participant(conn)
    other_id = insert_participant(conn)
    session_id = insert_intentional_session(conn, owner_id)

    with pytest.raises(sqlite3.IntegrityError):
        insert_checkout(conn, other_id, session_id)
    insert_checkout(conn, owner_id, session_id)
    with pytest.raises(sqlite3.IntegrityError):
        insert_checkout(conn, owner_id, session_id)

    conn.execute("DELETE FROM research_sessions WHERE id = ?", (session_id,))
    assert conn.execute("SELECT count(*) FROM research_session_checkouts").fetchone()[0] == 0


def test_canonical_server_sequence_is_unique_only_within_a_session(tmp_path):
    conn = connection(tmp_path)
    first_participant = insert_participant(conn)
    second_participant = insert_participant(conn)
    first_session = insert_intentional_session(conn, first_participant)
    second_session = insert_intentional_session(conn, second_participant)

    insert_event(
        conn,
        first_participant,
        first_session,
        sequence_number=10,
        server_sequence_number=1,
    )
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(
            conn,
            first_participant,
            first_session,
            sequence_number=11,
            server_sequence_number=1,
            event_type="checkout_submitted",
        )
    insert_event(
        conn,
        second_participant,
        second_session,
        sequence_number=10,
        server_sequence_number=1,
    )


def test_client_diagnostic_sequence_is_independent_of_canonical_order(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    session_id = insert_intentional_session(conn, participant_id)

    insert_event(
        conn,
        participant_id,
        session_id,
        sequence_number=20,
        server_sequence_number=1,
        client_sequence_number=7,
    )
    insert_event(
        conn,
        participant_id,
        session_id,
        sequence_number=21,
        server_sequence_number=2,
        client_sequence_number=1,
        event_type="checkout_submitted",
    )

    assert conn.execute(
        "SELECT server_sequence_number, client_sequence_number FROM research_events "
        "ORDER BY server_sequence_number"
    ).fetchall() == [(1, 7), (2, 1)]


def test_historical_event_shape_and_client_uuid_idempotency_remain_supported(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    session_id = insert_intentional_session(conn, participant_id)
    conn.execute(
        """
        INSERT INTO research_events (
            id, session_id, participant_id, sequence_number, event_type,
            feed_condition, client_timestamp, server_timestamp, metadata
        ) VALUES ('legacy-event', ?, ?, 0, 'session_started', 'balanced', ?, ?, '{}')
        """,
        (session_id, participant_id, NOW, NOW),
    )
    client_event_id = str(uuid.uuid4())
    insert_event(
        conn,
        participant_id,
        session_id,
        sequence_number=1,
        server_sequence_number=1,
        client_event_id=client_event_id,
        event_type="checkout_submitted",
    )
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(
            conn,
            participant_id,
            session_id,
            sequence_number=2,
            server_sequence_number=2,
            client_event_id=client_event_id,
            event_type="cooldown_started",
        )

    assert conn.execute(
        "SELECT server_sequence_number FROM research_events WHERE id = 'legacy-event'"
    ).fetchone()[0] is None


def test_next_server_sequence_counter_can_advance_transactionally(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    session_id = insert_intentional_session(conn, participant_id)

    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    allocated = conn.execute(
        """
        UPDATE research_sessions
        SET next_server_sequence_number = next_server_sequence_number + 1
        WHERE id = ?
        RETURNING next_server_sequence_number - 1
        """,
        (session_id,),
    ).fetchone()[0]
    conn.commit()

    assert allocated == 0
    assert conn.execute(
        "SELECT next_server_sequence_number FROM research_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()[0] == 1


def test_server_lifecycle_events_are_semantically_one_time_and_mutually_exclusive(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    session_id = insert_intentional_session(conn, participant_id)
    insert_event(
        conn,
        participant_id,
        session_id,
        sequence_number=1,
        server_sequence_number=1,
        event_type="session_finished_early",
        event_authority="server",
    )
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(
            conn,
            participant_id,
            session_id,
            sequence_number=2,
            server_sequence_number=2,
            event_type="session_finished_early",
            event_authority="server",
        )
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(
            conn,
            participant_id,
            session_id,
            sequence_number=3,
            server_sequence_number=3,
            event_type="session_boundary_reached",
            event_authority="server",
        )


@pytest.mark.parametrize(
    ("started_at", "ends_at"),
    [("2026-08-05T12:10:00+00:00", "2026-08-05T12:09:59+00:00")],
)
def test_cooldown_end_cannot_precede_start(tmp_path, started_at, ends_at):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_intentional_session(
            conn,
            participant_id,
            journey_state="cooldown",
            cooldown_started_at=started_at,
            cooldown_ends_at=ends_at,
        )


def test_override_available_cannot_precede_override_start(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_intentional_session(
            conn,
            participant_id,
            journey_state="cooldown",
            override_started_at="2026-08-05T12:00:15+00:00",
            override_available_at="2026-08-05T12:00:14+00:00",
        )


def test_invalid_override_reason_is_rejected(tmp_path):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_intentional_session(
            conn,
            participant_id,
            journey_state="completed",
            cooldown_outcome="overridden",
            override_reason="skip_wait",
        )


@pytest.mark.parametrize("cooldown_outcome", ["completed", "overridden"])
def test_terminal_cooldown_outcomes_are_representable(tmp_path, cooldown_outcome):
    conn = connection(tmp_path)
    participant_id = insert_participant(conn)
    session_id = insert_intentional_session(
        conn,
        participant_id,
        journey_state="completed",
        completed_at=LATER,
        cooldown_started_at=NOW,
        cooldown_ends_at=LATER,
        cooldown_outcome=cooldown_outcome,
        cooldown_completed_at=LATER,
        override_reason="change_plan" if cooldown_outcome == "overridden" else None,
    )
    assert conn.execute(
        "SELECT cooldown_outcome FROM research_sessions WHERE id = ?", (session_id,)
    ).fetchone()[0] == cooldown_outcome


def test_legacy_schema_upgrade_preserves_rows_and_enables_v1(tmp_path):
    conn = sqlite3.connect(tmp_path / "legacy-upgrade.db")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE research_participants (
            id TEXT PRIMARY KEY,
            access_token_hash TEXT NOT NULL UNIQUE,
            assigned_condition TEXT NOT NULL CHECK (assigned_condition IN ('regular', 'balanced')),
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            withdrawn_at TEXT,
            deletion_requested_at TEXT
        );
        CREATE TABLE research_sessions (
            id TEXT PRIMARY KEY,
            participant_id TEXT NOT NULL REFERENCES research_participants(id) ON DELETE CASCADE,
            feed_condition TEXT NOT NULL CHECK (feed_condition IN ('regular', 'balanced')),
            feed_policy_version TEXT NOT NULL,
            feed_seed TEXT NOT NULL,
            application_version TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            withdrawn_at TEXT,
            deletion_requested_at TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE research_events (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
            participant_id TEXT NOT NULL REFERENCES research_participants(id) ON DELETE CASCADE,
            sequence_number INTEGER NOT NULL CHECK (sequence_number >= 0),
            event_type TEXT NOT NULL CHECK (event_type IN ('session_started', 'post_liked')),
            post_id TEXT,
            content_category TEXT,
            feed_condition TEXT NOT NULL,
            client_timestamp TEXT NOT NULL,
            server_timestamp TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            UNIQUE (session_id, sequence_number)
        );
        CREATE TABLE research_feed_items (
            id TEXT PRIMARY KEY,
            feed_request_id TEXT NOT NULL,
            session_id TEXT NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
            participant_id TEXT NOT NULL REFERENCES research_participants(id) ON DELETE CASCADE,
            post_id TEXT NOT NULL,
            feed_position INTEGER NOT NULL,
            content_category TEXT NOT NULL,
            feed_policy_version TEXT NOT NULL,
            selection_bucket TEXT NOT NULL,
            selection_reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (feed_request_id, post_id),
            UNIQUE (feed_request_id, feed_position)
        );
        INSERT INTO research_participants
            VALUES ('participant-1', 'legacy-hash', 'regular', 'active',
                    '2026-01-01T00:00:00+00:00', NULL, NULL);
        INSERT INTO research_sessions
            VALUES ('legacy-session', 'participant-1', 'regular', 'regular-v1',
                    'legacy-seed', 'legacy-app', 'active',
                    '2026-01-01T00:00:00+00:00', NULL, NULL, NULL,
                    '2026-01-01T00:00:00+00:00');
        INSERT INTO research_events
            VALUES ('legacy-event', 'legacy-session', 'participant-1', 7,
                    'post_liked', 'legacy-post', 'regular', 'regular',
                    '2026-01-01T00:01:00+00:00', '2026-01-01T00:01:01+00:00', '{}');
        INSERT INTO research_feed_items
            VALUES ('legacy-feed-item', 'legacy-request', 'legacy-session',
                    'participant-1', 'legacy-post', 0, 'regular', 'regular-v1',
                    'normal', 'existing_chrysalis_rank',
                    '2026-01-01T00:00:30+00:00');
        """
    )

    ensure_sqlite_research_tables(conn)

    assert conn.execute(
        "SELECT status, journey_version FROM research_sessions WHERE id = 'legacy-session'"
    ).fetchone() == ("active", None)
    assert conn.execute(
        "SELECT post_id FROM research_feed_items WHERE id = 'legacy-feed-item'"
    ).fetchone()[0] == "legacy-post"
    assert conn.execute(
        "SELECT server_sequence_number, received_at FROM research_events "
        "WHERE id = 'legacy-event'"
    ).fetchone() == (7, "2026-01-01T00:01:01+00:00")
    assert conn.execute(
        "SELECT next_server_sequence_number FROM research_sessions "
        "WHERE id = 'legacy-session'"
    ).fetchone()[0] == 8

    insert_intentional_session(conn, "participant-1", session_id="new-v1-session")
    assert conn.execute(
        "SELECT journey_state FROM research_sessions WHERE id = 'new-v1-session'"
    ).fetchone()[0] == "planned"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
