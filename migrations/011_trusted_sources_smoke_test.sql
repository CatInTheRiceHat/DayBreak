-- ============================================================================
-- Smoke test for migration 011_trusted_sources.sql
--
-- HOW TO USE: run 011_trusted_sources.sql FIRST, then paste this whole file into
-- the Supabase SQL Editor and run it. Each check prints `PASS: ...` (look at the
-- "Notices" / messages output) or aborts with a clear error.
--
-- NON-DESTRUCTIVE: every test row is created inside a transaction that ROLLS
-- BACK at the end, so nothing persists. No real channel ids, no secrets.
-- Safe to run repeatedly.
-- ============================================================================

-- 1) The three tables exist ---------------------------------------------------
do $$
begin
    if to_regclass('public.trusted_youtube_channels')   is null then raise exception 'FAIL: trusted_youtube_channels missing'; end if;
    if to_regclass('public.blocked_youtube_channels')   is null then raise exception 'FAIL: blocked_youtube_channels missing'; end if;
    if to_regclass('public.youtube_channel_candidates') is null then raise exception 'FAIL: youtube_channel_candidates missing'; end if;
    raise notice 'PASS: all three trust tables exist';
end $$;

-- 2) RLS enabled on every table, and NO public policies (service-role only) ----
do $$
declare
    rls_count int;
    pol_count int;
begin
    select count(*) into rls_count
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname in ('trusted_youtube_channels','blocked_youtube_channels','youtube_channel_candidates')
      and c.relrowsecurity;
    if rls_count <> 3 then raise exception 'FAIL: RLS not enabled on all three tables (got %)', rls_count; end if;

    select count(*) into pol_count
    from pg_policies
    where schemaname = 'public'
      and tablename in ('trusted_youtube_channels','blocked_youtube_channels','youtube_channel_candidates');
    if pol_count <> 0 then raise exception 'FAIL: % public RLS policy(ies) present — these tables must be service-role only', pol_count; end if;

    raise notice 'PASS: RLS enabled on 3 tables with 0 public policies (anon/authenticated blocked)';
end $$;

-- 3) Functional checks, all inside a transaction we ROLL BACK -----------------
begin;

-- 3a) an approved trusted channel can be inserted
do $$
begin
    insert into public.trusted_youtube_channels
        (channel_id, channel_title, source_group, trust_tier, status, approved_by, approved_at)
    values ('UC_SMOKE_APPROVED', 'Smoke Approved', 'trusted/news', 'institutional', 'approved', 'smoke-test', now());
    raise notice 'PASS: approved trusted channel inserted';
exception when others then
    raise exception 'FAIL: could not insert approved trusted channel: %', sqlerrm;
end $$;

-- 3b) an invalid status is rejected by the CHECK constraint
do $$
begin
    begin
        insert into public.trusted_youtube_channels (channel_id, status)
        values ('UC_SMOKE_BADSTATUS', 'bogus_status');
        raise exception 'FAIL: invalid status was accepted (status CHECK constraint missing)';
    exception when check_violation then
        raise notice 'PASS: invalid status correctly rejected by CHECK';
    end;
end $$;

-- 3c) an invalid trust_tier is rejected too
do $$
begin
    begin
        insert into public.trusted_youtube_channels (channel_id, status, trust_tier)
        values ('UC_SMOKE_BADTIER', 'approved', 'not_a_tier');
        raise exception 'FAIL: invalid trust_tier was accepted (trust_tier CHECK missing)';
    exception when check_violation then
        raise notice 'PASS: invalid trust_tier correctly rejected by CHECK';
    end;
end $$;

-- 3d) a candidate channel can be queued
insert into public.youtube_channel_candidates
    (channel_id, channel_title, suggested_source_group, discovery_source, review_status)
values ('UC_SMOKE_CANDIDATE', 'Smoke Candidate', 'trusted/science', 'manual', 'new');

-- 3e) a blocked channel can be inserted
insert into public.blocked_youtube_channels (channel_id, channel_title, reason, blocked_by)
values ('UC_SMOKE_BLOCKED', 'Smoke Blocked', 'manual_block', 'smoke-test');

-- 3f) non-approved trusted rows, to prove the ingestion SELECT excludes them
insert into public.trusted_youtube_channels (channel_id, status) values
    ('UC_SMOKE_CAND_T',   'candidate'),
    ('UC_SMOKE_REJECTED', 'rejected'),
    ('UC_SMOKE_DISABLED', 'disabled');

-- 3g) the ingestion service path = SELECT ... WHERE status='approved'
--     (this is exactly what core/trust_registry.load_approved_trusted_channels does)
do $$
declare
    approved_cnt int;
    leaked_cnt   int;
begin
    select count(*) into approved_cnt
    from public.trusted_youtube_channels
    where status = 'approved' and channel_id like 'UC_SMOKE_%';
    if approved_cnt <> 1 then
        raise exception 'FAIL: expected exactly 1 approved smoke channel, got %', approved_cnt;
    end if;

    select count(*) into leaked_cnt
    from public.trusted_youtube_channels
    where status = 'approved'
      and channel_id in ('UC_SMOKE_CAND_T', 'UC_SMOKE_REJECTED', 'UC_SMOKE_DISABLED');
    if leaked_cnt <> 0 then
        raise exception 'FAIL: candidate/rejected/disabled leaked into approved selection';
    end if;

    raise notice 'PASS: ingestion SELECT returns only approved (candidate/rejected/disabled excluded)';
end $$;

-- 3h) candidate queue does NOT feed ingestion (separate table)
do $$
declare cand_cnt int;
begin
    select count(*) into cand_cnt from public.youtube_channel_candidates where channel_id = 'UC_SMOKE_CANDIDATE';
    if cand_cnt <> 1 then raise exception 'FAIL: candidate not stored in review queue'; end if;
    raise notice 'PASS: candidate stored in review queue only (never selected for ingestion)';
end $$;

rollback;  -- NON-DESTRUCTIVE: discard every smoke row created above

do $$ begin raise notice 'ALL SMOKE CHECKS PASSED — transaction rolled back, nothing persisted.'; end $$;
