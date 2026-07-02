#!/usr/bin/env python3.13
"""
Cleanup for the English-only / US-focused Chrysalis demo feed.

Finds feed_videos rows that fail core.language_filter (non-English script,
non-English language code, non-English source query, or non-US region) and either
BLOCKS them (default, reversible) or DELETES them (only with --delete, after a
backup). Raw data is never destroyed without the explicit flag.

Backends:
  • sqlite   (default; local demo DB resolved from core.database)
  • postgres (Supabase) when --database-url is given or DATABASE_URL is set

Modes:
  (default)    mark matching rows status='blocked' + set safety_reason
  --dry-run    report counts + sample rows only; change nothing
  --delete     hard-delete, but first copy matching rows into a backup table and
               print rollback SQL. Requires this explicit flag.

Usage:
  .venv/bin/python3.13 scripts/block_non_english_videos.py --dry-run
  .venv/bin/python3.13 scripts/block_non_english_videos.py              # block
  .venv/bin/python3.13 scripts/block_non_english_videos.py --delete     # destructive
  .venv/bin/python3.13 scripts/block_non_english_videos.py --backend postgres --delete
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import resolve_database_path  # noqa: E402
from core.language_filter import LANGUAGE_POLICY, verdict  # noqa: E402

SAMPLE_LIMIT = 15
# Columns used to evaluate the language policy (must exist in feed_videos).
_EVAL_COLUMNS = (
    "youtube_video_id", "title", "description", "channel_title", "tags",
    "display_title", "display_channel", "display_hashtags", "source_query",
    "source_category", "status",
)


def _reason(row: dict) -> str | None:
    decision = verdict(row)
    if decision["allowed"]:
        return None
    return decision["language_reason"] or ("region" if decision["region_blocked"] else "non_english")


def _safety_text(reason: str) -> str:
    return f"Blocked by {LANGUAGE_POLICY} policy: {reason}"


# ── SQLite backend ───────────────────────────────────────────────────────────

def _sqlite_scan(conn) -> list[tuple[str, str, str]]:
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM feed_videos WHERE status IS NULL OR status != 'blocked'"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    out = []
    for row in rows:
        reason = _reason(dict(row))
        if reason:
            out.append((row["youtube_video_id"], (row["title"] or "")[:60], reason))
    return out


def _sqlite_apply(conn, ids, *, delete, backup_name):
    placeholders = ",".join("?" for _ in ids)
    if delete:
        conn.execute(
            f"CREATE TABLE {backup_name} AS SELECT * FROM feed_videos "
            f"WHERE youtube_video_id IN ({placeholders})", ids,
        )
        conn.execute(f"DELETE FROM feed_videos WHERE youtube_video_id IN ({placeholders})", ids)
    else:
        for vid, _title, reason in _ID_REASONS:
            conn.execute(
                "UPDATE feed_videos SET status='blocked', safety_reason=? WHERE youtube_video_id=?",
                (_safety_text(reason), vid),
            )
    conn.commit()


# ── Postgres (Supabase) backend ──────────────────────────────────────────────

def _pg_scan(conn) -> list[tuple[str, str, str]]:
    cur = conn.cursor()
    cur.execute(
        "SELECT youtube_video_id, title, description, channel_title, tags, "
        "display_title, display_channel, display_hashtags, source_query, "
        "source_category, status FROM feed_videos "
        "WHERE status IS NULL OR status <> 'blocked'"
    )
    cols = [d[0] for d in cur.description]
    out = []
    for record in cur.fetchall():
        row = dict(zip(cols, record))
        reason = _reason(row)
        if reason:
            out.append((row["youtube_video_id"], (row["title"] or "")[:60], reason))
    return out


def _pg_apply(conn, ids, *, delete, backup_name):
    cur = conn.cursor()
    if delete:
        cur.execute(
            f'CREATE TABLE "{backup_name}" AS SELECT * FROM feed_videos '
            "WHERE youtube_video_id = ANY(%s)", (ids,),
        )
        cur.execute("DELETE FROM feed_videos WHERE youtube_video_id = ANY(%s)", (ids,))
    else:
        for vid, _title, reason in _ID_REASONS:
            cur.execute(
                "UPDATE feed_videos SET status='blocked', safety_reason=%s WHERE youtube_video_id=%s",
                (_safety_text(reason), vid),
            )
    conn.commit()


_ID_REASONS: list[tuple[str, str, str]] = []


def run(*, backend: str, db_path: str | None, database_url: str | None, delete: bool, dry_run: bool) -> dict:
    global _ID_REASONS
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"feed_videos_lang_backup_{timestamp}"

    if backend == "postgres":
        import psycopg2  # noqa: PLC0415
        conn = psycopg2.connect(database_url or os.environ["DATABASE_URL"])
        scan, apply_changes, quote = _pg_scan, _pg_apply, '"'
    else:
        conn = sqlite3.connect(db_path or resolve_database_path())
        scan, apply_changes, quote = _sqlite_scan, _sqlite_apply, ""

    try:
        bad = scan(conn)
        _ID_REASONS = bad
        ids = [vid for vid, _t, _r in bad]

        # 1) always print a dry-run summary + sample first
        print(f"Backend: {backend}  Policy: {LANGUAGE_POLICY}")
        print(f"Matched {len(bad)} non-English / non-US row(s).")
        for vid, title, reason in bad[:SAMPLE_LIMIT]:
            print(f"  - {vid} [{reason}] {title}")
        if len(bad) > SAMPLE_LIMIT:
            print(f"  …and {len(bad) - SAMPLE_LIMIT} more")

        result = {"matched": len(bad), "blocked": 0, "deleted": 0, "backup_table": None, "rollback_sql": None}
        if dry_run or not ids:
            print("Dry run — no changes written." if dry_run else "Nothing to change.")
            return result

        apply_changes(conn, ids, delete=delete, backup_name=backup_name)
        if delete:
            result["deleted"] = len(ids)
            result["backup_table"] = backup_name
            result["rollback_sql"] = (
                f"INSERT INTO feed_videos SELECT * FROM {quote}{backup_name}{quote};"
            )
            print(f"Deleted {len(ids)} row(s). Backup table: {backup_name}")
            print(f"Rollback: {result['rollback_sql']}")
        else:
            result["blocked"] = len(ids)
            print(f"Marked {len(ids)} row(s) status='blocked' (reversible; safety_reason set).")
        return result
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Block/delete non-English feed_videos rows.")
    parser.add_argument("--backend", choices=["sqlite", "postgres", "auto"], default="auto")
    parser.add_argument("--db", default=None, help="SQLite DB path.")
    parser.add_argument("--database-url", default=None, help="Postgres/Supabase URL.")
    parser.add_argument("--dry-run", action="store_true", help="Report only; change nothing.")
    parser.add_argument("--delete", action="store_true", help="Hard-delete (after backup). Destructive.")
    args = parser.parse_args()

    backend = args.backend
    if backend == "auto":
        backend = "postgres" if (args.database_url or os.environ.get("DATABASE_URL")) else "sqlite"

    run(
        backend=backend,
        db_path=args.db,
        database_url=args.database_url,
        delete=args.delete,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
