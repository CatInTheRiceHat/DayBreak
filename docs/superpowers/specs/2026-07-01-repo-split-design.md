# Repo Split: Website (About) + Backend (MorphoMedia)

**Date:** 2026-07-01
**Goal:** Move the algorithm/backend and the portfolio website into two separate
repositories so the website stays clean and self-contained.

## Background

The current `MorphoMedia` repo holds both halves:
- A React/Vite **portfolio website** in `website/`
- A FastAPI **algorithm/backend** (`core/`, `api.py`, `api/index.py`,
  `migration_scheduler.py`, `scripts/`, `tests/`, `migrations/`, `integrations/`,
  `datasets/`, `supabase/`).

They are already loosely coupled: the frontend calls the backend over HTTP via
`VITE_API_URL` (defaults to same-origin). Today they are co-deployed by one
`vercel.json` that routes `/api/*` to the Python function and everything else to
the SPA.

The `.git` directory is ~40GB, but the tracked history is tiny (~2,000 reachable
objects, largest real blob 15MB). The bloat is unreachable/dangling blobs
(multiple 1–2GB each) left over from past history rewrites. A fresh history drops
it entirely.

## Decisions

- **Fresh history** for both repos (old commit messages are gibberish; nothing
  worth preserving).
- **`About`** (new GitHub repo, `github.com/CatInTheRiceHat/About`) → the
  **portfolio website**, promoted to repo root.
- **`MorphoMedia`** (existing repo) → the **algorithm/backend**, branded/URL'd as
  "Chrysalis". Stays in the local `~/Documents/Chrysalis` folder (keeps `.venv`,
  DB, `datasets/`, and the `hf` HuggingFace remote).
- CORS is already configured in `api/index.py` (`allow_origins=["*"]`), so no code
  change is needed for cross-origin.

## Repo contents

**About (website):** tracked `website/` files promoted to root; website-only
`vercel.json` (framework `vite`, SPA rewrite, no `/api` rewrite); `VITE_API_URL`
env → backend URL.

**MorphoMedia (backend):** `core/`, `api.py`, `api/`, `migration_scheduler.py`,
`scripts/`, `tests/`, `migrations/`, `integrations/`, `supabase/`, `datasets/`,
`archive/`, `results/`, `docs/`, `.claude/` pipeline, `CLAUDE.md`,
`README_ALGORITHM.md`, `requirements.txt`, `.python-version`, `chrysalis.db`,
`ai_channels.json`; backend `vercel.json` (Python function + 07:00/19:00 crons);
`hf` remote retained.

## Execution phases

- **Phase 0 — Backup.** `git bundle create ~/Documents/chrysalis-fullbackup-2026-07-01.bundle --all` (done, 64MB).
- **Phase 1 — Website repo.** Extract tracked `website/` files via `git archive`
  (no `node_modules`) into `~/Documents/About`, promoted to root. Add website
  `vercel.json`. `git init` → clean commit → `origin = About` → force-push.
- **Phase 2 — Backend repo.** In `~/Documents/Chrysalis`: orphan branch, drop
  `website/`, keep backend files, add backend `vercel.json`, clean commit, keep
  `origin = MorphoMedia` + `hf`, push. `git reflog expire --all && git gc
  --prune=now` to reclaim ~40GB.
- **Phase 3 — Wire.** Set `VITE_API_URL` on the website's Vercel project to the
  backend URL; verify both build.

## Follow-ups (out of scope for this task)

- Optionally rename the `MorphoMedia` GitHub repo → `Chrysalis` (cosmetic).
- Rebrand the website with its own name (since "Chrysalis" now belongs to the
  algorithm site).
- Rewrite the website's About page to be about the Chrysalis project.
