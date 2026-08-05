# DayBreak automation boundary

> Historical inventory captured before the August 2026 repository cleanup.
> Paths and duplicate-file counts below describe that earlier snapshot.

This package is an organizational boundary, not a new runtime. Phase 1 adds no
scheduler, worker, queue, startup hook, route, database operation, or network
call. Reusable ranking, recommendation, labeling, moderation, trust-registry,
research-policy, and persistence logic remains in `core/` and `integrations/`.

## Current deployment and import paths

- `vercel.json` rewrites every `/api/:path*` request to `api/index.py`. That file
  is the production FastAPI entry point and directly imports
  `integrations.youtube_ingest.ingest_youtube_videos_postgres`.
- Local development runs `api.py`, whose `/api/admin/ingest/youtube` handler
  directly imports `integrations.youtube_ingest.ingest_youtube_videos_sqlite`.
- `.github/workflows/youtube-feed-ingest.yml` invokes the deployed
  `/api/admin/ingest/youtube` URL. It does not import Python code or check out the
  repository.
- `scripts/ingest_youtube_feed.py` remains the manual SQLite command and imports
  `integrations.youtube_ingest.ingest_youtube_videos_sqlite`.
- The browser build enters through `website/src/main.jsx`, which imports
  `website/src/App.jsx`; Vite and npm use `website/vite.config.js` and
  `website/package.json` by their canonical names.
- PostgreSQL automation is installed by the SQL in `migrations/`; no Supabase
  Edge Function or repository migration runner was found.
- No existing production entry point imports `automation`. This is deliberate
  for Phase 1.

## Confirmed production automation inventory

"Active" below means the implementation is on an active application path. A
hosted scheduler or database migration is marked unclear when repository evidence
cannot prove that it is enabled in the deployment.

| Process | Current entry point | Trigger / scheduler | Runtime | Required environment | Status | Reusable logic called | Known concerns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Scheduled YouTube feed ingestion | `.github/workflows/youtube-feed-ingest.yml` -> `POST /api/admin/ingest/youtube` in `api/index.py:admin_ingest_youtube` | GitHub Actions cron `7 0,6,12,18 * * *` (00:07, 06:07, 12:07, 18:07 UTC) and `workflow_dispatch` | GitHub-hosted runner calling the Vercel FastAPI deployment and Supabase/Postgres | Workflow: `CHRYSALIS_API_BASE_URL`, `FEED_INGEST_SECRET`; API: `DATABASE_URL`, `YOUTUBE_API_KEY`, `FEED_INGEST_SECRET`; optional `YOUTUBE_FEED_QUERIES`, `MAX_TRUSTED_CHANNELS_PER_RUN` | Active configuration; actual repository/action enablement cannot be proven locally | `integrations.youtube_ingest.ingest_youtube_videos_postgres`, plus existing `core` labeling, integrity, language, ranking, trust, and reputation services | No workflow concurrency guard, retry/backoff, or curl timeout; no job-level lock; API query-string secret remains accepted; YouTube calls have timeout but no retry; zero-candidate runs can report success. README currently says once daily although workflow is four times daily. |
| API-triggered YouTube ingestion (production) | `api/index.py:admin_ingest_youtube` | Authenticated API request; currently called by the GitHub workflow and may be called manually | Vercel Python function + Supabase/Postgres | `DATABASE_URL`, `YOUTUBE_API_KEY`, `FEED_INGEST_SECRET`; optional ingestion overrides above | Active production endpoint | `integrations.youtube_ingest.ingest_youtube_videos_postgres` | Request query parameters can increase work within integration clamps; no lock or job run ID; same secret may be supplied as `?secret=`, which can leak through URL logs. Row upserts are idempotent by `youtube_video_id`, but whole-job execution is not locked. |
| API-triggered YouTube ingestion (local) | `api.py:admin_ingest_youtube` | Authenticated API request | Main local FastAPI process + SQLite | `YOUTUBE_API_KEY`, `FEED_INGEST_SECRET`; optional `DATABASE_PATH`, `YOUTUBE_FEED_QUERIES`, `MAX_TRUSTED_CHANNELS_PER_RUN` | Development/local production analogue | `integrations.youtube_ingest.ingest_youtube_videos_sqlite` | Same query-string-secret and no-lock concerns; it is not the Vercel deployment entry point. |
| Stale Migration Mode drop schedules | `vercel.json` entries for `/api/cron/drop?mode=morning` and `?mode=evening` | Vercel cron at 07:00 and 19:00 | Vercel rewrite to `api/index.py` | None can make the missing route work; historical handler optionally checked `CRON_SECRET` and used `DATABASE_URL` | Possibly inactive / obsolete: scheduler entries exist, route does not | Historical `_run_drop` used `core.algorithm.build_prototype_feed`; `_write_drop` wrote `migration_drops` | Requests currently resolve to no matching FastAPI route. The handler and its table were intentionally removed in commit `d92a956`; leaving schedules creates failed/no-op cron traffic and misleading deployment state. |
| Unscheduled YouTube cron endpoint | `api/index.py:cron_extract` at `GET /api/cron/extract` | API request; no repository scheduler references it | Vercel Python function + Supabase/Postgres | `DATABASE_URL`, `YOUTUBE_API_KEY`; `CRON_SECRET` is optional in current code; optional ingestion overrides | Implemented but scheduler status unclear / possibly inactive | `integrations.youtube_ingest.ingest_youtube_videos_postgres` | Authentication fails open when `CRON_SECRET` is blank. It overlaps the GitHub job's ingestion service, has different default results/query (15 versus 10), and has no lock/retry. |
| Optional public-signal refresh during feed reads | `api/index.py:_load_research_feed_source` and `chrysalis_feed`; SQLite equivalents in `api.py` | API feed/research-feed request when `CHRYSALIS_REFRESH_PUBLIC_SIGNALS_ON_FEED` is truthy | Vercel/Postgres or local FastAPI/SQLite | `CHRYSALIS_REFRESH_PUBLIC_SIGNALS_ON_FEED`; normal database configuration | Conditional; production flag state unclear | `core.public_signals.storage.load_or_scan_context_postgres` / `load_or_scan_context_sqlite` | A GET can perform writes; no separate schedule, retry, or expired-record cleanup. The current provider is a deterministic no-network stub. |
| Live-topic YouTube cache refresh | `integrations/youtube_service.py:fetch_videos_by_topic`, exposed by both API entry points | API request after a cache miss or four-hour TTL expiry | FastAPI process / Vercel instance memory | `YOUTUBE_API_KEY` | Active request-time automation | `core.preferences` locale normalization and YouTube Data API adapter in the same module | Cache is process-local and disappears on cold start; instances do not share state; failures fall back silently and have no retry. This is not the scheduled ingestion job. |
| Research event batching and recovery | `website/src/lib/researchEvents.js:createResearchEventService`, started by `ResearchPage` | User events; batches of 100; exponential timers from 1s to 30s; retry on browser `online` and `visibilitychange` | Participant browser -> research routes in `research_api.py` -> Vercel/Postgres or local FastAPI/SQLite | Browser: `VITE_API_URL`, optional `VITE_APP_VERSION`; API: normal database configuration | Active on `/study` | `research_api.create_research_router`; `core.research_storage.insert_event_batch`, session and provenance functions; `core.ranking.research_policies` for the research feed | LocalStorage queue has no size/age cap; all failures retry alike, so a permanent 4xx can poison the queue; completion blocks while events remain; some caller errors are swallowed. Event UUID and `(session_id, sequence_number)` constraints provide server idempotency. |
| Meaningful research exposure timers | `website/src/components/research/useMeaningfulPostVisibility.js:useMeaningfulPostVisibility` and `meaningfulVisibility.js:createMeaningfulVisibilityTracker` | IntersectionObserver and browser timers at >=60% visibility (impression at 1s, viewed at 3s) | Participant browser | Same research browser/API configuration | Active on research cards | `researchEvents.track` and research provenance helpers | Depends on an open, visible browser tab; tracking promise failures are swallowed by `.catch(() => {})`. |
| Progressive break prompts | `website/src/components/reels/useSessionTimer.js:useSessionTimer`, `sessionBreaks.js`, and `BreakScreen.jsx` | One-second browser interval while the feed is active/visible; thresholds 60/90/120/150+ minutes | Browser | None; optional `?breaks=demo` changes the time scale in the client | Active client-side automation | Pure timing rules in `sessionBreaks.js`; research sessions send break events through `researchEvents` | Browser/in-memory timing resets with component lifecycle; ordinary completions are localStorage-only (last 50); it is a nudge, not a server-enforced timer. |
| Automatic feed pagination | `website/src/components/reels/ReelsPage.jsx:loadPage` and its bottom-sentinel effect | IntersectionObserver as the user approaches the end of the feed | Browser -> FastAPI feed/research-feed endpoints | `VITE_API_URL`; normal API database configuration | Active client-side automation | Backend `core.ranking.feed` or `core.ranking.research_policies`; client dedupe and interest ranking | Later-page failures wait for another intersection/scroll rather than using a timed retry; browser activity is required. |
| Pilot usage-event writes | `website/src/lib/events.js:logEvent`, called from `ReelsPage` | Fire-and-forget application events, including `session_start` on feed mount | Browser -> Supabase `usage_events` | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | Active when Supabase and a user ID are present | Supabase client; schema/RLS in `migrations/013_usage_events.sql` | Failures are intentionally swallowed; no retry, event ID, deduplication, batching, or retention job. |
| Deferred diagnostic persistence | `website/src/components/FirstRunGate.jsx:FirstRunGate` -> `website/src/lib/diagnostics.js:saveDiagnostic` | On sign-in or a later visit when pending localStorage data exists | Browser -> Supabase | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | Active when the diagnostics table exists; deployment state unclear because no matching migration is present | Supabase diagnostics adapter | Retry is visit-driven, not timed; a committed response lost in transit can cause an append-only duplicate; errors are not surfaced to the user. |
| Comment safety and cooldown | `website/src/components/reels/CommentsPanel.jsx:handleSend` -> `commentSafety.js:analyzeComment` | User submission plus a one-second browser interval for the five-second caution cooldown | Browser only | None | Active demo/client automation | Pure heuristic `analyzeComment` | No backend moderation, persistence, audit log, or centralized policy; closing/reloading the component resets in-memory state. |
| Database `updated_at` maintenance | `migrations/009_user_content_preferences.sql:set_updated_at`; `migrations/010_profiles.sql:public.set_updated_at`; `migrations/011_trusted_sources.sql:public.set_updated_at` | PostgreSQL `BEFORE UPDATE` triggers `trg_ucp_updated_at`, `trg_profiles_updated_at`, `trg_trusted_set_updated_at`, `trg_blocked_set_updated_at`, and `trg_candidates_set_updated_at` | Supabase/Postgres | None beyond migration/database administration | Active if migrations were applied; deployed migration state unclear | Database-local timestamp function | Three migrations redefine the shared function. Migration 014 later drops `youtube_channel_candidates`, so the candidate trigger disappears if migrations are applied numerically. |
| Auth profile creation | `migrations/010_profiles.sql:public.handle_new_user`, trigger `trg_on_auth_user_created` | PostgreSQL `AFTER INSERT` on `auth.users` | Supabase/Postgres | Supabase Auth/database configuration | Active if migration 010 was applied; deployed migration state unclear | Database-local profile insert and username collision retry loop | Security-definer function is sensitive to migration correctness; it retries username collisions and is idempotent by profile ID, but repository state cannot prove the trigger is installed. |

Manual ingestion, data processing, scoring, experiment, graphing, seeding,
curation, cleanup, and QA scripts are intentionally not represented above as
recurring production jobs. Their paths and behavior remain unchanged.

## Phase 1 configuration boundary

`automation/config.py` records only automation-facing names and current ingestion
limits:

- scheduler/invocation names: `FEED_INGEST_SECRET`, `CRON_SECRET`, and
  `CHRYSALIS_API_BASE_URL`;
- ingestion-specific names: `YOUTUBE_API_KEY`, `YOUTUBE_FEED_QUERIES`, and
  `MAX_TRUSTED_CHANNELS_PER_RUN`;
- current handler defaults: 10 results/query for the admin endpoint, 15 for
  `cron_extract`, and a seven-day window;
- integration clamps: 1-25 results/query and 2-7 days;
- current YouTube ingestion request timeout: 12 seconds;
- current trusted-channel default: two channels per run.

The two-channel value follows `integrations/youtube_ingest.py`; the operational
guide in `docs/trust_sources_operations.md` still says five and should be
corrected separately. `DATABASE_URL` remains general database configuration, and
`POPULAR_MIN_SCORE` remains recommendation/filter policy in
`core/ranking/modes.py`; neither belongs in automation configuration.

`load_scheduler_auth` reads secrets only from an explicitly supplied mapping or
the process environment, supplies no fallback secret, and hides values from its
representation. `missing_automation_environment` performs a non-mutating
presence check. Database credentials are deliberately not centralized here.
These definitions are not yet imported by production code, so existing behavior
and defaults remain authoritative until a characterized Phase 2 migration.

## Cron route mismatch investigation

Repository-wide current-tree searches find `/api/cron/drop` only in
`vercel.json` and historical/design documentation. Git history provides the
decisive evidence:

1. Before commit `d92a956`, `api/index.py` contained both `cron_drop` and
   `cron_extract` at the same time. This rules out a rename.
2. `cron_drop` generated morning/evening Migration Mode feeds with `_run_drop`
   and stored them through `_write_drop` in `migration_drops`.
3. `cron_extract` independently called
   `ingest_youtube_videos_postgres` to populate `feed_videos` from YouTube.
4. Commit `d92a956` intentionally removed `cron_drop`, `_run_drop`,
   `_write_drop`, and the Migration Mode read API. Its
   `migrations/014_drop_dead_tables.sql` describes the writer as never having
   run in production and drops `migration_drops`.
5. The same cleanup did not remove the two `/api/cron/drop` entries from
   `vercel.json`. They are stale configuration, not aliases for `cron_extract`.

Conclusion: `/api/cron/drop` is obsolete. `/api/cron/extract` is a separate,
implemented YouTube ingestion trigger and is not proven to be scheduled. It
overlaps exactly with the GitHub workflow at the reusable ingestion layer. The
recommended correction is to remove the stale Vercel drop schedules after
confirming the Vercel dashboard uses this file, and to choose one canonical
YouTube scheduler. Do not simply change `drop` to `extract`: doing so would add
07:00 and 19:00 ingestion calls to the four GitHub calls per day. Upserts reduce
duplicate rows, but simultaneous or repeated jobs would still consume YouTube
quota and face job-level race/locking gaps. No correction is made in Phase 1.

## Files whose names contain `" 2"`

The repository tracks 43 paths containing the literal substring `" 2"`. Forty
use it as a duplicate suffix; three archived screenshots contain a year beginning
with `2` and are not duplicate-suffix candidates. Comparisons below use current
worktree bytes; where a user-modified canonical CSS file changes the comparison,
the committed-state result is noted without modifying either file.

| Path | Compared with | Classification | Evidence / activity assessment |
| --- | --- | --- | --- |
| `core/labeling/taxonomy 2.py` | `core/labeling/taxonomy.py` | Byte-for-byte identical | Canonical module is imported; the space-suffixed name is not a valid normal dotted import. |
| `core/public_signals/__init__ 2.py` | `core/public_signals/__init__.py` | Byte-for-byte identical | Only canonical `__init__.py` initializes the package. |
| `migrations/001_video_labels 2.sql` | `migrations/001_video_labels.sql` | Byte-for-byte identical | No repository migration runner was found, but a wildcard migration command would include both. |
| `migrations/002_public_signals 2.sql` | `migrations/002_public_signals.sql` | Byte-for-byte identical | Same wildcard and migration-identity risk. |
| `migrations/006_feed_video_short_description 2.sql` | `migrations/006_feed_video_short_description.sql` | Byte-for-byte identical | Same wildcard and migration-identity risk. |
| `migrations/007_feed_video_integrity_metadata 2.sql` | `migrations/007_feed_video_integrity_metadata.sql` | Byte-for-byte identical | Same wildcard and migration-identity risk. |
| `migrations/008_feed_video_display_metadata 2.sql` | `migrations/008_feed_video_display_metadata.sql` | Byte-for-byte identical | Same wildcard and migration-identity risk. |
| `migrations/012_ai_channel_curation 2.sql` | `migrations/012_ai_channel_curation.sql` | Byte-for-byte identical | Same wildcard and migration-identity risk. |
| `migrations/seed_trusted_youtube_channels.example 2.sql` | `migrations/seed_trusted_youtube_channels.example.sql` | Byte-for-byte identical | Example/manual seed, not a numbered production migration. |
| `screenshots/reels-compass-mobile-375-light-open 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `screenshots/reels-feed-desktop-wide-1440-light 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `screenshots/reels-feed-laptop-1280-dark 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `screenshots/reels-feed-laptop-1280-light 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `screenshots/reels-feed-mobile-375-dark 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `screenshots/reels-feed-mobile-375-light 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `screenshots/reels-feed-tablet-768-light 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `screenshots/reels-live-youtube-embed-desktop-1440-light 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `screenshots/reels-onboarding-desktop-1280-light 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `screenshots/reels-onboarding-mobile-375-light 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `screenshots/reels-why-mobile-375-light-open 2.png` | suffix-free PNG | Byte-for-byte identical | Static QA artifact. |
| `scripts/graphs 2.py` | `scripts/graphs.py` | Byte-for-byte identical | Manual analysis script; canonical path is documented/expected. |
| `scripts/ingest_youtube_feed 2.py` | `scripts/ingest_youtube_feed.py` | Byte-for-byte identical | Manual ingestion duplicate; no workflow references the suffix path. |
| `tests/test_algorithm 2.py` | `tests/test_algorithm.py` | Different and potentially active | Broad pytest discovery can match `test_*.py`; suffix file is an older/smaller test suite, while canonical adds appearance-theme coverage. |
| `tests/test_taxonomy 2.py` | `tests/test_taxonomy.py` | Byte-for-byte identical | Broad pytest discovery can collect both, duplicating test execution. |
| `website/eslint.config 2.js` | `website/eslint.config.js` | Byte-for-byte identical | ESLint uses the canonical config name; `eslint .` may still inspect arbitrary JS files. |
| `website/package 2.json` | `website/package.json` | Different but apparently obsolete | npm uses `package.json`; canonical adds diagnostic/research tests and `qa:study`. No repository reference selects the suffix file. |
| `website/public/favicon 2.svg` | `website/public/favicon.svg` | Byte-for-byte identical | `website/index.html` uses the canonical asset path. |
| `website/qa/live-content-check 2.mjs` | `website/qa/live-content-check.mjs` | Byte-for-byte identical | No package script selects the suffix file; it could only run by an explicit manual path. |
| `website/qa/responsive-check 2.mjs` | `website/qa/responsive-check.mjs` | Byte-for-byte identical | `qa:responsive` selects the canonical file explicitly. |
| `website/src/App 2.css` | `website/src/App.css` | Different but apparently obsolete | `App.jsx` imports canonical `App.css`; suffix version predates current loader styling. |
| `website/src/App 2.jsx` | `website/src/App.jsx` | Different but apparently obsolete | `main.jsx` imports canonical `App.jsx`; suffix version predates current routes/research flow. ESLint may still scan it. |
| `website/src/auth 2.css` | `website/src/auth.css` | Different but apparently obsolete | `App.jsx` imports canonical `auth.css`; suffix version lacks current auth/diagnostic styles. |
| `website/src/brand 2.js` | `website/src/brand.js` | Different but apparently obsolete | Runtime imports canonical `brand.js`; suffix version contains the prior Chrysalis-facing brand values. ESLint may still scan it. |
| `website/src/community 2.css` | `website/src/community.css` | Byte-for-byte identical | Runtime imports canonical CSS. |
| `website/src/home 2.css` | `website/src/home.css` | Different but apparently obsolete | The committed blobs are identical; the live canonical file has a pre-existing user modification that is intentionally preserved. Runtime imports canonical CSS. |
| `website/src/index 2.css` | `website/src/index.css` | Different but apparently obsolete | `main.jsx` imports canonical `index.css`; suffix file predates the current DayBreak design-system foundation. |
| `website/src/main 2.jsx` | `website/src/main.jsx` | Byte-for-byte identical | Vite uses canonical `main.jsx` from `index.html`. |
| `website/src/reels 2.css` | `website/src/reels.css` | Different but apparently obsolete | Runtime imports canonical CSS; suffix file predates the current semantic design tokens. Canonical also has a preserved user modification. |
| `website/src/saved 2.css` | `website/src/saved.css` | Different but apparently obsolete | Runtime imports canonical CSS; suffix file predates current accessibility and token changes. |
| `website/vite.config 2.js` | `website/vite.config.js` | Different but apparently obsolete | Vite uses canonical `vite.config.js`; suffix file lacks the fixed development port. |
| `archive/visual-assets/error-screenshots/Screenshot 2026-05-09 at 4.02.51 PM.png` | No suffix-free counterpart | Unclear | Literal `" 2"` comes from the date `2026`; this is not evidence of a duplicate copy. |
| `archive/visual-assets/error-screenshots/Screenshot 2026-05-09 at 4.02.58 PM.png` | No suffix-free counterpart | Unclear | Literal `" 2"` comes from the date `2026`; this is not evidence of a duplicate copy. |
| `archive/visual-assets/error-screenshots/Screenshot 2026-05-10 at 11.06.07 AM.png` | No suffix-free counterpart | Unclear | Literal `" 2"` comes from the date `2026`; this is not evidence of a duplicate copy. |

The duplicate numbered migrations are especially risky organizationally. No
automatic migration runner is present, and the README applies migrations by
explicit path, so the repository does not prove that they have run twice.
However, `psql ... migrations/*.sql`, a dashboard upload, or a future runner
could treat each filename as a distinct migration. Byte identity makes many
current SQL effects repeatable where `IF EXISTS`/`IF NOT EXISTS` guards are used,
but it does not remove duplicate migration identity, ordering ambiguity, noisy
history, or the risk that future edits update only one copy. They should be
removed only in a separately verified cleanup after deployed migration history
is known.

## Deferred beyond Phase 1

- No executable job has moved into `automation/jobs/`.
- No route, workflow, cron schedule, frequency, environment, database trigger,
  migration, retry policy, ingestion limit, or authentication behavior changed.
- No scheduler, worker, queue, Celery, Redis, startup hook, or lock was added.
- Cron correction, fail-closed authentication, locking/idempotency,
  observability, retries, retention, and duplicate deletion all require separate
  behavior-changing work.
- A safe Phase 2 should migrate only the production admin-ingestion
  orchestration: add one tested function under
  `automation/jobs/youtube_feed_ingest.py` that delegates unchanged to
  `integrations.youtube_ingest.ingest_youtube_videos_postgres`, then make only
  `api/index.py:admin_ingest_youtube` call it. Keep the route, method, parameters,
  response, secret check, workflow URL, schedule, and ingestion defaults
  unchanged; do not touch `cron_extract` in the same step.
