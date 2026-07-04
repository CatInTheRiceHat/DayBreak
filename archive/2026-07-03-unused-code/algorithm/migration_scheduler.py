"""
Migration Mode scheduler.

Runs build_prototype_feed() twice daily (07:00 morning, 19:00 evening) using
fixed, non-personalized weights. Each run freezes 10-15 posts to chrysalis.db
so every user sees the same curated drop for that period.

Usage (imported by api.py):
    from migration_scheduler import create_scheduler

    scheduler = create_scheduler()
    scheduler.start()   # on app startup
    scheduler.stop()    # on app shutdown

Standalone test run (writes one drop immediately):
    python3 migration_scheduler.py --run morning
    python3 migration_scheduler.py --run evening
"""

import json
import logging
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

from core.algorithm import add_engagement, build_prototype_feed, validate_and_clean

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(ROOT / "chrysalis.db")))
DATASET_PATH = ROOT / "datasets" / "processed_dataset.csv"

# ---------------------------------------------------------------------------
# Drop configuration
# ---------------------------------------------------------------------------

DROP_K = 12  # items per drop — sits in the middle of the 10-15 spec range

# Standard Migration Mode weights (diversity + prosocial biased)
MORNING_WEIGHTS = {"e": 0.20, "d": 0.35, "p": 0.35, "r": 0.10}

# Evening weights: pull back on engagement, tighten risk — more reflective/calming
EVENING_WEIGHTS = {"e": 0.15, "d": 0.35, "p": 0.35, "r": 0.15}

# Non-personalized: no age group, no user-specific history
_MIGRATION_USER_PROFILE = {"age_group": None}

# Columns to persist in feed_json (only what exists in the dataset)
_FEED_COLS = ["video_id", "topic", "channel", "prosocial", "risk",
              "engagement", "diversity", "score"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_dataset() -> pd.DataFrame:
    df = pd.read_csv(DATASET_PATH)
    # Fill columns required by validate_and_clean that may be absent from the CSV.
    # Defaults are neutral: no active engagement signal, mid-range creator authenticity.
    _defaults = {
        "topic": "unlabeled",
        "prosocial": 0,
        "risk": 0,
        "active_engagement_ratio": 0.0,
        "creator_authenticity": 0.5,
    }
    for col, default in _defaults.items():
        if col not in df.columns:
            df[col] = default
    df = validate_and_clean(df)
    df, _ = add_engagement(df)
    return df


def _run_drop(weights: dict) -> list[dict]:
    df = _load_dataset()
    feed = build_prototype_feed(
        df,
        weights=weights,
        k=DROP_K,
        user_profile=_MIGRATION_USER_PROFILE,
        recent_window=10,
    ).reset_index(drop=True)
    cols = [c for c in _FEED_COLS if c in feed.columns]
    return feed[cols].to_dict(orient="records")


def _write_drop(mode: str, feed: list[dict], scheduled_at: str) -> None:
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO migration_drops
                (drop_date, mode, scheduled_at, feed_json, item_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (today, mode, scheduled_at, json.dumps(feed), len(feed)),
        )
        conn.commit()
        logger.info(
            "Migration drop written — date=%s mode=%s items=%d",
            today, mode, len(feed),
        )
    except Exception:
        logger.exception("Failed to write migration drop to DB")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Scheduled jobs (called by APScheduler)
# ---------------------------------------------------------------------------

def run_morning_drop() -> None:
    scheduled_at = f"{date.today().isoformat()}T07:00:00"
    logger.info("Running morning Migration Mode drop")
    try:
        feed = _run_drop(MORNING_WEIGHTS)
        _write_drop("morning", feed, scheduled_at)
    except Exception:
        logger.exception("Morning migration drop failed")


def run_evening_drop() -> None:
    scheduled_at = f"{date.today().isoformat()}T19:00:00"
    logger.info("Running evening Migration Mode drop")
    try:
        feed = _run_drop(EVENING_WEIGHTS)
        _write_drop("evening", feed, scheduled_at)
    except Exception:
        logger.exception("Evening migration drop failed")


# ---------------------------------------------------------------------------
# Public factory (used by api.py)
# ---------------------------------------------------------------------------

def create_scheduler() -> BackgroundScheduler:
    """Return a configured (but not yet started) BackgroundScheduler."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_morning_drop, "cron", hour=7,  minute=0, id="migration_morning")
    scheduler.add_job(run_evening_drop, "cron", hour=19, minute=0, id="migration_evening")
    return scheduler


# ---------------------------------------------------------------------------
# Standalone test runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Manually trigger a Migration Mode drop")
    parser.add_argument("--run", choices=["morning", "evening"], required=True)
    args = parser.parse_args()

    if args.run == "morning":
        run_morning_drop()
    else:
        run_evening_drop()

    print("Done. Check chrysalis.db migration_drops table.")
