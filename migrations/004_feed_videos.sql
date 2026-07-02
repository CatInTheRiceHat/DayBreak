-- Migration 004 - Daily YouTube feed ingestion storage
--
-- Stores active YouTube Data API metadata for the Algorithm feed. These are
-- metadata rows only; Chrysalis never downloads, proxies, converts, or rehosts
-- YouTube videos.

CREATE TABLE IF NOT EXISTS feed_videos (
    id                  TEXT PRIMARY KEY,
    source              TEXT NOT NULL DEFAULT 'youtube',
    youtube_video_id    TEXT NOT NULL UNIQUE,
    title               TEXT,
    channel_title       TEXT,
    channel_id          TEXT,
    description         TEXT,
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
