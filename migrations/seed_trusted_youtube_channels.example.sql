-- ============================================================================
-- SEED TEMPLATE — trusted_youtube_channels (EXAMPLE / PLACEHOLDERS ONLY)
-- ============================================================================
--
-- ⚠️  DO NOT RUN THIS FILE AS-IS. ⚠️
--
-- Every channel_id below is a fake placeholder (UC_REPLACE_ME_*). Running this
-- unchanged just inserts useless rows you will have to delete. This file is a
-- COPY-EDIT TEMPLATE: replace each UC_REPLACE_ME_* with a REAL YouTube channel
-- id (the "UC..." id, NOT the @handle), confirm the title/handle/source_group,
-- and only then run the rows you actually want.
--
-- Trust is a HUMAN decision. `approved_by` should be your name/initials and
-- `status` should be 'approved' only after you have reviewed the channel.
--
-- START SMALL: approve 3–5 channels, run ingestion once, watch your YouTube API
-- quota for a day (each approved channel costs ~1 search.list per run, and the
-- cron runs 4×/day). Do NOT approve dozens at once. See:
--   migrations/011_trusted_sources.sql           (schema + RLS)
--   migrations/011_trusted_sources_smoke_test.sql (verify the migration)
--   docs/trust_sources_operations.md             (operational checklist + quota)
--
-- `on conflict (channel_id) do nothing` makes re-running safe (no duplicates).
-- ============================================================================

insert into public.trusted_youtube_channels (
    channel_id,        -- REAL "UC..." channel id (replace me)
    channel_title,
    channel_handle,
    channel_url,
    source_group,      -- trusted/news | trusted/science | trusted/education |
                       -- trusted/mental_health | trusted/positivity |
                       -- trusted/productivity | trusted/lifestyle | trusted/culture
    trust_tier,        -- institutional | established_creator | candidate | experimental
    status,            -- 'approved' only after human review
    notes,
    approved_by,
    approved_at
) values
    ('UC_REPLACE_ME_NEWS', 'Example Trusted News Channel', '@example_news',
     'https://www.youtube.com/@example_news', 'trusted/news', 'institutional',
     'approved', 'PLACEHOLDER — replace channel_id before running', 'manual', now()),

    ('UC_REPLACE_ME_SCIENCE', 'Example Science Explainer', '@example_science',
     'https://www.youtube.com/@example_science', 'trusted/science', 'established_creator',
     'approved', 'PLACEHOLDER — replace channel_id before running', 'manual', now()),

    ('UC_REPLACE_ME_WELLNESS', 'Example Mental-Health Channel', '@example_wellness',
     'https://www.youtube.com/@example_wellness', 'trusted/mental_health', 'established_creator',
     'approved', 'PLACEHOLDER — replace channel_id before running', 'manual', now())
on conflict (channel_id) do nothing;

-- ----------------------------------------------------------------------------
-- Optional: queue a channel for later review instead of approving it now.
-- ----------------------------------------------------------------------------
-- insert into public.youtube_channel_candidates
--     (channel_id, channel_title, suggested_source_group, discovery_source,
--      why_suggested, review_status)
-- values
--     ('UC_REPLACE_ME_CANDIDATE', 'Example To Review', 'trusted/education',
--      'manual', 'Looks promising; needs a human pass', 'needs_review')
-- on conflict (channel_id) do nothing;

-- ----------------------------------------------------------------------------
-- Optional: hard-block a channel (never ingested or served, any lane).
-- ----------------------------------------------------------------------------
-- insert into public.blocked_youtube_channels
--     (channel_id, channel_title, reason, blocked_by)
-- values
--     ('UC_REPLACE_ME_BLOCKED', 'Example Blocked', 'ragebait', 'manual')
-- on conflict (channel_id) do nothing;
