-- Migration 017 - Intentional Break Loop storage foundation
--
-- Legacy research sessions retain the status, timestamps, event ordering, and
-- feed-request provenance established by migrations 015 and 016. The nullable
-- journey_version discriminator opts only new rows into the v1 journey model.

alter table public.research_sessions
    add column journey_version text,
    add column journey_state text,
    add column intention text,
    add column planned_video_count integer,
    add column estimated_duration_seconds integer,
    add column suggested_cooldown_seconds integer,
    add column selected_cooldown_seconds integer,
    add column plan_version text,
    add column plan_created_at timestamptz,
    add column session_started_at timestamptz,
    add column finish_reason text,
    add column highest_reached_position integer,
    add column boundary_reached_at timestamptz,
    add column checkout_entered_at timestamptz,
    add column cooldown_started_at timestamptz,
    add column cooldown_ends_at timestamptz,
    add column cooldown_outcome text,
    add column cooldown_completed_at timestamptz,
    add column override_started_at timestamptz,
    add column override_available_at timestamptz,
    add column override_reason text,
    add column previous_session_id uuid
        references public.research_sessions(id) on delete set null,
    add column cancelled_at timestamptz,
    add column next_server_sequence_number bigint,
    add column retain_until timestamptz;

alter table public.research_sessions
    add constraint research_sessions_journey_version_check
        check (journey_version is null or journey_version = 'intentional_break_v1'),
    add constraint research_sessions_journey_state_check
        check (
            journey_version is null or (
                journey_state is not null and journey_state in (
                    'planned', 'active', 'checkout', 'cooldown', 'completed', 'cancelled'
                )
            )
        ),
    add constraint research_sessions_intention_check
        check (
            journey_version is null or (
                intention is not null and intention in (
                    'relax', 'learn', 'inspired', 'catch_up', 'quick_break'
                )
            )
        ),
    add constraint research_sessions_planned_video_count_check
        check (
            journey_version is null or (
                planned_video_count is not null and planned_video_count in (5, 10, 20, 40)
            )
        ),
    add constraint research_sessions_estimated_duration_check
        check (
            journey_version is null or (
                estimated_duration_seconds is not null
                and estimated_duration_seconds = planned_video_count * 30
            )
        ),
    add constraint research_sessions_suggested_cooldown_check
        check (
            journey_version is null or (
                suggested_cooldown_seconds is not null
                and suggested_cooldown_seconds between 300 and 7200
                and suggested_cooldown_seconds % 300 = 0
                and suggested_cooldown_seconds = planned_video_count * 60
            )
        ),
    add constraint research_sessions_selected_cooldown_check
        check (
            selected_cooldown_seconds is null or (
                selected_cooldown_seconds between 300 and 7200
                and selected_cooldown_seconds % 300 = 0
            )
        ),
    add constraint research_sessions_plan_fields_check
        check (
            journey_version is null or (
                plan_version is not null and length(plan_version) > 0
                and plan_created_at is not null
                and feed_condition = 'balanced'
                and feed_policy_version = 'balanced-v1'
            )
        ),
    add constraint research_sessions_finish_reason_check
        check (finish_reason is null or finish_reason in ('boundary_reached', 'finished_early')),
    add constraint research_sessions_highest_position_check
        check (
            journey_version is null or (
                highest_reached_position is not null
                and highest_reached_position between 0 and planned_video_count
            )
        ),
    add constraint research_sessions_cooldown_outcome_check
        check (cooldown_outcome is null or cooldown_outcome in ('completed', 'overridden')),
    add constraint research_sessions_override_reason_check
        check (override_reason is null or override_reason in (
            'change_plan', 'opened_automatically', 'want_another_session', 'other'
        )),
    add constraint research_sessions_cooldown_time_order_check
        check (
            cooldown_started_at is null or cooldown_ends_at is null
            or cooldown_ends_at >= cooldown_started_at
        ),
    add constraint research_sessions_override_time_order_check
        check (
            override_started_at is null or override_available_at is null
            or override_available_at >= override_started_at
        ),
    add constraint research_sessions_next_server_sequence_check
        check (next_server_sequence_number >= 0),
    add constraint research_sessions_id_participant_unique
        unique (id, participant_id);

create unique index idx_research_sessions_one_nonterminal_intentional_break
    on public.research_sessions (participant_id)
    where journey_version = 'intentional_break_v1'
      and journey_state in ('planned', 'active', 'checkout', 'cooldown');

create index idx_research_sessions_previous_session
    on public.research_sessions (previous_session_id)
    where previous_session_id is not null;

create table public.research_session_items (
    id                    uuid primary key default gen_random_uuid(),
    session_id            uuid not null,
    participant_id        uuid not null references public.research_participants(id) on delete cascade,
    post_id               text not null,
    session_position      integer not null check (session_position >= 1),
    content_category      text not null check (content_category in (
        'healthy', 'positive', 'regular', 'perspective', 'reduced', 'blocked', 'unknown'
    )),
    feed_policy_version   text not null check (feed_policy_version = 'balanced-v1'),
    selection_bucket      text not null check (selection_bucket in ('normal', 'healthy', 'diversity')),
    selection_reason      text not null check (selection_reason in (
        'existing_chrysalis_rank',
        'normal_interest_target',
        'healthy_category_target',
        'perspective_variety_target',
        'inventory_fallback'
    )),
    ranking_snapshot      jsonb not null default '{}'::jsonb,
    provenance_metadata   jsonb not null default '{}'::jsonb,
    reserved_at           timestamptz not null default now(),
    first_issued_at       timestamptz,
    first_impressed_at    timestamptz,
    first_viewed_at       timestamptz,
    constraint research_session_items_session_owner_fk
        foreign key (session_id, participant_id)
        references public.research_sessions(id, participant_id) on delete cascade,
    constraint research_session_items_position_unique unique (session_id, session_position),
    constraint research_session_items_post_unique unique (session_id, post_id)
);

create index idx_research_session_items_participant_session
    on public.research_session_items (participant_id, session_id);

create table public.research_session_checkouts (
    session_id                  uuid primary key,
    participant_id              uuid not null references public.research_participants(id) on delete cascade,
    worthwhile_answer           text not null check (worthwhile_answer in (
        'yes', 'mostly', 'not_really', 'prefer_not_to_answer'
    )),
    perceived_control_answer    jsonb not null check (
        perceived_control_answer in ('1'::jsonb, '2'::jsonb, '3'::jsonb, '4'::jsonb, '5'::jsonb)
        or perceived_control_answer = '"prefer_not_to_answer"'::jsonb
    ),
    mood_answer                 text not null check (mood_answer in (
        'better', 'same', 'worse', 'prefer_not_to_answer'
    )),
    checkout_version            text not null check (length(checkout_version) > 0),
    submitted_at                timestamptz not null default now(),
    constraint research_session_checkouts_session_owner_fk
        foreign key (session_id, participant_id)
        references public.research_sessions(id, participant_id) on delete cascade
);

-- sequence_number remains the required legacy compatibility sequence. Future
-- Intentional Break writers can mirror server_sequence_number into it while
-- keeping client_sequence_number diagnostic-only.
alter table public.research_events
    add column server_sequence_number bigint,
    add column client_event_id uuid,
    add column client_sequence_number bigint,
    add column received_at timestamptz,
    add column event_authority text;

update public.research_events
set server_sequence_number = sequence_number,
    received_at = server_timestamp
where server_sequence_number is null or received_at is null;

alter table public.research_events
    alter column received_at set default now(),
    alter column received_at set not null,
    alter column client_timestamp drop not null,
    add constraint research_events_server_sequence_check
        check (server_sequence_number is null or server_sequence_number >= 0),
    add constraint research_events_client_sequence_check
        check (client_sequence_number is null or client_sequence_number >= 0),
    add constraint research_events_authority_check
        check (event_authority is null or event_authority in ('server', 'client'));

alter table public.research_events
    drop constraint research_events_event_type_check;

alter table public.research_events
    add constraint research_events_event_type_check check (event_type in (
        'session_plan_created',
        'session_started',
        'session_finished_early',
        'session_boundary_reached',
        'checkout_submitted',
        'cooldown_started',
        'cooldown_completed',
        'cooldown_override_started',
        'cooldown_overridden',
        'session_cancelled',
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
    ));

create unique index idx_research_events_canonical_session_sequence
    on public.research_events (session_id, server_sequence_number)
    where server_sequence_number is not null;

create unique index idx_research_events_client_event_id
    on public.research_events (client_event_id)
    where client_event_id is not null;

create unique index idx_research_events_server_lifecycle_once
    on public.research_events (session_id, event_type)
    where event_authority = 'server'
      and event_type in (
          'session_plan_created',
          'session_started',
          'session_finished_early',
          'session_boundary_reached',
          'checkout_submitted',
          'cooldown_started',
          'cooldown_completed',
          'cooldown_override_started',
          'cooldown_overridden',
          'session_cancelled'
      );

create unique index idx_research_events_server_finish_once
    on public.research_events (session_id, (case
        when event_type in ('session_finished_early', 'session_boundary_reached') then 1
    end))
    where event_authority = 'server'
      and event_type in ('session_finished_early', 'session_boundary_reached');

create unique index idx_research_events_server_cooldown_outcome_once
    on public.research_events (session_id, (case
        when event_type in ('cooldown_completed', 'cooldown_overridden') then 1
    end))
    where event_authority = 'server'
      and event_type in ('cooldown_completed', 'cooldown_overridden');

update public.research_sessions as session
set next_server_sequence_number = coalesce((
    select max(event.server_sequence_number) + 1
    from public.research_events as event
    where event.session_id = session.id
), 0);

alter table public.research_sessions
    alter column next_server_sequence_number set default 0,
    alter column next_server_sequence_number set not null;

alter table public.research_session_items enable row level security;
alter table public.research_session_checkouts enable row level security;

-- No browser policies or grants are added. The backend-only access model from
-- migrations 015 and 016 therefore applies to both new tables.
