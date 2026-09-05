#!/usr/bin/env python3
"""
Load deterministic demo seed videos into the local SQLite feed_videos table.

These seeds give the healthier Chrysalis feed real-shaped content to classify and
rank locally (the dev DB ships nearly empty), so the content taxonomy and - later -
the balanced algorithm are demonstrable without hitting the YouTube API.

Behavior:
  - Ensures the feed_videos table/columns exist (reuses the ingestion schema).
  - Retires prior chrysalis_seed rows that are no longer in the seed file.
  - Inserts or updates rows keyed on youtube_video_id, scoped to chrysalis_seed, so
    existing non-seed ingested videos are preserved.
  - Leaves chrysalis_scores NULL on purpose, so the live scorer + taxonomy run on
    the seeds end to end (proving the pipeline, not a hardcoded label).

Usage:
    .venv/bin/python scripts/seed_demo_videos.py            # default DB
    .venv/bin/python scripts/seed_demo_videos.py --db path/to.db
    .venv/bin/python scripts/seed_demo_videos.py --reset    # delete prior seeds first
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import resolve_database_path  # noqa: E402
from integrations.youtube_ingest import ensure_sqlite_feed_videos_table  # noqa: E402

SEED_FILE = ROOT / "datasets" / "seed_videos.json"
SEED_SOURCE_QUERY = "chrysalis_seed"
WATCH_URL = "https://www.youtube.com/watch?v={vid}"


def _load_seeds() -> list[dict]:
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    return data.get("videos", [])


def seed_database(db_path: str, *, reset: bool = False) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_sqlite_feed_videos_table(conn)
        if reset:
            conn.execute(
                "DELETE FROM feed_videos WHERE source_query = ?", (SEED_SOURCE_QUERY,)
            )
        seeds = _load_seeds()
        seed_ids = [seed["youtube_video_id"] for seed in seeds]
        removed = 0
        if seed_ids:
            placeholders = ",".join("?" for _ in seed_ids)
            cur = conn.execute(
                f"""
                DELETE FROM feed_videos
                WHERE source_query = ?
                  AND youtube_video_id NOT IN ({placeholders})
                """,
                (SEED_SOURCE_QUERY, *seed_ids),
            )
            removed = cur.rowcount
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        updated = 0
        skipped = 0
        for i, seed in enumerate(seeds):
            vid = seed["youtube_video_id"]
            existing = conn.execute(
                """
                SELECT source_query
                FROM feed_videos
                WHERE youtube_video_id = ?
                """,
                (vid,),
            ).fetchone()
            values = (
                f"seed-{vid}",
                vid,
                seed.get("title"),
                seed.get("channel_title"),
                f"seed-channel-{i}",
                seed.get("description"),
                json.dumps(seed.get("tags", [])),
                seed.get("thumbnail_url"),
                WATCH_URL.format(vid=vid),
                seed.get("duration_seconds", 90),
                seed.get("view_count", 12000),
                seed.get("topic"),
                seed.get("category_id"),
                seed.get("source_category"),
                SEED_SOURCE_QUERY,
                round(0.75 - i * 0.01, 4),  # gentle, stable ordering
                seed.get("published_at", now),
                now,
                now,
            )
            if existing and existing["source_query"] != SEED_SOURCE_QUERY:
                skipped += 1
                continue
            if existing:
                conn.execute(
                    """
                    UPDATE feed_videos
                    SET id = ?, title = ?, channel_title = ?, channel_id = ?,
                        description = ?, tags = ?, thumbnail_url = ?, watch_url = ?,
                        duration_seconds = ?, view_count = ?, topic = ?,
                        category_id = ?, source_category = ?, source_query = ?,
                        source_type = 'search', popularity_score = 0, score = ?,
                        status = 'active', published_at = ?, updated_at = ?,
                        chrysalis_scores = NULL, ranking_reason = NULL,
                        safety_reason = NULL, concern_reason = NULL,
                        label_confidence = NULL, scored_at = NULL,
                        scoring_version = NULL
                    WHERE youtube_video_id = ?
                      AND source_query = ?
                    """,
                    (
                        values[0],
                        values[2],
                        values[3],
                        values[4],
                        values[5],
                        values[6],
                        values[7],
                        values[8],
                        values[9],
                        values[10],
                        values[11],
                        values[12],
                        values[13],
                        values[14],
                        values[15],
                        values[16],
                        values[18],
                        vid,
                        SEED_SOURCE_QUERY,
                    ),
                )
                updated += 1
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO feed_videos (
                    id, source, youtube_video_id, title, channel_title, channel_id,
                    description, tags, thumbnail_url, watch_url, duration_seconds,
                    view_count, topic, category_id, source_category, source_query,
                    source_type, popularity_score, score, status, published_at,
                    created_at, updated_at
                ) VALUES (?, 'youtube', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          'search', 0, ?, 'active', ?, ?, ?)
                """,
                values,
            )
            inserted += 1
        conn.commit()
        total = conn.execute(
            "SELECT COUNT(*) FROM feed_videos WHERE source_query = ?",
            (SEED_SOURCE_QUERY,),
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "removed": removed,
        "seed_rows_total": total,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo videos into feed_videos.")
    parser.add_argument("--db", default=None, help="SQLite DB path (default: resolved project DB).")
    parser.add_argument("--reset", action="store_true", help="Delete prior chrysalis_seed rows first.")
    args = parser.parse_args()

    db_path = args.db or resolve_database_path()
    result = seed_database(db_path, reset=args.reset)
    print(f"DB: {db_path}")
    print(
        f"Seeds inserted: {result['inserted']}, "
        f"updated: {result['updated']}, "
        f"removed stale: {result['removed']}, "
        f"skipped (already present): {result['skipped']}, "
        f"total seed rows: {result['seed_rows_total']}"
    )


if __name__ == "__main__":
    main()
