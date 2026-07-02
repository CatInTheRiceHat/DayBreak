"""
Schema migration: adds the migration_drops table to chrysalis.db.
Safe to run multiple times — uses IF NOT EXISTS.

Usage:
    python3 -m scripts.init_db
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.database import resolve_database_path
from core.public_signals.storage import ensure_sqlite_public_signal_tables

DB_PATH = resolve_database_path()

CREATE_MIGRATION_DROPS = """
CREATE TABLE IF NOT EXISTS migration_drops (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    drop_date    TEXT    NOT NULL,
    mode         TEXT    NOT NULL CHECK(mode IN ('morning', 'evening')),
    scheduled_at TEXT    NOT NULL,
    feed_json    TEXT    NOT NULL,
    item_count   INTEGER NOT NULL,
    UNIQUE(drop_date, mode)
);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_migration_drops_date
    ON migration_drops(drop_date);
"""


CREATE_COCOON_PROFILES = """
CREATE TABLE IF NOT EXISTS cocoon_profiles (
    user_id       TEXT    PRIMARY KEY,
    start_minutes INTEGER NOT NULL,
    current_week  INTEGER NOT NULL DEFAULT 0,
    start_date    TEXT    NOT NULL,
    graduated     INTEGER NOT NULL DEFAULT 0
);
"""


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(CREATE_MIGRATION_DROPS)
        conn.execute(CREATE_INDEX)
        conn.execute(CREATE_COCOON_PROFILES)
        ensure_sqlite_public_signal_tables(conn)
        conn.commit()
        print(f"OK: migration, cocoon, and public signal tables ready in {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
