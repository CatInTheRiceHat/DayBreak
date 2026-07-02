"""
Shared content-preferences storage for Chrysalis.

Language + region preferences power lightweight, privacy-respecting feed
targeting (relevanceLanguage / regionCode on YouTube searches). This module is
the single source of truth used by both backends:

  - api.py        -> SQLite  (local dev)
  - api/index.py  -> Postgres (Supabase / production)

Identity is either a logged-in ``user_id`` or, for anonymous visitors, a
frontend-generated ``session_id`` (UUID persisted in the browser). We never
store exact GPS coordinates — only a coarse language/region the user confirms.

Reads never raise: a missing row yields English + United States defaults with
``has_completed_language_setup = False`` so callers can always render a feed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

DEFAULT_LANGUAGE = "en"
DEFAULT_REGION = "US"

_SPECIAL_LANGUAGE_CODES = {
    "zh-hans": "zh-Hans",
    "zh-hant": "zh-Hant",
}

# Column order used by the SELECT helpers below.
_COLUMNS = (
    "id",
    "user_id",
    "session_id",
    "preferred_language",
    "region_code",
    "use_approx_location",
    "location_city",
    "location_country",
    "has_completed_language_setup",
    "created_at",
    "updated_at",
)
_SELECT_COLS = ", ".join(_COLUMNS)

# Fields a client is allowed to write.
_EDITABLE = (
    "preferred_language",
    "region_code",
    "use_approx_location",
    "location_city",
    "location_country",
    "has_completed_language_setup",
)

_BOOL_FIELDS = ("use_approx_location", "has_completed_language_setup")


def _placeholder(backend: str) -> str:
    return "%s" if backend == "postgres" else "?"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_language_code(value: str | None) -> str:
    """Return a YouTube-safe language code, defaulting to English."""
    if not isinstance(value, str):
        return DEFAULT_LANGUAGE
    code = value.strip()
    if not code:
        return DEFAULT_LANGUAGE
    special = _SPECIAL_LANGUAGE_CODES.get(code.lower())
    if special:
        return special
    normalized = code.lower()
    if len(normalized) == 2 and normalized.isalpha():
        return normalized
    return DEFAULT_LANGUAGE


def normalize_region_code(value: str | None) -> str:
    """Return an ISO-3166-ish alpha-2 region code, defaulting to US."""
    if not isinstance(value, str):
        return DEFAULT_REGION
    normalized = value.strip().upper()
    if len(normalized) == 2 and normalized.isalpha():
        return normalized
    return DEFAULT_REGION


# ---------------------------------------------------------------------------
# Table creation (defensive — the canonical schema lives in migrations/009)
# ---------------------------------------------------------------------------

def ensure_sqlite_preferences_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_content_preferences (
            id                           TEXT PRIMARY KEY,
            user_id                      TEXT,
            session_id                   TEXT,
            preferred_language           TEXT    NOT NULL DEFAULT 'en',
            region_code                  TEXT    NOT NULL DEFAULT 'US',
            use_approx_location          INTEGER NOT NULL DEFAULT 0,
            location_city                TEXT,
            location_country             TEXT,
            has_completed_language_setup INTEGER NOT NULL DEFAULT 0,
            created_at                   TEXT,
            updated_at                   TEXT
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uniq_ucp_user_id "
        "ON user_content_preferences (user_id) WHERE user_id IS NOT NULL"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uniq_ucp_session_id "
        "ON user_content_preferences (session_id) WHERE session_id IS NOT NULL"
    )
    conn.commit()


def ensure_postgres_preferences_table(conn) -> None:
    """Mirror migration 009 so production keeps working even if the migration
    has not been applied yet. Idempotent."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_content_preferences (
            id                           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id                      UUID,
            session_id                   TEXT,
            preferred_language           TEXT        NOT NULL DEFAULT 'en',
            region_code                  TEXT        NOT NULL DEFAULT 'US',
            use_approx_location          BOOLEAN     NOT NULL DEFAULT FALSE,
            location_city                TEXT,
            location_country             TEXT,
            has_completed_language_setup BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uniq_ucp_user_id "
        "ON user_content_preferences (user_id) WHERE user_id IS NOT NULL"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uniq_ucp_session_id "
        "ON user_content_preferences (session_id) WHERE session_id IS NOT NULL"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def default_preferences(
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    return {
        "id": None,
        "user_id": user_id,
        "session_id": session_id,
        "preferred_language": DEFAULT_LANGUAGE,
        "region_code": DEFAULT_REGION,
        "use_approx_location": False,
        "location_city": None,
        "location_country": None,
        "has_completed_language_setup": False,
        "created_at": None,
        "updated_at": None,
    }


def _row_to_dict(row) -> dict:
    out = dict(zip(_COLUMNS, row))
    out["preferred_language"] = normalize_language_code(out.get("preferred_language"))
    out["region_code"] = normalize_region_code(out.get("region_code"))
    for field in _BOOL_FIELDS:
        out[field] = bool(out[field])
    for ts in ("created_at", "updated_at"):
        value = out.get(ts)
        if isinstance(value, datetime):
            out[ts] = value.isoformat()
        elif value is not None:
            out[ts] = str(value)
    if out.get("id") is not None:
        out["id"] = str(out["id"])
    if out.get("user_id") is not None:
        out["user_id"] = str(out["user_id"])
    return out


def _fetch_row(conn, backend: str, user_id: str | None, session_id: str | None):
    ph = _placeholder(backend)
    cur = conn.cursor()
    if user_id:
        cur.execute(
            f"SELECT {_SELECT_COLS} FROM user_content_preferences WHERE user_id = {ph}",
            (user_id,),
        )
        row = cur.fetchone()
        if row is not None:
            return row
    if session_id:
        cur.execute(
            f"SELECT {_SELECT_COLS} FROM user_content_preferences WHERE session_id = {ph}",
            (session_id,),
        )
        row = cur.fetchone()
        if row is not None:
            return row
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_preferences(
    conn,
    *,
    backend: str,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Return saved preferences for the user/session, or English/US defaults.

    Never raises on a missing row — the feed must always be renderable.
    """
    row = _fetch_row(conn, backend, user_id, session_id)
    if row is None:
        return default_preferences(user_id, session_id)
    return _row_to_dict(row)


def upsert_preferences(
    conn,
    *,
    backend: str,
    user_id: str | None = None,
    session_id: str | None = None,
    **fields,
) -> dict:
    """Insert or update the preferences row for the given identity.

    Only keys in ``_EDITABLE`` are written; unknown keys are ignored. Returns the
    persisted preferences dict.
    """
    ph = _placeholder(backend)
    existing = _fetch_row(conn, backend, user_id, session_id)
    updates = {k: v for k, v in fields.items() if k in _EDITABLE and v is not None}
    if "preferred_language" in updates:
        updates["preferred_language"] = normalize_language_code(updates["preferred_language"])
    if "region_code" in updates:
        updates["region_code"] = normalize_region_code(updates["region_code"])
    for field in _BOOL_FIELDS:
        if field in updates:
            updates[field] = bool(updates[field])
    now = _now_iso()
    cur = conn.cursor()

    if existing is not None:
        existing_id = existing[0]
        if updates:
            set_clause = ", ".join(f"{col} = {ph}" for col in updates)
            params = list(updates.values()) + [now, existing_id]
            cur.execute(
                f"UPDATE user_content_preferences SET {set_clause}, updated_at = {ph} "
                f"WHERE id = {ph}",
                params,
            )
            conn.commit()
    else:
        merged = default_preferences(user_id, session_id)
        merged.update(updates)
        new_id = str(uuid.uuid4())
        cols = (
            "id", "user_id", "session_id", "preferred_language", "region_code",
            "use_approx_location", "location_city", "location_country",
            "has_completed_language_setup", "created_at", "updated_at",
        )
        values = [
            new_id,
            user_id,
            session_id,
            merged["preferred_language"],
            merged["region_code"],
            merged["use_approx_location"],
            merged["location_city"],
            merged["location_country"],
            merged["has_completed_language_setup"],
            now,
            now,
        ]
        placeholders = ", ".join([ph] * len(cols))
        cur.execute(
            f"INSERT INTO user_content_preferences ({', '.join(cols)}) "
            f"VALUES ({placeholders})",
            values,
        )
        conn.commit()

    return get_preferences(conn, backend=backend, user_id=user_id, session_id=session_id)
