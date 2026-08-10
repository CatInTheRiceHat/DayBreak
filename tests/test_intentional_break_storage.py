import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core.research_storage import (
    IntentionalBreakStorageError,
    append_intentional_break_client_events,
    cancel_intentional_break_plan,
    confirm_intentional_break_override,
    create_intentional_break_plan,
    create_participant,
    ensure_sqlite_research_tables,
    finish_intentional_break_early,
    get_current_intentional_break_journey,
    read_intentional_break_items,
    reconcile_intentional_break_cooldown,
    start_intentional_break_override,
    start_intentional_break_session,
    start_session,
    submit_intentional_break_checkout,
)


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "intentional-break-storage.db"
    conn = sqlite3.connect(path, timeout=5)
    ensure_sqlite_research_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def participant(db):
    return create_participant(db, backend="sqlite", condition="balanced")


def reserved_items(count, *, prefix="post"):
    return [
        {
            "post_id": f"{prefix}-{position}",
            "content_category": "positive" if position % 2 else "healthy",
            "source_type": "research_feed",
            "feed_request_id": f"request-{prefix}",
            "feed_policy_version": "balanced-v1",
            "selection_bucket": "healthy",
            "selection_reason": "healthy_category_target",
            "ranking_snapshot": {"score": count - position},
            "provenance_metadata": {"inventory": "fixture"},
        }
        for position in range(1, count + 1)
    ]


def create_plan(
    db,
    participant,
    *,
    count=5,
    key="plan-1",
    previous_session_id=None,
    now=NOW,
    items=None,
):
    return create_intentional_break_plan(
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        intention="quick_break",
        planned_video_count=count,
        selected_cooldown_seconds=300,
        reserved_items=items or reserved_items(count),
        plan_idempotency_key=key,
        previous_session_id=previous_session_id,
        now=now,
    )


def start_plan(db, participant, plan, *, key="start-1", now=NOW):
    return start_intentional_break_session(
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key=key,
        now=now,
    )


def impression(post_id, *, event_id=None, diagnostic=1, timestamp=NOW, ratio=0.7):
    return {
        "client_event_id": event_id or str(uuid.uuid4()),
        "client_sequence_number": diagnostic,
        "event_type": "post_impression",
        "post_id": post_id,
        "client_timestamp": timestamp,
        "metadata": {"visibility_ratio": ratio, "visible_ms": 1000},
    }


def append(db, participant, plan, events, *, now=NOW):
    return append_intentional_break_client_events(
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        events=events,
        now=now,
    )


def enter_checkout(db, participant, plan, *, now=NOW):
    return finish_intentional_break_early(
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="finish-1",
        now=now,
    )


def submit_checkout(db, participant, plan, *, key="checkout-1", now=NOW):
    return submit_intentional_break_checkout(
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        worthwhile_answer="yes",
        perceived_control_answer=3,
        mood_answer="same",
        checkout_version="checkout-v1",
        submission_idempotency_key=key,
        now=now,
    )


def assert_code(code, callable_, *args, **kwargs):
    with pytest.raises(IntentionalBreakStorageError) as caught:
        callable_(*args, **kwargs)
    assert caught.value.code == code


@pytest.mark.parametrize(
    ("count", "estimated", "suggested"),
    [(5, 150, 300), (10, 300, 600), (20, 600, 1200), (40, 1200, 2400)],
)
def test_valid_plans_are_exactly_sized_and_ordered(
    db, participant, count, estimated, suggested
):
    plan = create_plan(db, participant, count=count, key=f"plan-{count}")

    assert plan["journey_state"] == "planned"
    assert plan["estimated_duration_seconds"] == estimated
    assert plan["suggested_cooldown_seconds"] == suggested
    assert db.execute(
        "SELECT post_id, session_position FROM research_session_items "
        "WHERE session_id = ? ORDER BY session_position",
        (plan["session_id"],),
    ).fetchall() == [(f"post-{position}", position) for position in range(1, count + 1)]


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("planned_video_count", 6, "invalid_plan"),
        ("intention", "focus", "invalid_plan"),
        ("selected_cooldown_seconds", 301, "invalid_plan"),
    ],
)
def test_invalid_plan_values_are_rejected(db, participant, field, value, code):
    arguments = {
        "backend": "sqlite",
        "participant_id": participant["participant_id"],
        "intention": "relax",
        "planned_video_count": 5,
        "selected_cooldown_seconds": 300,
        "reserved_items": reserved_items(5),
        "plan_idempotency_key": "invalid-plan",
        "now": NOW,
    }
    arguments[field] = value
    assert_code(code, create_intentional_break_plan, db, **arguments)


@pytest.mark.parametrize("batch_size", [4, 6])
def test_plan_rejects_smaller_or_larger_reserved_batch(db, participant, batch_size):
    assert_code(
        "invalid_reserved_batch",
        create_intentional_break_plan,
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        intention="relax",
        planned_video_count=5,
        selected_cooldown_seconds=300,
        reserved_items=reserved_items(batch_size),
        plan_idempotency_key=f"wrong-size-{batch_size}",
        now=NOW,
    )


def test_plan_rejects_duplicate_posts_and_invalid_provenance(db, participant):
    duplicates = reserved_items(5)
    duplicates[-1]["post_id"] = duplicates[0]["post_id"]
    assert_code(
        "invalid_reserved_batch",
        create_intentional_break_plan,
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        intention="relax",
        planned_video_count=5,
        selected_cooldown_seconds=300,
        reserved_items=duplicates,
        plan_idempotency_key="duplicate-post",
        now=NOW,
    )
    invalid = reserved_items(5)
    del invalid[0]["source_type"]
    assert_code(
        "invalid_reserved_batch",
        create_intentional_break_plan,
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        intention="relax",
        planned_video_count=5,
        selected_cooldown_seconds=300,
        reserved_items=invalid,
        plan_idempotency_key="invalid-provenance",
        now=NOW,
    )


def test_plan_rolls_back_session_event_and_items_on_item_failure(db, participant):
    db.execute(
        "CREATE TRIGGER reject_reserved_item BEFORE INSERT ON research_session_items "
        "WHEN NEW.post_id = 'post-3' BEGIN SELECT RAISE(ABORT, 'fixture rejection'); END"
    )
    db.commit()

    assert_code(
        "invalid_reserved_batch", create_plan, db, participant, key="atomic-failure"
    )
    assert db.execute("SELECT count(*) FROM research_sessions").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM research_session_items").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM research_events").fetchone()[0] == 0


def test_plan_idempotency_nonterminal_rule_and_legacy_compatibility(db, participant):
    first = create_plan(db, participant)
    replay = create_plan(db, participant)
    assert replay["session_id"] == first["session_id"]
    assert db.execute("SELECT count(*) FROM research_sessions").fetchone()[0] == 1

    assert_code(
        "idempotency_conflict",
        create_plan,
        db,
        participant,
        key="plan-1",
        items=reserved_items(5, prefix="different"),
    )
    assert_code(
        "existing_nonterminal_session", create_plan, db, participant, key="plan-2"
    )


def test_legacy_session_does_not_block_v1_plan(db, participant):
    authenticated = {
        "participant_id": participant["participant_id"],
        "assigned_condition": "balanced",
        "status": "active",
    }
    start_session(
        db,
        backend="sqlite",
        participant=authenticated,
        application_version="legacy",
        client_timestamp=NOW,
    )
    assert create_plan(db, participant)["journey_state"] == "planned"


def test_previous_completed_linkage_and_foreign_ownership(db, participant):
    previous = create_plan(db, participant, key="previous")
    start_plan(db, participant, previous)
    enter_checkout(db, participant, previous)
    submit_checkout(db, participant, previous)
    reconcile_intentional_break_cooldown(
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=previous["session_id"],
        now=NOW + timedelta(seconds=300),
    )
    current = create_plan(
        db,
        participant,
        key="current",
        previous_session_id=previous["session_id"],
        now=NOW + timedelta(seconds=600),
    )
    start_plan(db, participant, current, key="start-current", now=NOW + timedelta(seconds=600))
    metadata = json.loads(db.execute(
        "SELECT metadata FROM research_events WHERE session_id = ? "
        "AND event_type = 'session_started'",
        (current["session_id"],),
    ).fetchone()[0])
    assert metadata["previous_session_id"] == previous["session_id"]
    assert metadata["previous_cooldown_outcome"] == "completed"
    assert metadata["seconds_since_previous_session_completed"] == 300

    other = create_participant(db, backend="sqlite", condition="balanced")
    other_plan = create_plan(db, other, key="other-plan")
    cancel_intentional_break_plan(
        db,
        backend="sqlite",
        participant_id=other["participant_id"],
        session_id=other_plan["session_id"],
        idempotency_key="cancel-other",
        now=NOW,
    )
    assert_code(
        "session_not_owned",
        create_plan,
        db,
        participant,
        key="bad-link",
        previous_session_id=other_plan["session_id"],
    )


def test_start_is_explicit_idempotent_and_visible_to_another_read(db, participant):
    plan = create_plan(db, participant)
    started = start_plan(db, participant, plan)
    replay = start_plan(db, participant, plan)
    current = get_current_intentional_break_journey(
        db, backend="sqlite", participant_id=participant["participant_id"], now=NOW
    )
    assert started["journey_state"] == replay["journey_state"] == "active"
    assert current["session_id"] == plan["session_id"]
    assert db.execute(
        "SELECT count(*) FROM research_events WHERE session_id = ? "
        "AND event_type = 'session_started'",
        (plan["session_id"],),
    ).fetchone()[0] == 1


def test_incomplete_batch_and_cancelled_plan_cannot_start(db, participant):
    plan = create_plan(db, participant)
    db.execute(
        "DELETE FROM research_session_items WHERE session_id = ? AND session_position = 5",
        (plan["session_id"],),
    )
    db.commit()
    assert_code("invalid_reserved_batch", start_plan, db, participant, plan)

    db.execute(
        "INSERT INTO research_session_items (id, session_id, participant_id, post_id, "
        "session_position, content_category, feed_policy_version, selection_bucket, "
        "selection_reason, ranking_snapshot, provenance_metadata, reserved_at) "
        "VALUES (?, ?, ?, 'post-5', 5, 'positive', 'balanced-v1', 'healthy', "
        "'healthy_category_target', '{}', '{}', ?)",
        (str(uuid.uuid4()), plan["session_id"], participant["participant_id"], NOW.isoformat()),
    )
    db.commit()
    cancel_intentional_break_plan(
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="cancel-1",
        now=NOW,
    )
    assert_code("invalid_transition", start_plan, db, participant, plan)


def test_cancel_is_planned_only_and_idempotent(db, participant):
    plan = create_plan(db, participant)
    cancelled = cancel_intentional_break_plan(
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="cancel-1",
        now=NOW,
    )
    replay = cancel_intentional_break_plan(
        db,
        backend="sqlite",
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="cancel-1",
        now=NOW + timedelta(seconds=1),
    )
    assert cancelled["cancelled_at"] == replay["cancelled_at"]
    assert get_current_intentional_break_journey(
        db, participant_id=participant["participant_id"], now=NOW
    ) is None


def test_item_reads_are_stable_paginated_and_write_once(db, participant):
    plan = create_plan(db, participant, count=10)
    assert_code(
        "invalid_transition",
        read_intentional_break_items,
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        start_position=1,
        requested_limit=4,
        now=NOW,
    )
    start_plan(db, participant, plan)
    first = read_intentional_break_items(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        start_position=1,
        requested_limit=4,
        now=NOW,
    )
    middle = read_intentional_break_items(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        cursor=5,
        limit=4,
        now=NOW + timedelta(minutes=1),
    )
    final = read_intentional_break_items(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        start_position=9,
        requested_limit=4,
        now=NOW + timedelta(minutes=1),
    )
    reset = read_intentional_break_items(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        start_position=1,
        requested_limit=4,
        now=NOW + timedelta(minutes=2),
    )
    assert [item["post_id"] for item in first["items"]] == [f"post-{i}" for i in range(1, 5)]
    assert [item["global_position"] for item in middle["items"]] == [5, 6, 7, 8]
    assert [item["global_position"] for item in final["items"]] == [9, 10]
    assert final["has_more"] is False and final["next_cursor"] is None
    assert reset["items"] == first["items"]
    assert db.execute(
        "SELECT count(*) FROM research_session_items WHERE session_id = ?",
        (plan["session_id"],),
    ).fetchone()[0] == 10


def test_items_are_unavailable_after_feed_exit(db, participant):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    enter_checkout(db, participant, plan)
    assert_code(
        "invalid_transition",
        read_intentional_break_items,
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        start_position=1,
        requested_limit=5,
        now=NOW,
    )


def test_client_events_use_server_order_and_server_derived_provenance(db, participant):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    events = [
        impression("post-1", diagnostic=90),
        {
            "client_event_id": str(uuid.uuid4()),
            "client_sequence_number": 2,
            "event_type": "post_viewed",
            "post_id": "post-1",
            "client_timestamp": NOW,
            "metadata": {"feed_position": 999, "selection_bucket": "forged"},
        },
    ]
    result = append(db, participant, plan, events)
    rows = db.execute(
        "SELECT server_sequence_number, sequence_number, client_sequence_number, "
        "content_category, metadata FROM research_events WHERE session_id = ? "
        "AND event_authority = 'client' ORDER BY server_sequence_number",
        (plan["session_id"],),
    ).fetchall()
    assert [row[0] for row in rows] == sorted(row[0] for row in rows)
    assert all(row[0] == row[1] for row in rows)
    assert [row[2] for row in rows] == [90, 2]
    assert rows[0][3] == "positive"
    assert json.loads(rows[1][4])["feed_position"] == 1
    assert json.loads(rows[1][4])["selection_bucket"] == "healthy"
    assert result["accepted"][1]["server_sequence_number"] == rows[1][0]


def test_client_event_idempotency_conflict_and_unreserved_rejection(db, participant):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    event = impression("post-1", event_id="11111111-1111-4111-8111-111111111111")
    first = append(db, participant, plan, [event])
    replay = append(db, participant, plan, [event], now=NOW + timedelta(seconds=10))
    assert first["accepted"][0]["server_sequence_number"] == replay["accepted"][0]["server_sequence_number"]
    assert replay["duplicates"] == [event["client_event_id"]]
    conflict = {**event, "post_id": "post-2"}
    assert_code("idempotency_conflict", append, db, participant, plan, [conflict])
    assert_code(
        "event_provenance_invalid",
        append,
        db,
        participant,
        plan,
        [impression("not-reserved")],
    )


def test_boundary_requires_final_impression_and_orders_events(db, participant):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    nonfinal = append(db, participant, plan, [impression("post-4")])
    assert nonfinal["journey"]["journey_state"] == "active"
    viewed = {
        "client_event_id": str(uuid.uuid4()),
        "client_sequence_number": 2,
        "event_type": "post_viewed",
        "post_id": "post-5",
        "client_timestamp": NOW,
        "metadata": {},
    }
    assert append(db, participant, plan, [viewed])["journey"]["journey_state"] == "active"
    final = impression("post-5", event_id="22222222-2222-4222-8222-222222222222")
    boundary = append(db, participant, plan, [final])
    client_sequence = boundary["accepted"][0]["server_sequence_number"]
    boundary_sequence = boundary["lifecycle_events"][0]["server_sequence_number"]
    assert boundary["journey"]["journey_state"] == "checkout"
    assert boundary["journey"]["finish_reason"] == "boundary_reached"
    assert client_sequence + 1 == boundary_sequence
    append(db, participant, plan, [final])
    assert db.execute(
        "SELECT count(*) FROM research_events WHERE session_id = ? "
        "AND event_type = 'session_boundary_reached'",
        (plan["session_id"],),
    ).fetchone()[0] == 1


@pytest.mark.parametrize(
    ("meaningful_positions", "expected_highest"),
    [
        ([], 0),
        ([2], 2),
        ([1, 2, 3, 4], 4),
    ],
)
def test_finish_early_preserves_only_server_accepted_meaningful_progress(
    db, participant, meaningful_positions, expected_highest
):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    for diagnostic, position in enumerate(meaningful_positions, start=1):
        append(
            db,
            participant,
            plan,
            [impression(f"post-{position}", diagnostic=diagnostic)],
        )
    finish = finish_intentional_break_early(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="finish-1",
        now=NOW,
    )
    assert finish["highest_reached_position"] == expected_highest
    assert finish["finish_reason"] == "finished_early"
    stored = db.execute(
        "SELECT journey_state, finish_reason, highest_reached_position, "
        "checkout_entered_at FROM research_sessions WHERE id = ?",
        (plan["session_id"],),
    ).fetchone()
    assert stored[:3] == ("checkout", "finished_early", expected_highest)
    assert stored[3] is not None
    event_rows = db.execute(
        "SELECT event_type, metadata FROM research_events WHERE session_id = ? "
        "ORDER BY server_sequence_number",
        (plan["session_id"],),
    ).fetchall()
    finish_events = [row for row in event_rows if row[0] == "session_finished_early"]
    assert len(finish_events) == 1
    assert json.loads(finish_events[0][1])["highest_meaningful_position"] == expected_highest
    assert sum(row[0] == "post_impression" for row in event_rows) == len(meaningful_positions)


def test_highest_position_never_decreases_and_finish_outcomes_are_exclusive(db, participant):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    append(db, participant, plan, [impression("post-4")])
    append(db, participant, plan, [impression("post-2")])
    assert get_current_intentional_break_journey(
        db, participant_id=participant["participant_id"], now=NOW
    )["highest_reached_position"] == 4
    finish = finish_intentional_break_early(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="finish-1",
        now=NOW,
    )
    assert finish["highest_reached_position"] == 4
    assert finish["finish_reason"] == "finished_early"
    append(db, participant, plan, [impression("post-5")])
    assert db.execute(
        "SELECT count(*) FROM research_events WHERE session_id = ? "
        "AND event_type = 'session_boundary_reached'",
        (plan["session_id"],),
    ).fetchone()[0] == 0


def test_finish_early_validates_state_and_idempotency(db, participant):
    plan = create_plan(db, participant)
    assert_code(
        "invalid_transition",
        finish_intentional_break_early,
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="planned-finish",
        now=NOW,
    )
    start_plan(db, participant, plan)
    first = enter_checkout(db, participant, plan)
    replay = enter_checkout(db, participant, plan)
    assert first["checkout_entered_at"] == replay["checkout_entered_at"]
    assert_code(
        "invalid_transition",
        finish_intentional_break_early,
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="different-finish-key",
        now=NOW,
    )
    assert db.execute(
        "SELECT count(*) FROM research_events WHERE session_id = ? "
        "AND event_type = 'session_finished_early'",
        (plan["session_id"],),
    ).fetchone()[0] == 1


def test_finish_early_event_and_transition_roll_back_atomically(db, participant):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    db.execute(
        "CREATE TRIGGER reject_finish_early_transition "
        "BEFORE UPDATE OF journey_state ON research_sessions "
        "WHEN NEW.finish_reason = 'finished_early' "
        "BEGIN SELECT RAISE(ABORT, 'forced finish failure'); END"
    )
    db.commit()

    assert_code(
        "invalid_transition",
        finish_intentional_break_early,
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="atomic-finish",
        now=NOW,
    )
    assert db.execute(
        "SELECT journey_state, finish_reason, highest_reached_position "
        "FROM research_sessions WHERE id = ?",
        (plan["session_id"],),
    ).fetchone() == ("active", None, 0)
    assert db.execute(
        "SELECT count(*) FROM research_events WHERE session_id = ? "
        "AND event_type = 'session_finished_early'",
        (plan["session_id"],),
    ).fetchone()[0] == 0


@pytest.mark.parametrize(
    ("worthwhile", "control", "mood"),
    [
        ("yes", 1, "better"),
        ("mostly", 3, "same"),
        ("not_really", 5, "worse"),
        ("prefer_not_to_answer", "prefer_not_to_answer", "prefer_not_to_answer"),
    ],
)
def test_checkout_accepts_every_answer_category(db, participant, worthwhile, control, mood):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    enter_checkout(db, participant, plan)
    result = submit_intentional_break_checkout(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        worthwhile_answer=worthwhile,
        perceived_control_answer=control,
        mood_answer=mood,
        checkout_version="checkout-v1",
        submission_idempotency_key="checkout-answers",
        now=NOW,
    )
    assert result["journey_state"] == "cooldown"
    assert result["checkout_submitted"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("worthwhile_answer", None),
        ("worthwhile_answer", "maybe"),
        ("perceived_control_answer", "3"),
        ("perceived_control_answer", 6),
        ("mood_answer", "mixed"),
    ],
)
def test_checkout_rejects_missing_or_invalid_answers(db, participant, field, value):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    enter_checkout(db, participant, plan)
    arguments = {
        "participant_id": participant["participant_id"],
        "session_id": plan["session_id"],
        "worthwhile_answer": "yes",
        "perceived_control_answer": 3,
        "mood_answer": "same",
        "checkout_version": "checkout-v1",
        "submission_idempotency_key": "invalid-checkout",
        "now": NOW,
    }
    arguments[field] = value
    assert_code("checkout_invalid", submit_intentional_break_checkout, db, **arguments)


def test_checkout_is_single_idempotent_and_starts_server_timed_cooldown(db, participant):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    enter_checkout(db, participant, plan)
    first = submit_checkout(db, participant, plan)
    replay = submit_checkout(db, participant, plan, now=NOW + timedelta(seconds=10))
    assert first["cooldown_started_at"] == replay["cooldown_started_at"] == NOW.isoformat()
    assert first["cooldown_ends_at"] == (NOW + timedelta(seconds=300)).isoformat()
    sequences = db.execute(
        "SELECT event_type, server_sequence_number FROM research_events "
        "WHERE session_id = ? AND event_type IN ('checkout_submitted', 'cooldown_started') "
        "ORDER BY server_sequence_number",
        (plan["session_id"],),
    ).fetchall()
    assert sequences[0][1] + 1 == sequences[1][1]
    assert [row[0] for row in sequences] == ["checkout_submitted", "cooldown_started"]
    assert db.execute("SELECT count(*) FROM research_session_checkouts").fetchone()[0] == 1
    assert_code(
        "idempotency_conflict",
        submit_intentional_break_checkout,
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        worthwhile_answer="mostly",
        perceived_control_answer=3,
        mood_answer="same",
        checkout_version="checkout-v1",
        submission_idempotency_key="checkout-1",
        now=NOW,
    )


@pytest.mark.parametrize("offset", [0, 1, 300])
def test_natural_cooldown_completion_timing_and_idempotency(db, participant, offset):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    enter_checkout(db, participant, plan)
    submit_checkout(db, participant, plan)
    check_time = NOW + timedelta(seconds=300 + offset)
    first = reconcile_intentional_break_cooldown(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        now=check_time,
    )
    second = reconcile_intentional_break_cooldown(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        now=check_time + timedelta(seconds=1),
    )
    assert first["journey_state"] == second["journey_state"] == "completed"
    assert first["cooldown_outcome"] == "completed"
    assert db.execute(
        "SELECT count(*) FROM research_events WHERE session_id = ? "
        "AND event_type = 'cooldown_completed'",
        (plan["session_id"],),
    ).fetchone()[0] == 1
    assert get_current_intentional_break_journey(
        db, participant_id=participant["participant_id"], now=check_time
    ) is None


def test_cooldown_does_not_complete_before_end_and_current_read_reconciles(db, participant):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    enter_checkout(db, participant, plan)
    submit_checkout(db, participant, plan)
    early = reconcile_intentional_break_cooldown(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        now=NOW + timedelta(seconds=299),
    )
    assert early["journey_state"] == "cooldown"
    assert early["cooldown_remaining_seconds"] == 1
    completed = get_current_intentional_break_journey(
        db,
        participant_id=participant["participant_id"],
        now=NOW + timedelta(seconds=300),
    )
    assert completed["journey_state"] == "completed"


def test_override_has_stable_fifteen_second_pause_and_idempotent_start(db, participant):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    enter_checkout(db, participant, plan)
    submit_checkout(db, participant, plan)
    first = start_intentional_break_override(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="override-start-1",
        now=NOW + timedelta(seconds=10),
    )
    retry = start_intentional_break_override(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="another-tab-key",
        now=NOW + timedelta(seconds=12),
    )
    refreshed = get_current_intentional_break_journey(
        db,
        participant_id=participant["participant_id"],
        now=NOW + timedelta(seconds=12),
    )
    expected = (NOW + timedelta(seconds=25)).isoformat()
    assert first["override_available_at"] == retry["override_available_at"] == expected
    assert refreshed["override_available_at"] == expected
    assert db.execute(
        "SELECT count(*) FROM research_events WHERE session_id = ? "
        "AND event_type = 'cooldown_override_started'",
        (plan["session_id"],),
    ).fetchone()[0] == 1


def test_override_confirmation_rules_and_natural_completion_race(db, participant):
    plan = create_plan(db, participant)
    start_plan(db, participant, plan)
    enter_checkout(db, participant, plan)
    submit_checkout(db, participant, plan)
    assert_code(
        "override_not_started",
        confirm_intentional_break_override,
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        reason_code="change_plan",
        confirmation_idempotency_key="confirm-before-start",
        now=NOW + timedelta(seconds=1),
    )
    start_intentional_break_override(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="start-override",
        now=NOW + timedelta(seconds=2),
    )
    assert_code(
        "override_pause_active",
        confirm_intentional_break_override,
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        reason_code="change_plan",
        confirmation_idempotency_key="early-confirm",
        now=NOW + timedelta(seconds=16),
    )
    assert_code(
        "event_not_allowed",
        confirm_intentional_break_override,
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        reason_code="skip_wait",
        confirmation_idempotency_key="bad-reason",
        now=NOW + timedelta(seconds=17),
    )
    completed = confirm_intentional_break_override(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        reason_code="change_plan",
        confirmation_idempotency_key="confirm-override",
        now=NOW + timedelta(seconds=17),
    )
    replay = confirm_intentional_break_override(
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        reason_code="change_plan",
        confirmation_idempotency_key="confirm-override",
        now=NOW + timedelta(seconds=18),
    )
    assert completed["cooldown_outcome"] == replay["cooldown_outcome"] == "overridden"
    assert db.execute(
        "SELECT count(*) FROM research_events WHERE session_id = ? "
        "AND event_type = 'cooldown_overridden'",
        (plan["session_id"],),
    ).fetchone()[0] == 1
    assert_code(
        "idempotency_conflict",
        confirm_intentional_break_override,
        db,
        participant_id=participant["participant_id"],
        session_id=plan["session_id"],
        reason_code="other",
        confirmation_idempotency_key="confirm-override",
        now=NOW + timedelta(seconds=19),
    )

    second = create_plan(db, participant, key="race-plan", now=NOW + timedelta(seconds=20))
    start_plan(db, participant, second, key="race-start", now=NOW + timedelta(seconds=20))
    enter_checkout(db, participant, second, now=NOW + timedelta(seconds=20))
    submit_checkout(db, participant, second, key="race-checkout", now=NOW + timedelta(seconds=20))
    start_intentional_break_override(
        db,
        participant_id=participant["participant_id"],
        session_id=second["session_id"],
        idempotency_key="race-override",
        now=NOW + timedelta(seconds=30),
    )
    natural_winner = confirm_intentional_break_override(
        db,
        participant_id=participant["participant_id"],
        session_id=second["session_id"],
        reason_code="other",
        confirmation_idempotency_key="race-confirm",
        now=NOW + timedelta(seconds=320),
    )
    assert natural_winner["cooldown_outcome"] == "completed"
    assert db.execute(
        "SELECT count(*) FROM research_events WHERE session_id = ? "
        "AND event_type = 'cooldown_overridden'",
        (second["session_id"],),
    ).fetchone()[0] == 0


def test_participant_and_session_errors_are_stable(db, participant):
    assert_code(
        "participant_not_found",
        get_current_intentional_break_journey,
        db,
        participant_id=str(uuid.uuid4()),
        now=NOW,
    )
    plan = create_plan(db, participant)
    other = create_participant(db, backend="sqlite", condition="balanced")
    assert_code(
        "session_not_owned",
        start_intentional_break_session,
        db,
        participant_id=other["participant_id"],
        session_id=plan["session_id"],
        idempotency_key="wrong-owner",
        now=NOW,
    )
    db.execute(
        "UPDATE research_participants SET status = 'withdrawn' WHERE id = ?",
        (participant["participant_id"],),
    )
    db.commit()
    assert_code(
        "participant_inactive",
        get_current_intentional_break_journey,
        db,
        participant_id=participant["participant_id"],
        now=NOW,
    )


def test_two_sqlite_plan_attempts_create_at_most_one_nonterminal_session(tmp_path):
    path = tmp_path / "concurrent-plan.db"
    setup = sqlite3.connect(path, timeout=5)
    ensure_sqlite_research_tables(setup)
    participant = create_participant(setup, backend="sqlite", condition="balanced")
    setup.close()
    barrier = threading.Barrier(2)
    outcomes = []

    def worker(index):
        conn = sqlite3.connect(path, timeout=5)
        barrier.wait()
        try:
            outcomes.append(create_plan(conn, participant, key=f"concurrent-{index}"))
        except IntentionalBreakStorageError as exc:
            outcomes.append(exc.code)
        finally:
            conn.close()

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    verify = sqlite3.connect(path)
    assert verify.execute(
        "SELECT count(*) FROM research_sessions WHERE journey_state = 'planned'"
    ).fetchone()[0] == 1
    assert sum(isinstance(outcome, dict) for outcome in outcomes) == 1
    assert "existing_nonterminal_session" in outcomes
    verify.close()


def test_concurrent_final_impressions_create_one_boundary_and_unique_sequences(tmp_path):
    path = tmp_path / "concurrent-boundary.db"
    setup = sqlite3.connect(path, timeout=5)
    ensure_sqlite_research_tables(setup)
    participant = create_participant(setup, backend="sqlite", condition="balanced")
    plan = create_plan(setup, participant)
    start_plan(setup, participant, plan)
    setup.close()
    barrier = threading.Barrier(2)
    outcomes = []

    def worker(index):
        conn = sqlite3.connect(path, timeout=5)
        barrier.wait()
        try:
            outcomes.append(append(
                conn,
                participant,
                plan,
                [impression("post-5", diagnostic=index + 1)],
            ))
        except IntentionalBreakStorageError as exc:
            outcomes.append(exc.code)
        finally:
            conn.close()

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    verify = sqlite3.connect(path)
    assert all(isinstance(outcome, dict) for outcome in outcomes)
    assert verify.execute(
        "SELECT count(*) FROM research_events WHERE event_type = 'session_boundary_reached'"
    ).fetchone()[0] == 1
    sequences = [row[0] for row in verify.execute(
        "SELECT server_sequence_number FROM research_events ORDER BY server_sequence_number"
    )]
    assert len(sequences) == len(set(sequences))
    assert verify.execute(
        "SELECT journey_state FROM research_sessions WHERE id = ?", (plan["session_id"],)
    ).fetchone()[0] == "checkout"
    verify.close()


def test_concurrent_checkout_submissions_create_one_checkout(tmp_path):
    path = tmp_path / "concurrent-checkout.db"
    setup = sqlite3.connect(path, timeout=5)
    ensure_sqlite_research_tables(setup)
    participant = create_participant(setup, backend="sqlite", condition="balanced")
    plan = create_plan(setup, participant)
    start_plan(setup, participant, plan)
    enter_checkout(setup, participant, plan)
    setup.close()
    barrier = threading.Barrier(2)
    outcomes = []

    def worker(index):
        conn = sqlite3.connect(path, timeout=5)
        barrier.wait()
        try:
            outcomes.append(submit_checkout(
                conn,
                participant,
                plan,
                key=f"concurrent-checkout-{index}",
            ))
        except IntentionalBreakStorageError as exc:
            outcomes.append(exc.code)
        finally:
            conn.close()

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    verify = sqlite3.connect(path)
    assert sum(isinstance(outcome, dict) for outcome in outcomes) == 1
    assert "checkout_invalid" in outcomes
    assert verify.execute("SELECT count(*) FROM research_session_checkouts").fetchone()[0] == 1
    assert verify.execute(
        "SELECT count(*) FROM research_events WHERE event_type = 'checkout_submitted'"
    ).fetchone()[0] == 1
    verify.close()
