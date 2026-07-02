"""Trust-source registry for YouTube feed ingestion (Parts A/B/C).

Three human-curated tables back a single workflow:

    discovered channel → candidate queue → human review
                       → approved / rejected → ingestion uses ONLY approved

  * ``trusted_youtube_channels``  — approved/candidate/rejected/... channels.
    Only ``status = 'approved'`` rows are eligible for the trusted ingestion
    lane (see integrations/youtube_ingest.fetch_trusted_channel_candidates).
  * ``blocked_youtube_channels``  — hard denylist; these channels are never
    ingested or served, even if a video passes every other filter.
  * ``youtube_channel_candidates`` — a *review queue only*. Nothing here feeds
    ingestion; a human promotes a candidate into trusted_youtube_channels.

AI never auto-promotes a candidate. Promotion is a human writing status='approved'.

This module is sqlite-first for the local demo DB; the Postgres/Supabase shape
lives in migrations/011_trusted_sources.sql with the same columns. Loaders treat
a missing table as "no trust registry configured" and return empties so the feed
keeps working with the search + mostPopular lanes (Part G — backward compat).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3

# ── Recommended controlled vocabularies ──────────────────────────────────────
TRUSTED_SOURCE_GROUPS: tuple[str, ...] = (
    "trusted/news",
    "trusted/science",
    "trusted/education",
    "trusted/mental_health",
    "trusted/positivity",
    "trusted/productivity",
    "trusted/lifestyle",
    "trusted/culture",
)
TRUST_TIERS: tuple[str, ...] = (
    "institutional",
    "established_creator",
    "candidate",
    "experimental",
)
TRUSTED_STATUSES: tuple[str, ...] = (
    "candidate",
    "approved",
    "rejected",
    "needs_review",
    "disabled",
)
BLOCKED_REASONS: tuple[str, ...] = (
    "foreign_language_leak",
    "ragebait",
    "misinformation",
    "gossip_drama",
    "explicit_or_unsafe",
    "spam_or_repost",
    "low_quality",
    "manual_block",
)
CANDIDATE_REVIEW_STATUSES: tuple[str, ...] = (
    "new",
    "needs_review",
    "approved",
    "rejected",
    "stale",
)

# The single status that makes a trusted-channel row eligible for ingestion.
TRUSTED_STATUS_APPROVED = "approved"

# ── AI-assisted curation vocabulary (the import/upsert workflow) ─────────────
# AI inserts labeled rows; a human removes/disables exceptions later. trust_status
# is the unified curation label the import speaks; it is routed to the existing
# trusted/blocked tables (trusted/pending/rejected → trusted_youtube_channels;
# blocked → blocked_youtube_channels).
AI_TRUST_STATUSES: tuple[str, ...] = ("trusted", "blocked", "pending", "rejected")
AI_REVIEW_STATUS_DEFAULT = "unreviewed"
AI_ADDED_BY = "ai"

# trust_status → status value written on trusted_youtube_channels.
_TRUST_STATUS_TO_TRUSTED_STATUS = {
    "trusted": "approved",
    "pending": "needs_review",
    "rejected": "rejected",
}

# New columns added to BOTH trusted_youtube_channels and blocked_youtube_channels
# so AI curation + human review live on the existing tables (no new table).
_AI_CURATION_COLUMNS_SQLITE: dict[str, str] = {
    "platform":      "TEXT DEFAULT 'youtube'",
    "trust_status":  "TEXT",
    "added_by":      "TEXT DEFAULT 'human'",
    "ai_confidence": "REAL",
    "ai_reason":     "TEXT",
    "active":        "INTEGER DEFAULT 1",
    "review_status": "TEXT DEFAULT 'unreviewed'",
    "reviewed_by":   "TEXT",
    "reviewed_at":   "TEXT",
    "review_notes":  "TEXT",
}


@dataclass(frozen=True)
class TrustedChannel:
    channel_id: str
    channel_title: str
    source_group: str
    trust_tier: str
    status: str
    channel_handle: str | None = None
    channel_url: str | None = None
    notes: str | None = None
    risk_notes: str | None = None


# ── DDL (sqlite) ──────────────────────────────────────────────────────────────
_CREATE_TRUSTED_SQLITE = """
CREATE TABLE IF NOT EXISTS trusted_youtube_channels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id      TEXT NOT NULL UNIQUE,
    channel_title   TEXT,
    channel_handle  TEXT,
    channel_url     TEXT,
    source_group    TEXT,
    trust_tier      TEXT,
    status          TEXT NOT NULL DEFAULT 'candidate',
    notes           TEXT,
    risk_notes      TEXT,
    approved_by     TEXT,
    approved_at     TEXT,
    last_checked_at TEXT,
    created_at      TEXT,
    updated_at      TEXT
)
"""
_CREATE_BLOCKED_SQLITE = """
CREATE TABLE IF NOT EXISTS blocked_youtube_channels (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id    TEXT NOT NULL UNIQUE,
    channel_title TEXT,
    reason        TEXT,
    blocked_by    TEXT,
    blocked_at    TEXT,
    created_at    TEXT,
    updated_at    TEXT
)
"""
_CREATE_CANDIDATES_SQLITE = """
CREATE TABLE IF NOT EXISTS youtube_channel_candidates (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id            TEXT NOT NULL UNIQUE,
    channel_title         TEXT,
    channel_handle        TEXT,
    channel_url           TEXT,
    suggested_source_group TEXT,
    discovery_source      TEXT,
    why_suggested         TEXT,
    possible_risks        TEXT,
    sample_video_titles   TEXT,
    subscriber_count      INTEGER,
    recent_upload_count   INTEGER,
    language_notes        TEXT,
    recommended_status    TEXT,
    review_status         TEXT NOT NULL DEFAULT 'new',
    review_notes          TEXT,
    checked_at            TEXT,
    created_at            TEXT,
    updated_at            TEXT
)
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_ai_curation_columns_sqlite(conn: sqlite3.Connection) -> None:
    """Add the AI-curation / human-review columns to the trusted + blocked tables
    if missing. Idempotent (checks PRAGMA before each ALTER)."""
    for table in ("trusted_youtube_channels", "blocked_youtube_channels"):
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, column_type in _AI_CURATION_COLUMNS_SQLITE.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def ensure_trust_tables_sqlite(conn: sqlite3.Connection) -> None:
    """Create the three trust tables if absent, and ensure AI-curation columns.
    Idempotent."""
    conn.execute(_CREATE_TRUSTED_SQLITE)
    conn.execute(_CREATE_BLOCKED_SQLITE)
    conn.execute(_CREATE_CANDIDATES_SQLITE)
    _ensure_ai_curation_columns_sqlite(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_trusted_channels_status "
        "ON trusted_youtube_channels (status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_blocked_channels_channel "
        "ON blocked_youtube_channels (channel_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_channel_candidates_review "
        "ON youtube_channel_candidates (review_status)"
    )
    conn.commit()


def _table_missing(exc: Exception) -> bool:
    return "no such table" in str(exc).lower()


def load_approved_trusted_channels(conn: sqlite3.Connection) -> list[TrustedChannel]:
    """Return only ``status = 'approved'`` trusted channels.

    A missing table means "no trust registry configured" → empty list, so the
    feed keeps running on the existing lanes (backward compatibility).
    """
    base_cols = ("SELECT channel_id, channel_title, channel_handle, channel_url, "
                 "source_group, trust_tier, status, notes, risk_notes "
                 "FROM trusted_youtube_channels WHERE status = ? "
                 "AND channel_id IS NOT NULL AND channel_id <> ''")
    try:
        # Only ACTIVE approved rows are eligible (inactive = human-disabled).
        rows = conn.execute(
            base_cols + " AND (active IS NULL OR active <> 0) ORDER BY id",
            (TRUSTED_STATUS_APPROVED,),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _table_missing(exc):
            return []
        if "no such column" in str(exc).lower():
            # Pre-AI-curation schema (no `active` column) — fall back to legacy.
            rows = conn.execute(base_cols + " ORDER BY id",
                                (TRUSTED_STATUS_APPROVED,)).fetchall()
        else:
            raise
    return [
        TrustedChannel(
            channel_id=r["channel_id"],
            channel_title=r["channel_title"] or "",
            source_group=r["source_group"] or "trusted/culture",
            trust_tier=r["trust_tier"] or "candidate",
            status=r["status"],
            channel_handle=r["channel_handle"],
            channel_url=r["channel_url"],
            notes=r["notes"],
            risk_notes=r["risk_notes"],
        )
        for r in rows
    ]


def load_blocked_channel_ids(conn: sqlite3.Connection) -> set[str]:
    """Return the set of hard-blocked channel ids (empty if table missing)."""
    base = ("SELECT channel_id FROM blocked_youtube_channels "
            "WHERE channel_id IS NOT NULL AND channel_id <> ''")
    try:
        # Inactive blocked rows are ignored (human un-blocked the channel).
        rows = conn.execute(base + " AND (active IS NULL OR active <> 0)").fetchall()
    except sqlite3.OperationalError as exc:
        if _table_missing(exc):
            return set()
        if "no such column" in str(exc).lower():
            rows = conn.execute(base).fetchall()
        else:
            raise
    return {r["channel_id"] if isinstance(r, sqlite3.Row) else r[0] for r in rows}


def load_channel_candidates(conn: sqlite3.Connection) -> list[dict]:
    """Return the candidate review queue (empty if table missing).

    This is a review queue only — it never feeds ingestion.
    """
    try:
        rows = conn.execute(
            "SELECT channel_id, channel_title, suggested_source_group, "
            "discovery_source, review_status, recommended_status "
            "FROM youtube_channel_candidates ORDER BY id"
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _table_missing(exc):
            return []
        raise
    return [dict(r) for r in rows]


# ── Postgres loaders (production cron path) ──────────────────────────────────
# Postgres tables are created by migrations/011_trusted_sources.sql. If that
# migration has not been applied yet, a SELECT raises and aborts the txn — we
# roll back and return empty so ingestion still runs on search + popular (Part G).
_TRUSTED_SELECT_COLUMNS = (
    "channel_id, channel_title, channel_handle, channel_url, "
    "source_group, trust_tier, status, notes, risk_notes"
)


def _pg_table_missing(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "does not exist" in msg or "undefinedtable" in msg


def _pg_rollback(conn) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


def _pg_active_then_legacy(conn, sql_active: str, sql_legacy: str, params: tuple):
    """Run an active-gated query; if the `active` column doesn't exist yet
    (pre-012 schema) fall back to the legacy query; if the table is missing,
    return None. Rolls back the aborted txn between attempts."""
    for sql in (sql_active, sql_legacy):
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        except Exception:
            _pg_rollback(conn)
            continue
    return None


def load_approved_trusted_channels_postgres(conn) -> list[TrustedChannel]:
    """Postgres equivalent of :func:`load_approved_trusted_channels` (active-gated)."""
    base = (f"SELECT {_TRUSTED_SELECT_COLUMNS} FROM trusted_youtube_channels "
            "WHERE status = %s AND channel_id IS NOT NULL AND channel_id <> ''")
    rows = _pg_active_then_legacy(
        conn,
        base + " AND (active IS NULL OR active = true) ORDER BY id",
        base + " ORDER BY id",
        (TRUSTED_STATUS_APPROVED,),
    )
    if rows is None:
        return []
    return [
        TrustedChannel(
            channel_id=r[0],
            channel_title=r[1] or "",
            source_group=r[4] or "trusted/culture",
            trust_tier=r[5] or "candidate",
            status=r[6],
            channel_handle=r[2],
            channel_url=r[3],
            notes=r[7],
            risk_notes=r[8],
        )
        for r in rows
    ]


def load_blocked_channel_ids_postgres(conn) -> set[str]:
    """Postgres equivalent of :func:`load_blocked_channel_ids` (active-gated)."""
    base = ("SELECT channel_id FROM blocked_youtube_channels "
            "WHERE channel_id IS NOT NULL AND channel_id <> ''")
    rows = _pg_active_then_legacy(
        conn,
        base + " AND (active IS NULL OR active = true)",
        base,
        (),
    )
    if rows is None:
        return set()
    return {r[0] for r in rows if r and r[0]}


# ── Write helpers (used by tests now; the human-review workflow/admin later) ──
def upsert_trusted_channel_sqlite(
    conn: sqlite3.Connection,
    *,
    channel_id: str,
    channel_title: str = "",
    source_group: str = "trusted/culture",
    trust_tier: str = "candidate",
    status: str = "candidate",
    channel_handle: str | None = None,
    channel_url: str | None = None,
    notes: str | None = None,
    risk_notes: str | None = None,
    approved_by: str | None = None,
) -> None:
    ensure_trust_tables_sqlite(conn)
    now = _now_iso()
    approved_at = now if status == TRUSTED_STATUS_APPROVED else None
    conn.execute(
        """
        INSERT INTO trusted_youtube_channels
            (channel_id, channel_title, channel_handle, channel_url, source_group,
             trust_tier, status, notes, risk_notes, approved_by, approved_at,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            channel_title=excluded.channel_title,
            channel_handle=excluded.channel_handle,
            channel_url=excluded.channel_url,
            source_group=excluded.source_group,
            trust_tier=excluded.trust_tier,
            status=excluded.status,
            notes=excluded.notes,
            risk_notes=excluded.risk_notes,
            approved_by=excluded.approved_by,
            approved_at=excluded.approved_at,
            updated_at=excluded.updated_at
        """,
        (channel_id, channel_title, channel_handle, channel_url, source_group,
         trust_tier, status, notes, risk_notes, approved_by, approved_at, now, now),
    )
    conn.commit()


def block_channel_sqlite(
    conn: sqlite3.Connection,
    *,
    channel_id: str,
    channel_title: str = "",
    reason: str = "manual_block",
    blocked_by: str | None = None,
) -> None:
    ensure_trust_tables_sqlite(conn)
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO blocked_youtube_channels
            (channel_id, channel_title, reason, blocked_by, blocked_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            channel_title=excluded.channel_title,
            reason=excluded.reason,
            blocked_by=excluded.blocked_by,
            updated_at=excluded.updated_at
        """,
        (channel_id, channel_title, reason, blocked_by, now, now, now),
    )
    conn.commit()


def add_channel_candidate_sqlite(
    conn: sqlite3.Connection,
    *,
    channel_id: str,
    channel_title: str = "",
    suggested_source_group: str | None = None,
    discovery_source: str | None = None,
    why_suggested: str | None = None,
    possible_risks: str | None = None,
    review_status: str = "new",
    recommended_status: str | None = None,
) -> None:
    ensure_trust_tables_sqlite(conn)
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO youtube_channel_candidates
            (channel_id, channel_title, suggested_source_group, discovery_source,
             why_suggested, possible_risks, recommended_status, review_status,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            channel_title=excluded.channel_title,
            suggested_source_group=excluded.suggested_source_group,
            discovery_source=excluded.discovery_source,
            why_suggested=excluded.why_suggested,
            possible_risks=excluded.possible_risks,
            recommended_status=excluded.recommended_status,
            review_status=excluded.review_status,
            updated_at=excluded.updated_at
        """,
        (channel_id, channel_title, suggested_source_group, discovery_source,
         why_suggested, possible_risks, recommended_status, review_status, now, now),
    )
    conn.commit()


# ── AI-assisted curation import / upsert ─────────────────────────────────────
def validate_ai_curation_row(raw: dict) -> dict:
    """Validate + normalize one AI curation row. Raises ValueError on bad input.

    `active` defaults to True, except pending/rejected which default to inactive
    (so they are never eligible for ingestion until a human acts).
    """
    if not isinstance(raw, dict):
        raise ValueError("curation row must be a JSON object")
    channel_id = str(raw.get("channel_id") or "").strip()
    if not channel_id:
        raise ValueError("channel_id is required")
    trust_status = str(raw.get("trust_status") or "").strip().lower()
    if trust_status not in AI_TRUST_STATUSES:
        raise ValueError(
            f"invalid trust_status {raw.get('trust_status')!r}; "
            f"allowed: {', '.join(AI_TRUST_STATUSES)}"
        )
    conf_raw = raw.get("confidence_score", raw.get("ai_confidence"))
    try:
        confidence = float(conf_raw)
    except (TypeError, ValueError):
        raise ValueError("confidence_score is required and must be a number in 0..1")
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"confidence_score {confidence} is out of range 0..1")

    active = raw.get("active")
    if active is None:
        active = trust_status not in ("pending", "rejected")
    else:
        active = bool(active)

    return {
        "platform": (str(raw.get("platform") or "youtube").strip().lower() or "youtube"),
        "channel_id": channel_id,
        "channel_title": str(raw.get("channel_title") or "").strip(),
        "channel_url": (str(raw.get("channel_url")).strip() if raw.get("channel_url") else None),
        "trust_status": trust_status,
        "source_type": (str(raw.get("source_type") or raw.get("source_category") or "").strip() or None),
        "confidence_score": confidence,
        "reason": (str(raw.get("reason") or raw.get("ai_reason") or "").strip() or None),
        "active": active,
    }


def _human_reviewed(existing) -> bool:
    """True if a human has reviewed this row (so AI must not overwrite the
    decision/review fields)."""
    if existing is None:
        return False
    keys = existing.keys() if hasattr(existing, "keys") else ()
    review_status = (existing["review_status"] or "").strip().lower() if "review_status" in keys else ""
    reviewed_by = existing["reviewed_by"] if "reviewed_by" in keys else None
    return bool(reviewed_by) or (review_status not in ("", AI_REVIEW_STATUS_DEFAULT))


def _resolved_active(existing, requested_active: bool, force_reactivate: bool) -> int:
    """Never reactivate a human-disabled (active=0) row unless force_reactivate."""
    existing_active = 1
    if existing is not None and "active" in (existing.keys() if hasattr(existing, "keys") else ()):
        existing_active = 1 if (existing["active"] is None or existing["active"]) else 0
    if existing is not None and existing_active == 0 and not force_reactivate:
        return 0
    return 1 if requested_active else 0


def upsert_ai_channel_curation(conn, *, backend: str = "sqlite",
                               force_reactivate: bool = False, **fields) -> dict:
    """Idempotently upsert one AI-labeled channel row into the existing trust
    tables. Returns {action, table, channel_id, active, trust_status}.

    Routing: trusted/pending/rejected → trusted_youtube_channels;
             blocked → blocked_youtube_channels (a hard exclude when active).
    Safety: this only records curation. A trusted row still passes through the
    full ingestion gate (language/safety/relevance) — it is never a bypass.
    """
    row = validate_ai_curation_row(fields)
    if backend == "postgres":
        return _upsert_ai_curation_postgres(conn, row, force_reactivate=force_reactivate)
    return _upsert_ai_curation_sqlite(conn, row, force_reactivate=force_reactivate)


def _upsert_ai_curation_sqlite(conn: sqlite3.Connection, row: dict, *, force_reactivate: bool) -> dict:
    ensure_trust_tables_sqlite(conn)
    if row["trust_status"] == "blocked":
        return _upsert_blocked_ai_sqlite(conn, row, force_reactivate)
    return _upsert_trusted_ai_sqlite(conn, row, force_reactivate)


def _upsert_trusted_ai_sqlite(conn, row, force_reactivate) -> dict:
    cid = row["channel_id"]
    now = _now_iso()
    mapped_status = _TRUST_STATUS_TO_TRUSTED_STATUS[row["trust_status"]]
    existing = conn.execute(
        "SELECT * FROM trusted_youtube_channels WHERE channel_id=?", (cid,)
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO trusted_youtube_channels "
            "(channel_id, channel_title, channel_url, source_group, status, trust_status, "
            " platform, added_by, ai_confidence, ai_reason, active, review_status, "
            " created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, row["channel_title"], row["channel_url"], row["source_type"], mapped_status,
             row["trust_status"], row["platform"], AI_ADDED_BY, row["confidence_score"],
             row["reason"], 1 if row["active"] else 0, AI_REVIEW_STATUS_DEFAULT, now, now),
        )
        conn.commit()
        return {"action": "inserted", "table": "trusted_youtube_channels",
                "channel_id": cid, "active": row["active"], "trust_status": row["trust_status"]}

    new_active = _resolved_active(existing, row["active"], force_reactivate)
    if _human_reviewed(existing):
        # AI may only refresh its own signals — never the human's decision/review.
        conn.execute(
            "UPDATE trusted_youtube_channels SET ai_confidence=?, ai_reason=?, "
            "source_group=COALESCE(?, source_group), updated_at=? WHERE channel_id=?",
            (row["confidence_score"], row["reason"], row["source_type"], now, cid),
        )
    else:
        conn.execute(
            "UPDATE trusted_youtube_channels SET "
            "channel_title=COALESCE(NULLIF(?,''), channel_title), "
            "channel_url=COALESCE(?, channel_url), source_group=COALESCE(?, source_group), "
            "status=?, trust_status=?, platform=?, added_by=?, ai_confidence=?, ai_reason=?, "
            "active=?, updated_at=? WHERE channel_id=?",
            (row["channel_title"], row["channel_url"], row["source_type"], mapped_status,
             row["trust_status"], row["platform"], AI_ADDED_BY, row["confidence_score"],
             row["reason"], new_active, now, cid),
        )
    conn.commit()
    return {"action": "updated", "table": "trusted_youtube_channels",
            "channel_id": cid, "active": bool(new_active), "trust_status": row["trust_status"]}


def _upsert_blocked_ai_sqlite(conn, row, force_reactivate) -> dict:
    cid = row["channel_id"]
    now = _now_iso()
    reason = row["reason"] or row["source_type"] or "manual_block"
    existing = conn.execute(
        "SELECT * FROM blocked_youtube_channels WHERE channel_id=?", (cid,)
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO blocked_youtube_channels "
            "(channel_id, channel_title, reason, blocked_by, blocked_at, trust_status, "
            " platform, added_by, ai_confidence, ai_reason, active, review_status, "
            " created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, row["channel_title"], reason, AI_ADDED_BY, now, "blocked", row["platform"],
             AI_ADDED_BY, row["confidence_score"], row["reason"], 1 if row["active"] else 0,
             AI_REVIEW_STATUS_DEFAULT, now, now),
        )
        conn.commit()
        return {"action": "inserted", "table": "blocked_youtube_channels",
                "channel_id": cid, "active": row["active"], "trust_status": "blocked"}

    new_active = _resolved_active(existing, row["active"], force_reactivate)
    if _human_reviewed(existing):
        conn.execute(
            "UPDATE blocked_youtube_channels SET ai_confidence=?, ai_reason=?, "
            "reason=COALESCE(?, reason), updated_at=? WHERE channel_id=?",
            (row["confidence_score"], row["reason"], row["source_type"], now, cid),
        )
    else:
        conn.execute(
            "UPDATE blocked_youtube_channels SET "
            "channel_title=COALESCE(NULLIF(?,''), channel_title), reason=?, trust_status=?, "
            "platform=?, added_by=?, ai_confidence=?, ai_reason=?, active=?, updated_at=? "
            "WHERE channel_id=?",
            (row["channel_title"], reason, "blocked", row["platform"], AI_ADDED_BY,
             row["confidence_score"], row["reason"], new_active, now, cid),
        )
    conn.commit()
    return {"action": "updated", "table": "blocked_youtube_channels",
            "channel_id": cid, "active": bool(new_active), "trust_status": "blocked"}


# ── Postgres upsert (production / Supabase path) ─────────────────────────────
def _pg_existing(cur, table: str, channel_id: str):
    cur.execute(
        f"SELECT active, review_status, reviewed_by FROM {table} WHERE channel_id = %s",
        (channel_id,),
    )
    t = cur.fetchone()
    if t is None:
        return None
    return {"active": t[0], "review_status": t[1], "reviewed_by": t[2]}


def _upsert_ai_curation_postgres(conn, row: dict, *, force_reactivate: bool) -> dict:
    if row["trust_status"] == "blocked":
        return _upsert_blocked_ai_postgres(conn, row, force_reactivate)
    return _upsert_trusted_ai_postgres(conn, row, force_reactivate)


def _upsert_trusted_ai_postgres(conn, row, force_reactivate) -> dict:
    cur = conn.cursor()
    cid = row["channel_id"]
    mapped_status = _TRUST_STATUS_TO_TRUSTED_STATUS[row["trust_status"]]
    existing = _pg_existing(cur, "trusted_youtube_channels", cid)
    if existing is None:
        cur.execute(
            "INSERT INTO trusted_youtube_channels "
            "(channel_id, channel_title, channel_url, source_group, status, trust_status, "
            " platform, added_by, ai_confidence, ai_reason, active, review_status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (cid, row["channel_title"], row["channel_url"], row["source_type"], mapped_status,
             row["trust_status"], row["platform"], AI_ADDED_BY, row["confidence_score"],
             row["reason"], row["active"], AI_REVIEW_STATUS_DEFAULT),
        )
        conn.commit()
        return {"action": "inserted", "table": "trusted_youtube_channels",
                "channel_id": cid, "active": row["active"], "trust_status": row["trust_status"]}

    new_active = bool(_resolved_active(existing, row["active"], force_reactivate))
    if _human_reviewed(existing):
        cur.execute(
            "UPDATE trusted_youtube_channels SET ai_confidence=%s, ai_reason=%s, "
            "source_group=COALESCE(%s, source_group), updated_at=now() WHERE channel_id=%s",
            (row["confidence_score"], row["reason"], row["source_type"], cid),
        )
    else:
        cur.execute(
            "UPDATE trusted_youtube_channels SET "
            "channel_title=COALESCE(NULLIF(%s,''), channel_title), "
            "channel_url=COALESCE(%s, channel_url), source_group=COALESCE(%s, source_group), "
            "status=%s, trust_status=%s, platform=%s, added_by=%s, ai_confidence=%s, "
            "ai_reason=%s, active=%s, updated_at=now() WHERE channel_id=%s",
            (row["channel_title"], row["channel_url"], row["source_type"], mapped_status,
             row["trust_status"], row["platform"], AI_ADDED_BY, row["confidence_score"],
             row["reason"], new_active, cid),
        )
    conn.commit()
    return {"action": "updated", "table": "trusted_youtube_channels",
            "channel_id": cid, "active": new_active, "trust_status": row["trust_status"]}


def _upsert_blocked_ai_postgres(conn, row, force_reactivate) -> dict:
    cur = conn.cursor()
    cid = row["channel_id"]
    reason = row["reason"] or row["source_type"] or "manual_block"
    existing = _pg_existing(cur, "blocked_youtube_channels", cid)
    if existing is None:
        cur.execute(
            "INSERT INTO blocked_youtube_channels "
            "(channel_id, channel_title, reason, blocked_by, trust_status, platform, "
            " added_by, ai_confidence, ai_reason, active, review_status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (cid, row["channel_title"], reason, AI_ADDED_BY, "blocked", row["platform"],
             AI_ADDED_BY, row["confidence_score"], row["reason"], row["active"],
             AI_REVIEW_STATUS_DEFAULT),
        )
        conn.commit()
        return {"action": "inserted", "table": "blocked_youtube_channels",
                "channel_id": cid, "active": row["active"], "trust_status": "blocked"}

    new_active = bool(_resolved_active(existing, row["active"], force_reactivate))
    if _human_reviewed(existing):
        cur.execute(
            "UPDATE blocked_youtube_channels SET ai_confidence=%s, ai_reason=%s, "
            "reason=COALESCE(%s, reason), updated_at=now() WHERE channel_id=%s",
            (row["confidence_score"], row["reason"], row["source_type"], cid),
        )
    else:
        cur.execute(
            "UPDATE blocked_youtube_channels SET "
            "channel_title=COALESCE(NULLIF(%s,''), channel_title), reason=%s, trust_status=%s, "
            "platform=%s, added_by=%s, ai_confidence=%s, ai_reason=%s, active=%s, "
            "updated_at=now() WHERE channel_id=%s",
            (row["channel_title"], reason, "blocked", row["platform"], AI_ADDED_BY,
             row["confidence_score"], row["reason"], new_active, cid),
        )
    conn.commit()
    return {"action": "updated", "table": "blocked_youtube_channels",
            "channel_id": cid, "active": new_active, "trust_status": "blocked"}
