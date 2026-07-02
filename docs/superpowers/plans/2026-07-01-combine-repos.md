# Combine Repos (Algorithm + Portfolio) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the Portfolio repo into the Chrysalis repo as a two-folder monorepo (`algorithm/` + `portfolio/`), preserving both histories, keeping both sites deployable on Vercel.

**Architecture:** All current Chrysalis working-tree content (tracked + local untracked artifacts) moves into `algorithm/` via a `find`-based move (robust to odd filenames), staged so git records renames and preserves history. Portfolio is grafted into `portfolio/` via `git subtree add`, which carries its commit history in. All work happens on a safety branch in `~/Documents/Chrysalis`; the standalone Portfolio repo is left untouched as a backup.

**Tech Stack:** git (subtree), Vite/React (both frontends), Python serverless API (Chrysalis), Vercel (deploy).

> **Note on this plan file:** During Task 2 this file moves from `docs/superpowers/plans/` to `algorithm/docs/superpowers/plans/` along with everything else. After Task 2, continue reading/updating it at its new path: `algorithm/docs/superpowers/plans/2026-07-01-combine-repos.md`.

> **This is a repo-restructure + deploy-config task, not feature code.** There are no unit tests to write; "verification" means running builds and inspecting git/filesystem state. Steps are written accordingly.

---

### Task 1: Safety branch and clean-state check

**Files:** none (git state only)

- [ ] **Step 1: Confirm the working tree is clean**

Run:
```bash
cd ~/Documents/Chrysalis && git status --short
```
Expected: no output (clean). If there is output, stop and resolve before continuing.

- [ ] **Step 2: Record the current HEAD as a recovery point**

Run:
```bash
cd ~/Documents/Chrysalis && git branch backup/pre-monorepo && git rev-parse --short HEAD
```
Expected: prints a short SHA. `backup/pre-monorepo` now points at the pre-change state for easy rollback (`git reset --hard backup/pre-monorepo`).

- [ ] **Step 3: Create and switch to the work branch**

Run:
```bash
cd ~/Documents/Chrysalis && git switch -c combine-monorepo
```
Expected: "Switched to a new branch 'combine-monorepo'".

---

### Task 2: Move all Chrysalis content into `algorithm/`

**Files:**
- Create: `algorithm/` (new top-level folder)
- Move: every current top-level entry except `.git` into `algorithm/`

- [ ] **Step 1: Create the target folder**

Run:
```bash
cd ~/Documents/Chrysalis && mkdir algorithm
```
Expected: no output; `algorithm/` exists.

- [ ] **Step 2: Move every top-level entry (tracked + untracked, incl. dotfiles) into `algorithm/`**

Run:
```bash
cd ~/Documents/Chrysalis && find . -maxdepth 1 -mindepth 1 ! -name .git ! -name algorithm -exec mv {} algorithm/ \;
```
Expected: no output. `find -maxdepth 1 -mindepth 1` enumerates all top-level items including dotfiles and the special-character path under `archive/`; each is moved into `algorithm/`. This moves untracked local artifacts (`.env`, `.venv`, `chrysalis.db`, `__pycache__`, `reports/`, `VK-LSVD/`) as well as tracked files.

- [ ] **Step 3: Verify root now contains only `algorithm/` and `.git`**

Run:
```bash
cd ~/Documents/Chrysalis && ls -A
```
Expected: exactly `algorithm` and `.git` (nothing else).

- [ ] **Step 4: Stage the move**

Run:
```bash
cd ~/Documents/Chrysalis && git add -A
```
Expected: no output.

- [ ] **Step 5: Verify git recorded renames (history preserved)**

Run:
```bash
cd ~/Documents/Chrysalis && git status --short | head -5 && echo "---rename count---" && git status --short | grep -c '^R'
```
Expected: entries begin with `R` (renamed), e.g. `R  api.py -> algorithm/api.py`. The rename count should be large (dozens+). If files show as `D`/`A` (deleted/added) instead of `R`, that is still acceptable — `git log --follow` will detect the content-identical rename — but `R` confirms it directly.

- [ ] **Step 6: Confirm history follows a moved file**

Run:
```bash
cd ~/Documents/Chrysalis && git commit -q -m "refactor: move Chrysalis (algorithm) into algorithm/ subfolder" && git log --follow --oneline -3 -- algorithm/api.py
```
Expected: shows commit history for `api.py` from before the move (proves `--follow` traces through the rename).

---

### Task 3: Verify the algorithm site still builds from its new location

**Files:** none (build check only)

- [ ] **Step 1: Confirm the algorithm's Vercel config is intact and paths are relative**

Run:
```bash
cd ~/Documents/Chrysalis && cat algorithm/vercel.json
```
Expected: unchanged JSON — `buildCommand` is `cd website && npm install && npm run build`, `outputDirectory` is `website/dist`, plus the `/api` rewrites and crons. These paths are relative to `algorithm/`, so they resolve correctly once Vercel's Root Directory is `algorithm` (set in Task 6).

- [ ] **Step 2: Build the frontend exactly as Vercel will**

Run:
```bash
cd ~/Documents/Chrysalis/algorithm/website && npm install && npm run build
```
Expected: install completes and Vite prints a successful build with output written to `dist/` (i.e. `algorithm/website/dist`). If it fails, stop — the move should not have changed build behavior, so a failure indicates a pre-existing issue to investigate before proceeding.

- [ ] **Step 3 (optional, local backend only): recreate the Python venv**

The moved `.venv` now lives at `algorithm/.venv` but its scripts hardcode the old absolute path, so it is broken. It is gitignored and only needed to run the backend locally. Recreate it if you plan to run the backend locally:
```bash
cd ~/Documents/Chrysalis/algorithm && rm -rf .venv && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```
Expected: a fresh `.venv` and installed dependencies. Skip this step if you only deploy via Vercel.

---

### Task 4: Graft the Portfolio repo into `portfolio/` (history preserved)

**Files:**
- Create: `portfolio/` (populated from the Portfolio repo, with its history)

- [ ] **Step 1: Confirm the Portfolio source repo is clean and on `main`**

Run:
```bash
cd ~/Documents/Portfolio && git switch main 2>/dev/null; git status --short && git branch --show-current
```
Expected: no status output (clean) and branch `main`. This local repo is the subtree source and stays untouched as a backup.

- [ ] **Step 2: Add the Portfolio repo as a temporary source remote and fetch it**

Run:
```bash
cd ~/Documents/Chrysalis && git remote add portfolio-src ~/Documents/Portfolio && git fetch portfolio-src
```
Expected: fetch reports branches from `portfolio-src` (e.g. `portfolio-src/main`).

- [ ] **Step 3: Subtree-add Portfolio into `portfolio/`**

Run:
```bash
cd ~/Documents/Chrysalis && git subtree add --prefix=portfolio portfolio-src main
```
Expected: "Added dir 'portfolio'" and a merge commit. `portfolio/` now contains the Portfolio site, and Portfolio's commit history is joined into this repo's history.

- [ ] **Step 4: Remove the temporary remote**

Run:
```bash
cd ~/Documents/Chrysalis && git remote remove portfolio-src
```
Expected: no output.

- [ ] **Step 5: Verify structure and that Portfolio history came along**

Run:
```bash
cd ~/Documents/Chrysalis && ls -A && echo "---portfolio contents---" && ls portfolio && echo "---portfolio history---" && git log --oneline -3 -- portfolio/index.html
```
Expected: root shows `algorithm`, `portfolio`, `.git`; `portfolio/` contains `src/`, `public/`, `index.html`, `package.json`, `vercel.json`; and the log shows Portfolio's original commits (e.g. "strip Portfolio down to the About Me landing").

---

### Task 5: Verify the portfolio site builds from its new location

**Files:** none (build check only)

- [ ] **Step 1: Confirm Portfolio's Vercel config is intact**

Run:
```bash
cd ~/Documents/Chrysalis && cat portfolio/vercel.json
```
Expected: unchanged JSON — `framework: "vite"` with the SPA rewrite (`/(.*) -> /index.html`).

- [ ] **Step 2: Build the portfolio exactly as Vercel will**

Run:
```bash
cd ~/Documents/Chrysalis/portfolio && npm install && npm run build
```
Expected: install completes and Vite prints a successful build to `dist/` (i.e. `portfolio/dist`). If it fails, stop and investigate before proceeding.

---

### Task 6: Publish the monorepo and wire up Vercel

**Files:** none (git remote + Vercel dashboard)

- [ ] **Step 1: Merge the work branch into `main`**

Run:
```bash
cd ~/Documents/Chrysalis && git switch main && git merge --no-ff combine-monorepo -m "feat: combine algorithm + portfolio into one monorepo"
```
Expected: fast-forward-free merge completes; `main` now has the monorepo layout.

- [ ] **Step 2: Push `main` to the Chrysalis GitHub repo**

Run:
```bash
cd ~/Documents/Chrysalis && git push origin main
```
Expected: push succeeds to `github.com/CatInTheRiceHat/Chrysalis`. (Do NOT push to the `hf` remote — the HuggingFace Space is intentionally left as-is.)

- [ ] **Step 3: Update the existing Chrysalis Vercel project's Root Directory**

Manual, in the Vercel dashboard:
1. Open the existing Chrysalis project → **Settings → Build & Deployment** (or **General**).
2. Set **Root Directory** to `algorithm`.
3. Save, then trigger a redeploy (Deployments → ⋯ → Redeploy, or push any commit).

Expected: the redeploy uses `algorithm/vercel.json`; the site, `/api/*`, and crons work as before.

- [ ] **Step 4: Create a new Vercel project for the portfolio**

Manual, in the Vercel dashboard:
1. **Add New → Project** → import the **same** `CatInTheRiceHat/Chrysalis` GitHub repo.
2. During setup, set **Root Directory** to `portfolio`.
3. Framework preset should auto-detect **Vite** (from `portfolio/vercel.json`); keep defaults.
4. Deploy.

Expected: a second Vercel deployment serving the Portfolio site from `portfolio/`.

- [ ] **Step 5: Retire the old Portfolio deployment (optional)**

The old standalone Portfolio Vercel project keeps deploying from the old `CatInTheRiceHat/Portfolio` repo. Either delete that Vercel project to avoid a duplicate live site, or leave it — it is harmless. The old GitHub repo remains as a backup regardless.

- [ ] **Step 6: Final verification**

Confirm in a browser: the Chrysalis (algorithm) URL loads and its API responds; the new Portfolio URL loads the About Me landing. Both are now served from the single combined repo.

---

## Rollback

If anything goes wrong before Task 6 Step 2 (the push), reset the local repo:
```bash
cd ~/Documents/Chrysalis && git switch main && git reset --hard backup/pre-monorepo
```
This restores the pre-change state. The Portfolio repo was never modified.
