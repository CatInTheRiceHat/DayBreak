-- Migration 006 - Short display captions for feed videos
--
-- Keeps raw YouTube descriptions intact while adding a cleaned caption field
-- for compact Reels-style UI display.

ALTER TABLE feed_videos
    ADD COLUMN IF NOT EXISTS short_description TEXT;
