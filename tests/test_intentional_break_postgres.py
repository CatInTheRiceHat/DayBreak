"""Real PostgreSQL verification for migrations 015-017 and Intentional Break.

The entire module skips unless the dedicated destructive-test opt-in is present.
It never reads ``DATABASE_URL`` as a test target and never falls back to SQLite.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.research_storage import (
    IntentionalBreakStorageError,
    ResearchNotFoundError,
    append_intentional_break_client_events,
    authenticate_participant,
    confirm_intentional_break_override,
    create_intentional_break_plan,
    create_participant,
    finish_intentional_break_early,
    read_intentional_break_items,
    reconcile_intentional_break_cooldown,
    record_feed_items,
    start_intentional_break_override,
    start_intentional_break_session,
    start_session,
    submit_intentional_break_checkout,
)
from research_api import INTENTIONAL_BREAK_API_PREFIX, create_research_router
from scripts.pilot_participant_admin import delete_participant
from tests.postgres_test_utils import (
    PostgresHarness,
    connect_postgres,
    delete_test_participants,
    postgres_connection,
    postgres_harness,
    postgres_skip_reason,
    reserved_items,
)


SKIP_REASON = postgres_skip_reason()
pytestmark = pytest.mark.skipif(SKIP_REASON is not None, reason=SKIP_REASON or "")

NOW = datetime(2026, 8, 9, 19, 0, tzinfo=timezone.utc)
BASE = f"/api/research{INTENTIONAL_BREAK_API_PREFIX}"


class Clock:
    def __init__(self, value: datetime = NOW):
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def inventory(count: int = 60) -> list[dict]:
    rows = []
    for index in range(count):
        if index % 10 < 6:
            title = f"Harmless comedy music clip {index}"
            description = "A normal low-risk general interest video with jokes and music."
            category = "comedy"
        elif index % 10 < 9:
            title = f"Calm journaling walk {index}"
            description = "Drink water, stretch, journal with gratitude, and take a gentle walk."
            category = "wellness"
        else:
            title = f"Different perspectives {index}"
            description = "A respectful conversation with an open mind and common ground."
            category = "perspectives"
        rows.append({
            "video_id": f"pg-post-{index}",
            "title": title,
            "description": description,
            "channel_id": f"pg-creator-{index % 17}",
            "channel_title": f"PG Creator {index % 17}",
            "source_category": category,
            "source_query": f"{category} seed",
            "source_type": "search",
            "integrity_score": 0.9,
            "tags": [category],
        })
    return rows


def build_postgres_api(harness: PostgresHarness, clock: Clock | None = None):
    test_clock = clock or Clock()

    def connect():
        return connect_postgres(harness.config)

    app = FastAPI()
    app.include_router(create_research_router(
        get_connection=connect,
        backend="postgres",
        load_feed_source=lambda _conn: (inventory(), None),
        clock=test_clock,
    ))
    return TestClient(app), test_clock


def api_participant(client: TestClient) -> dict:
    response = client.post("/api/research/participants")
    assert response.status_code == 201, response.text
    participant = response.json()
    participant["headers"] = {
        "Authorization": f"Bearer {participant['access_token']}"
    }
    return participant


def api_plan(client: TestClient, participant: dict, *, key: str | None = None) -> dict:
    response = client.post(
        f"{BASE}/plans",
        headers=participant["headers"],
        json={
            "intention": "quick_break",
            "planned_video_count": 5,
            "selected_cooldown_seconds": 300,
            "idempotency_key": key or str(uuid.uuid4()),
            "participant_notice_version": "intentional-break-v1",
            "participant_notice_acknowledged": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["journey"]


def api_command(
    client: TestClient,
    participant: dict,
    session_id: str,
    action: str,
    body: dict | None = None,
):
    return client.post(
        f"{BASE}/sessions/{session_id}/{action}",
        headers=participant["headers"],
        json=body or {"idempotency_key": str(uuid.uuid4())},
    )


def meaningful_impression(post_id: str, *, sequence: int = 1) -> dict:
    return {
        "client_event_id": str(uuid.uuid4()),
        "client_sequence_number": sequence,
        "event_type": "post_impression",
        "post_id": post_id,
        "client_timestamp": NOW.isoformat(),
        "metadata": {"visibility_ratio": 0.75, "visible_ms": 1000},
    }


def create_storage_plan(conn, participant_id: str, prefix: str, *, now=NOW) -> dict:
    return create_intentional_break_plan(
        conn,
        backend="postgres",
        participant_id=participant_id,
        intention="quick_break",
        planned_video_count=5,
        selected_cooldown_seconds=300,
        reserved_items=reserved_items(prefix),
        plan_idempotency_key=f"{prefix}-plan-{uuid.uuid4()}",
        now=now,
    )


def start_storage_plan(conn, participant_id: str, session_id: str, *, now=NOW) -> dict:
    return start_intentional_break_session(
        conn,
        backend="postgres",
        participant_id=participant_id,
        session_id=session_id,
        idempotency_key=f"start-{uuid.uuid4()}",
        now=now,
    )


def storage_checkout(conn, participant_id: str, session_id: str, *, now=NOW) -> dict:
    return submit_intentional_break_checkout(
        conn,
        backend="postgres",
        participant_id=participant_id,
        session_id=session_id,
        worthwhile_answer="yes",
        perceived_control_answer=3,
        mood_answer="same",
        checkout_version="intentional-break-v1",
        submission_idempotency_key=f"checkout-{uuid.uuid4()}",
        now=now,
    )


def test_real_migrations_upgrade_legacy_rows(postgres_harness, postgres_connection):
    assert postgres_harness.migrations_executed == (
        "015_research_sessions_and_events.sql",
        "016_research_feed_policies.sql",
        "017_intentional_break_loop.sql",
    )
    legacy = postgres_harness.legacy
    with postgres_connection.cursor() as cur:
        cur.execute(
            """
            SELECT id, journey_version, journey_state, next_server_sequence_number
            FROM public.research_sessions
            WHERE participant_id = %s ORDER BY id
            """,
            (legacy["participant_id"],),
        )
        sessions = cur.fetchall()
        assert len(sessions) == 2
        assert all(row[1] is None and row[2] is None for row in sessions)
        counters = {str(row[0]): row[3] for row in sessions}
        assert counters[legacy["session_id"]] == 5
        assert counters[legacy["second_session_id"]] == 0

        cur.execute(
            """
            SELECT sequence_number, server_sequence_number,
                   server_timestamp = received_at, metadata
            FROM public.research_events WHERE session_id = %s ORDER BY sequence_number
            """,
            (legacy["session_id"],),
        )
        events = cur.fetchall()
        assert [(row[0], row[1]) for row in events] == [(0, 0), (4, 4)]
        assert all(row[2] for row in events)
        assert events[1][3]["nested"]["source"] == "migration-fixture"

        cur.execute(
            "SELECT count(*) FROM public.research_feed_items "
            "WHERE feed_request_id = %s",
            (legacy["feed_request_id"],),
        )
        assert cur.fetchone()[0] == 1


def test_postgres_catalog_contains_required_objects(postgres_connection):
    expected_session_columns = {
        "journey_version", "journey_state", "intention", "planned_video_count",
        "estimated_duration_seconds", "suggested_cooldown_seconds",
        "selected_cooldown_seconds", "plan_version", "plan_created_at",
        "session_started_at", "finish_reason", "highest_reached_position",
        "boundary_reached_at", "checkout_entered_at", "cooldown_started_at",
        "cooldown_ends_at", "cooldown_outcome", "cooldown_completed_at",
        "override_started_at", "override_available_at", "override_reason",
        "previous_session_id", "cancelled_at", "next_server_sequence_number",
        "retain_until",
    }
    with postgres_connection.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'research_sessions'"
        )
        assert expected_session_columns <= {row[0] for row in cur.fetchall()}

        cur.execute(
            """
            SELECT c.relname, c.relrowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname IN ('research_participants', 'research_sessions',
                  'research_events', 'research_feed_items',
                  'research_session_items', 'research_session_checkouts')
            """
        )
        rls = dict(cur.fetchall())
        assert set(rls) == {
            "research_participants", "research_sessions", "research_events",
            "research_feed_items", "research_session_items",
            "research_session_checkouts",
        }
        assert all(rls.values())

        cur.execute(
            """
            SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name IN ('research_session_items',
                                 'research_session_checkouts', 'research_events')
            """
        )
        columns: dict[str, set[str]] = {}
        for table, column in cur.fetchall():
            columns.setdefault(table, set()).add(column)
        assert {
            "id", "session_id", "participant_id", "post_id", "session_position",
            "ranking_snapshot", "provenance_metadata", "reserved_at",
            "first_issued_at", "first_impressed_at", "first_viewed_at",
        } <= columns["research_session_items"]
        assert {
            "session_id", "participant_id", "worthwhile_answer",
            "perceived_control_answer", "mood_answer", "checkout_version",
            "submitted_at",
        } <= columns["research_session_checkouts"]
        assert {
            "server_sequence_number", "client_event_id", "client_sequence_number",
            "received_at", "event_authority",
        } <= columns["research_events"]

        cur.execute(
            """
            SELECT conrelid::regclass::text, conname, contype,
                   pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid IN (
                'public.research_session_items'::regclass,
                'public.research_session_checkouts'::regclass,
                'public.research_events'::regclass
            )
            """
        )
        constraints = cur.fetchall()
        item_defs = "\n".join(row[3] for row in constraints if row[0].endswith("research_session_items"))
        checkout_defs = "\n".join(row[3] for row in constraints if row[0].endswith("research_session_checkouts"))
        event_defs = "\n".join(row[3] for row in constraints if row[0].endswith("research_events"))
        assert "UNIQUE (session_id, session_position)" in item_defs
        assert "UNIQUE (session_id, post_id)" in item_defs
        assert "FOREIGN KEY (session_id, participant_id)" in item_defs
        assert "ON DELETE CASCADE" in item_defs
        assert "PRIMARY KEY (session_id)" in checkout_defs
        assert "FOREIGN KEY (session_id, participant_id)" in checkout_defs
        assert "ON DELETE CASCADE" in checkout_defs
        assert "worthwhile_answer" in checkout_defs
        assert "perceived_control_answer" in checkout_defs
        assert "mood_answer" in checkout_defs
        assert "session_finished_early" in event_defs
        assert "session_boundary_reached" in event_defs

        cur.execute(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename IN "
            "('research_sessions', 'research_events')"
        )
        indexes = dict(cur.fetchall())
        assert "idx_research_events_canonical_session_sequence" in indexes
        assert "UNIQUE" in indexes["idx_research_events_canonical_session_sequence"]
        assert "server_sequence_number IS NOT NULL" in indexes[
            "idx_research_events_canonical_session_sequence"
        ]
        nonterminal = indexes["idx_research_sessions_one_nonterminal_intentional_break"]
        assert "UNIQUE" in nonterminal
        assert "journey_version" in nonterminal
        for state in ("planned", "active", "checkout", "cooldown"):
            assert state in nonterminal
        assert "completed" not in nonterminal
        assert "idx_research_events_server_lifecycle_once" in indexes
        assert "idx_research_events_server_finish_once" in indexes
        assert "idx_research_events_server_cooldown_outcome_once" in indexes


def test_postgres_rls_catalog_and_browser_roles_where_available(
    postgres_harness, postgres_connection, capsys
):
    with postgres_connection.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM pg_policies WHERE schemaname = 'public' "
            "AND tablename LIKE 'research_%'"
        )
        assert cur.fetchone()[0] == 0
        cur.execute(
            """
            SELECT rolname, pg_has_role(current_user, oid, 'USAGE')
            FROM pg_roles WHERE rolname IN ('anon', 'authenticated')
            ORDER BY rolname
            """
        )
        available = cur.fetchall()

    settable = [role for role, can_set in available if can_set]
    if not settable:
        print(
            "Supabase anon/authenticated role behavior not reproduced; "
            "PostgreSQL RLS enablement and absence of policies verified."
        )
        assert "not reproduced" in capsys.readouterr().out
        return

    from psycopg2 import sql

    for role in settable:
        role_conn = connect_postgres(postgres_harness.config)
        try:
            with role_conn.cursor() as cur:
                cur.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
                operations = (
                    (
                        "SELECT count(*) FROM public.research_participants",
                        (),
                        "select",
                    ),
                    (
                        "INSERT INTO public.research_participants "
                        "(access_token_hash, assigned_condition) "
                        "VALUES ('rls-browser-insert-must-not-persist', 'balanced')",
                        (),
                        "insert",
                    ),
                    (
                        "UPDATE public.research_participants SET status = 'withdrawn' "
                        "WHERE id = %s",
                        (postgres_harness.legacy["participant_id"],),
                        "update",
                    ),
                    (
                        "DELETE FROM public.research_participants WHERE id = %s",
                        (postgres_harness.legacy["participant_id"],),
                        "delete",
                    ),
                )
                for statement, params, operation in operations:
                    cur.execute("SAVEPOINT browser_operation")
                    denied_by_error = False
                    affected = None
                    try:
                        cur.execute(statement, params)
                        if operation == "select":
                            affected = int(cur.fetchone()[0])
                        else:
                            affected = cur.rowcount
                    except Exception as exc:
                        if getattr(exc, "pgcode", None) != "42501":
                            raise
                        denied_by_error = True
                    cur.execute("ROLLBACK TO SAVEPOINT browser_operation")
                    if not denied_by_error:
                        # With table grants, default-deny RLS presents zero visible rows;
                        # without grants, PostgreSQL raises insufficient_privilege.
                        assert affected == 0
            role_conn.rollback()
        finally:
            role_conn.close()
    print(f"Supabase browser-role RLS exercised with SET ROLE: {', '.join(settable)}")

    with postgres_connection.cursor() as cur:
        cur.execute(
            "SELECT status FROM public.research_participants WHERE id = %s",
            (postgres_harness.legacy["participant_id"],),
        )
        assert cur.fetchone()[0] == "active"
        cur.execute(
            "SELECT count(*) FROM public.research_participants "
            "WHERE access_token_hash = 'rls-browser-insert-must-not-persist'"
        )
        assert cur.fetchone()[0] == 0


def test_postgres_natural_api_journey_and_native_types(postgres_harness):
    client, clock = build_postgres_api(postgres_harness)
    participant = api_participant(client)
    participant_id = participant["participant_id"]
    try:
        journey = api_plan(client, participant)
        session_id = journey["session_id"]
        assert str(uuid.UUID(session_id)) == session_id
        started = api_command(client, participant, session_id, "start")
        assert started.status_code == 200, started.text
        assert started.json()["data"]["journey"]["journey_state"] == "active"

        page = client.get(
            f"{BASE}/sessions/{session_id}/items?start_position=1&limit=5",
            headers=participant["headers"],
        )
        assert page.status_code == 200, page.text
        items = page.json()["data"]["items"]
        assert [item["session_position"] for item in items] == [1, 2, 3, 4, 5]
        assert len({item["post_id"] for item in items}) == 5

        event_response = api_command(
            client,
            participant,
            session_id,
            "events",
            {"events": [
                meaningful_impression(item["post_id"], sequence=index)
                for index, item in enumerate(items, start=1)
            ]},
        )
        assert event_response.status_code == 200, event_response.text
        boundary = event_response.json()["data"]
        assert boundary["journey"]["journey_state"] == "checkout"
        assert len(boundary["resulting_lifecycle_events"]) == 1

        checkout = api_command(client, participant, session_id, "checkout", {
            "worthwhile": "yes",
            "perceived_control": 4,
            "mood": "better",
            "checkout_version": "intentional-break-v1",
            "idempotency_key": str(uuid.uuid4()),
        })
        assert checkout.status_code == 200, checkout.text
        assert checkout.json()["data"]["journey"]["journey_state"] == "cooldown"
        clock.value += timedelta(seconds=301)
        completed = client.get(
            f"{BASE}/sessions/{session_id}/cooldown",
            headers=participant["headers"],
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["data"]["journey"]["journey_state"] == "completed"
        assert completed.json()["data"]["cooldown_outcome"] == "completed"

        conn = connect_postgres(postgres_harness.config)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT server_sequence_number, event_type, metadata,
                           client_event_id, server_timestamp, received_at
                    FROM public.research_events WHERE session_id = %s
                    ORDER BY server_sequence_number
                    """,
                    (session_id,),
                )
                events = cur.fetchall()
                assert [row[0] for row in events] == list(range(11))
                assert [row[1] for row in events] == [
                    "session_plan_created", "session_started",
                    "post_impression", "post_impression", "post_impression",
                    "post_impression", "post_impression", "session_boundary_reached",
                    "checkout_submitted", "cooldown_started", "cooldown_completed",
                ]
                assert len({row[0] for row in events}) == len(events)
                assert isinstance(events[2][2], dict)
                assert events[2][2]["provenance_metadata"]["inventory_table"] == "feed_videos"
                assert isinstance(events[2][3], uuid.UUID)
                assert events[2][4].tzinfo is not None
                assert events[2][5].tzinfo is not None
                cur.execute(
                    "SELECT count(*), min(session_position), max(session_position) "
                    "FROM public.research_session_items WHERE session_id = %s",
                    (session_id,),
                )
                assert cur.fetchone() == (5, 1, 5)
                cur.execute(
                    "SELECT count(*) FROM public.research_session_checkouts "
                    "WHERE session_id = %s",
                    (session_id,),
                )
                assert cur.fetchone()[0] == 1
        finally:
            conn.close()
    finally:
        client.close()
        delete_test_participants(postgres_harness.config, participant_id)


def test_postgres_finish_early_preserves_meaningful_measurement(postgres_harness):
    client, clock = build_postgres_api(postgres_harness)
    participant = api_participant(client)
    participant_id = participant["participant_id"]
    try:
        journey = api_plan(client, participant)
        session_id = journey["session_id"]
        assert api_command(client, participant, session_id, "start").status_code == 200
        page = client.get(
            f"{BASE}/sessions/{session_id}/items?start_position=1&limit=5",
            headers=participant["headers"],
        ).json()["data"]["items"]
        forged_non_impression = {
            "client_event_id": str(uuid.uuid4()),
            "client_sequence_number": 999,
            "event_type": "post_viewed",
            "post_id": page[1]["post_id"],
            "client_timestamp": NOW.isoformat(),
            "metadata": {
                "session_position": 5,
                "feed_position": 5,
                "highest_reached_position": 5,
            },
        }
        events = api_command(client, participant, session_id, "events", {
            "events": [meaningful_impression(page[0]["post_id"]), forged_non_impression]
        })
        assert events.status_code == 200, events.text
        assert events.json()["data"]["journey"]["highest_reached_position"] == 1

        finished = api_command(client, participant, session_id, "finish-early")
        assert finished.status_code == 200, finished.text
        finish_journey = finished.json()["data"]["journey"]
        assert finish_journey["highest_reached_position"] == 1
        assert finish_journey["finish_reason"] == "finished_early"
        checkout = api_command(client, participant, session_id, "checkout", {
            "worthwhile": "mostly",
            "perceived_control": 3,
            "mood": "same",
            "checkout_version": "intentional-break-v1",
            "idempotency_key": str(uuid.uuid4()),
        })
        assert checkout.status_code == 200
        clock.value += timedelta(seconds=301)
        assert client.get(
            f"{BASE}/sessions/{session_id}/cooldown",
            headers=participant["headers"],
        ).json()["data"]["journey_state"] == "completed"

        conn = connect_postgres(postgres_harness.config)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT highest_reached_position FROM public.research_sessions "
                    "WHERE id = %s",
                    (session_id,),
                )
                assert cur.fetchone()[0] == 1
                cur.execute(
                    "SELECT metadata FROM public.research_events "
                    "WHERE session_id = %s AND event_type = 'session_finished_early'",
                    (session_id,),
                )
                assert cur.fetchone()[0]["highest_meaningful_position"] == 1
        finally:
            conn.close()
    finally:
        client.close()
        delete_test_participants(postgres_harness.config, participant_id)


def test_postgres_concurrent_plan_creation(postgres_harness):
    setup = connect_postgres(postgres_harness.config)
    participant = create_participant(setup, backend="postgres", condition="balanced")
    setup.close()
    participant_id = participant["participant_id"]
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt(index: int):
        conn = connect_postgres(postgres_harness.config)
        try:
            barrier.wait()
            create_intentional_break_plan(
                conn,
                backend="postgres",
                participant_id=participant_id,
                intention="quick_break",
                planned_video_count=5,
                selected_cooldown_seconds=300,
                reserved_items=reserved_items(f"concurrent-plan-{index}"),
                plan_idempotency_key=f"concurrent-plan-key-{index}-{uuid.uuid4()}",
                now=NOW,
            )
            result = "success"
        except IntentionalBreakStorageError as exc:
            result = exc.code
        finally:
            conn.close()
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert all(not thread.is_alive() for thread in threads)
    assert outcomes.count("success") == 1
    assert len(outcomes) == 2

    verify = connect_postgres(postgres_harness.config)
    try:
        with verify.cursor() as cur:
            cur.execute(
                "SELECT id FROM public.research_sessions WHERE participant_id = %s "
                "AND journey_state IN ('planned', 'active', 'checkout', 'cooldown')",
                (participant_id,),
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            cur.execute(
                "SELECT count(*) FROM public.research_session_items WHERE session_id = %s",
                (rows[0][0],),
            )
            assert cur.fetchone()[0] == 5
    finally:
        verify.close()
        delete_test_participants(postgres_harness.config, participant_id)


def test_postgres_concurrent_final_impressions(postgres_harness):
    setup = connect_postgres(postgres_harness.config)
    participant = create_participant(setup, backend="postgres", condition="balanced")
    participant_id = participant["participant_id"]
    plan = create_storage_plan(setup, participant_id, f"final-{uuid.uuid4()}")
    start_storage_plan(setup, participant_id, plan["session_id"])
    items = read_intentional_break_items(
        setup, backend="postgres", participant_id=participant_id,
        session_id=plan["session_id"], start_position=1, requested_limit=5, now=NOW,
    )["items"]
    setup.close()
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def attempt(index: int):
        conn = connect_postgres(postgres_harness.config)
        try:
            barrier.wait()
            append_intentional_break_client_events(
                conn, backend="postgres", participant_id=participant_id,
                session_id=plan["session_id"],
                events=[meaningful_impression(items[-1]["post_id"], sequence=index)],
                now=NOW,
            )
            outcomes.append("success")
        except IntentionalBreakStorageError as exc:
            outcomes.append(exc.code)
        finally:
            conn.close()

    threads = [threading.Thread(target=attempt, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert all(not thread.is_alive() for thread in threads)
    assert outcomes == ["success", "success"] or sorted(outcomes) == ["success", "success"]

    verify = connect_postgres(postgres_harness.config)
    try:
        with verify.cursor() as cur:
            cur.execute(
                "SELECT journey_state FROM public.research_sessions WHERE id = %s",
                (plan["session_id"],),
            )
            assert cur.fetchone()[0] == "checkout"
            cur.execute(
                "SELECT count(*) FROM public.research_events WHERE session_id = %s "
                "AND event_type = 'session_boundary_reached'",
                (plan["session_id"],),
            )
            assert cur.fetchone()[0] == 1
            cur.execute(
                "SELECT count(*), count(DISTINCT server_sequence_number) "
                "FROM public.research_events WHERE session_id = %s",
                (plan["session_id"],),
            )
            count, distinct_count = cur.fetchone()
            assert count == distinct_count
    finally:
        verify.close()
        delete_test_participants(postgres_harness.config, participant_id)


def test_postgres_concurrent_checkout(postgres_harness):
    setup = connect_postgres(postgres_harness.config)
    participant = create_participant(setup, backend="postgres", condition="balanced")
    participant_id = participant["participant_id"]
    plan = create_storage_plan(setup, participant_id, f"checkout-{uuid.uuid4()}")
    start_storage_plan(setup, participant_id, plan["session_id"])
    finish_intentional_break_early(
        setup, backend="postgres", participant_id=participant_id,
        session_id=plan["session_id"], idempotency_key=f"finish-{uuid.uuid4()}", now=NOW,
    )
    setup.close()
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def attempt(index: int):
        conn = connect_postgres(postgres_harness.config)
        try:
            barrier.wait()
            submit_intentional_break_checkout(
                conn, backend="postgres", participant_id=participant_id,
                session_id=plan["session_id"], worthwhile_answer="yes",
                perceived_control_answer=3, mood_answer="same",
                checkout_version="intentional-break-v1",
                submission_idempotency_key=f"racing-checkout-{index}-{uuid.uuid4()}",
                now=NOW,
            )
            outcomes.append("success")
        except IntentionalBreakStorageError as exc:
            outcomes.append(exc.code)
        finally:
            conn.close()

    threads = [threading.Thread(target=attempt, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert all(not thread.is_alive() for thread in threads)
    assert outcomes.count("success") == 1
    assert len(outcomes) == 2

    verify = connect_postgres(postgres_harness.config)
    try:
        with verify.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM public.research_session_checkouts WHERE session_id = %s",
                (plan["session_id"],),
            )
            assert cur.fetchone()[0] == 1
            for event_type in ("checkout_submitted", "cooldown_started"):
                cur.execute(
                    "SELECT count(*) FROM public.research_events "
                    "WHERE session_id = %s AND event_type = %s",
                    (plan["session_id"], event_type),
                )
                assert cur.fetchone()[0] == 1
    finally:
        verify.close()
        delete_test_participants(postgres_harness.config, participant_id)


def test_postgres_override_and_natural_completion_race(postgres_harness):
    setup = connect_postgres(postgres_harness.config)
    participant = create_participant(setup, backend="postgres", condition="balanced")
    participant_id = participant["participant_id"]
    plan = create_storage_plan(setup, participant_id, f"override-race-{uuid.uuid4()}")
    start_storage_plan(setup, participant_id, plan["session_id"])
    finish_intentional_break_early(
        setup, backend="postgres", participant_id=participant_id,
        session_id=plan["session_id"], idempotency_key=f"finish-{uuid.uuid4()}", now=NOW,
    )
    storage_checkout(setup, participant_id, plan["session_id"], now=NOW)
    start_intentional_break_override(
        setup, backend="postgres", participant_id=participant_id,
        session_id=plan["session_id"], idempotency_key=f"override-{uuid.uuid4()}",
        now=NOW + timedelta(seconds=10),
    )
    setup.close()
    authoritative_end = NOW + timedelta(seconds=301)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def reconcile():
        conn = connect_postgres(postgres_harness.config)
        try:
            barrier.wait()
            result = reconcile_intentional_break_cooldown(
                conn, backend="postgres", participant_id=participant_id,
                session_id=plan["session_id"], now=authoritative_end,
            )
            outcomes.append(result["cooldown_outcome"])
        finally:
            conn.close()

    def confirm():
        conn = connect_postgres(postgres_harness.config)
        try:
            barrier.wait()
            result = confirm_intentional_break_override(
                conn, backend="postgres", participant_id=participant_id,
                session_id=plan["session_id"], reason_code="change_plan",
                confirmation_idempotency_key=f"confirm-{uuid.uuid4()}",
                now=authoritative_end,
            )
            outcomes.append(result["cooldown_outcome"])
        finally:
            conn.close()

    threads = [threading.Thread(target=reconcile), threading.Thread(target=confirm)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert all(not thread.is_alive() for thread in threads)
    assert outcomes == ["completed", "completed"] or sorted(outcomes) == ["completed", "completed"]

    verify = connect_postgres(postgres_harness.config)
    try:
        with verify.cursor() as cur:
            cur.execute(
                "SELECT journey_state, cooldown_outcome FROM public.research_sessions "
                "WHERE id = %s",
                (plan["session_id"],),
            )
            assert cur.fetchone() == ("completed", "completed")
            cur.execute(
                "SELECT event_type FROM public.research_events WHERE session_id = %s "
                "AND event_type IN ('cooldown_completed', 'cooldown_overridden')",
                (plan["session_id"],),
            )
            assert cur.fetchall() == [("cooldown_completed",)]
    finally:
        verify.close()
        delete_test_participants(postgres_harness.config, participant_id)


def test_postgres_wrong_participant_is_non_enumerating_and_zero_mutation(postgres_harness):
    client, _clock = build_postgres_api(postgres_harness)
    owner = api_participant(client)
    outsider = api_participant(client)
    try:
        journey = api_plan(client, owner)
        session_id = journey["session_id"]
        assert api_command(client, owner, session_id, "start").status_code == 200
        before_conn = connect_postgres(postgres_harness.config)
        try:
            with before_conn.cursor() as cur:
                cur.execute(
                    "SELECT journey_state, next_server_sequence_number FROM "
                    "public.research_sessions WHERE id = %s",
                    (session_id,),
                )
                before_state = cur.fetchone()
                cur.execute(
                    "SELECT count(*) FROM public.research_events WHERE session_id = %s",
                    (session_id,),
                )
                before_events = cur.fetchone()[0]
                cur.execute(
                    "SELECT count(*) FROM public.research_session_checkouts WHERE session_id = %s",
                    (session_id,),
                )
                before_checkouts = cur.fetchone()[0]
        finally:
            before_conn.close()

        current = client.get(f"{BASE}/current", headers=outsider["headers"])
        assert current.status_code == 200
        assert current.json()["data"]["journey"] is None
        attempts = [
            client.get(f"{BASE}/sessions/{session_id}", headers=outsider["headers"]),
            client.get(f"{BASE}/sessions/{session_id}/items", headers=outsider["headers"]),
            api_command(client, outsider, session_id, "events", {
                "events": [meaningful_impression("unknown-post")]
            }),
            api_command(client, outsider, session_id, "finish-early"),
            api_command(client, outsider, session_id, "checkout", {
                "worthwhile": "yes", "perceived_control": 3, "mood": "same",
                "checkout_version": "intentional-break-v1",
                "idempotency_key": str(uuid.uuid4()),
            }),
            api_command(client, outsider, session_id, "override/start"),
            api_command(client, outsider, session_id, "override/confirm", {
                "reason_code": "change_plan", "idempotency_key": str(uuid.uuid4())
            }),
        ]
        for response in attempts:
            assert response.status_code == 404, response.text
            assert response.json()["error_code"] == "session_not_found"

        after_conn = connect_postgres(postgres_harness.config)
        try:
            with after_conn.cursor() as cur:
                cur.execute(
                    "SELECT journey_state, next_server_sequence_number FROM "
                    "public.research_sessions WHERE id = %s",
                    (session_id,),
                )
                assert cur.fetchone() == before_state
                cur.execute(
                    "SELECT count(*) FROM public.research_events WHERE session_id = %s",
                    (session_id,),
                )
                assert cur.fetchone()[0] == before_events
                cur.execute(
                    "SELECT count(*) FROM public.research_session_checkouts WHERE session_id = %s",
                    (session_id,),
                )
                assert cur.fetchone()[0] == before_checkouts
        finally:
            after_conn.close()
    finally:
        client.close()
        delete_test_participants(
            postgres_harness.config,
            owner["participant_id"],
            outsider["participant_id"],
        )


def test_postgres_admin_cascade_rehearsal(postgres_harness):
    conn = connect_postgres(postgres_harness.config)
    target = create_participant(conn, backend="postgres", condition="balanced")
    other = create_participant(conn, backend="postgres", condition="regular")
    target_id = target["participant_id"]
    other_id = other["participant_id"]
    try:
        authenticated = authenticate_participant(
            conn, backend="postgres", access_token=target["access_token"]
        )
        legacy = start_session(
            conn, backend="postgres", participant=authenticated,
            application_version="postgres-admin-rehearsal", client_timestamp=NOW,
        )
        record_feed_items(
            conn, backend="postgres", participant_id=target_id,
            session_id=legacy["session_id"], feed_request_id=str(uuid.uuid4()),
            items=[{
                "post_id": f"legacy-admin-{uuid.uuid4()}", "feed_position": 0,
                "content_category": "positive", "feed_policy_version": "balanced-v1",
                "selection_bucket": "healthy", "selection_reason": "healthy_category_target",
            }],
        )
        plan = create_storage_plan(conn, target_id, f"admin-{uuid.uuid4()}")
        start_storage_plan(conn, target_id, plan["session_id"])
        finish_intentional_break_early(
            conn, backend="postgres", participant_id=target_id,
            session_id=plan["session_id"], idempotency_key=f"finish-{uuid.uuid4()}", now=NOW,
        )
        storage_checkout(conn, target_id, plan["session_id"], now=NOW)

        result = delete_participant(
            conn, backend="postgres", participant_id=target_id, withdraw_first=True, now=NOW,
        )
        assert result["participant_remaining"] == 0
        assert not any(result["related_rows_remaining"].values())
        assert result["unrelated_participants_preserved"] is True
        with pytest.raises(ResearchNotFoundError):
            authenticate_participant(
                conn, backend="postgres", access_token=target["access_token"]
            )
        assert authenticate_participant(
            conn, backend="postgres", access_token=other["access_token"]
        )["participant_id"] == other_id
    finally:
        conn.close()
        delete_test_participants(postgres_harness.config, target_id, other_id)
