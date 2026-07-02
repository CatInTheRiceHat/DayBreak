-- Migration 011 - Trust-source registry for YouTube feed ingestion
--
-- A human-curated source-quality layer for the feed (Parts A/B/C). Three tables
-- back a single workflow that AI is NOT allowed to short-circuit:
--
--     discovered channel → candidate queue → human review
--                        → approved / rejected → ingestion uses ONLY approved
--
--   * trusted_youtube_channels   — approved/candidate/rejected/... channels.
--                                  Only status='approved' rows feed the trusted
--                                  ingestion lane.
--   * blocked_youtube_channels   — hard denylist; never ingested or served.
--   * youtube_channel_candidates — review queue ONLY; never feeds ingestion.
--
-- SECURITY: these are operator/curation tables, not user-facing. RLS is enabled
-- with NO public policy, so anon/authenticated clients cannot read or write them;
-- only the Supabase service role (used by the ingestion cron) bypasses RLS. No
-- secrets, credentials, or personal data live here — only public channel metadata
-- and human review notes.
--
-- Idempotent: safe to run repeatedly. Mirrors the sqlite schema created at
-- runtime by core/trust_registry.ensure_trust_tables_sqlite().

-- ---------------------------------------------------------------------------
-- A) trusted_youtube_channels — approved sources for the trusted lane
-- ---------------------------------------------------------------------------
create table if not exists public.trusted_youtube_channels (
    id              bigserial primary key,
    channel_id      text        not null unique,
    channel_title   text,
    channel_handle  text,
    channel_url     text,
    source_group    text,       -- trusted/news, trusted/science, trusted/education,
                                --  trusted/mental_health, trusted/positivity,
                                --  trusted/productivity, trusted/lifestyle, trusted/culture
    trust_tier      text,       -- institutional | established_creator | candidate | experimental
    status          text        not null default 'candidate',
                                --  candidate | approved | rejected | needs_review | disabled
    notes           text,
    risk_notes      text,
    approved_by     text,       -- who approved (human reviewer); never auto-set by AI
    approved_at     timestamptz,
    last_checked_at timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    constraint trusted_status_chk check (
        status in ('candidate', 'approved', 'rejected', 'needs_review', 'disabled')
    ),
    -- trust_tier is a closed enum the reputation scorer relies on (nullable).
    constraint trusted_trust_tier_chk check (
        trust_tier is null
        or trust_tier in ('institutional', 'established_creator', 'candidate', 'experimental')
    )
);

create index if not exists idx_trusted_channels_status
    on public.trusted_youtube_channels (status);
create index if not exists idx_trusted_channels_source_group
    on public.trusted_youtube_channels (source_group);

-- ---------------------------------------------------------------------------
-- B) blocked_youtube_channels — hard denylist
-- ---------------------------------------------------------------------------
create table if not exists public.blocked_youtube_channels (
    id            bigserial primary key,
    channel_id    text        not null unique,
    channel_title text,
    reason        text,        -- foreign_language_leak | ragebait | misinformation |
                               --  gossip_drama | explicit_or_unsafe | spam_or_repost |
                               --  low_quality | manual_block
    blocked_by    text,        -- who blocked it (human)
    blocked_at    timestamptz  not null default now(),
    created_at    timestamptz  not null default now(),
    updated_at    timestamptz  not null default now()
);

create index if not exists idx_blocked_channels_channel
    on public.blocked_youtube_channels (channel_id);

-- ---------------------------------------------------------------------------
-- C) youtube_channel_candidates — review queue ONLY (never feeds ingestion)
-- ---------------------------------------------------------------------------
create table if not exists public.youtube_channel_candidates (
    id                     bigserial primary key,
    channel_id             text        not null unique,
    channel_title          text,
    channel_handle         text,
    channel_url            text,
    suggested_source_group text,
    discovery_source       text,       -- how it was discovered (search_lane, popular_lane, manual, ...)
    why_suggested          text,
    possible_risks         text,
    sample_video_titles    text,       -- newline/JSON sample for the reviewer
    subscriber_count       bigint,
    recent_upload_count    integer,
    language_notes         text,
    recommended_status     text,       -- a *suggestion* for the human, not a decision
    review_status          text        not null default 'new',
                                       --  new | needs_review | approved | rejected | stale
    review_notes           text,
    checked_at             timestamptz,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now(),

    constraint candidate_review_status_chk check (
        review_status in ('new', 'needs_review', 'approved', 'rejected', 'stale')
    )
);

create index if not exists idx_channel_candidates_review
    on public.youtube_channel_candidates (review_status);

-- ---------------------------------------------------------------------------
-- updated_at auto-touch. Keeps updated_at honest on UPDATE without relying on
-- the writer to set it. Idempotent (create-or-replace fn + drop-if-exists trigger).
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_trusted_set_updated_at on public.trusted_youtube_channels;
create trigger trg_trusted_set_updated_at
    before update on public.trusted_youtube_channels
    for each row execute function public.set_updated_at();

drop trigger if exists trg_blocked_set_updated_at on public.blocked_youtube_channels;
create trigger trg_blocked_set_updated_at
    before update on public.blocked_youtube_channels
    for each row execute function public.set_updated_at();

drop trigger if exists trg_candidates_set_updated_at on public.youtube_channel_candidates;
create trigger trg_candidates_set_updated_at
    before update on public.youtube_channel_candidates
    for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Lock down: operator-only tables. RLS on, no public policy → service role only.
-- (Anon/authenticated clients get zero rows; the ingestion service role, which
--  bypasses RLS, is the only reader/writer.)
-- ---------------------------------------------------------------------------
alter table public.trusted_youtube_channels   enable row level security;
alter table public.blocked_youtube_channels   enable row level security;
alter table public.youtube_channel_candidates enable row level security;
