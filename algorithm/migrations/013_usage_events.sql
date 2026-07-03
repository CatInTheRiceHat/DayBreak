-- Migration 013 - Usage events (per-user behavioral logging for the pilot)
--
-- Append-only event log so we can measure whether users voluntarily return to the
-- feed over the pilot week. The primary metric is `session_start`: one row each
-- time a signed-in user opens the feed, giving distinct sessions, timestamps, and
-- return visits per user.
--
-- SECURITY / PRIVACY NOTES:
--   * user_id references auth.users so every event is scoped to a real account.
--   * Row Level Security is enabled with an INSERT-only policy pinned to
--     auth.uid() = user_id, so a user can only write their own events and cannot
--     forge or read other users' rows. Analysis is done with the service role.

create table public.usage_events (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id),
  event_type text not null,
  payload jsonb default '{}',
  created_at timestamptz not null default now()
);

alter table public.usage_events enable row level security;

create policy "insert own events" on public.usage_events
  for insert with check (auth.uid() = user_id);
