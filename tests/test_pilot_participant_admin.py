import sqlite3
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.research_storage import (
    ResearchNotFoundError,
    authenticate_participant,
    create_intentional_break_plan,
    create_participant,
    ensure_sqlite_research_tables,
    record_feed_items,
    start_session,
)
from research_api import INTENTIONAL_BREAK_API_PREFIX, create_research_router
from scripts.pilot_participant_admin import (
    AdminError,
    _print_preview,
    _require_production_delete_confirmation,
    delete_participant,
    exact_participant_id,
    main,
    preview_participant,
    retention_preview,
    set_participant_retention,
    withdraw_participant,
)


NOW = datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc)
BASE = f"/api/research{INTENTIONAL_BREAK_API_PREFIX}"


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "pilot-admin.db"
    conn = sqlite3.connect(path)
    ensure_sqlite_research_tables(conn)
    yield conn, path
    conn.close()


def reserved_items(prefix="pilot"):
    return [
        {
            "post_id": f"{prefix}-post-{position}",
            "content_category": "positive",
            "source_type": "research_feed",
            "feed_request_id": f"{prefix}-request",
            "feed_policy_version": "balanced-v1",
            "selection_bucket": "healthy",
            "selection_reason": "healthy_category_target",
            "ranking_snapshot": {"private_score": position},
            "provenance_metadata": {"fixture": True},
        }
        for position in range(1, 6)
    ]


def participant_graph(conn, *, prefix="target"):
    participant = create_participant(conn, backend="sqlite", condition="balanced")
    authenticated = authenticate_participant(
        conn, backend="sqlite", access_token=participant["access_token"]
    )
    legacy = start_session(
        conn,
        backend="sqlite",
        participant=authenticated,
        application_version="pilot-rehearsal",
        client_timestamp=NOW,
    )
    record_feed_items(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=legacy["session_id"],
        feed_request_id=str(uuid.uuid4()),
        items=[{
            "post_id": f"{prefix}-legacy-post",
            "feed_position": 0,
            "content_category": "positive",
            "feed_policy_version": "balanced-v1",
            "selection_bucket": "healthy",
            "selection_reason": "healthy_category_target",
        }],
    )
    plan = create_intentional_break_plan(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        intention="quick_break",
        planned_video_count=5,
        selected_cooldown_seconds=300,
        reserved_items=reserved_items(prefix),
        plan_idempotency_key=f"{prefix}-plan-key",
        now=NOW,
    )
    conn.execute(
        "INSERT INTO research_session_checkouts "
        "(session_id, participant_id, worthwhile_answer, perceived_control_answer, "
        "mood_answer, checkout_version, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            plan["session_id"],
            participant["participant_id"],
            "yes",
            3,
            "same",
            "intentional-break-v1",
            NOW.isoformat(),
        ),
    )
    conn.commit()
    return participant, legacy, plan


def test_preview_counts_without_mutation_or_secret_output(database, capsys):
    conn, _path = database
    participant, _legacy, plan = participant_graph(conn)
    before_changes = conn.total_changes

    preview = preview_participant(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
    )
    _print_preview(preview)
    output = capsys.readouterr().out

    assert preview["session_count"] == 2
    assert preview["event_count"] == 2
    assert preview["legacy_feed_item_count"] == 1
    assert preview["reserved_item_count"] == 5
    assert preview["checkout_count"] == 1
    assert preview["nonterminal_session_id"] == plan["session_id"]
    assert preview["nonterminal_journey_state"] == "planned"
    assert conn.total_changes == before_changes
    assert participant["access_token"] not in output
    token_hash = conn.execute(
        "SELECT access_token_hash FROM research_participants WHERE id = ?",
        (participant["participant_id"],),
    ).fetchone()[0]
    private_seed = conn.execute(
        "SELECT feed_seed FROM research_sessions WHERE id = ?",
        (plan["session_id"],),
    ).fetchone()[0]
    assert token_hash not in output
    assert private_seed not in output
    assert "ranking_snapshot" not in output


def test_preview_missing_or_partial_participant_fails_safely(database):
    conn, _path = database
    with pytest.raises(AdminError, match="participant not found"):
        preview_participant(
            conn, backend="sqlite", participant_id=str(uuid.uuid4())
        )
    with pytest.raises(AdminError, match="one complete UUID"):
        exact_participant_id("1234")


def test_withdraw_preserves_data_invalidates_token_and_is_repeatable(database):
    conn, _path = database
    participant, _legacy, _plan = participant_graph(conn)
    other = create_participant(conn, backend="sqlite", condition="regular")

    first = withdraw_participant(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        now=NOW,
    )
    second = withdraw_participant(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        now=NOW.replace(hour=19),
    )

    assert first["after"]["status"] == "withdrawn"
    assert first["after"]["withdrawn_at"] == NOW.isoformat()
    assert second["after"]["withdrawn_at"] == NOW.isoformat()
    assert second["after"]["session_count"] == 2
    authenticated = authenticate_participant(
        conn, backend="sqlite", access_token=participant["access_token"]
    )
    assert authenticated["status"] == "withdrawn"
    assert conn.execute(
        "SELECT status FROM research_participants WHERE id = ?",
        (other["participant_id"],),
    ).fetchone()[0] == "active"


def test_withdraw_preserves_pending_deletion_status(database):
    conn, _path = database
    participant = create_participant(conn, backend="sqlite", condition="balanced")
    conn.execute(
        "UPDATE research_participants SET status = 'deletion_requested', "
        "deletion_requested_at = ? WHERE id = ?",
        (NOW.isoformat(), participant["participant_id"]),
    )
    conn.commit()

    result = withdraw_participant(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        now=NOW,
    )
    assert result["after"]["status"] == "deletion_requested"
    assert result["after"]["withdrawn_at"] == NOW.isoformat()
    assert result["after"]["deletion_requested_at"] == NOW.isoformat()


def test_delete_cascades_every_research_table_and_preserves_other_participant(database):
    conn, _path = database
    target, _legacy, _plan = participant_graph(conn)
    other, _other_legacy, _other_plan = participant_graph(conn, prefix="other")

    result = delete_participant(
        conn,
        backend="sqlite",
        participant_id=target["participant_id"],
    )

    assert result["participant_remaining"] == 0
    assert result["related_rows_remaining"] == {
        "research_sessions": 0,
        "research_events": 0,
        "research_feed_items": 0,
        "research_session_items": 0,
        "research_session_checkouts": 0,
    }
    assert result["unrelated_participants_preserved"] is True
    assert authenticate_participant(
        conn, backend="sqlite", access_token=other["access_token"]
    )["status"] == "active"
    with pytest.raises(ResearchNotFoundError):
        authenticate_participant(
            conn, backend="sqlite", access_token=target["access_token"]
        )


def test_delete_missing_participant_and_missing_confirmation_are_safe(database):
    conn, path = database
    participant, _legacy, _plan = participant_graph(conn)
    missing = str(uuid.uuid4())
    with pytest.raises(AdminError, match="participant not found"):
        delete_participant(conn, backend="sqlite", participant_id=missing)

    result = main([
        "--backend",
        "sqlite",
        "--db-path",
        str(path),
        "delete",
        "--participant-id",
        participant["participant_id"],
        "--confirm-participant-id",
        str(uuid.uuid4()),
    ])
    assert result != 0
    assert authenticate_participant(
        conn, backend="sqlite", access_token=participant["access_token"]
    )["status"] == "active"


def test_postgres_delete_requires_separate_production_confirmation():
    with pytest.raises(AdminError, match="--production-confirm"):
        _require_production_delete_confirmation("postgres", False)
    _require_production_delete_confirmation("postgres", True)
    _require_production_delete_confirmation("sqlite", False)


def test_withdraw_delete_is_atomic_and_invalidates_credential(database):
    conn, _path = database
    participant, _legacy, _plan = participant_graph(conn)

    result = delete_participant(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        withdraw_first=True,
        now=NOW,
    )

    assert result["participant_remaining"] == 0
    assert not any(result["related_rows_remaining"].values())
    with pytest.raises(ResearchNotFoundError):
        authenticate_participant(
            conn, backend="sqlite", access_token=participant["access_token"]
        )


def test_delete_rolls_back_if_cascade_cannot_complete(database):
    conn, _path = database
    participant, _legacy, _plan = participant_graph(conn)
    conn.execute(
        "CREATE TRIGGER prevent_pilot_delete BEFORE DELETE ON research_participants "
        "BEGIN SELECT RAISE(ABORT, 'rehearsal failure'); END"
    )

    with pytest.raises(sqlite3.IntegrityError):
        delete_participant(
            conn,
            backend="sqlite",
            participant_id=participant["participant_id"],
        )
    assert authenticate_participant(
        conn, backend="sqlite", access_token=participant["access_token"]
    )["status"] == "active"
    assert preview_participant(
        conn, backend="sqlite", participant_id=participant["participant_id"]
    )["session_count"] == 2


def test_retention_marking_and_count_only_preview(database):
    conn, _path = database
    participant, _legacy, _plan = participant_graph(conn)
    target = datetime(2027, 2, 5, 0, 0, tzinfo=timezone.utc)

    marked = set_participant_retention(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        retain_until=target,
    )
    changes_before_preview = conn.total_changes
    counts = retention_preview(
        conn, backend="sqlite", before=target
    )

    assert marked["updated_sessions"] == 2
    assert counts["eligible_participant_count"] == 1
    assert counts["eligible_session_count"] == 2
    assert counts["unmarked_session_count"] == 0
    assert conn.total_changes == changes_before_preview


def _api_for_path(path):
    def connect():
        conn = sqlite3.connect(path)
        ensure_sqlite_research_tables(conn)
        return conn

    app = FastAPI()
    app.include_router(create_research_router(
        get_connection=connect,
        backend="sqlite",
        load_feed_source=lambda _conn: ([], None),
        clock=lambda: NOW,
    ))
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("get", "/current", None),
        ("get", "/sessions/{session_id}", None),
        ("post", "/plans", {
            "intention": "quick_break",
            "planned_video_count": 5,
            "selected_cooldown_seconds": 300,
            "idempotency_key": str(uuid.uuid4()),
            "participant_notice_version": "intentional-break-v1",
            "participant_notice_acknowledged": True,
        }),
        ("post", "/sessions/{session_id}/cancel", {"idempotency_key": str(uuid.uuid4())}),
        ("post", "/sessions/{session_id}/start", {"idempotency_key": str(uuid.uuid4())}),
        ("get", "/sessions/{session_id}/items", None),
        ("post", "/sessions/{session_id}/events", {"events": [{
            "client_event_id": str(uuid.uuid4()),
            "client_sequence_number": 1,
            "event_type": "post_impression",
            "post_id": "post-1",
            "client_timestamp": NOW.isoformat(),
            "metadata": {},
        }]}),
        ("post", "/sessions/{session_id}/finish-early", {"idempotency_key": str(uuid.uuid4())}),
        ("post", "/sessions/{session_id}/checkout", {
            "idempotency_key": str(uuid.uuid4()),
            "worthwhile": "yes",
            "perceived_control": 3,
            "mood": "same",
            "checkout_version": "intentional-break-v1",
        }),
        ("get", "/sessions/{session_id}/cooldown", None),
        ("post", "/sessions/{session_id}/override/start", {"idempotency_key": str(uuid.uuid4())}),
        ("post", "/sessions/{session_id}/override/confirm", {
            "idempotency_key": str(uuid.uuid4()),
            "reason_code": "change_plan",
        }),
    ],
)
def test_withdrawn_credential_is_blocked_by_every_intentional_break_endpoint(
    database, method, suffix, body
):
    conn, path = database
    participant = create_participant(conn, backend="sqlite", condition="balanced")
    withdraw_participant(
        conn,
        backend="sqlite",
        participant_id=participant["participant_id"],
        now=NOW,
    )
    session_id = str(uuid.uuid4())
    response = _api_for_path(path).request(
        method,
        f"{BASE}{suffix.format(session_id=session_id)}",
        headers={"Authorization": f"Bearer {participant['access_token']}"},
        json=body,
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "participant_inactive"


def test_deleted_credential_is_invalid_for_intentional_break_api(database):
    conn, path = database
    participant = create_participant(conn, backend="sqlite", condition="balanced")
    delete_participant(
        conn, backend="sqlite", participant_id=participant["participant_id"]
    )

    response = _api_for_path(path).get(
        f"{BASE}/current",
        headers={"Authorization": f"Bearer {participant['access_token']}"},
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "invalid_credential"
