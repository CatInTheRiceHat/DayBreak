import sqlite3
from datetime import datetime, timezone

import pytest

from core.research_storage import (
    ResearchConflictError,
    authenticate_participant,
    complete_session,
    create_participant,
    ensure_sqlite_research_tables,
    insert_event_batch,
    record_feed_items,
    start_session,
)


FEED_REQUEST_ID = "77777777-7777-4777-8777-777777777777"


def connection(tmp_path):
    conn = sqlite3.connect(tmp_path / "research.db")
    ensure_sqlite_research_tables(conn)
    return conn


def new_session(conn, *, condition="balanced"):
    participant = create_participant(conn, backend="sqlite", condition=condition)
    authenticated = authenticate_participant(
        conn,
        backend="sqlite",
        access_token=participant["access_token"],
    )
    session = start_session(
        conn,
        backend="sqlite",
        participant=authenticated,
        application_version="test-build",
        client_timestamp=datetime.now(timezone.utc),
    )
    record_feed_items(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=session["session_id"],
        feed_request_id=FEED_REQUEST_ID,
        items=[{
            "post_id": "video-1",
            "feed_position": 0,
            "content_category": "positive",
            "feed_policy_version": session["feed_policy_version"],
            "selection_bucket": "healthy" if condition == "balanced" else "normal",
            "selection_reason": (
                "healthy_category_target"
                if condition == "balanced"
                else "existing_chrysalis_rank"
            ),
        }],
    )
    return participant, session


def event(event_id, sequence_number, event_type="post_liked"):
    return {
        "event_id": event_id,
        "sequence_number": sequence_number,
        "event_type": event_type,
        "post_id": "video-1",
        "content_category": "positive",
        "client_timestamp": datetime.now(timezone.utc),
        "metadata": {
            "interaction_source": "action_rail",
            "feed_request_id": FEED_REQUEST_ID,
        },
    }


def test_creates_anonymous_participant_without_identity_fields(tmp_path):
    conn = connection(tmp_path)
    participant = create_participant(conn, backend="sqlite", condition="regular")

    assert participant["assigned_condition"] == "regular"
    assert participant["participant_id"]
    assert participant["access_token"]
    columns = {row[1] for row in conn.execute("PRAGMA table_info(research_participants)")}
    assert not ({"name", "email", "phone", "ip_address", "school"} & columns)
    conn.close()


def test_each_started_session_is_separate_and_inherits_condition(tmp_path):
    conn = connection(tmp_path)
    participant = create_participant(conn, backend="sqlite", condition="balanced")
    authenticated = authenticate_participant(
        conn, backend="sqlite", access_token=participant["access_token"]
    )
    first = start_session(
        conn,
        backend="sqlite",
        participant=authenticated,
        application_version="one",
        client_timestamp=datetime.now(timezone.utc),
    )
    second = start_session(
        conn,
        backend="sqlite",
        participant=authenticated,
        application_version="one",
        client_timestamp=datetime.now(timezone.utc),
    )

    assert first["session_id"] != second["session_id"]
    assert first["participant_id"] == second["participant_id"]
    assert first["feed_condition"] == second["feed_condition"] == "balanced"
    assert conn.execute(
        "SELECT count(*) FROM research_events WHERE event_type = 'session_started'"
    ).fetchone()[0] == 2
    conn.close()


def test_duplicate_event_id_is_acknowledged_but_inserted_once(tmp_path):
    conn = connection(tmp_path)
    participant, session = new_session(conn)
    row = event("11111111-1111-4111-8111-111111111111", 1)

    first = insert_event_batch(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=session["session_id"],
        events=[row],
    )
    second = insert_event_batch(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=session["session_id"],
        events=[row],
    )

    assert len(first["accepted"]) == 1
    assert second["duplicates"] == [row["event_id"]]
    assert conn.execute(
        "SELECT count(*) FROM research_events WHERE id = ?", (row["event_id"],)
    ).fetchone()[0] == 1
    conn.close()


def test_out_of_order_events_are_stored_by_sequence(tmp_path):
    conn = connection(tmp_path)
    participant, session = new_session(conn)
    late = event("22222222-2222-4222-8222-222222222222", 2, "post_unliked")
    early = event("33333333-3333-4333-8333-333333333333", 1, "post_liked")

    insert_event_batch(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=session["session_id"],
        events=[late],
    )
    insert_event_batch(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=session["session_id"],
        events=[early],
    )

    assert conn.execute(
        "SELECT event_type FROM research_events WHERE sequence_number > 0 "
        "ORDER BY sequence_number"
    ).fetchall() == [("post_liked",), ("post_unliked",)]
    conn.close()


def test_sequence_number_cannot_be_reused_for_a_different_event(tmp_path):
    conn = connection(tmp_path)
    participant, session = new_session(conn)
    first = event("44444444-4444-4444-8444-444444444444", 1)
    conflicting = event("55555555-5555-4555-8555-555555555555", 1, "post_unliked")
    insert_event_batch(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=session["session_id"],
        events=[first],
    )

    with pytest.raises(ResearchConflictError):
        insert_event_batch(
            conn,
            backend="sqlite",
            participant_id=participant["participant_id"],
            session_id=session["session_id"],
            events=[conflicting],
        )
    conn.close()


def test_completion_is_atomic_and_idempotent(tmp_path):
    conn = connection(tmp_path)
    participant, session = new_session(conn, condition="regular")
    completion = {
        "event_id": "66666666-6666-4666-8666-666666666666",
        "sequence_number": 1,
        "client_timestamp": datetime.now(timezone.utc),
        "metadata": {},
    }

    first = complete_session(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=session["session_id"],
        event=completion,
    )
    retry = complete_session(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=session["session_id"],
        event=completion,
    )

    assert first["status"] == "completed"
    assert first["completed_at"]
    assert retry["duplicate"] is True
    assert conn.execute(
        "SELECT count(*) FROM research_events WHERE event_type = 'session_completed'"
    ).fetchone()[0] == 1
    conn.close()
