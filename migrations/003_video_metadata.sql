-- Migration 003 — Richer YouTube metadata fields (Postgres / Supabase)
--
-- Adds the official/available YouTube metadata Chrysalis now stores for the cheap
-- Layer-1 content scanner: creator tags, normalized duration, and a thumbnail URL.
-- Run once in the Supabase SQL Editor on databases that already have a `videos`
-- table. New databases get these columns directly from supabase_schema.sql, so this
-- migration is a no-op there thanks to IF NOT EXISTS.
--
-- SQLite (local chrysalis.db) upgrades automatically via _ensure_label_columns()
-- in integrations/youtube_extractor.py — no manual step needed.
--
-- All columns are nullable so existing rows (extracted before this patch) stay
-- valid and simply carry NULL until their next fetch.

ALTER TABLE videos ADD COLUMN IF NOT EXISTS tags             JSONB;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS duration_seconds INTEGER;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS thumbnail_url    TEXT;
