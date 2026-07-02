"""
SQLite/Postgres cache helpers for public signal records.

The scanner layer is optional. If the cache is empty, the v1 stub provider writes
fresh neutral records so feed requests do not repeatedly rescan the same target.
"""

from __future__ import annotations

import json
from typing import Iterable

from .explain import safety_record_reason
from .provider import PublicSignalProvider, StubPublicSignalProvider
from .ranking import PublicSignalContext
from .schema import (
    ChannelSafetyRecord,
    PublicSignalRecord,
    PUBLIC_SIGNAL_VERSION,
    expiry_iso,
    iso_utc,
)


SQLITE_PUBLIC_SIGNAL_TABLES = """
CREATE TABLE IF NOT EXISTS public_signal_records (
    target_type TEXT NOT NULL CHECK(target_type IN ('channel', 'video')),
    target_id TEXT NOT NULL,
    concern_score REAL NOT NULL DEFAULT 0,
    support_score REAL NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0,
    main_concerns TEXT NOT NULL DEFAULT '[]',
    supportive_signals TEXT NOT NULL DEFAULT '[]',
    evidence_count INTEGER NOT NULL DEFAULT 0,
    source_quality TEXT NOT NULL DEFAULT 'weak',
    recency TEXT NOT NULL DEFAULT 'old',
    requires_human_review INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    last_checked TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    signal_version TEXT NOT NULL,
    PRIMARY KEY (target_type, target_id)
);

CREATE TABLE IF NOT EXISTS channel_safety_records (
    channel_id TEXT PRIMARY KEY,
    channel_title TEXT,
    status TEXT NOT NULL CHECK(status IN ('trusted', 'neutral', 'caution', 'do_not_recommend')),
    requires_human_review INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    signal_target_type TEXT,
    signal_target_id TEXT,
    last_checked TEXT NOT NULL,
    review_after TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    signal_version TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_public_signal_expires
    ON public_signal_records (expires_at);

CREATE INDEX IF NOT EXISTS idx_channel_safety_status
    ON channel_safety_records (status, expires_at);
"""


POSTGRES_PUBLIC_SIGNAL_TABLES = """
CREATE TABLE IF NOT EXISTS public_signal_records (
    target_type TEXT NOT NULL CHECK(target_type IN ('channel', 'video')),
    target_id TEXT NOT NULL,
    concern_score REAL NOT NULL DEFAULT 0,
    support_score REAL NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0,
    main_concerns JSONB NOT NULL DEFAULT '[]'::jsonb,
    supportive_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    source_quality TEXT NOT NULL DEFAULT 'weak',
    recency TEXT NOT NULL DEFAULT 'old',
    requires_human_review BOOLEAN NOT NULL DEFAULT FALSE,
    summary TEXT NOT NULL DEFAULT '',
    last_checked TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    provider TEXT NOT NULL,
    signal_version TEXT NOT NULL,
    PRIMARY KEY (target_type, target_id)
);

CREATE TABLE IF NOT EXISTS channel_safety_records (
    channel_id TEXT PRIMARY KEY,
    channel_title TEXT,
    status TEXT NOT NULL CHECK(status IN ('trusted', 'neutral', 'caution', 'do_not_recommend')),
    requires_human_review BOOLEAN NOT NULL DEFAULT FALSE,
    reason TEXT,
    signal_target_type TEXT,
    signal_target_id TEXT,
    last_checked TIMESTAMPTZ NOT NULL,
    review_after TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    provider TEXT NOT NULL,
    signal_version TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_public_signal_expires
    ON public_signal_records (expires_at);

CREATE INDEX IF NOT EXISTS idx_channel_safety_status
    ON channel_safety_records (status, expires_at);
"""


def ensure_sqlite_public_signal_tables(conn) -> None:
    conn.executescript(SQLITE_PUBLIC_SIGNAL_TABLES)
    conn.commit()


def ensure_postgres_public_signal_tables(conn) -> None:
    cur = conn.cursor()
    cur.execute(POSTGRES_PUBLIC_SIGNAL_TABLES)
    conn.commit()


def load_cached_context_sqlite(
    conn,
    rows: Iterable[dict],
) -> PublicSignalContext:
    """
    Read already-cached public-signal context without creating tables or records.
    Missing cache tables simply produce a neutral context.
    """
    row_list = list(rows)
    context = PublicSignalContext.empty()
    try:
        for channel_id, _channel_title in _unique_channels(row_list):
            signal = _get_sqlite_public_signal(conn, "channel", channel_id)
            safety = _get_sqlite_channel_safety(conn, channel_id)
            if signal is not None:
                context.channel_signals[channel_id] = signal
            if safety is not None:
                context.channel_safety[channel_id] = safety

        for video_id, _row in _unique_videos(row_list):
            signal = _get_sqlite_public_signal(conn, "video", video_id)
            if signal is not None:
                context.video_signals[video_id] = signal
    except Exception:
        return PublicSignalContext.empty()
    return context


def load_cached_context_postgres(
    conn,
    rows: Iterable[dict],
) -> PublicSignalContext:
    """
    Read already-cached public-signal context without creating tables or records.
    Missing cache tables simply produce a neutral context.
    """
    row_list = list(rows)
    context = PublicSignalContext.empty()
    channel_ids = [cid for cid, _ in _unique_channels(row_list)]
    video_ids = [vid for vid, _ in _unique_videos(row_list)]
    try:
        cur = conn.cursor()

        if channel_ids:
            cur.execute(
                """
                SELECT * FROM public_signal_records
                WHERE target_type = 'channel' AND target_id IN %s
                """,
                (tuple(channel_ids),),
            )
            for row in _cursor_rows(cur):
                signal = PublicSignalRecord.from_row(row)
                if signal is not None and not signal.is_expired():
                    context.channel_signals[row["target_id"]] = signal

            cur.execute(
                "SELECT * FROM channel_safety_records WHERE channel_id IN %s",
                (tuple(channel_ids),),
            )
            for row in _cursor_rows(cur):
                safety = ChannelSafetyRecord.from_row(row)
                if safety is not None and not safety.is_expired():
                    context.channel_safety[row["channel_id"]] = safety

        if video_ids:
            cur.execute(
                """
                SELECT * FROM public_signal_records
                WHERE target_type = 'video' AND target_id IN %s
                """,
                (tuple(video_ids),),
            )
            for row in _cursor_rows(cur):
                signal = PublicSignalRecord.from_row(row)
                if signal is not None and not signal.is_expired():
                    context.video_signals[row["target_id"]] = signal
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return PublicSignalContext.empty()
    return context


def load_or_scan_context_sqlite(
    conn,
    rows: Iterable[dict],
    provider: PublicSignalProvider | None = None,
) -> PublicSignalContext:
    provider = provider or StubPublicSignalProvider()
    ensure_sqlite_public_signal_tables(conn)
    row_list = list(rows)
    context = PublicSignalContext.empty()

    for channel_id, channel_title in _unique_channels(row_list):
        signal = _get_sqlite_public_signal(conn, "channel", channel_id)
        if signal is None:
            signal = provider.scan_channel(channel_id, channel_title)
            _upsert_sqlite_public_signal(conn, signal, provider.name)

        safety = _get_sqlite_channel_safety(conn, channel_id)
        if safety is None:
            safety = derive_channel_safety(signal, channel_title)
            _upsert_sqlite_channel_safety(conn, safety, provider.name)

        context.channel_signals[channel_id] = signal
        context.channel_safety[channel_id] = safety

    for video_id, row in _unique_videos(row_list):
        signal = _get_sqlite_public_signal(conn, "video", video_id)
        if signal is None:
            signal = provider.scan_video(video_id, row)
            _upsert_sqlite_public_signal(conn, signal, provider.name)
        context.video_signals[video_id] = signal

    conn.commit()
    return context


def load_or_scan_context_postgres(
    conn,
    rows: Iterable[dict],
    provider: PublicSignalProvider | None = None,
) -> PublicSignalContext:
    provider = provider or StubPublicSignalProvider()
    ensure_postgres_public_signal_tables(conn)
    row_list = list(rows)
    context = PublicSignalContext.empty()

    for channel_id, channel_title in _unique_channels(row_list):
        signal = _get_postgres_public_signal(conn, "channel", channel_id)
        if signal is None:
            signal = provider.scan_channel(channel_id, channel_title)
            _upsert_postgres_public_signal(conn, signal, provider.name)

        safety = _get_postgres_channel_safety(conn, channel_id)
        if safety is None:
            safety = derive_channel_safety(signal, channel_title)
            _upsert_postgres_channel_safety(conn, safety, provider.name)

        context.channel_signals[channel_id] = signal
        context.channel_safety[channel_id] = safety

    for video_id, row in _unique_videos(row_list):
        signal = _get_postgres_public_signal(conn, "video", video_id)
        if signal is None:
            signal = provider.scan_video(video_id, row)
            _upsert_postgres_public_signal(conn, signal, provider.name)
        context.video_signals[video_id] = signal

    conn.commit()
    return context


def derive_channel_safety(
    signal: PublicSignalRecord,
    channel_title: str = "",
) -> ChannelSafetyRecord:
    status = "neutral"
    if signal.support_score >= 0.65 and signal.concern_score < 0.25 and signal.confidence >= 0.4:
        status = "trusted"
    elif signal.concern_score >= 0.35 or signal.requires_human_review:
        status = "caution"

    requires_review = bool(signal.requires_human_review or signal.concern_score >= 0.65)
    reason = safety_record_reason(signal)
    now = iso_utc()
    expires = expiry_iso(requires_review)
    return ChannelSafetyRecord(
        channel_id=signal.target_id,
        channel_title=channel_title,
        status=status,
        requires_human_review=requires_review,
        reason=reason,
        signal_target_type=signal.target_type,
        signal_target_id=signal.target_id,
        last_checked=now,
        review_after=expires if requires_review else expiry_iso(False),
        expires_at=expires,
    )


def _unique_channels(rows: list[dict]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for row in rows:
        channel_id = str(row.get("channel_id") or "").strip()
        if not channel_id or channel_id in seen:
            continue
        seen.add(channel_id)
        result.append((channel_id, str(row.get("channel_title") or row.get("channel") or "")))
    return result


def _unique_videos(rows: list[dict]) -> list[tuple[str, dict]]:
    seen: set[str] = set()
    result: list[tuple[str, dict]] = []
    for row in rows:
        video_id = str(row.get("video_id") or row.get("youtube_id") or "").strip()
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        result.append((video_id, row))
    return result


def _get_sqlite_public_signal(conn, target_type: str, target_id: str) -> PublicSignalRecord | None:
    row = conn.execute(
        """
        SELECT * FROM public_signal_records
        WHERE target_type = ? AND target_id = ?
        """,
        (target_type, target_id),
    ).fetchone()
    signal = PublicSignalRecord.from_row(_row_to_dict(row))
    if signal is None or signal.is_expired():
        return None
    return signal


def _get_sqlite_channel_safety(conn, channel_id: str) -> ChannelSafetyRecord | None:
    row = conn.execute(
        "SELECT * FROM channel_safety_records WHERE channel_id = ?",
        (channel_id,),
    ).fetchone()
    safety = ChannelSafetyRecord.from_row(_row_to_dict(row))
    if safety is None or safety.is_expired():
        return None
    return safety


def _upsert_sqlite_public_signal(conn, signal: PublicSignalRecord, provider: str) -> None:
    conn.execute(
        """
        INSERT INTO public_signal_records (
            target_type, target_id, concern_score, support_score, confidence,
            main_concerns, supportive_signals, evidence_count, source_quality,
            recency, requires_human_review, summary, last_checked, expires_at,
            provider, signal_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(target_type, target_id) DO UPDATE SET
            concern_score = excluded.concern_score,
            support_score = excluded.support_score,
            confidence = excluded.confidence,
            main_concerns = excluded.main_concerns,
            supportive_signals = excluded.supportive_signals,
            evidence_count = excluded.evidence_count,
            source_quality = excluded.source_quality,
            recency = excluded.recency,
            requires_human_review = excluded.requires_human_review,
            summary = excluded.summary,
            last_checked = excluded.last_checked,
            expires_at = excluded.expires_at,
            provider = excluded.provider,
            signal_version = excluded.signal_version
        """,
        _signal_values(signal, provider, sqlite=True),
    )


def _upsert_sqlite_channel_safety(conn, safety: ChannelSafetyRecord, provider: str) -> None:
    conn.execute(
        """
        INSERT INTO channel_safety_records (
            channel_id, channel_title, status, requires_human_review, reason,
            signal_target_type, signal_target_id, last_checked, review_after,
            expires_at, provider, signal_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            channel_title = excluded.channel_title,
            status = excluded.status,
            requires_human_review = excluded.requires_human_review,
            reason = excluded.reason,
            signal_target_type = excluded.signal_target_type,
            signal_target_id = excluded.signal_target_id,
            last_checked = excluded.last_checked,
            review_after = excluded.review_after,
            expires_at = excluded.expires_at,
            provider = excluded.provider,
            signal_version = excluded.signal_version
        """,
        _safety_values(safety, provider, sqlite=True),
    )


def _get_postgres_public_signal(conn, target_type: str, target_id: str) -> PublicSignalRecord | None:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM public_signal_records
        WHERE target_type = %s AND target_id = %s
        """,
        (target_type, target_id),
    )
    row = cur.fetchone()
    signal = PublicSignalRecord.from_row(_cursor_row(cur, row))
    if signal is None or signal.is_expired():
        return None
    return signal


def _get_postgres_channel_safety(conn, channel_id: str) -> ChannelSafetyRecord | None:
    cur = conn.cursor()
    cur.execute("SELECT * FROM channel_safety_records WHERE channel_id = %s", (channel_id,))
    row = cur.fetchone()
    safety = ChannelSafetyRecord.from_row(_cursor_row(cur, row))
    if safety is None or safety.is_expired():
        return None
    return safety


def _upsert_postgres_public_signal(conn, signal: PublicSignalRecord, provider: str) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO public_signal_records (
            target_type, target_id, concern_score, support_score, confidence,
            main_concerns, supportive_signals, evidence_count, source_quality,
            recency, requires_human_review, summary, last_checked, expires_at,
            provider, signal_version
        ) VALUES (
            %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT(target_type, target_id) DO UPDATE SET
            concern_score = excluded.concern_score,
            support_score = excluded.support_score,
            confidence = excluded.confidence,
            main_concerns = excluded.main_concerns,
            supportive_signals = excluded.supportive_signals,
            evidence_count = excluded.evidence_count,
            source_quality = excluded.source_quality,
            recency = excluded.recency,
            requires_human_review = excluded.requires_human_review,
            summary = excluded.summary,
            last_checked = excluded.last_checked,
            expires_at = excluded.expires_at,
            provider = excluded.provider,
            signal_version = excluded.signal_version
        """,
        _signal_values(signal, provider, sqlite=False),
    )


def _upsert_postgres_channel_safety(conn, safety: ChannelSafetyRecord, provider: str) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO channel_safety_records (
            channel_id, channel_title, status, requires_human_review, reason,
            signal_target_type, signal_target_id, last_checked, review_after,
            expires_at, provider, signal_version
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(channel_id) DO UPDATE SET
            channel_title = excluded.channel_title,
            status = excluded.status,
            requires_human_review = excluded.requires_human_review,
            reason = excluded.reason,
            signal_target_type = excluded.signal_target_type,
            signal_target_id = excluded.signal_target_id,
            last_checked = excluded.last_checked,
            review_after = excluded.review_after,
            expires_at = excluded.expires_at,
            provider = excluded.provider,
            signal_version = excluded.signal_version
        """,
        _safety_values(safety, provider, sqlite=False),
    )


def _signal_values(signal: PublicSignalRecord, provider: str, sqlite: bool) -> tuple:
    return (
        signal.target_type,
        signal.target_id,
        signal.concern_score,
        signal.support_score,
        signal.confidence,
        json.dumps(signal.main_concerns),
        json.dumps(signal.supportive_signals),
        signal.evidence_count,
        signal.source_quality,
        signal.recency,
        int(signal.requires_human_review) if sqlite else signal.requires_human_review,
        signal.summary,
        signal.last_checked,
        signal.expires_at,
        provider,
        PUBLIC_SIGNAL_VERSION,
    )


def _safety_values(safety: ChannelSafetyRecord, provider: str, sqlite: bool) -> tuple:
    return (
        safety.channel_id,
        safety.channel_title,
        safety.status,
        int(safety.requires_human_review) if sqlite else safety.requires_human_review,
        safety.reason,
        safety.signal_target_type,
        safety.signal_target_id,
        safety.last_checked,
        safety.review_after,
        safety.expires_at,
        provider,
        PUBLIC_SIGNAL_VERSION,
    )


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except (TypeError, ValueError):
        return None


def _cursor_row(cur, row) -> dict | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def _cursor_rows(cur) -> list[dict]:
    """Fetch all remaining rows from a cursor as column-keyed dicts."""
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]
