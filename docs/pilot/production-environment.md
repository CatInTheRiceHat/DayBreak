# Intentional Break pilot production environment

This is the operator checklist for the closed PostgreSQL/Supabase pilot. It
documents configuration and verification; it does not authorize a deployment or
a production migration. Never place secret values in this file, frontend build
variables, logs, screenshots, or release records.

## Pilot runtime

The hosted `/study` API requires these server-only variables:

| Variable | Classification | Operational rule |
| --- | --- | --- |
| `DATABASE_URL` | Required for pilot runtime | Trusted backend PostgreSQL connection. Never expose it to the browser or use it as the integration-test default. |
| `INTENTIONAL_BREAK_PLAN_SEED_SECRET` | Required for pilot runtime | Dedicated backend-only plan-selection secret. Keep it stable for the entire running pilot. |

`INTENTIONAL_BREAK_PLAN_SEED_SECRET` keys deterministic private selection during
plan creation and idempotent retries. It must never use a `VITE_` prefix or be
sent to the frontend. The current backend retains compatibility fallbacks, but a
production pilot must configure the dedicated variable and must not rely on
those fallbacks.

Rotating the secret can alter deterministic selection for plans that have not
yet been materialized, including retried creation commands whose batch was not
committed. It does not rewrite existing materialized
`research_session_items` batches. Rotate only at a documented contract/release
boundary, record the boundary, and verify the new release before invitations.

These backend variables are required only when the corresponding production
operation is enabled:

| Variable | Required when |
| --- | --- |
| `FEED_INGEST_SECRET` | The protected feed-ingestion endpoint or its GitHub workflow is used. |
| `YOUTUBE_API_KEY` | Production YouTube ingestion or request-time YouTube lookup is used. It remains backend-only. |
| `CRON_SECRET` | A production cron endpoint relies on it for authentication. Confirm the actual scheduled route before relying on it; `vercel.json` currently lists legacy `/api/cron/drop` schedules and does not apply migrations. |

## Frontend and deployment variables

`VITE_API_URL` is optional when the website and API are served from the same
origin, because the frontend defaults to relative `/api` requests. Set it when
the `/study` frontend calls a separately hosted API.

`VITE_APP_VERSION` is optional build metadata used by the existing general
research-event path. It is not a trustworthy substitute for a deployment Git
SHA and does not change the Intentional Break contract. The release record below
is authoritative for the pilot deployment identity.

`VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` configure the existing browser
Supabase client for sign-in, profiles, diagnostics, and usage events. The
anonymous bearer-token `/study` Intentional Break API does not require them for
its research storage path. Configure them only if those normal-product features
are part of the deployed pilot experience. Supabase's anon key is frontend
configuration; database URLs, service credentials, and the plan seed secret are
not.

## PostgreSQL integration-test environment

The repository integration suite uses only these test controls:

| Variable | Purpose |
| --- | --- |
| `TEST_POSTGRES_DATABASE_URL` | Dedicated, disposable PostgreSQL integration target. |
| `ALLOW_POSTGRES_INTEGRATION_TESTS` | Must equal `1` before any integration mutation. |
| `ALLOW_UNMARKED_POSTGRES_TEST_DATABASE` | Additional opt-in for a verified disposable provider database whose database name cannot include `test`, `testing`, or `ci`. |

Never set `TEST_POSTGRES_DATABASE_URL` to the production pilot database. The
harness rejects a target whose host/port/database identity matches
`DATABASE_URL`, `PRODUCTION_DATABASE_URL`, or `PILOT_DATABASE_URL`, even when the
additional override is present. It also refuses unmarked and production-looking
identities unless the additional override is explicit. The two-variable base
opt-in is always mandatory.

The suite prints only `host:port/database`; credentials and full URLs are never
printed. It takes an advisory lock, drops only the known public research tables
in the dedicated test database, applies the real migration files, runs isolated
UUID-based fixtures, and drops those research tables at teardown. Do not run
parallel integration suites against the same database.

Safe default command:

```bash
.venv/bin/python -m pytest -q tests/test_intentional_break_postgres.py
```

Without the URL and explicit opt-in, classify the result as:

- PostgreSQL integration suite: **SKIPPED**
- Reason: dedicated test PostgreSQL environment not configured
- Repository harness: ready
- PostgreSQL validation: not performed

Only report PostgreSQL as validated when that command actually connects and
executes the tests. Record the test count, pass/fail result, sanitized database
identity, PostgreSQL version, migrations executed, and whether browser-role RLS
testing was full or limited to catalog/RLS inspection.

## Production migration 017 procedure

Migration application is manual. No Vercel build or repository automation
applies migration 017.

1. Back up or snapshot the pilot PostgreSQL database according to the operator's established practice.
2. Confirm the current applied migration state. Verify 015 and 016 are present and 017 has not already been applied.
3. Record the intended migration file checksum or reviewed commit, then apply `migrations/017_intentional_break_loop.sql` exactly once with the trusted operator connection.
4. Inspect PostgreSQL catalogs for the new `research_sessions` columns; `research_session_items`; `research_session_checkouts`; event sequence/client/authority fields; ownership foreign keys and cascades; unique indexes; lifecycle constraints; and the partial unique nonterminal index.
5. Verify RLS is enabled on all research tables. Where Supabase `anon` and `authenticated` roles exist, verify they cannot select, insert, update, or delete research rows directly. Verify the trusted backend role can complete required server operations.
6. Run a dummy participant lifecycle through plan, exact finite items, start, impressions, boundary or Finish Early, checkout, cooldown, and completion. Rehearse participant deletion and confirm all dummy research rows cascade while unrelated rows remain.
7. Record the operator, timestamp, migration version, verification result, dummy participant deletion, and release record reference.

Do not apply migration 017 to production merely because the disposable
integration suite passed. Production execution is a separate reviewed operator
action.

## Release and deployment identity

Before participant invitations, create a release record outside participant
data containing:

- Git commit SHA
- Vercel deployment ID and deployment URL
- Applied migration version (through 017 when production migration is approved)
- Pilot contract version (`intentional-break-v1` for this implementation)
- Pilot start date and timezone

Also record the integration-test result and RLS scope. Do not use a session's
`application_version` as the Git SHA: existing code paths use it for application
or contract identifiers, and it is not a reliable deployment identity. If
`VITE_APP_VERSION` is set, record its value as secondary build metadata only.

## Final pre-invitation checks

- The dedicated seed secret is configured server-side and its stability owner is identified.
- The production database snapshot and migration state are recorded.
- Migration 017, catalog objects, RLS, and the dummy lifecycle are verified by an authorized operator.
- The release identity record is complete.
- The disposable PostgreSQL suite result is recorded without credentials.
- No integration test configuration points to the pilot database.
