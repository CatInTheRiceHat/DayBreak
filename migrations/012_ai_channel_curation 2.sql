-- Migration 012 - AI-assisted channel curation fields
--
-- Extends the EXISTING trust tables (011) so AI can insert labeled, reviewable
-- rows that a human later removes/disables. No new table — the curation columns
-- live on trusted_youtube_channels and blocked_youtube_channels.
--
-- Workflow: AI inserts rows (added_by='ai', review_status='unreviewed'); a human
-- edits/disables exceptions in Supabase. AI never overwrites a human's review or
-- a human-disabled (active=false) row (enforced in core/trust_registry.py).
--
-- A trusted/whitelisted row is NEVER a safety bypass: ingestion still runs every
-- video through the English-only, blocked-language, blocked-term, and integrity
-- gates. `active` only gates *eligibility*, not the safety checks.
--
-- Idempotent and non-destructive: only ADD COLUMN IF NOT EXISTS + guarded
-- CHECK/index additions. Safe to run repeatedly. Run AFTER 011.

-- ── Curation columns on BOTH trust tables ───────────────────────────────────
do $$
declare
    tbl text;
begin
    foreach tbl in array array['trusted_youtube_channels', 'blocked_youtube_channels']
    loop
        execute format('alter table public.%I add column if not exists platform text default ''youtube''', tbl);
        execute format('alter table public.%I add column if not exists trust_status text', tbl);
        execute format('alter table public.%I add column if not exists added_by text default ''human''', tbl);
        execute format('alter table public.%I add column if not exists ai_confidence numeric', tbl);
        execute format('alter table public.%I add column if not exists ai_reason text', tbl);
        execute format('alter table public.%I add column if not exists active boolean not null default true', tbl);
        execute format('alter table public.%I add column if not exists review_status text default ''unreviewed''', tbl);
        execute format('alter table public.%I add column if not exists reviewed_by text', tbl);
        execute format('alter table public.%I add column if not exists reviewed_at timestamptz', tbl);
        execute format('alter table public.%I add column if not exists review_notes text', tbl);
    end loop;
end $$;

-- ── Constraints: trust_status vocabulary + confidence range (guarded) ────────
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'trusted_trust_status_chk') then
        alter table public.trusted_youtube_channels add constraint trusted_trust_status_chk
            check (trust_status is null or trust_status in ('trusted','blocked','pending','rejected'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'trusted_ai_confidence_chk') then
        alter table public.trusted_youtube_channels add constraint trusted_ai_confidence_chk
            check (ai_confidence is null or (ai_confidence >= 0 and ai_confidence <= 1));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'blocked_trust_status_chk') then
        alter table public.blocked_youtube_channels add constraint blocked_trust_status_chk
            check (trust_status is null or trust_status in ('trusted','blocked','pending','rejected'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'blocked_ai_confidence_chk') then
        alter table public.blocked_youtube_channels add constraint blocked_ai_confidence_chk
            check (ai_confidence is null or (ai_confidence >= 0 and ai_confidence <= 1));
    end if;
end $$;

-- ── Indexes for the active-gated ingestion queries ──────────────────────────
create index if not exists idx_trusted_channels_status_active
    on public.trusted_youtube_channels (status, active);
create index if not exists idx_blocked_channels_active
    on public.blocked_youtube_channels (active);

-- updated_at auto-touch trigger + RLS are inherited from migration 011.
