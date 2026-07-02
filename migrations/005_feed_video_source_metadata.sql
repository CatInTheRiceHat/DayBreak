-- Migration 005 - YouTube feed source metadata
--
-- Stores the broad ingestion bucket and exact search query used to discover a
-- feed video. These fields are analysis/balancing metadata only; reels modes do
-- not use them as separate content pools.

ALTER TABLE feed_videos
    ADD COLUMN IF NOT EXISTS source_category TEXT;

ALTER TABLE feed_videos
    ADD COLUMN IF NOT EXISTS source_query TEXT;

UPDATE feed_videos
SET source_category = COALESCE(source_category, topic)
WHERE source_category IS NULL;

CREATE INDEX IF NOT EXISTS idx_feed_videos_source_category
    ON feed_videos (source_category);

CREATE INDEX IF NOT EXISTS idx_feed_videos_source_query
    ON feed_videos (source_query);
