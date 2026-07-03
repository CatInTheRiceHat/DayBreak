# Chrysalis

## Project context

Chrysalis is a mental-health-aware social media recommendation algorithm. The
live feed is served through three reels ranking modes defined in
`core/ranking/modes.py`:

- **daily-dew** — a small, calm, grounding taste
- **metamorphosis** — the recovery mode: very few items, and only when low-risk
- **flutter-feed** — unlimited (closest to a normal feed)

All three draw from the same safe pool (`feed_videos`); mode-specific behavior
lives in the ranking/explanation layer.

Python interpreter: `.venv/bin/python3.13` (system Python lacks pytest and project deps).
Dataset: `datasets/processed_dataset.csv`.
Database: `chrysalis.db` (SQLite, project root); Supabase/Postgres in production.

Run tests: `.venv/bin/python -m pytest -q`

## Archived

The old multi-agent test pipeline (test-runner / simulation-agent / fact-checker
/ analysis-agent / fix-agent) and the deprecated Cocoon/Migration Mode code were
retired on 2026-07-03. Preserved under `../archive/2026-07-03-unused-code/` — see
that folder's `README.md`.
