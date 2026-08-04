import json
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError

from core.research_storage import create_participant, ensure_sqlite_research_tables
from research_api import (
    CompleteSessionRequest,
    EventBatchRequest,
    ResearchEventRequest,
    StartSessionRequest,
    create_research_router,
)


def route_endpoint(router, path, method):
    for route in router.routes:
        if route.path == path and method.upper() in route.methods:
            return route.endpoint
    raise AssertionError(f"Missing {method} {path}")


@pytest.fixture
def api(tmp_path):
    db_path = tmp_path / "api-research.db"

    def connect():
        conn = sqlite3.connect(db_path)
        ensure_sqlite_research_tables(conn)
        return conn

    rows = []
    for index in range(18):
        if index < 9:
            title = f"Harmless comedy music clip {index}"
            description = "A normal low-risk general interest video with jokes, games and music."
            category = "comedy"
        elif index < 15:
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
            "channel_id": f"creator-{index % 8}",
            "channel_title": f"Creator {index % 8}",
            "source_category": category,
            "source_query": f"{category} seed",
            "source_type": "search",
            "integrity_score": 0.8,
            "tags": [category],
        })
    router = create_research_router(
        get_connection=connect,
        backend="sqlite",
        load_feed_source=lambda _conn: (rows, None),
    )
    return router, connect


def start_condition(router, connect, condition):
    conn = connect()
    participant = create_participant(conn, backend="sqlite", condition=condition)
    conn.close()
    start = route_endpoint(router, "/api/research/sessions", "POST")
    session = start(
        StartSessionRequest(
            application_version="test",
            client_timestamp=datetime.now(timezone.utc),
        ),
        authorization=f"Bearer {participant['access_token']}",
    )
    return participant, session


def load_feed(router, participant, session, **overrides):
    endpoint = route_endpoint(router, "/api/research/sessions/{session_id}/feed", "GET")
    params = {
        "session_id": session["session_id"],
        "response": Response(),
        "k": 12,
        "exclude_ids": None,
        "condition": None,
        "feed_policy_version": None,
        "seed": None,
        "authorization": f"Bearer {participant['access_token']}",
    }
    params.update(overrides)
    return endpoint(**params)


def test_api_accepts_valid_event_and_derives_identity_and_condition(api):
    router, connect = api
    create = route_endpoint(router, "/api/research/participants", "POST")
    start = route_endpoint(router, "/api/research/sessions", "POST")
    write = route_endpoint(router, "/api/research/events/batch", "POST")

    participant = create()
    session = start(
        StartSessionRequest(
            application_version="test",
            client_timestamp=datetime.now(timezone.utc),
        ),
        authorization=f"Bearer {participant['access_token']}",
    )
    feed = load_feed(router, participant, session, k=1)
    issued = feed["items"][0]
    request = EventBatchRequest(
        session_id=session["session_id"],
        events=[{
            "event_id": "77777777-7777-4777-8777-777777777777",
            "sequence_number": 1,
            "event_type": "post_impression",
            "post_id": issued["post_id"],
            "content_category": "blocked",
            "client_timestamp": datetime.now(timezone.utc),
            "metadata": {
                "visibility_ratio": 0.75,
                "visible_ms": 1000,
                "feed_request_id": issued["feed_request_id"],
                "feed_policy_version": "forged-policy",
                "selection_bucket": "forged-bucket",
                "selection_reason": "forged-reason",
                "feed_position": 999,
            },
        }],
    )
    result = write(request, authorization=f"Bearer {participant['access_token']}")

    assert result["ok"] is True
    conn = connect()
    row = conn.execute(
        "SELECT participant_id, feed_condition, content_category, metadata, server_timestamp "
        "FROM research_events "
        "WHERE id = '77777777-7777-4777-8777-777777777777'"
    ).fetchone()
    conn.close()
    assert row[0] == participant["participant_id"]
    assert row[1] == participant["assigned_condition"]
    assert row[2] == issued["content_category"]
    metadata = json.loads(row[3])
    assert metadata["feed_policy_version"] == issued["feed_policy_version"]
    assert metadata["selection_bucket"] == issued["selection_bucket"]
    assert metadata["selection_reason"] == issued["selection_reason"]
    assert metadata["feed_position"] == issued["feed_position"]
    assert row[4]


def test_regular_and_balanced_sessions_receive_versioned_server_policies(api):
    router, connect = api
    regular_participant, regular_session = start_condition(router, connect, "regular")
    balanced_participant, balanced_session = start_condition(router, connect, "balanced")

    regular_feed = load_feed(router, regular_participant, regular_session)
    balanced_feed = load_feed(router, balanced_participant, balanced_session)

    assert regular_session["feed_policy_version"] == "regular-v1"
    assert balanced_session["feed_policy_version"] == "balanced-v1"
    assert {item["feed_policy_version"] for item in regular_feed["items"]} == {"regular-v1"}
    assert {item["feed_policy_version"] for item in balanced_feed["items"]} == {"balanced-v1"}

    conn = connect()
    started = conn.execute(
        "SELECT metadata FROM research_events WHERE session_id = ? AND event_type = 'session_started'",
        (balanced_session["session_id"],),
    ).fetchone()[0]
    stored_policy = conn.execute(
        "SELECT feed_policy_version FROM research_sessions WHERE id = ?",
        (balanced_session["session_id"],),
    ).fetchone()[0]
    conn.close()
    assert json.loads(started)["feed_policy_version"] == "balanced-v1"
    assert stored_policy == "balanced-v1"
    assert "feed_seed" not in balanced_session
    assert "feed_seed" not in balanced_feed


def test_development_debug_header_is_opt_in(api, monkeypatch):
    router, connect = api
    participant, session = start_condition(router, connect, "balanced")
    endpoint = route_endpoint(router, "/api/research/sessions/{session_id}/feed", "GET")
    response = Response()
    monkeypatch.setenv("CHRYSALIS_RESEARCH_DEBUG", "1")

    endpoint(
        session_id=session["session_id"],
        response=response,
        k=1,
        exclude_ids=None,
        condition=None,
        feed_policy_version=None,
        seed=None,
        authorization=f"Bearer {participant['access_token']}",
    )

    assert response.headers["X-Chrysalis-Research-Policy"] == "balanced-v1"


def test_post_events_without_issued_feed_provenance_are_rejected(api):
    router, connect = api
    participant, session = start_condition(router, connect, "regular")
    write = route_endpoint(router, "/api/research/events/batch", "POST")
    request = EventBatchRequest(
        session_id=session["session_id"],
        events=[{
            "event_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "sequence_number": 1,
            "event_type": "post_liked",
            "post_id": "not-issued",
            "client_timestamp": datetime.now(timezone.utc),
        }],
    )

    with pytest.raises(HTTPException) as raised:
        write(request, authorization=f"Bearer {participant['access_token']}")
    assert raised.value.status_code == 409


def test_client_condition_policy_and_seed_overrides_are_rejected(api):
    router, connect = api
    participant, session = start_condition(router, connect, "regular")
    for override in (
        {"condition": "balanced"},
        {"feed_policy_version": "balanced-v1"},
        {"seed": "client-seed"},
    ):
        with pytest.raises(HTTPException) as raised:
            load_feed(router, participant, session, **override)
        assert raised.value.status_code == 400


def test_session_cannot_read_another_participants_feed(api):
    router, connect = api
    owner, session = start_condition(router, connect, "regular")
    outsider, _ = start_condition(router, connect, "balanced")

    with pytest.raises(HTTPException) as raised:
        load_feed(router, outsider, session)
    assert raised.value.status_code == 404
    assert owner["participant_id"] != outsider["participant_id"]


@pytest.mark.parametrize("status", ["completed", "withdrawn", "deletion_requested"])
def test_inactive_sessions_cannot_load_research_feed(api, status):
    router, connect = api
    participant, session = start_condition(router, connect, "regular")
    conn = connect()
    conn.execute("UPDATE research_sessions SET status = ? WHERE id = ?", (status, session["session_id"]))
    conn.commit()
    conn.close()

    with pytest.raises(HTTPException) as raised:
        load_feed(router, participant, session)
    assert raised.value.status_code == 409


def test_inactive_participant_cannot_load_research_feed(api):
    router, connect = api
    participant, session = start_condition(router, connect, "regular")
    conn = connect()
    conn.execute(
        "UPDATE research_participants SET status = 'withdrawn' WHERE id = ?",
        (participant["participant_id"],),
    )
    conn.commit()
    conn.close()

    with pytest.raises(HTTPException) as raised:
        load_feed(router, participant, session)
    assert raised.value.status_code == 409


def test_invalid_event_type_is_rejected():
    with pytest.raises(ValidationError, match="event_type"):
        ResearchEventRequest(
            event_id="88888888-8888-4888-8888-888888888888",
            sequence_number=1,
            event_type="private_message_read",
            client_timestamp=datetime.now(timezone.utc),
        )


def test_post_event_requires_post_id():
    with pytest.raises(ValidationError, match="post_id"):
        ResearchEventRequest(
            event_id="99999999-9999-4999-8999-999999999999",
            sequence_number=1,
            event_type="post_liked",
            client_timestamp=datetime.now(timezone.utc),
        )


def test_timestamp_must_include_timezone():
    with pytest.raises(ValidationError, match="timezone"):
        StartSessionRequest(
            application_version="test",
            client_timestamp=datetime.now(),
        )


def test_unstructured_or_sensitive_metadata_is_rejected():
    with pytest.raises(ValidationError, match="unsupported metadata"):
        ResearchEventRequest(
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            sequence_number=1,
            event_type="post_reported",
            post_id="post-a",
            client_timestamp=datetime.now(timezone.utc),
            metadata={"comment_text": "private text must not be stored"},
        )


def test_missing_bearer_token_is_unauthorized(api):
    router, _ = api
    start = route_endpoint(router, "/api/research/sessions", "POST")
    with pytest.raises(HTTPException) as raised:
        start(
            StartSessionRequest(
                application_version="test",
                client_timestamp=datetime.now(timezone.utc),
            ),
            authorization=None,
        )
    assert raised.value.status_code == 401


def test_session_started_and_completed_are_server_owned_event_types():
    with pytest.raises(ValidationError, match="event_type"):
        ResearchEventRequest(
            event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            sequence_number=1,
            event_type="session_started",
            client_timestamp=datetime.now(timezone.utc),
        )

    request = CompleteSessionRequest(
        event_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        sequence_number=1,
        client_timestamp=datetime.now(timezone.utc),
    )
    assert str(request.event_id) == "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
