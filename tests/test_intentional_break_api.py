import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.research_storage import create_participant, ensure_sqlite_research_tables
from research_api import INTENTIONAL_BREAK_API_PREFIX, create_research_router


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
BASE = f"/api/research{INTENTIONAL_BREAK_API_PREFIX}"


class Clock:
    def __init__(self):
        self.value = NOW

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


def inventory(count=60):
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
            "video_id": f"post-{index}",
            "title": title,
            "description": description,
            "channel_id": f"creator-{index % 17}",
            "channel_title": f"Creator {index % 17}",
            "source_category": category,
            "source_query": f"{category} seed",
            "source_type": "search",
            "integrity_score": 0.9,
            "tags": [category],
        })
    return rows


def build_api(tmp_path, *, rows=None, loader=None):
    db_path = tmp_path / f"intentional-api-{uuid.uuid4()}.db"
    clock = Clock()

    def connect():
        conn = sqlite3.connect(db_path, timeout=5)
        ensure_sqlite_research_tables(conn)
        return conn

    source_rows = inventory() if rows is None else rows
    source_loader = loader or (lambda _conn: (source_rows, None))
    app = FastAPI()
    app.include_router(create_research_router(
        get_connection=connect,
        backend="sqlite",
        load_feed_source=source_loader,
        clock=clock,
    ))
    return {
        "app": app,
        "client": TestClient(app),
        "connect": connect,
        "clock": clock,
        "rows": source_rows,
    }


@pytest.fixture
def api(tmp_path):
    return build_api(tmp_path)


def participant(api, *, condition=None):
    if condition is None:
        result = api["client"].post("/api/research/participants")
        assert result.status_code == 201
        value = result.json()
    else:
        conn = api["connect"]()
        value = create_participant(conn, backend="sqlite", condition=condition)
        conn.close()
    value["headers"] = {"Authorization": f"Bearer {value['access_token']}"}
    return value


def plan_body(*, count=5, key=None, **overrides):
    body = {
        "intention": "quick_break",
        "planned_video_count": count,
        "selected_cooldown_seconds": 300,
        "idempotency_key": key or str(uuid.uuid4()),
        "participant_notice_version": "intentional-break-v1",
        "participant_notice_acknowledged": True,
    }
    body.update(overrides)
    return body


def create_plan(api, person, *, body=None):
    result = api["client"].post(
        f"{BASE}/plans",
        json=body or plan_body(),
        headers=person["headers"],
    )
    assert result.status_code == 201, result.text
    return result.json()["data"]["journey"]


def command(api, person, session_id, action, *, body=None):
    return api["client"].post(
        f"{BASE}/sessions/{session_id}/{action}",
        json=body or {"idempotency_key": str(uuid.uuid4())},
        headers=person["headers"],
    )


def start_plan(api, person, journey, *, key=None):
    result = command(
        api,
        person,
        journey["session_id"],
        "start",
        body={"idempotency_key": key or str(uuid.uuid4())},
    )
    assert result.status_code == 200, result.text
    return result.json()["data"]["journey"]


def enter_checkout(api, person, journey, *, key=None):
    result = command(
        api,
        person,
        journey["session_id"],
        "finish-early",
        body={"idempotency_key": key or str(uuid.uuid4())},
    )
    assert result.status_code == 200, result.text
    return result.json()["data"]["journey"]


def checkout(api, person, journey, *, key=None, **overrides):
    body = {
        "worthwhile": "yes",
        "perceived_control": 3,
        "mood": "same",
        "checkout_version": "intentional-break-v1",
        "idempotency_key": key or str(uuid.uuid4()),
    }
    body.update(overrides)
    return command(api, person, journey["session_id"], "checkout", body=body)


def impression(post_id, *, event_id=None, sequence=1):
    return {
        "client_event_id": event_id or str(uuid.uuid4()),
        "client_sequence_number": sequence,
        "event_type": "post_impression",
        "post_id": post_id,
        "client_timestamp": NOW.isoformat(),
        "metadata": {"visibility_ratio": 0.75, "visible_ms": 1000},
    }


def post_events(api, person, journey, events):
    return command(
        api,
        person,
        journey["session_id"],
        "events",
        body={"events": events},
    )


def assert_error(response, *, status, code, retryable=False):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == code
    assert body["retryable"] is retryable
    assert body["message"]
    assert body["server_timestamp"]
    assert body["contract_version"] == "intentional-break-v1"
    return body


def test_route_registration_and_legacy_coexistence(api):
    routes = {
        (method.upper(), path)
        for path, operations in api["app"].openapi()["paths"].items()
        for method in operations
        if method != "parameters"
    }
    expected = {
        ("GET", f"{BASE}/current"),
        ("GET", f"{BASE}/sessions/{{session_id}}"),
        ("POST", f"{BASE}/plans"),
        ("POST", f"{BASE}/sessions/{{session_id}}/cancel"),
        ("POST", f"{BASE}/sessions/{{session_id}}/start"),
        ("GET", f"{BASE}/sessions/{{session_id}}/items"),
        ("POST", f"{BASE}/sessions/{{session_id}}/events"),
        ("POST", f"{BASE}/sessions/{{session_id}}/finish-early"),
        ("POST", f"{BASE}/sessions/{{session_id}}/checkout"),
        ("GET", f"{BASE}/sessions/{{session_id}}/cooldown"),
        ("POST", f"{BASE}/sessions/{{session_id}}/override/start"),
        ("POST", f"{BASE}/sessions/{{session_id}}/override/confirm"),
    }
    assert expected <= routes
    assert ("POST", "/api/research/participants") in routes
    assert ("POST", "/api/research/sessions") in routes
    assert ("GET", "/api/research/sessions/{session_id}/feed") in routes
    assert ("POST", "/api/research/events/batch") in routes
    assert ("POST", "/api/research/sessions/{session_id}/complete") in routes
    assert not any(path.startswith(BASE) and path.endswith("/complete") for _, path in routes)

    root = Path(__file__).parents[1]
    assert "create_research_router" in (root / "api.py").read_text()
    assert "create_research_router" in (root / "api" / "index.py").read_text()


def test_authentication_and_non_enumerating_ownership(api):
    missing = api["client"].get(f"{BASE}/current")
    assert_error(missing, status=401, code="authentication_required")
    invalid = api["client"].get(
        f"{BASE}/current", headers={"Authorization": "Bearer invalid"}
    )
    assert_error(invalid, status=401, code="invalid_credential")

    owner = participant(api)
    outsider = participant(api)
    journey = create_plan(api, owner)
    valid = api["client"].get(f"{BASE}/current", headers=owner["headers"])
    assert valid.status_code == 200
    foreign = api["client"].get(
        f"{BASE}/sessions/{journey['session_id']}", headers=outsider["headers"]
    )
    assert_error(foreign, status=404, code="session_not_found")

    conn = api["connect"]()
    conn.execute(
        "UPDATE research_participants SET status = 'withdrawn' WHERE id = ?",
        (owner["participant_id"],),
    )
    conn.commit()
    conn.close()
    inactive = api["client"].get(f"{BASE}/current", headers=owner["headers"])
    assert_error(inactive, status=403, code="participant_inactive")


def test_participant_id_cannot_be_supplied_by_plan_client(api):
    person = participant(api)
    response = api["client"].post(
        f"{BASE}/plans",
        headers=person["headers"],
        json=plan_body(participant_id=str(uuid.uuid4())),
    )
    assert_error(response, status=400, code="invalid_request")


def test_current_journey_resumes_each_nonterminal_stage_and_lazy_completion(api):
    person = participant(api)
    empty = api["client"].get(f"{BASE}/current", headers=person["headers"])
    assert empty.json()["data"]["journey"] is None
    planned = create_plan(api, person)
    assert api["client"].get(
        f"{BASE}/current", headers=person["headers"]
    ).json()["data"]["journey"]["journey_state"] == "planned"
    active = start_plan(api, person, planned)
    assert api["client"].get(
        f"{BASE}/current", headers=person["headers"]
    ).json()["data"]["journey"]["journey_state"] == "active"
    entered = enter_checkout(api, person, active)
    assert api["client"].get(
        f"{BASE}/current", headers=person["headers"]
    ).json()["data"]["journey"]["journey_state"] == "checkout"
    cooldown = checkout(api, person, entered)
    assert cooldown.status_code == 200
    assert api["client"].get(
        f"{BASE}/current", headers=person["headers"]
    ).json()["data"]["journey"]["journey_state"] == "cooldown"
    api["clock"].advance(300)
    due = api["client"].get(f"{BASE}/current", headers=person["headers"])
    assert due.json()["data"]["journey"]["journey_state"] == "completed"
    next_read = api["client"].get(f"{BASE}/current", headers=person["headers"])
    assert next_read.json()["data"]["journey"] is None


@pytest.mark.parametrize("count", [5, 10, 20, 40])
def test_plan_creation_uses_exact_fixed_balanced_batch(api, count):
    person = participant(api, condition="regular")
    response = api["client"].post(
        f"{BASE}/plans",
        headers=person["headers"],
        json=plan_body(count=count),
    )
    assert response.status_code == 201
    body = response.json()
    journey = body["data"]["journey"]
    assert journey["journey_state"] == "planned"
    assert journey["feed_condition"] == "balanced"
    assert journey["feed_policy_version"] == "balanced-v1"
    assert body["data"]["plan_summary"]["reserved_count"] == count
    assert body["data"]["plan_summary"]["ordered_positions"] == list(range(1, count + 1))
    conn = api["connect"]()
    stored = conn.execute(
        "SELECT post_id, session_position FROM research_session_items "
        "WHERE session_id = ? ORDER BY session_position",
        (journey["session_id"],),
    ).fetchall()
    conn.close()
    assert len(stored) == count
    assert len({row[0] for row in stored}) == count
    assert [row[1] for row in stored] == list(range(1, count + 1))
    encoded = json.dumps(body).lower()
    assert "feed_seed" not in encoded
    assert "access_token_hash" not in encoded


def test_plan_selection_and_storage_replay_are_deterministic(api):
    person = participant(api)
    key = str(uuid.uuid4())
    request = plan_body(key=key)
    first = api["client"].post(f"{BASE}/plans", headers=person["headers"], json=request)
    conn = api["connect"]()
    first_order = conn.execute(
        "SELECT post_id FROM research_session_items ORDER BY session_position"
    ).fetchall()
    conn.close()
    replay = api["client"].post(f"{BASE}/plans", headers=person["headers"], json=request)
    conn = api["connect"]()
    replay_order = conn.execute(
        "SELECT post_id FROM research_session_items ORDER BY session_position"
    ).fetchall()
    count = conn.execute("SELECT count(*) FROM research_sessions").fetchone()[0]
    conn.close()
    assert first.status_code == replay.status_code == 201
    assert first.json()["data"]["journey"]["session_id"] == replay.json()["data"]["journey"]["session_id"]
    assert first_order == replay_order
    assert count == 1

    conflict = api["client"].post(
        f"{BASE}/plans",
        headers=person["headers"],
        json=plan_body(key=key, intention="relax"),
    )
    assert_error(conflict, status=409, code="idempotency_conflict")
    existing = api["client"].post(
        f"{BASE}/plans", headers=person["headers"], json=plan_body()
    )
    assert_error(existing, status=409, code="existing_nonterminal_session")


@pytest.mark.parametrize(
    "overrides",
    [
        {"intention": "focus"},
        {"planned_video_count": 6},
        {"selected_cooldown_seconds": 301},
        {"participant_notice_acknowledged": False},
        {"participant_notice_version": "wrong-version"},
        {"idempotency_key": "not-a-uuid"},
    ],
)
def test_plan_validation_returns_contract_error(api, overrides):
    person = participant(api)
    response = api["client"].post(
        f"{BASE}/plans",
        headers=person["headers"],
        json=plan_body(**overrides),
    )
    assert_error(response, status=400, code="invalid_request")


def test_insufficient_inventory_and_inventory_failure_are_classified(tmp_path):
    scarce = build_api(tmp_path, rows=inventory(4))
    person = participant(scarce)
    response = scarce["client"].post(
        f"{BASE}/plans", headers=person["headers"], json=plan_body(count=5)
    )
    body = assert_error(response, status=409, code="insufficient_inventory")
    assert body["available_count"] == 4
    assert body["requested_count"] == 5
    conn = scarce["connect"]()
    assert conn.execute("SELECT count(*) FROM research_sessions").fetchone()[0] == 0
    conn.close()

    unavailable = build_api(
        tmp_path,
        loader=lambda _conn: (_ for _ in ()).throw(RuntimeError("inventory offline")),
    )
    person = participant(unavailable)
    response = unavailable["client"].post(
        f"{BASE}/plans", headers=person["headers"], json=plan_body()
    )
    assert_error(response, status=503, code="inventory_unavailable", retryable=True)


def test_cancel_start_and_corrupted_batch_transitions(api):
    person = participant(api)
    planned = create_plan(api, person)
    key = str(uuid.uuid4())
    cancelled = command(
        api, person, planned["session_id"], "cancel", body={"idempotency_key": key}
    )
    replay = command(
        api, person, planned["session_id"], "cancel", body={"idempotency_key": key}
    )
    assert cancelled.json()["data"]["journey"]["journey_state"] == "cancelled"
    assert replay.json()["data"]["journey"]["cancelled_at"] == cancelled.json()["data"]["journey"]["cancelled_at"]
    cannot_start = command(api, person, planned["session_id"], "start")
    assert_error(cannot_start, status=409, code="invalid_transition")

    next_plan = create_plan(api, person)
    conn = api["connect"]()
    conn.execute(
        "DELETE FROM research_session_items WHERE session_id = ? AND session_position = 5",
        (next_plan["session_id"],),
    )
    conn.commit()
    conn.close()
    corrupted = command(api, person, next_plan["session_id"], "start")
    assert_error(corrupted, status=409, code="invalid_reserved_batch")


def test_start_is_explicit_idempotent_and_returns_previous_metadata(api):
    person = participant(api)
    first = create_plan(api, person)
    assert first["journey_state"] == "planned"
    active = start_plan(api, person, first)
    enter_checkout(api, person, active)
    checkout(api, person, first)
    api["clock"].advance(300)
    api["client"].get(
        f"{BASE}/sessions/{first['session_id']}/cooldown", headers=person["headers"]
    )
    second = create_plan(api, person, body=plan_body(previous_session_id=first["session_id"]))
    key = str(uuid.uuid4())
    started = command(
        api, person, second["session_id"], "start", body={"idempotency_key": key}
    )
    replay = command(
        api, person, second["session_id"], "start", body={"idempotency_key": key}
    )
    assert started.json()["data"]["journey"]["journey_state"] == "active"
    assert replay.json()["data"]["journey"]["session_started_at"] == started.json()["data"]["journey"]["session_started_at"]
    cannot_cancel = command(api, person, second["session_id"], "cancel")
    assert_error(cannot_cancel, status=409, code="invalid_transition")
    conn = api["connect"]()
    metadata = json.loads(conn.execute(
        "SELECT metadata FROM research_events WHERE session_id = ? "
        "AND event_type = 'session_started'",
        (second["session_id"],),
    ).fetchone()[0])
    conn.close()
    assert metadata["previous_session_id"] == first["session_id"]
    assert metadata["previous_cooldown_outcome"] == "completed"


def test_items_are_stable_paginated_write_once_and_state_restricted(api):
    person = participant(api)
    planned = create_plan(api, person, body=plan_body(count=10))
    before = api["client"].get(
        f"{BASE}/sessions/{planned['session_id']}/items", headers=person["headers"]
    )
    assert_error(before, status=409, code="invalid_transition")
    active = start_plan(api, person, planned)
    first = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/items?start_position=1&limit=4",
        headers=person["headers"],
    )
    second = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/items?start_position=5&limit=4",
        headers=person["headers"],
    )
    reset = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/items?start_position=1&limit=4",
        headers=person["headers"],
    )
    first_items = first.json()["data"]["items"]
    assert [item["session_position"] for item in first_items] == [1, 2, 3, 4]
    assert [item["session_position"] for item in second.json()["data"]["items"]] == [5, 6, 7, 8]
    assert reset.json()["data"]["items"] == first_items
    conn = api["connect"]()
    first_issued_at = conn.execute(
        "SELECT first_issued_at FROM research_session_items "
        "WHERE session_id = ? AND session_position = 1",
        (active["session_id"],),
    ).fetchone()[0]
    conn.close()
    api["clock"].advance(60)
    api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/items?start_position=1&limit=4",
        headers=person["headers"],
    )
    conn = api["connect"]()
    assert conn.execute(
        "SELECT first_issued_at FROM research_session_items "
        "WHERE session_id = ? AND session_position = 1",
        (active["session_id"],),
    ).fetchone()[0] == first_issued_at
    assert conn.execute(
        "SELECT count(*) FROM research_session_items WHERE session_id = ?",
        (active["session_id"],),
    ).fetchone()[0] == 10
    conn.close()
    exclusions = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/items?exclude_ids=post-1",
        headers=person["headers"],
    )
    assert_error(exclusions, status=400, code="invalid_request")
    enter_checkout(api, person, active)
    after = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/items", headers=person["headers"]
    )
    assert_error(after, status=409, code="invalid_transition")


def test_events_return_server_order_idempotency_and_server_provenance(api):
    person = participant(api)
    active = start_plan(api, person, create_plan(api, person))
    page = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/items?limit=5",
        headers=person["headers"],
    ).json()["data"]["items"]
    post_id = page[0]["post_id"]
    event_id = str(uuid.uuid4())
    events = [
        impression(post_id, event_id=event_id, sequence=90),
        {
            "client_event_id": str(uuid.uuid4()),
            "client_sequence_number": 2,
            "event_type": "post_viewed",
            "post_id": post_id,
            "client_timestamp": NOW.isoformat(),
            "metadata": {"feed_position": 999, "selection_bucket": "forged"},
        },
        {
            "client_event_id": str(uuid.uuid4()),
            "event_type": "post_liked",
            "post_id": post_id,
            "client_timestamp": NOW.isoformat(),
            "metadata": {"interaction_source": "action_rail"},
        },
    ]
    accepted = post_events(api, person, active, events)
    assert accepted.status_code == 200
    results = accepted.json()["data"]["events"]
    assert all(item["newly_accepted"] for item in results)
    assert [item["server_sequence_number"] for item in results] == sorted(
        item["server_sequence_number"] for item in results
    )
    replay = post_events(api, person, active, [events[0]])
    assert replay.json()["data"]["events"][0]["idempotent_replay"] is True
    assert replay.json()["data"]["events"][0]["server_sequence_number"] == results[0]["server_sequence_number"]
    conn = api["connect"]()
    row = conn.execute(
        "SELECT client_sequence_number, content_category, metadata FROM research_events "
        "WHERE client_event_id = ?", (event_id,),
    ).fetchone()
    conn.close()
    assert row[0] == 90
    assert row[1] == page[0]["content_category"]
    metadata = json.loads(row[2])
    assert metadata["feed_position"] == 1
    assert metadata["selection_bucket"] == page[0]["selection_bucket"]


def test_event_validation_conflicts_and_boundary_response(api):
    person = participant(api)
    active = start_plan(api, person, create_plan(api, person))
    items = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/items?limit=5",
        headers=person["headers"],
    ).json()["data"]["items"]
    canonical = {**impression(items[0]["post_id"]), "server_sequence_number": 999}
    rejected = post_events(api, person, active, [canonical])
    assert_error(rejected, status=400, code="invalid_request")
    unreserved = post_events(api, person, active, [impression("not-reserved")])
    assert_error(unreserved, status=409, code="event_provenance_invalid")

    event_id = str(uuid.uuid4())
    first = impression(items[1]["post_id"], event_id=event_id)
    assert post_events(api, person, active, [first]).status_code == 200
    conflicting = {**first, "post_id": items[2]["post_id"]}
    conflict = post_events(api, person, active, [conflicting])
    assert_error(conflict, status=409, code="idempotency_conflict")

    final = post_events(api, person, active, [impression(items[-1]["post_id"])])
    data = final.json()["data"]
    assert data["journey"]["journey_state"] == "checkout"
    client_sequence = data["events"][0]["server_sequence_number"]
    boundary_sequence = data["resulting_lifecycle_events"][0]["server_sequence_number"]
    assert client_sequence + 1 == boundary_sequence
    no_early = command(api, person, active["session_id"], "finish-early")
    assert_error(no_early, status=409, code="invalid_transition")


def test_finish_early_validation_and_idempotency(api):
    person = participant(api)
    active = start_plan(api, person, create_plan(api, person))
    items = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/items?limit=5",
        headers=person["headers"],
    ).json()["data"]["items"]
    assert post_events(api, person, active, [impression(items[1]["post_id"])]).status_code == 200
    untrusted_position = command(
        api,
        person,
        active["session_id"],
        "finish-early",
        body={"idempotency_key": str(uuid.uuid4()), "current_position": 4},
    )
    assert_error(untrusted_position, status=400, code="invalid_request")
    key = str(uuid.uuid4())
    first = command(
        api,
        person,
        active["session_id"],
        "finish-early",
        body={"idempotency_key": key},
    )
    replay = command(
        api,
        person,
        active["session_id"],
        "finish-early",
        body={"idempotency_key": key},
    )
    assert first.json()["data"]["journey"]["journey_state"] == "checkout"
    assert first.json()["data"]["journey"]["highest_reached_position"] == 2
    assert replay.json()["data"]["journey"]["checkout_entered_at"] == first.json()["data"]["journey"]["checkout_entered_at"]
    conn = api["connect"]()
    finish_metadata = json.loads(conn.execute(
        "SELECT metadata FROM research_events WHERE session_id = ? "
        "AND event_type = 'session_finished_early'",
        (active["session_id"],),
    ).fetchone()[0])
    conn.close()
    assert finish_metadata["highest_meaningful_position"] == 2
    assert "current_position" not in json.dumps(finish_metadata)
    conflict = command(
        api,
        person,
        active["session_id"],
        "finish-early",
        body={"idempotency_key": str(uuid.uuid4())},
    )
    assert_error(conflict, status=409, code="invalid_transition")


def test_finish_early_foreign_access_is_non_enumerating_and_identity_is_not_client_controlled(api):
    owner = participant(api)
    outsider = participant(api)
    active = start_plan(api, owner, create_plan(api, owner))
    foreign = command(api, outsider, active["session_id"], "finish-early")
    assert_error(foreign, status=404, code="session_not_found")
    supplied_identity = command(
        api,
        owner,
        active["session_id"],
        "finish-early",
        body={
            "idempotency_key": str(uuid.uuid4()),
            "participant_id": outsider["participant_id"],
        },
    )
    assert_error(supplied_identity, status=400, code="invalid_request")


@pytest.mark.parametrize(
    ("worthwhile", "control", "mood"),
    [
        ("yes", 1, "better"),
        ("mostly", 3, "same"),
        ("not_really", 5, "worse"),
        ("prefer_not_to_answer", "prefer_not_to_answer", "prefer_not_to_answer"),
    ],
)
def test_checkout_answers_and_cooldown_response(api, worthwhile, control, mood):
    person = participant(api)
    active = start_plan(api, person, create_plan(api, person))
    enter_checkout(api, person, active)
    response = checkout(
        api,
        person,
        active,
        worthwhile=worthwhile,
        perceived_control=control,
        mood=mood,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["journey"]["journey_state"] == "cooldown"
    assert data["cooldown_started_at"] == NOW.isoformat()
    assert data["cooldown_ends_at"] == (NOW + timedelta(seconds=300)).isoformat()
    assert data["remaining_seconds"] == 300


def test_checkout_invalid_version_and_conflicting_retry(api):
    person = participant(api)
    active = start_plan(api, person, create_plan(api, person))
    enter_checkout(api, person, active)
    invalid = checkout(api, person, active, checkout_version="old")
    assert_error(invalid, status=400, code="invalid_request")
    numeric_string = checkout(api, person, active, perceived_control="3")
    assert_error(numeric_string, status=400, code="invalid_request")
    key = str(uuid.uuid4())
    first = checkout(api, person, active, key=key)
    replay = checkout(api, person, active, key=key)
    assert first.json()["data"]["cooldown_started_at"] == replay.json()["data"]["cooldown_started_at"]
    conflict = checkout(api, person, active, key=key, worthwhile="mostly")
    assert_error(conflict, status=409, code="idempotency_conflict")


def test_cooldown_remaining_completion_and_no_items(api):
    person = participant(api)
    active = start_plan(api, person, create_plan(api, person))
    enter_checkout(api, person, active)
    checkout(api, person, active)
    api["clock"].advance(125)
    current = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/cooldown", headers=person["headers"]
    )
    assert current.json()["data"]["remaining_seconds"] == 175
    items = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/items", headers=person["headers"]
    )
    assert_error(items, status=409, code="invalid_transition")
    api["clock"].advance(175)
    completed = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/cooldown", headers=person["headers"]
    )
    repeated = api["client"].get(
        f"{BASE}/sessions/{active['session_id']}/cooldown", headers=person["headers"]
    )
    assert completed.json()["data"]["journey_state"] == "completed"
    assert repeated.json()["data"]["cooldown_outcome"] == "completed"
    conn = api["connect"]()
    assert conn.execute(
        "SELECT count(*) FROM research_events WHERE event_type = 'cooldown_completed'"
    ).fetchone()[0] == 1
    conn.close()


def test_override_pause_confirmation_idempotency_and_natural_race(api):
    person = participant(api)
    active = start_plan(api, person, create_plan(api, person))
    enter_checkout(api, person, active)
    checkout(api, person, active)
    key = str(uuid.uuid4())
    started = command(
        api,
        person,
        active["session_id"],
        "override/start",
        body={"idempotency_key": key},
    )
    assert started.json()["data"]["remaining_pause_seconds"] == 15
    api["clock"].advance(5)
    repeated = command(
        api,
        person,
        active["session_id"],
        "override/start",
        body={"idempotency_key": str(uuid.uuid4())},
    )
    assert repeated.json()["data"]["override_available_at"] == started.json()["data"]["override_available_at"]
    early = command(
        api,
        person,
        active["session_id"],
        "override/confirm",
        body={"idempotency_key": str(uuid.uuid4()), "reason_code": "change_plan"},
    )
    early_body = assert_error(early, status=409, code="override_pause_active")
    assert early_body["remaining_pause_seconds"] == 10
    assert early_body["override_available_at"] == started.json()["data"]["override_available_at"]
    invalid = command(
        api,
        person,
        active["session_id"],
        "override/confirm",
        body={"idempotency_key": str(uuid.uuid4()), "reason_code": "skip"},
    )
    assert_error(invalid, status=400, code="invalid_request")
    api["clock"].advance(10)
    confirm_key = str(uuid.uuid4())
    confirmed = command(
        api,
        person,
        active["session_id"],
        "override/confirm",
        body={"idempotency_key": confirm_key, "reason_code": "change_plan"},
    )
    replay = command(
        api,
        person,
        active["session_id"],
        "override/confirm",
        body={"idempotency_key": confirm_key, "reason_code": "change_plan"},
    )
    assert confirmed.json()["data"]["journey"]["cooldown_outcome"] == "overridden"
    assert replay.json()["data"]["journey"]["cooldown_outcome"] == "overridden"

    second = create_plan(api, person)
    start_plan(api, person, second)
    enter_checkout(api, person, second)
    checkout(api, person, second)
    command(api, person, second["session_id"], "override/start")
    api["clock"].advance(300)
    natural = command(
        api,
        person,
        second["session_id"],
        "override/confirm",
        body={"idempotency_key": str(uuid.uuid4()), "reason_code": "other"},
    )
    assert natural.json()["data"]["journey"]["cooldown_outcome"] == "completed"


def test_success_and_error_envelopes_do_not_expose_secrets(api):
    person = participant(api)
    success = api["client"].post(
        f"{BASE}/plans", headers=person["headers"], json=plan_body()
    )
    body = success.json()
    assert body["ok"] is True
    assert body["server_timestamp"] == NOW.isoformat()
    assert body["contract_version"] == "intentional-break-v1"
    encoded = json.dumps(body).lower()
    for secret_field in (
        "access_token",
        "access_token_hash",
        "feed_seed",
        "next_server_sequence_number",
        "retain_until",
    ):
        assert secret_field not in encoded
    error = api["client"].post(
        f"{BASE}/plans", headers=person["headers"], json={}
    )
    assert_error(error, status=400, code="invalid_request")
