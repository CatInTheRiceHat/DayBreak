-- Migration 014 - Drop dead tables
--
-- These four tables are no longer reachable from the running app. Removing them
-- (and their orphaned code) as part of the pilot cleanup.
--
--   videos                     -- legacy feed store, fully replaced by feed_videos.
--                                 Only a defensive try/except merge read it (0 rows).
--   cocoon_profiles            -- old Cocoon weaning program. Superseded by the
--                                 `metamorphosis` reels ranking mode; its only UI
--                                 (Metamorphosis.jsx inside the unrouted LiveDemo)
--                                 is dead. /api/cocoon/* endpoints removed.
--   migration_drops            -- old Migration Mode drops. Writer never ran in
--                                 production (scheduler only started in local api.py);
--                                 reader /api/migration/today only called by dead UI.
--   youtube_channel_candidates -- channel review queue that was never wired into any
--                                 endpoint, cron, or ingestion path.
--
-- CASCADE drops the tables' own indexes / RLS policies. No other table has a
-- foreign key into any of these, so nothing else is affected.

DROP TABLE IF EXISTS videos CASCADE;
DROP TABLE IF EXISTS cocoon_profiles CASCADE;
DROP TABLE IF EXISTS migration_drops CASCADE;
DROP TABLE IF EXISTS youtube_channel_candidates CASCADE;
