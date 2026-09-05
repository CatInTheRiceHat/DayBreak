-- Migration 007 - Feed video integrity metadata
--
-- Adds a deterministic safety/spam/analyzability layer without scoring polish.
-- Low-budget, amateur, casual, and small-creator videos remain eligible when
-- they are safe and analyzable.

ALTER TABLE feed_videos
    ADD COLUMN IF NOT EXISTS integrity_score REAL;

ALTER TABLE feed_videos
    ADD COLUMN IF NOT EXISTS integrity_flags JSONB;

ALTER TABLE feed_videos
    ADD COLUMN IF NOT EXISTS production_style TEXT;

ALTER TABLE feed_videos
    ADD COLUMN IF NOT EXISTS creator_scale TEXT;

CREATE INDEX IF NOT EXISTS idx_feed_videos_integrity_score
    ON feed_videos (integrity_score);
