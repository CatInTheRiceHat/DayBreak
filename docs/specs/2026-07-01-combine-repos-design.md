# Combine Repos: Algorithm (Chrysalis) + Portfolio into one monorepo

**Date:** 2026-07-01
**Goal:** Merge the two separate repos — Chrysalis (the algorithm/backend, full-stack)
and Portfolio (the "About Me" landing site) — into a single GitHub repository with two
subfolders, `algorithm/` and `portfolio/`, while keeping **both sites live on Vercel**.

## Background

Earlier today the original combined repo (`MorphoMedia`) was split into two repos:

- **Chrysalis** (`github.com/CatInTheRiceHat/Chrysalis`, local `~/Documents/Chrysalis`) —
  full-stack algorithm project: Python API (`api.py`, `api/index.py`), `core/`,
  `migrations/`, `supabase/`, its own Vite frontend in `website/`, cron jobs, and a
  (legacy) HuggingFace Space remote (`hf`).
- **Portfolio** (`github.com/CatInTheRiceHat/Portfolio`, local `~/Documents/Portfolio`) —
  a standalone Vite/React "About Me" landing site.

The user now wants them re-united into one repo but kept as two clearly separated sites:
the *algorithm* and the *portfolio*.

## Decisions

- **Target repo:** reuse the existing **Chrysalis** GitHub repo as the combined monorepo.
- **Layout:** symmetric subfolders — `algorithm/` (Chrysalis) and `portfolio/` (Portfolio).
- **History:** preserve the commit history of **both** projects in the merged repo.
- **Deployment:** both sites stay live on **Vercel**, as two independent Vercel projects
  pointing at the same repo with different Root Directories.
- **HuggingFace:** treated as unused/legacy — see analysis below. Not kept live. Can be
  revived later via a `git subtree push` if desired.
- The standalone `CatInTheRiceHat/Portfolio` GitHub repo is left untouched as a backup.

### Why HuggingFace is treated as unused

- `main`'s recent work is all Vercel-oriented (Python serverless `api/index.py`, cron jobs,
  "make api.py API-only", "recombine full-stack site").
- `hf/main` has diverged by ~61 commits from `main`, and `main` has ~6 commits not on
  `hf/main` — the two have not been kept in sync.
- HF's README frontmatter declares `sdk: docker`, but there is **no Dockerfile** on `main`.
  The Space runs off an old, separate lineage.

Conclusion: Chrysalis's live deployment is Vercel; the HF Space is stale. Moving Chrysalis
into `algorithm/` does not affect the live Vercel site.

## Final structure

```
Combined repo (root)/
├── algorithm/     ← all current Chrysalis code, moved verbatim
│   ├── api.py, api/, core/, migrations/, supabase/, website/, scripts/, tests/ ...
│   └── vercel.json   (unchanged; paths are relative to this folder)
└── portfolio/     ← Portfolio site, moved verbatim
    ├── src/, public/, index.html, package.json ...
    └── vercel.json   (unchanged; framework "vite", SPA rewrite)
```

## Implementation approach

### 1. Merge (history-preserving)

Performed inside the Chrysalis repo (`~/Documents/Chrysalis`):

1. Move all tracked Chrysalis files into `algorithm/` using `git mv` (git preserves history
   across the rename). Nested `.gitignore` files continue to work.
2. Move untracked-but-needed local artifacts on disk into `algorithm/` as well (e.g.
   `.venv`, `node_modules`, `chrysalis.db` if untracked) — or regenerate them. These are
   gitignored and not part of the merge; `.venv` may need recreating due to absolute paths.
3. Add Portfolio into `portfolio/` with `git subtree add --prefix=portfolio <portfolio-src> main`,
   using the local Portfolio repo as a temporary source remote. This carries Portfolio's
   commit history into the combined history.
4. Remove the temporary remote. Commit and push to Chrysalis `origin` (`main`).

### 2. Deployment (both stay live on Vercel)

- **Existing Chrysalis Vercel project:** change **Root Directory → `algorithm`**. Its
  `vercel.json` (with `cd website && ...` build, `/api` rewrites, and crons) works unchanged
  relative to that root.
- **New Vercel project for Portfolio:** create a new project on the *same* GitHub repo with
  **Root Directory → `portfolio`**. It picks up `portfolio/vercel.json` automatically.
- Optionally delete/retire the old Portfolio Vercel project (or leave it deploying from the
  old repo — harmless).
- Vercel dashboard steps are performed by the user; the exact click-path will be provided.

## Verification

- After the merge, from the repo root:
  - `cd algorithm && cd website && npm install && npm run build` succeeds (matches its
    `vercel.json` build command).
  - `cd portfolio && npm install && npm run build` succeeds.
  - Both `algorithm/vercel.json` and `portfolio/vercel.json` are present and unchanged.
- After Vercel wiring: both deployed URLs load correctly and Chrysalis's `/api/*` responds.

## Out of scope / non-goals

- No changes to application code, branding, or the sites' behavior.
- No keeping the HuggingFace Space live (revivable later, not part of this work).
- Renaming the GitHub repo (e.g. to `chrysalis-portfolio`) is optional and cosmetic.
