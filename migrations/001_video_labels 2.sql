-- Migration 001 — Chrysalis v1 video label/ranking fields (Postgres / Supabase)
--
-- Run once in the Supabase SQL Editor on databases that already have a `videos`
-- table (created implicitly by the older /api/cron/extract). New databases get
-- these columns directly from supabase_schema.sql, so this migration is a no-op
-- there thanks to IF NOT EXISTS.
--
-- SQLite (local chrysalis.db) upgrades automatically via _ensure_label_columns()
-- in integrations/youtube_extractor.py — no manual step needed.

ALTER TABLE videos ADD COLUMN IF NOT EXISTS chrysalis_scores  JSONB;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS ranking_reason    TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS safety_reason     TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS concern_reason    TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS label_confidence  REAL;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS scored_at         TIMESTAMPTZ;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS scoring_version   TEXT;

CREATE INDEX IF NOT EXISTS idx_videos_scoring_version ON videos (scoring_version);
CREATE INDEX IF NOT EXISTS idx_videos_topic           ON videos (topic);
