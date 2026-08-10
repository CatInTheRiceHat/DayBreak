#!/usr/bin/env python3
"""Safe manual participant administration for the closed DayBreak pilot.

This trusted-backend utility deliberately accepts only an exact anonymous
participant UUID. It never displays bearer credentials, token hashes, feed
seeds, event payloads, or database connection strings.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import resolve_database_path  # noqa: E402


RELATED_TABLES = (
    "research_sessions",
    "research_events",
    "research_feed_items",
    "research_session_items",
    "research_session_checkouts",
)
NONTERMINAL_STATES = ("planned", "active", "checkout", "cooldown")


class AdminError(RuntimeError):
    """Expected, safely reportable operator error."""


def _placeholder(backend: str) -> str:
    return "%s" if backend == "postgres" else "?"


def _db_timestamp(backend: str, value: datetime) -> datetime | str:
    return value if backend == "postgres" else value.isoformat()


def _serialize_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def exact_participant_id(value: str) -> str:
    """Return the canonical UUID or reject partial/non-UUID input."""
    try:
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError) as exc:
        raise AdminError("participant-id must be one complete UUID") from exc


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdminError("timestamp must be a valid ISO 8601 value") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AdminError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def connect_database(*, backend: str, db_path: str | None = None):
    """Open the configured trusted-backend connection without printing secrets."""
    if backend == "postgres":
        if not os.environ.get("DATABASE_URL"):
            raise AdminError("DATABASE_URL is required for the PostgreSQL backend")
        try:
            import psycopg2

            return psycopg2.connect(os.environ["DATABASE_URL"])
        except AdminError:
            raise
        except Exception as exc:
            raise AdminError(
                f"could not connect to PostgreSQL ({type(exc).__name__})"
            ) from exc

    conn = sqlite3.connect(resolve_database_path(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _begin_mutation(conn, *, backend: str) -> None:
    # A CLI preview may have opened an implicit read transaction. Start the
    # mutation from a clean boundary on both supported backends.
    conn.rollback()
    if backend == "sqlite":
        conn.execute("BEGIN IMMEDIATE")
    else:
        conn.cursor().execute("BEGIN")


def _count(cur, sql: str, params: tuple[Any, ...]) -> int:
    cur.execute(sql, params)
    return int(cur.fetchone()[0])


def preview_participant(
    conn,
    *,
    backend: str,
    participant_id: str,
    lock: bool = False,
) -> dict[str, Any]:
    """Return a bounded record-count preview containing no credentials or payloads."""
    participant_id = exact_participant_id(participant_id)
    ph = _placeholder(backend)
    lock_sql = " FOR UPDATE" if lock and backend == "postgres" else ""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, status, created_at, assigned_condition, withdrawn_at, "
        "deletion_requested_at FROM research_participants "
        f"WHERE id = {ph}{lock_sql}",
        (participant_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise AdminError("participant not found")

    session_count = _count(
        cur,
        f"SELECT count(*) FROM research_sessions WHERE participant_id = {ph}",
        (participant_id,),
    )
    event_count = _count(
        cur,
        f"SELECT count(*) FROM research_events WHERE participant_id = {ph}",
        (participant_id,),
    )
    legacy_item_count = _count(
        cur,
        f"SELECT count(*) FROM research_feed_items WHERE participant_id = {ph}",
        (participant_id,),
    )
    reserved_item_count = _count(
        cur,
        f"SELECT count(*) FROM research_session_items WHERE participant_id = {ph}",
        (participant_id,),
    )
    checkout_count = _count(
        cur,
        f"SELECT count(*) FROM research_session_checkouts WHERE participant_id = {ph}",
        (participant_id,),
    )
    placeholders = ", ".join([ph] * len(NONTERMINAL_STATES))
    cur.execute(
        "SELECT id, journey_state FROM research_sessions "
        f"WHERE participant_id = {ph} AND journey_version = 'intentional_break_v1' "
        f"AND journey_state IN ({placeholders}) ORDER BY plan_created_at DESC LIMIT 1",
        (participant_id, *NONTERMINAL_STATES),
    )
    journey = cur.fetchone()
    return {
        "participant_id": str(row[0]),
        "status": row[1],
        "created_at": _serialize_timestamp(row[2]),
        "assigned_condition": row[3],
        "withdrawn_at": _serialize_timestamp(row[4]),
        "deletion_requested_at": _serialize_timestamp(row[5]),
        "session_count": session_count,
        "event_count": event_count,
        "legacy_feed_item_count": legacy_item_count,
        "reserved_item_count": reserved_item_count,
        "checkout_count": checkout_count,
        "nonterminal_session_id": str(journey[0]) if journey else None,
        "nonterminal_journey_state": journey[1] if journey else None,
    }


def withdraw_participant(
    conn,
    *,
    backend: str,
    participant_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Atomically make a participant credential inactive while preserving data."""
    participant_id = exact_participant_id(participant_id)
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ph = _placeholder(backend)
    try:
        _begin_mutation(conn, backend=backend)
        before = preview_participant(
            conn, backend=backend, participant_id=participant_id, lock=True
        )
        cur = conn.cursor()
        # A pending deletion request is already inactive and must not be undone.
        target_status = (
            "deletion_requested"
            if before["status"] == "deletion_requested"
            else "withdrawn"
        )
        cur.execute(
            "UPDATE research_participants "
            f"SET status = {ph}, withdrawn_at = COALESCE(withdrawn_at, {ph}) "
            f"WHERE id = {ph}",
            (target_status, _db_timestamp(backend, timestamp), participant_id),
        )
        after = preview_participant(
            conn, backend=backend, participant_id=participant_id, lock=False
        )
        conn.commit()
        return {"before": before, "after": after}
    except Exception:
        conn.rollback()
        raise


def _zero_related_counts(conn, *, backend: str, participant_id: str) -> dict[str, int]:
    ph = _placeholder(backend)
    cur = conn.cursor()
    return {
        table: _count(
            cur,
            f"SELECT count(*) FROM {table} WHERE participant_id = {ph}",
            (participant_id,),
        )
        for table in RELATED_TABLES
    }


def delete_participant(
    conn,
    *,
    backend: str,
    participant_id: str,
    withdraw_first: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Atomically delete exactly one participant and verify its cascade."""
    participant_id = exact_participant_id(participant_id)
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ph = _placeholder(backend)
    try:
        _begin_mutation(conn, backend=backend)
        before = preview_participant(
            conn, backend=backend, participant_id=participant_id, lock=True
        )
        cur = conn.cursor()
        total_before = _count(cur, "SELECT count(*) FROM research_participants", ())
        if withdraw_first:
            cur.execute(
                "UPDATE research_participants "
                f"SET status = 'withdrawn', withdrawn_at = COALESCE(withdrawn_at, {ph}) "
                f"WHERE id = {ph}",
                (_db_timestamp(backend, timestamp), participant_id),
            )
        cur.execute(
            f"DELETE FROM research_participants WHERE id = {ph}",
            (participant_id,),
        )
        if cur.rowcount != 1:
            raise AdminError("participant deletion did not affect exactly one row")
        remaining = _zero_related_counts(
            conn, backend=backend, participant_id=participant_id
        )
        participant_remaining = _count(
            cur,
            f"SELECT count(*) FROM research_participants WHERE id = {ph}",
            (participant_id,),
        )
        total_after = _count(cur, "SELECT count(*) FROM research_participants", ())
        if participant_remaining or any(remaining.values()) or total_after != total_before - 1:
            raise AdminError("cascade verification failed; transaction was rolled back")
        conn.commit()
        return {
            "before": before,
            "participant_remaining": participant_remaining,
            "related_rows_remaining": remaining,
            "unrelated_participants_preserved": total_after == total_before - 1,
        }
    except Exception:
        conn.rollback()
        raise


def set_participant_retention(
    conn,
    *,
    backend: str,
    participant_id: str,
    retain_until: datetime,
) -> dict[str, Any]:
    """Set the existing session-level marker for one exact pilot participant."""
    participant_id = exact_participant_id(participant_id)
    ph = _placeholder(backend)
    try:
        _begin_mutation(conn, backend=backend)
        before = preview_participant(
            conn, backend=backend, participant_id=participant_id, lock=True
        )
        cur = conn.cursor()
        cur.execute(
            f"UPDATE research_sessions SET retain_until = {ph} WHERE participant_id = {ph}",
            (_db_timestamp(backend, retain_until), participant_id),
        )
        updated_sessions = cur.rowcount
        conn.commit()
        return {
            "participant_id": participant_id,
            "retain_until": retain_until.isoformat(),
            "updated_sessions": updated_sessions,
            "preview": before,
        }
    except Exception:
        conn.rollback()
        raise


def retention_preview(
    conn,
    *,
    backend: str,
    before: datetime,
) -> dict[str, Any]:
    """Count only rows already marked eligible; never performs a bulk deletion."""
    ph = _placeholder(backend)
    cutoff = _db_timestamp(backend, before)
    cur = conn.cursor()
    eligible_sessions = _count(
        cur,
        f"SELECT count(*) FROM research_sessions WHERE retain_until IS NOT NULL "
        f"AND retain_until <= {ph}",
        (cutoff,),
    )
    eligible_participants = _count(
        cur,
        "SELECT count(DISTINCT participant_id) FROM research_sessions "
        f"WHERE retain_until IS NOT NULL AND retain_until <= {ph}",
        (cutoff,),
    )
    unmarked_sessions = _count(
        cur,
        "SELECT count(*) FROM research_sessions WHERE retain_until IS NULL",
        (),
    )
    return {
        "before": before.isoformat(),
        "eligible_participant_count": eligible_participants,
        "eligible_session_count": eligible_sessions,
        "unmarked_session_count": unmarked_sessions,
    }


def _print_preview(value: dict[str, Any]) -> None:
    labels = (
        "participant_id",
        "status",
        "created_at",
        "assigned_condition",
        "withdrawn_at",
        "deletion_requested_at",
        "session_count",
        "event_count",
        "legacy_feed_item_count",
        "reserved_item_count",
        "checkout_count",
        "nonterminal_session_id",
        "nonterminal_journey_state",
    )
    for label in labels:
        print(f"{label}: {value.get(label)}")


def _confirm_withdraw(participant_id: str, *, assume_yes: bool) -> None:
    if assume_yes:
        return
    answer = input(f"Withdraw participant {participant_id}? Type 'withdraw' to continue: ")
    if answer.strip() != "withdraw":
        raise AdminError("withdrawal confirmation was not provided")


def _confirm_retention(participant_id: str, *, assume_yes: bool) -> None:
    if assume_yes:
        return
    answer = input(
        f"Set retention for participant {participant_id}? Type 'retention' to continue: "
    )
    if answer.strip() != "retention":
        raise AdminError("retention confirmation was not provided")


def _confirm_delete(participant_id: str, supplied: str | None) -> None:
    answer = supplied
    if answer is None:
        answer = input("Type the participant UUID to confirm deletion: ")
    if answer.strip() != participant_id:
        raise AdminError("deletion confirmation did not exactly match the participant UUID")


def _require_production_delete_confirmation(backend: str, confirmed: bool) -> None:
    if backend == "postgres" and not confirmed:
        raise AdminError("PostgreSQL deletion requires --production-confirm")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely preview, withdraw, or delete one anonymous pilot participant."
    )
    parser.add_argument(
        "--backend", choices=("sqlite", "postgres"), default="postgres"
    )
    parser.add_argument("--db-path", help="SQLite database path override")
    parser.add_argument(
        "--production-confirm",
        action="store_true",
        help="Required in addition to UUID confirmation for PostgreSQL deletion",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    preview = commands.add_parser("preview")
    preview.add_argument("--participant-id", required=True)

    withdraw = commands.add_parser("withdraw")
    withdraw.add_argument("--participant-id", required=True)
    withdraw.add_argument("--yes", action="store_true")

    delete = commands.add_parser("delete")
    delete.add_argument("--participant-id", required=True)
    delete.add_argument("--confirm-participant-id")

    combined = commands.add_parser("withdraw-delete")
    combined.add_argument("--participant-id", required=True)
    combined.add_argument("--confirm-participant-id")

    retention = commands.add_parser("set-retention")
    retention.add_argument("--participant-id", required=True)
    retention.add_argument("--retain-until", required=True)
    retention.add_argument("--yes", action="store_true")

    retention_check = commands.add_parser("retention-preview")
    retention_check.add_argument("--before", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    participant_id = (
        exact_participant_id(args.participant_id)
        if hasattr(args, "participant_id")
        else None
    )
    conn = None
    try:
        conn = connect_database(backend=args.backend, db_path=args.db_path)
        if args.command == "preview":
            _print_preview(preview_participant(
                conn, backend=args.backend, participant_id=participant_id
            ))
            return 0
        if args.command == "retention-preview":
            result = retention_preview(
                conn, backend=args.backend, before=parse_timestamp(args.before)
            )
            for key, value in result.items():
                print(f"{key}: {value}")
            print("No rows were changed. This command does not perform a bulk purge.")
            return 0

        preview = preview_participant(
            conn, backend=args.backend, participant_id=participant_id
        )
        _print_preview(preview)
        if args.command == "withdraw":
            _confirm_withdraw(participant_id, assume_yes=args.yes)
            result = withdraw_participant(
                conn, backend=args.backend, participant_id=participant_id
            )
            print(f"withdrawal complete: status={result['after']['status']}")
            print(f"withdrawn_at: {result['after']['withdrawn_at']}")
            return 0
        if args.command in {"delete", "withdraw-delete"}:
            _require_production_delete_confirmation(
                args.backend, args.production_confirm
            )
            _confirm_delete(participant_id, args.confirm_participant_id)
            result = delete_participant(
                conn,
                backend=args.backend,
                participant_id=participant_id,
                withdraw_first=args.command == "withdraw-delete",
            )
            print("deletion complete: participant_remaining=0")
            for table, count in result["related_rows_remaining"].items():
                print(f"{table}_remaining: {count}")
            print(
                "unrelated_participants_preserved: "
                f"{result['unrelated_participants_preserved']}"
            )
            return 0
        if args.command == "set-retention":
            _confirm_retention(participant_id, assume_yes=args.yes)
            result = set_participant_retention(
                conn,
                backend=args.backend,
                participant_id=participant_id,
                retain_until=parse_timestamp(args.retain_until),
            )
            print(f"retain_until: {result['retain_until']}")
            print(f"updated_sessions: {result['updated_sessions']}")
            return 0
        raise AdminError("unknown command")
    except AdminError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: database operation failed ({type(exc).__name__})", file=sys.stderr)
        return 3
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
