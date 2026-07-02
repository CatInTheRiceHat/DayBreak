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
DATABASE_PATH=./chrysalis.db

# Run the API server
python api.py
# Server starts at http://localhost:8000
```

### Local `/reels` live-video check

Run the API and Vite frontend together:

```bash
DATABASE_PATH=./chrysalis.db python api.py
cd website
npm run dev
```

`website/.env.local` should contain `VITE_API_URL=http://localhost:8000`.
The local API allows Vite on `localhost` or `127.0.0.1` ports `5173` and `5174`,
so `/reels` can still fetch live cards when Vite moves to the next open port.

### Daily YouTube feed ingestion

The Algorithm feed is populated by a backend-only YouTube Data API ingestion job.
The React frontend never calls YouTube Data API and never receives `YOUTUBE_API_KEY`.

Required backend env vars:

```bash
YOUTUBE_API_KEY=...
FEED_INGEST_SECRET=...
DATABASE_PATH=./chrysalis.db
```

Optional query override. Plain queries are still accepted and stored with
`source_category=custom`; use `category=query` to preserve analysis metadata:

```bash
YOUTUBE_FEED_QUERIES=news/current events=current events explained,gaming=gaming highlights
```

Manual local ingestion:

```bash
DATABASE_PATH=./chrysalis.db python scripts/ingest_youtube_feed.py --max-results 10 --days-back 7
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
Chrysalis/
├── core/algorithm.py          # Core ranking algorithm with Gini diversity, engagement decay
├── data.py               # Data processing utilities
├── metrics.py            # Evaluation metrics (diversity@k, streak detection, etc.)
├── graphs.py             # Visualization scripts for experiment results
├── api.py                # FastAPI web server with YouTube integration
├── experiments.py        # Run evaluation experiments
├── youtube_service.py    # YouTube Data API wrapper with caching
├── datasets/             # Processed datasets
├── results/              # Experiment outputs (CSVs, figures)
└── website/              # Frontend UI (served by api.py)
```

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
python experiments.py --n_sessions 10

# Generate result visualizations
python graphs.py --summary results/data/experiment_summary.csv
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

- `README_ALGORITHM.md` - Mathematical formulas and UI mapping guide
- `Social Media Algorithm Project Enhancement.md` - Research paper with full theoretical background

## License

MIT
