-- Migration 015 - Anonymous research participants, sessions, and events
--
-- This schema intentionally contains no names, email addresses, account ids,
-- IP addresses, precise location, device fingerprints, or free-response text.
-- Participant bearer tokens are returned once and stored only as SHA-256 hashes.

create extension if not exists pgcrypto;

create table if not exists public.research_participants (
    id                uuid primary key default gen_random_uuid(),
    access_token_hash text not null unique,
    assigned_condition text not null
        check (assigned_condition in ('regular', 'balanced')),
    status            text not null default 'active'
        check (status in ('active', 'withdrawn', 'deletion_requested')),
    created_at        timestamptz not null default now(),
    withdrawn_at      timestamptz,
    deletion_requested_at timestamptz
);

create table if not exists public.research_sessions (
    id                uuid primary key default gen_random_uuid(),
    participant_id    uuid not null references public.research_participants(id) on delete cascade,
    feed_condition    text not null
        check (feed_condition in ('regular', 'balanced')),
    application_version text not null,
    status            text not null default 'active'
        check (status in ('active', 'completed', 'withdrawn', 'deletion_requested')),
    started_at        timestamptz not null default now(),
    completed_at      timestamptz,
    withdrawn_at      timestamptz,
    deletion_requested_at timestamptz,
    created_at        timestamptz not null default now()
);

create table if not exists public.research_events (
    id                uuid primary key,
    session_id        uuid not null references public.research_sessions(id) on delete cascade,
    participant_id    uuid not null references public.research_participants(id) on delete cascade,
    sequence_number   bigint not null check (sequence_number >= 0),
    event_type        text not null check (event_type in (
        'session_started',
        'post_impression',
        'post_viewed',
        'post_liked',
        'post_unliked',
        'post_skipped',
        'post_reported',
        'break_prompt_shown',
        'break_prompt_accepted',
        'break_prompt_dismissed',
        'session_completed'
    )),
    post_id           text,
    content_category  text check (
        content_category is null or content_category in
        ('healthy', 'positive', 'regular', 'perspective', 'reduced', 'blocked', 'unknown')
    ),
    feed_condition    text not null check (feed_condition in ('regular', 'balanced')),
    client_timestamp  timestamptz not null,
    server_timestamp  timestamptz not null default now(),
    metadata          jsonb not null default '{}'::jsonb,
    constraint research_events_post_fields check (
        event_type not like 'post_%' or post_id is not null
    ),
    constraint research_events_session_sequence_unique unique (session_id, sequence_number)
);

create index if not exists idx_research_sessions_participant_started
    on public.research_sessions (participant_id, started_at desc);

create index if not exists idx_research_sessions_condition_status
    on public.research_sessions (feed_condition, status);

create index if not exists idx_research_events_session_sequence
    on public.research_events (session_id, sequence_number);

create index if not exists idx_research_events_type_server_time
    on public.research_events (event_type, server_timestamp);

create index if not exists idx_research_events_post
    on public.research_events (post_id)
    where post_id is not null;

-- Research data is written by the FastAPI backend's database role. Browser
-- Supabase clients receive no direct policies, so the anon/authenticated roles
-- cannot enumerate or mutate research records through PostgREST.
alter table public.research_participants enable row level security;
alter table public.research_sessions enable row level security;
alter table public.research_events enable row level security;

