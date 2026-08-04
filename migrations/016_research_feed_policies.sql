-- Migration 016 - Versioned research feed policies and issued-item provenance

create extension if not exists pgcrypto;

alter table public.research_sessions
    add column if not exists feed_policy_version text;

alter table public.research_sessions
    add column if not exists feed_seed text;

update public.research_sessions
set feed_policy_version = case feed_condition
    when 'regular' then 'regular-v1'
    when 'balanced' then 'balanced-v1'
end
where feed_policy_version is null;

update public.research_sessions
set feed_seed = encode(gen_random_bytes(24), 'hex')
where feed_seed is null;

alter table public.research_sessions
    alter column feed_policy_version set not null;

alter table public.research_sessions
    alter column feed_seed set not null;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'research_sessions_feed_policy_version_check'
    ) then
        alter table public.research_sessions
            add constraint research_sessions_feed_policy_version_check
            check (feed_policy_version in ('regular-v1', 'balanced-v1'));
    end if;
end $$;

create table if not exists public.research_feed_items (
    id                  uuid primary key default gen_random_uuid(),
    feed_request_id     uuid not null,
    session_id          uuid not null references public.research_sessions(id) on delete cascade,
    participant_id      uuid not null references public.research_participants(id) on delete cascade,
    post_id             text not null,
    feed_position       integer not null check (feed_position >= 0),
    content_category    text not null check (content_category in (
        'healthy', 'positive', 'regular', 'perspective', 'reduced', 'blocked', 'unknown'
    )),
    feed_policy_version text not null check (feed_policy_version in ('regular-v1', 'balanced-v1')),
    selection_bucket    text not null check (selection_bucket in ('normal', 'healthy', 'diversity')),
    selection_reason    text not null check (selection_reason in (
        'existing_chrysalis_rank',
        'normal_interest_target',
        'healthy_category_target',
        'perspective_variety_target',
        'inventory_fallback'
    )),
    created_at          timestamptz not null default now(),
    constraint research_feed_items_request_post_unique unique (feed_request_id, post_id),
    constraint research_feed_items_request_position_unique unique (feed_request_id, feed_position)
);

create index if not exists idx_research_feed_items_session_created
    on public.research_feed_items (session_id, created_at desc);

create index if not exists idx_research_feed_items_session_post
    on public.research_feed_items (session_id, post_id);

alter table public.research_feed_items enable row level security;
