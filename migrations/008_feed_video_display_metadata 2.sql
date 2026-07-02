-- Migration 008 - Display-safe feed metadata
--
-- Stores compact UI strings derived from raw YouTube metadata. Raw title,
-- description, and channel_title remain unchanged for analysis/debugging.

ALTER TABLE feed_videos
    ADD COLUMN IF NOT EXISTS display_title TEXT;

ALTER TABLE feed_videos
    ADD COLUMN IF NOT EXISTS display_channel TEXT;

ALTER TABLE feed_videos
    ADD COLUMN IF NOT EXISTS display_hashtags JSONB;
