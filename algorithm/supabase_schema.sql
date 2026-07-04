-- Run this once in Supabase SQL Editor to set up the Chrysalis schema.

-- Videos discovered by the daily YouTube feed ingestion endpoint. These are
-- metadata rows only; playback remains a standard YouTube iframe embed.
CREATE TABLE IF NOT EXISTS feed_videos (
    id                  TEXT PRIMARY KEY,
    source              TEXT NOT NULL DEFAULT 'youtube',
    youtube_video_id    TEXT NOT NULL UNIQUE,
    title               TEXT,
    channel_title       TEXT,
    channel_id          TEXT,
    description         TEXT,
    short_description   TEXT,
    display_title       TEXT,
    display_channel     TEXT,
    display_hashtags    JSONB,
    thumbnail_url       TEXT,
    embed_url           TEXT,
    watch_url           TEXT,
    published_at        TEXT,
    duration_seconds    INTEGER,
    view_count          BIGINT,
    tags                JSONB,
    category_id         TEXT,
    topic               TEXT,
    source_category     TEXT,
    source_query        TEXT,
    integrity_score     REAL,
    integrity_flags     JSONB,
    production_style    TEXT,
    creator_scale       TEXT,
    score               REAL,
    created_at          TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'active',
    chrysalis_scores    JSONB,
    ranking_reason      TEXT,
    safety_reason       TEXT,
    concern_reason      TEXT,
    label_confidence    REAL,
    scored_at           TIMESTAMPTZ,
    scoring_version     TEXT
);

CREATE INDEX IF NOT EXISTS idx_feed_videos_status_score
    ON feed_videos (status, score DESC, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_feed_videos_youtube_id
    ON feed_videos (youtube_video_id);

CREATE INDEX IF NOT EXISTS idx_feed_videos_source_category
    ON feed_videos (source_category);

CREATE INDEX IF NOT EXISTS idx_feed_videos_source_query
    ON feed_videos (source_query);

CREATE INDEX IF NOT EXISTS idx_feed_videos_integrity_score
    ON feed_videos (integrity_score);

-- Public Signal Scanner v1. These records are expiring context/review signals,
-- not permanent creator blacklists. v1 writes stub/neutral records unless a
-- future approved public-search provider is connected.
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
