# Desktop Feed Sizing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill large desktop screens by making the reels feed's `≥1100px` tier fluid with a raised, bounded ceiling — larger video and side panels instead of empty gutter.

**Architecture:** A single CSS media block (`@media (min-width: 1100px)` in `algorithm/website/src/reels.css`) changes. Five coordinated rules become fluid (`clamp`/`vw`) with higher hard ceilings. No new breakpoint, no JS, no component changes. Phone (`≤540px`) and mid (`540–1099px`) tiers are untouched.

**Tech Stack:** Plain CSS (Vite dev server at localhost:6767). Verification is visual, not unit-tested — CSS `clamp`/`dvh` values have no meaningful automated assertion, so each change is confirmed against the live render at representative widths.

**Spec:** `docs/superpowers/specs/2026-07-03-desktop-feed-sizing-design.md`

---

## Why one commit, not micro-commits

The five rule changes are interdependent: a wider `.reel-frame` and wider caption column only fit if the feed column / `.reel-layout` max-width can hold them. Applying them one at a time produces intermediate states that overflow. So Task 1 makes all coordinated edits, Task 2 verifies + tunes against the live render (including the feed-column fit the spec flagged), and Task 3 commits once the render is clean.

---

### Task 1: Apply the coordinated fluid-sizing edits

**Files:**
- Modify: `algorithm/website/src/reels.css` (inside `@media (min-width: 1100px)`, starting ~line 1138)

All five edits are within the single `@media (min-width: 1100px)` block. Match on the exact current declarations (line numbers approximate — match by text).

- [ ] **Step 1: Raise the stage ceiling and widen the compass rail column**

In `.reels-stage`, change:
```css
    grid-template-columns: minmax(260px, 340px) minmax(680px, 840px);
```
to:
```css
    grid-template-columns: minmax(260px, 400px) minmax(680px, 900px);
```
and change:
```css
    width: min(1280px, calc(100vw - 56px));
```
to:
```css
    width: min(1600px, calc(100vw - 56px));
```
(The feed column max is raised `840px → 900px` here so the wider inner grid from Step 2 has room — see the spec's feed-column note.)

- [ ] **Step 2: Widen the caption column and inner-grid max-width in `.reel-layout`**

Change:
```css
    grid-template-columns: minmax(190px, 240px) minmax(360px, 430px) 58px;
```
to:
```css
    grid-template-columns: minmax(190px, 300px) minmax(360px, 520px) 58px;
```
and change:
```css
    width: min(100%, 820px);
```
to:
```css
    width: min(100%, 900px);
```

- [ ] **Step 3: Make the video frame fluid and let it grow taller**

In `.reel-frame` (inside the same media block), change:
```css
    width: min(410px, 100%);
    height: min(82dvh, 656px);
```
to:
```css
    width: clamp(410px, 30vw, 520px);
    height: min(86dvh, 760px);
```

- [ ] **Step 4: Sanity-check the file parses**

Run: `cd algorithm/website && npx vite build 2>&1 | tail -5` (or rely on the dev server's HMR in Task 2). Expected: build succeeds with no CSS syntax error. If the dev server is already running, this step can be skipped in favor of watching HMR reload cleanly in Task 2.

---

### Task 2: Verify and tune against the live render

**Files:** none (observation + optional value tweaks in `reels.css`)

- [ ] **Step 1: Start the dev server (if not running)**

Run: `cd algorithm/website && npm run dev`
Expected: Vite serves on `http://localhost:6767` (strictPort).

- [ ] **Step 2: Check each representative width for overflow and video size**

Open `http://localhost:6767`, resize the browser (or use devtools responsive mode) to each width and confirm: no horizontal scrollbar, portrait video fully visible (not clipped by height), video visibly larger than before at the wide sizes.

| Width | Expectation |
|---|---|
| ~1280px (13" laptop) | Same as today or slightly larger; no regression |
| ~1512px (14"/16" MacBook) | Video + panels noticeably larger |
| ~1920px | Space filled, margins reasonable |
| ~2560px | Video large, panels frame it, no clipping, portrait fully visible |

- [ ] **Step 3: Tune if needed**

If the inner grid overflows the feed column at any width (horizontal scrollbar, or action rail pushed off), reduce `.reel-frame` `520px` and/or the caption column `300px`, or raise the `.reel-layout` `900px` / `.reels-stage` `900px` feed-column caps until it fits. If the video overflows vertically on a short window, lower `86dvh`/`760px`. Re-check all four widths after any change. Repeat until every width is clean.

---

### Task 3: Commit

- [ ] **Step 1: Confirm scope of the diff**

Run: `cd /Users/elaine/Documents/Chrysalis && git diff --stat algorithm/website/src/reels.css`
Expected: only `reels.css` changed.

- [ ] **Step 2: Commit**

```bash
cd /Users/elaine/Documents/Chrysalis
git add algorithm/website/src/reels.css
git commit -m "feat: fluid desktop feed sizing to fill large screens

Raise and make fluid the >=1100px reels tier so the video and side
panels grow on large displays instead of leaving empty gutter. Stage
ceiling 1280->1600px, video frame min(410px)->clamp(410px,30vw,520px),
height min(82dvh,656px)->min(86dvh,760px), widened compass rail and
caption columns. Phone and mid tiers unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review notes

- **Spec coverage:** all five spec table rows map to Task 1 Steps 1–3; the feed-column fit note maps to Task 1 Step 2 (raised `820→900`, `840→900`) plus Task 2 Step 3 tuning; verification widths map to Task 2 Step 2. Non-goals (phone/mid tiers, no margin content, no crop change) are respected — only the `≥1100px` block is touched.
- **Type/value consistency:** ceiling values used consistently — stage `1600px`, feed column `900px` (both `.reels-stage` col and `.reel-layout` width), video `clamp(410px, 30vw, 520px)`, height `min(86dvh, 760px)`, caption `minmax(190px, 300px)`, compass `minmax(260px, 400px)`.
- **No placeholders:** every edit shows exact before/after CSS.
