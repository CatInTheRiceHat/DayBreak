# Video Orientation Metadata — Design Spec

**Date:** 2026-07-02
**Status:** Approved for planning
**Goal:** Capture landscape vs. portrait orientation for every YouTube video in the
Chrysalis feed pipeline, store it as first-class metadata, expose it through the feed
API, and **split the feed by orientation** — the main vertical reel feed serves portrait
only, landscape videos are filed into their own feed.

## Problem

The pipeline stores `duration_seconds` and `thumbnail_url` but **no dimensional data** —
there is no way to tell a landscape upload from a vertical (Shorts-style) one. As a
result the feed cannot filter or rank by orientation, and today essentially all feed
videos are landscape with no way to confirm that from the data.

**Current frontend workaround (to be replaced):** `ReelCard` calls a client-side hook,
`useVideoOrientation.js`, which loads each video's `maxresdefault.jpg` off-screen and
compares pixel dimensions. Landscape-detected videos get a contained + blurred-backdrop
layout *inline in the same feed*. This is the unreliable thumbnail method — Shorts
thumbnails are padded to 16:9, and missing-maxres falls back to a guess — and it mixes
orientations in one feed. The DB-derived orientation replaces it.

## The reliable signal

YouTube thumbnail width/height **cannot** be trusted: Shorts thumbnails are padded to
16:9, so the reported image dimensions do not reflect the video's true orientation.

The accurate, documented source is the **`player` part** of `videos.list`. When the
request includes a `maxWidth`, YouTube returns `player.embedWidth` / `player.embedHeight`
computed from the video's true aspect ratio. Adding `player` to an existing
`videos.list` call costs **no extra quota** — it is one more part on the same call.

Orientation is derived from the ratio:

- `aspect_ratio = embedWidth / embedHeight`
- `portrait`  when `embedHeight > embedWidth`
- `landscape` when `embedWidth > embedHeight`
- `square`    when `aspect_ratio ≈ 1` (within a small tolerance)
- `unknown`   when `player` data is absent — **we do not guess** (no duration or
  thumbnail heuristic fallback)

## Components

### 1. Capture at ingest — `algorithm/integrations/youtube_ingest.py`

Three `videos.list` metadata calls currently request
`"snippet,contentDetails,statistics,status"`:

- line ~681 — `fetch_youtube_candidates` (search → metadata batch)
- line ~775 — `fetch_most_popular_candidates` (`chart=mostPopular`)
- line ~879 — `fetch_trusted_channel_candidates` (channel search → metadata batch)

For each: add `player` to the `part` string and add `maxWidth: 320` to the request
params. (The two `search` calls at ~656 / ~856 are unchanged — they carry no video
metadata; orientation comes from the `videos.list` batch that follows.)

In `_candidate_from_video_item` (~line 1340): read
`item["player"]["embedWidth"]` / `["embedHeight"]`, compute `aspect_ratio` and
`orientation` per the rules above, and add both to the candidate dict / dataclass
alongside `duration_seconds` and `thumbnail_url`. Absent/malformed `player` →
`orientation = "unknown"`, `aspect_ratio = None`.

A small pure helper, e.g. `_derive_orientation(embed_width, embed_height) -> tuple[float | None, str]`,
holds the ratio math so it is unit-testable in isolation.

### 2. Schema — `feed_videos` (SQLite + Postgres)

Add two columns to both `_CREATE_FEED_VIDEOS_*` definitions and the INSERT/UPSERT
statements:

- `aspect_ratio REAL`
- `orientation  TEXT`  (default `'unknown'`)

Existing rows: `aspect_ratio = NULL`, `orientation = 'unknown'`. Consistent with the
existing pattern where "new metadata fields are null/empty for older rows."

**Backfill script** (`algorithm/scripts/`): iterate existing `feed_videos` rows,
re-query `videos.list?part=player&maxWidth=320` in batches of 50, and update
`aspect_ratio` / `orientation`. Idempotent; safe to re-run. This turns "all landscape"
from an assumption into confirmed data.

### 3. Expose in the feed API — `algorithm/core/ranking/feed.py`

- Add `orientation` (and `aspect_ratio`) to the column SELECT in `build_feed` (~line 90).
- In `build_feed_payload` item shaping (~line 303), emit both:
  `"orientation": row.get("orientation") or "unknown"` and
  `"aspect_ratio": row.get("aspect_ratio")`. Older rows surface as `"unknown"` / `null`.
- Update the docstring field list (~line 88) to mention the new fields.

### 4. Orientation filter + feed split — feed query & API

Add an optional `orientation` filter parameter threaded from the API layer
(`algorithm/api/index.py`) into the feed load. When set (`orientation=portrait` or
`orientation=landscape`), the feed serves only rows matching that orientation; when
unset, no filtering occurs.

**Feed split (the product change):**

- The **main vertical reel feed** requests `orientation=portrait` — it becomes
  portrait-only. Vertical Shorts-style content only.
- **Landscape videos** are served as their own feed via `orientation=landscape`. This
  makes a distinct landscape feed *available from the API*.
- Rows with `orientation='unknown'` (older/un-backfilled) are treated as **portrait** by
  default so nothing silently disappears from the main feed before the backfill runs.
  Revisit once backfill is complete.

**Deferred (nav surface):** where the landscape feed *appears* in the UI — a dedicated
tab/route/section — is a fast follow-up, not part of this slice. This spec makes the
split real at the data + API level and leaves the navigation entry to green-light next.

### 5. Retire the client-side probe — `ReelCard.jsx`

Because orientation now arrives on the feed payload (Component 3) and the main feed is
portrait-only (Component 4):

- Delete `useVideoOrientation.js` and its import/usage in `ReelCard.jsx`.
- Drive `isLandscape` from the backend field:
  `const isLandscape = (reel.orientation ?? 'portrait') === 'landscape';`
- Keep the existing `reel-frame--landscape` contained/blurred-backdrop layout — it is
  the correct renderer for landscape videos, now used by the **landscape feed** rather
  than by inline detection in the main feed.

## Out of scope

- **`CroppedYouTubePlayer` crop tuning** for portrait videos (the 9:16 cover math is
  fine as-is for genuine portrait content). No change needed once the main feed is
  portrait-only.
- **Landscape-feed navigation UI** (tab/route) — deferred fast follow-up (Component 4).
- Any additional ranking-weight tuning beyond the orientation split.

## Testing

- **Unit** — `_derive_orientation`: landscape (1280×720), portrait (720×1280), square,
  and missing/zero dimensions → `unknown` / `None`.
- **Ingest** — `_candidate_from_video_item` with a `player` block populates
  `orientation`/`aspect_ratio`; with `player` absent yields `unknown`/`None`.
- **Feed** — `build_feed_payload` emits `orientation`/`aspect_ratio`; old rows without
  the columns surface as `unknown`/`null`; the `orientation` filter includes/excludes
  correctly, is a no-op when unset, and treats `unknown` as portrait.
- **Feed split** — `orientation=portrait` request excludes landscape rows;
  `orientation=landscape` request returns only landscape rows.
- **Frontend** — `ReelCard` reads `reel.orientation` (no thumbnail probe); a landscape
  reel renders the `reel-frame--landscape` layout, a portrait reel does not.
- Existing 87-test suite stays green.

## Rollout order

1. `_derive_orientation` helper + unit tests.
2. Ingest capture (part + maxWidth + candidate fields).
3. Schema columns + INSERT/UPSERT.
4. Feed SELECT + payload exposure.
5. `orientation` filter param + feed split (main = portrait, landscape feed available).
6. Retire `useVideoOrientation.js`; drive `ReelCard` from `reel.orientation`.
7. Backfill script.
