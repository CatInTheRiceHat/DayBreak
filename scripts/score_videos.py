#!/usr/bin/env python3.13
"""
Backfill Chrysalis v1 labels onto the `videos` table.

For every video row it computes the metadata LabelSet + explanation reasons and writes:
  chrysalis_scores, ranking_reason, safety_reason, concern_reason,
  label_confidence, scored_at, scoring_version

Default target is the local SQLite chrysalis.db. Pass --postgres to target the
Postgres database in $DATABASE_URL instead (used in production).

  python scripts/score_videos.py              # SQLite (chrysalis.db)
  python scripts/score_videos.py --postgres   # Postgres ($DATABASE_URL)

Reasons are mode-specific; the stored `ranking_reason` is computed for a neutral
default mode (flutter-feed). The /api/feed/{mode} endpoint recomputes reasons for the
requested mode at request time, so stored reasons are only a fallback/default.
"""

from __future__ import annotations

import os
import sys
import json
import time
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.ranking.feed import label_row          # noqa: E402
from core.labeling.explain import build_reasons   # noqa: E402
from core.labeling.schema import SCORING_VERSION  # noqa: E402
from core.database import resolve_database_path   # noqa: E402

DEFAULT_MODE = "flutter-feed"
DB_PATH = resolve_database_path()


def _score_one(row: dict) -> dict:
    labels = label_row(row)
    reasons = build_reasons(labels, DEFAULT_MODE)
    return {
        "chrysalis_scores": labels.to_dict(),
        "ranking_reason": reasons["ranking_reason"],
        "safety_reason": reasons["safety_reason"],
        "concern_reason": reasons["concern_reason"],
        "label_confidence": labels.confidence,
    }


def backfill_sqlite(db_path: Path) -> int:
    from integrations.youtube_extractor import _ensure_label_columns

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_label_columns(conn)  # add label columns to pre-v1 databases
    rows = [dict(r) for r in conn.execute("SELECT * FROM videos").fetchall()]
    n = 0
    for row in rows:
        scored = _score_one(row)
        conn.execute(
            """
            UPDATE videos SET
                chrysalis_scores = ?, ranking_reason = ?, safety_reason = ?,
                concern_reason = ?, label_confidence = ?, scored_at = ?,
                scoring_version = ?
            WHERE video_id = ?
            """,
            (
                json.dumps(scored["chrysalis_scores"]),
                scored["ranking_reason"], scored["safety_reason"],
                scored["concern_reason"], scored["label_confidence"],
                time.time(), SCORING_VERSION, row["video_id"],
            ),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


def backfill_postgres() -> int:
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM videos")
    rows = [dict(r) for r in cur.fetchall()]
    n = 0
    for row in rows:
        scored = _score_one(row)
        cur.execute(
            """
            UPDATE videos SET
                chrysalis_scores = %s, ranking_reason = %s, safety_reason = %s,
                concern_reason = %s, label_confidence = %s, scored_at = NOW(),
                scoring_version = %s
            WHERE video_id = %s
            """,
            (
                json.dumps(scored["chrysalis_scores"]),
                scored["ranking_reason"], scored["safety_reason"],
                scored["concern_reason"], scored["label_confidence"],
                SCORING_VERSION, row["video_id"],
            ),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Chrysalis v1 video labels")
    parser.add_argument("--postgres", action="store_true",
                        help="Target Postgres ($DATABASE_URL) instead of SQLite")
    args = parser.parse_args()

    if args.postgres:
        count = backfill_postgres()
        print(f"[score_videos] Scored {count} videos in Postgres (scoring_version={SCORING_VERSION}).")
    else:
        count = backfill_sqlite(DB_PATH)
        print(f"[score_videos] Scored {count} videos in {DB_PATH} (scoring_version={SCORING_VERSION}).")


if __name__ == "__main__":
    main()
