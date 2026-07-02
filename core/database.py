"""Shared database path helpers for local SQLite development."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "chrysalis.db"


def resolve_database_path(value: str | os.PathLike | None = None) -> Path:
    """
    Resolve the local SQLite database path consistently across API, extractor,
    scripts, and tests.

    DATABASE_PATH may be absolute, or relative to the project root.
    """
    raw = value if value is not None else os.environ.get("DATABASE_PATH")
    if not raw:
        return DEFAULT_DATABASE_PATH

    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
