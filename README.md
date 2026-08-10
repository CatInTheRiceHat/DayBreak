---
title: Chrysalis
emoji: 🦋
colorFrom: purple
colorTo: green
sdk: docker
app_port: 8080
pinned: false
---

# Chrysalis: Healthy Feed Algorithm

A youth-centric social media recommender system that prioritizes digital well-being over engagement maximization.

## Quick Start

```bash
# Install dependencies
pip install pandas numpy matplotlib fastapi uvicorn python-multipart

# Set up your YouTube API key (optional, for live video data)
cp .env.example .env
# Edit .env and add backend-only secrets:
#   YOUTUBE_API_KEY
#   FEED_INGEST_SECRET
# Optional:
#   YOUTUBE_FEED_QUERIES=category=query,category=query
# Optional: pin local SQLite storage. Relative paths resolve from project root.
DATABASE_PATH=./data/local/chrysalis.db

# Run the API server
python api.py
# Server starts at http://localhost:8000
```

### Local `/reels` live-video check

Run the API and Vite frontend together:

```bash
DATABASE_PATH=./data/local/chrysalis.db python api.py
cd website
npm run dev
```

`website/.env.local` should contain `VITE_API_URL=http://localhost:8000`.
The local API allows Vite on `localhost` or `127.0.0.1` ports `5173` and `5174`,
so `/reels` can still fetch live cards when Vite moves to the next open port.

### Anonymous research feed

`/study` uses an anonymous bearer credential and a server-owned research session.
The browser cannot select a condition: it requests
`GET /api/research/sessions/{session_id}/feed`, and the backend reads the stored
condition, private seed, and immutable policy version from the session record.

The current policies are:

- `regular-v1`: the existing `flutter-feed` ordering, with no additional
  research quota or repetition rule.
- `balanced-v1`: a deterministic, seeded 60% normal / 30% existing healthy or
  positive / 10% perspective target across a 12-item window, with bounded
  category and creator repetition penalties and inventory fallbacks.

Apply PostgreSQL migrations in order before deploying the research route:

```bash
psql "$DATABASE_URL" -f migrations/015_research_sessions_and_events.sql
psql "$DATABASE_URL" -f migrations/016_research_feed_policies.sql
psql "$DATABASE_URL" -f migrations/017_intentional_break_loop.sql
```

Migration execution is manual; this repository does not automatically apply
database migrations during deployment. Before a pilot release, follow the
backup, catalog/RLS verification, dummy-lifecycle, and release-record procedure
in [`docs/pilot/production-environment.md`](docs/pilot/production-environment.md).
Do not apply migration 017 more than once.

Local SQLite creates the same tables and upgrades Phase 1 research sessions on
startup. `feed_seed` is server-only. Issued item provenance is stored in
`research_feed_items`, then resolved by the server when it accepts any post
event; client-supplied category, position, bucket, reason, and policy values are
not authoritative.

For local verification only, `CHRYSALIS_RESEARCH_DEBUG=1` adds the active policy
to the `X-Chrysalis-Research-Policy` response header and backend log. Leave it
unset in production. Run the engineering distribution check with:

```bash
.venv/bin/python scripts/research_feed_sanity.py --windows 500 --window-size 12
```

The script uses the repository's demo-video fixtures and validates selection
behavior only; it does not analyze participants or support well-being claims.

### Opt-in PostgreSQL integration verification

The real PostgreSQL migration and Intentional Break integration suite is
destructive only to research tables in a dedicated disposable test database. It
never falls back to `DATABASE_URL`. With no explicit configuration, it skips:

```bash
.venv/bin/python -m pytest -q tests/test_intentional_break_postgres.py
```

To run it, provide a database whose name contains `test`, `testing`, or `ci`, and
set both `TEST_POSTGRES_DATABASE_URL` and
`ALLOW_POSTGRES_INTEGRATION_TESTS=1`. A verified disposable provider database
whose name cannot carry a test marker additionally requires
`ALLOW_UNMARKED_POSTGRES_TEST_DATABASE=1`. Targets matching `DATABASE_URL`,
`PRODUCTION_DATABASE_URL`, or `PILOT_DATABASE_URL` are always refused. The suite
prints only a sanitized host, port, and database name, applies the real 015-017
migration files, runs its checks, and removes the test research tables.

### Daily YouTube feed ingestion

The Algorithm feed is populated by a backend-only YouTube Data API ingestion job.
The React frontend never calls YouTube Data API and never receives `YOUTUBE_API_KEY`.

Required backend env vars:

```bash
YOUTUBE_API_KEY=...
FEED_INGEST_SECRET=...
DATABASE_PATH=./data/local/chrysalis.db
```

Optional query override. Plain queries are still accepted and stored with
`source_category=custom`; use `category=query` to preserve analysis metadata:

```bash
YOUTUBE_FEED_QUERIES=news/current events=current events explained,gaming=gaming highlights
```

Manual local ingestion:

```bash
DATABASE_PATH=./data/local/chrysalis.db python scripts/ingest_youtube_feed.py --max-results 10 --days-back 7
```

Or run through the API:

```bash
curl -X POST \
  -H "X-Feed-Ingest-Secret: $FEED_INGEST_SECRET" \
  "http://localhost:8000/api/admin/ingest/youtube"
```

The job searches recent, embeddable, English, US-region short videos across broad
topic buckets: news/current events, opinion/commentary, travel, food, cute animals,
fashion/aesthetic, gaming, comedy, internet culture, AI/technology, pop culture,
sports, wellness/mental health, study/productivity, lifestyle/vlogs,
education/explainers, and music/culture. It filters obvious explicit, shock,
humiliation, gambling, adult, violent, and low-quality content; stores
`source_category` and `source_query` as analysis metadata in `feed_videos`; and all
three `/api/feed/{mode}` routes draw from the same shared real-video pool. The
mode changes the reflection/explanation layer, not the source pool. Built-in
template cards remain frontend fallback/fill content only when there are not
enough real videos for `k`.

For hosted daily ingestion, configure GitHub repository secrets:

```bash
CHRYSALIS_API_BASE_URL=https://your-deployed-api.example
FEED_INGEST_SECRET=...
```

Then enable `.github/workflows/youtube-feed-ingest.yml`, which calls the admin
endpoint once per day and can also be run manually with `workflow_dispatch`.

## Project Structure

```
DayBreak/
├── api.py                 # Local FastAPI entry point
├── api/                   # Hosted/Vercel API entry point
├── core/                  # Ranking, labeling, storage, and policy logic
├── integrations/          # YouTube and external-service adapters
├── automation/            # Background-job boundary and configuration
├── scripts/               # Manual data, ingestion, and analysis commands
├── tests/                 # Python test suite
├── website/               # React/Vite frontend
│   └── src/
│       ├── app/           # Router and app-wide boundaries
│       ├── features/      # Code grouped by product feature
│       ├── lib/           # Shared services and adapters
│       ├── shared/        # Reusable UI
│       └── styles/        # Global styles
├── data/                  # Local DBs, datasets, curation, and schema snapshots
├── migrations/            # Ordered PostgreSQL/Supabase migrations
├── assets/                # Archived graphics and visual QA captures
└── docs/                  # Plans, specs, research, runbooks, and reports
```

See `docs/README.md`, `assets/README.md`, `data/README.md`, and
`website/src/README.md` for where new files should go.

## Algorithm Overview

The ranking formula balances four key factors:

| Factor | Weight (entertainment preset) | Purpose |
|--------|-------------------------------|---------|
| Engagement (e) | 0.55 | Baseline popularity, decayed during passive consumption |
| Diversity (d) | 0.20 | Gini coefficient promotes content variety |
| Prosocial (p) | 0.15 | Up-ranks prosocial/bridging content |
| Risk (r) | 0.10 | Down-ranks harmful upward comparison triggers |

### Key Features

- **Passive Consumption Decay**: Detects doomscrolling and forces diversity injection
- **Similarity Mindset Modifier**: Mitigates harmful social comparison by checking creator-user similarity
- **Gini Coefficient Diversity**: Mathematically enforces content variety to prevent filter bubbles
- **User-Controllable Weights**: Frontend sliders allow real-time algorithm adjustment

## Running Experiments

```bash
# Run 10 evaluation sessions
python scripts/experiments.py --n_sessions 10

# Generate result visualizations
python scripts/graphs.py --summary results/data/experiment_summary.csv
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serves the frontend UI |
| `/api/run/local` | POST | Run algorithm with custom weights |
| `/api/youtube/videos/{topic}` | GET | Fetch live YouTube video IDs |
| `/api/youtube/cache` | GET | Debug YouTube cache status |
| `/api/admin/ingest/youtube` | POST | Secret-protected daily YouTube feed ingestion |
| `/api/feed/{mode}` | GET | Serve Chrysalis-ranked Algorithm feed cards |

## Configuration

Presets available in `core/algorithm.py`:
- `baseline` - Engagement-only ranking
- `entertainment` - Balanced weights (default)
- `inspiration` - High diversity focus
- `learning` - High prosocial focus

Night mode adds extra risk penalty and caps feed length at 15.

## Documentation

- `docs/architecture/algorithm.md` - Mathematical formulas and UI mapping guide
- `docs/research/social-media-algorithm-project-enhancement.md` - Research paper with full theoretical background
- `docs/README.md` - Documentation filing guide

## License

MIT
