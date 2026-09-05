"""
Schema setup: ensures the public-signal tables exist in chrysalis.db.
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


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_sqlite_public_signal_tables(conn)
        conn.commit()
        print(f"OK: public signal tables ready in {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
