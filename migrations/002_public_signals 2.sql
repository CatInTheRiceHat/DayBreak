-- Migration 002 - Public Signal Scanner v1 (Postgres / Supabase)
--
-- Stores expiring public reputation/context records. These records are review
-- context, not permanent blacklists. v1 writes stub/neutral records only unless
-- a future approved provider is connected.

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

