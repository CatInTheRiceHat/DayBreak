# Video Orientation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture each YouTube video's landscape/portrait orientation from the reliable `player` embed dimensions, store it in `feed_videos`, expose it in the feed API, split the reel feed by orientation (main = portrait, landscape = its own feed), and retire the flaky client-side thumbnail probe.

**Architecture:** Orientation is derived at ingest from `videos.list?part=player&maxWidth=…` (`embedWidth`/`embedHeight`), persisted as two new columns (`orientation TEXT`, `aspect_ratio REAL`), surfaced on the feed payload, and used as an optional `orientation` query-filter on `GET /api/feed/{mode}`. The frontend passes `orientation=portrait` for the main feed and reads the backend field instead of probing thumbnails.

**Tech Stack:** Python 3.13 (`.venv/bin/python3.13`), SQLite + Postgres, FastAPI (`algorithm/api/index.py`), React (Vite) frontend under `algorithm/website/`. Tests: pytest.

**Interpreter for all test commands:** `cd algorithm && .venv/bin/python3.13 -m pytest …`

---

## File Structure

- `algorithm/integrations/youtube_ingest.py` — new `_derive_orientation` helper; add `player`+`maxWidth` to the three `videos.list` calls; parse orientation in `_candidate_from_video_item`; add dataclass fields; schema/migration/INSERT/SELECT changes.
- `algorithm/tests/test_youtube_ingest.py` — unit tests for `_derive_orientation` and ingest capture.
- `algorithm/core/ranking/feed.py` — emit `orientation`/`aspect_ratio` in the payload item.
- `algorithm/api/index.py` — optional `orientation` query param + row filter (unknown→portrait).
- `algorithm/tests/test_feed_orientation.py` — new: payload exposure + filter behavior.
- `algorithm/scripts/backfill_orientation.py` — new: backfill existing rows.
- `algorithm/website/src/components/reels/ReelCard.jsx` — read `reel.orientation`, drop the probe.
- `algorithm/website/src/components/reels/useVideoOrientation.js` — deleted.
- `algorithm/website/src/components/reels/ReelsPage.jsx` — carry `orientation` in `apiItemToCard`; send `orientation=portrait` on the main feed fetch.

---

## Task 1: `_derive_orientation` helper

**Files:**
- Modify: `algorithm/integrations/youtube_ingest.py` (add helper near `_safe_int`, ~line 1749)
- Test: `algorithm/tests/test_youtube_ingest.py`

- [ ] **Step 1: Write the failing test**

Add to `algorithm/tests/test_youtube_ingest.py`:

```python
from integrations.youtube_ingest import _derive_orientation


def test_derive_orientation_landscape():
    assert _derive_orientation(1280, 720) == (pytest.approx(1280 / 720), "landscape")


def test_derive_orientation_portrait():
    assert _derive_orientation(720, 1280) == (pytest.approx(720 / 1280), "portrait")


def test_derive_orientation_square():
    ratio, label = _derive_orientation(300, 300)
    assert label == "square"
    assert ratio == pytest.approx(1.0)


def test_derive_orientation_missing_or_zero():
    assert _derive_orientation(None, None) == (None, "unknown")
    assert _derive_orientation(0, 720) == (None, "unknown")
    assert _derive_orientation(1280, 0) == (None, "unknown")
```

Ensure `import pytest` is present at the top of the file (it is used elsewhere; add if missing).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithm && .venv/bin/python3.13 -m pytest tests/test_youtube_ingest.py::test_derive_orientation_landscape -v`
Expected: FAIL with `ImportError: cannot import name '_derive_orientation'`

- [ ] **Step 3: Write minimal implementation**

Add to `algorithm/integrations/youtube_ingest.py` (just below `_safe_int`):

```python
def _derive_orientation(
    embed_width: int | None,
    embed_height: int | None,
) -> tuple[float | None, str]:
    """Classify a video's orientation from its YouTube embed dimensions.

    `videos.list?part=player&maxWidth=...` returns embedWidth/embedHeight that
    reflect the video's true aspect ratio (thumbnails are unreliable for Shorts).
    Returns (aspect_ratio, orientation). Missing/zero dims -> (None, "unknown");
    we never guess from duration or thumbnails.
    """
    w = _safe_int(embed_width)
    h = _safe_int(embed_height)
    if w <= 0 or h <= 0:
        return None, "unknown"
    ratio = w / h
    if ratio >= 1.05:
        orientation = "landscape"
    elif ratio <= 0.95:
        orientation = "portrait"
    else:
        orientation = "square"
    return ratio, orientation
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithm && .venv/bin/python3.13 -m pytest tests/test_youtube_ingest.py -k derive_orientation -v`
Expected: 4 passing

- [ ] **Step 5: Commit**

```bash
git add algorithm/integrations/youtube_ingest.py algorithm/tests/test_youtube_ingest.py
git commit -m "feat: _derive_orientation helper from YouTube embed dimensions"
```

---

## Task 2: Capture orientation at ingest

**Files:**
- Modify: `algorithm/integrations/youtube_ingest.py` — three `videos.list` calls (~681, ~775, ~879), `_candidate_from_video_item` (~1340–1460), `FeedVideoCandidate` dataclass (~230–252)
- Test: `algorithm/tests/test_youtube_ingest.py`

- [ ] **Step 1: Write the failing test**

Add to `algorithm/tests/test_youtube_ingest.py`. First extend the `_video` fixture to accept an optional player block (add the parameter and the `player` key):

```python
def _video(
    video_id: str,
    title: str,
    duration: str = "PT1M20S",
    views: str = "12000",
    description: str | None = None,
    player: dict | None = None,   # NEW
) -> dict:
    item = {
        "id": video_id,
        "snippet": { ... },        # unchanged existing snippet
        "contentDetails": {"duration": duration},
        "statistics": {"viewCount": views},
        "status": { ... },          # unchanged existing status
    }
    if player is not None:
        item["player"] = player
    return item
```

(Keep the existing `snippet`/`status` bodies exactly as they are; only add the
`player` parameter and the trailing `if player` block.)

Then add the test:

```python
from integrations.youtube_ingest import _candidate_from_video_item
import datetime as _dt


def test_candidate_captures_orientation_from_player():
    item = _video(
        "vid_landscape",
        "Calm study reset tips for students",
        player={"embedWidth": 1280, "embedHeight": 720},
    )
    candidate = _candidate_from_video_item(
        item,
        source_category="study",
        source_query="student focus",
        now=_dt.datetime(2026, 7, 2, tzinfo=_dt.timezone.utc),
        days_back=365,
    )
    assert candidate is not None
    assert candidate.orientation == "landscape"
    assert candidate.aspect_ratio == pytest.approx(1280 / 720)


def test_candidate_orientation_unknown_without_player():
    item = _video("vid_noplayer", "Calm study reset tips for students")
    candidate = _candidate_from_video_item(
        item,
        source_category="study",
        source_query="student focus",
        now=_dt.datetime(2026, 7, 2, tzinfo=_dt.timezone.utc),
        days_back=365,
    )
    assert candidate is not None
    assert candidate.orientation == "unknown"
    assert candidate.aspect_ratio is None
```

> Note: confirm the real signature of `_candidate_from_video_item` at ~line 1340
> and match its keyword arguments exactly (it takes `item`, `source_category`,
> `source_query`, `now`, `days_back`). Adjust the call above if the signature
> differs; do not change the function's parameters in this step.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithm && .venv/bin/python3.13 -m pytest tests/test_youtube_ingest.py::test_candidate_captures_orientation_from_player -v`
Expected: FAIL — `AttributeError: 'FeedVideoCandidate' object has no attribute 'orientation'`

- [ ] **Step 3a: Add dataclass fields**

In `FeedVideoCandidate` (append after `popularity_score: float = 0.0`, ~line 252):

```python
    # Orientation derived from the YouTube player embed dimensions at ingest.
    # Defaulted so older call sites / deserializers keep working; "unknown" when
    # the player block is absent.
    orientation: str = "unknown"
    aspect_ratio: float | None = None
```

- [ ] **Step 3b: Parse orientation in `_candidate_from_video_item`**

Near where `thumbnail_url = _best_thumbnail(snippet)` is computed (~line 1385), add:

```python
    player = item.get("player") or {}
    aspect_ratio, orientation = _derive_orientation(
        player.get("embedWidth"), player.get("embedHeight")
    )
```

Then in the `return FeedVideoCandidate(...)` construction (~line 1421), add the two
fields (anywhere among the keyword args, e.g. after `popularity_score=...` if
present, otherwise near `duration_seconds=`):

```python
        orientation=orientation,
        aspect_ratio=aspect_ratio,
```

- [ ] **Step 3c: Request the `player` part on all three `videos.list` calls**

For each of these three `request("videos", { ... })` calls, change the `part` value
and add `maxWidth`:

- `fetch_youtube_candidates` (~line 681)
- `fetch_most_popular_candidates` (~line 775)
- `fetch_trusted_channel_candidates` (~line 879)

Change:

```python
            "part": "snippet,contentDetails,statistics,status",
```
to:
```python
            "part": "snippet,contentDetails,statistics,status,player",
            "maxWidth": 320,
```

(The two `request("search", …)` calls at ~656 and ~856 are unchanged — search items
carry no player data; orientation comes from the `videos.list` metadata batch.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithm && .venv/bin/python3.13 -m pytest tests/test_youtube_ingest.py -k orientation -v`
Expected: all orientation tests pass

- [ ] **Step 5: Commit**

```bash
git add algorithm/integrations/youtube_ingest.py algorithm/tests/test_youtube_ingest.py
git commit -m "feat: capture video orientation from player embed dims at ingest"
```

---

## Task 3: Persist orientation columns (schema + migration + INSERT)

**Files:**
- Modify: `algorithm/integrations/youtube_ingest.py` — `_CREATE_FEED_VIDEOS_SQLITE`/`_POSTGRES` (~282, ~326), `_ensure_sqlite_feed_video_columns` (~434), `ensure_postgres_feed_videos_table` (~457), SQLite INSERT (~1478), Postgres INSERT (~1537), `_candidate_sqlite_values` (~1600–1637)
- Test: `algorithm/tests/test_youtube_ingest.py`

- [ ] **Step 1: Write the failing test**

The existing `test_youtube_ingest_stores_filtered_real_videos_without_duplicate_inserts`
runs the full SQLite ingest. Add a focused assertion by writing a new test that ingests
one video with a player block and reads the stored column. Add to
`algorithm/tests/test_youtube_ingest.py`:

```python
import sqlite3
from integrations.youtube_ingest import (
    ensure_sqlite_feed_videos_table,
    _insert_or_update_feed_video_sqlite,
    _candidate_from_video_item,
)


def test_orientation_persists_to_sqlite(tmp_path):
    conn = sqlite3.connect(tmp_path / "feed.db")
    ensure_sqlite_feed_videos_table(conn)
    item = _video(
        "vid_persist",
        "Calm study reset tips for students",
        player={"embedWidth": 720, "embedHeight": 1280},
    )
    candidate = _candidate_from_video_item(
        item, source_category="study", source_query="focus",
        now=_dt.datetime(2026, 7, 2, tzinfo=_dt.timezone.utc), days_back=365,
    )
    _insert_or_update_feed_video_sqlite(conn, candidate)
    row = conn.execute(
        "SELECT orientation, aspect_ratio FROM feed_videos WHERE youtube_video_id = ?",
        ("vid_persist",),
    ).fetchone()
    assert row[0] == "portrait"
    assert row[1] == pytest.approx(720 / 1280)
```

> Confirm the real name of the SQLite insert function near line 1478 (it may be
> `_insert_or_update_feed_video_sqlite` or similar) and the table-ensure function
> near line 408; match the actual names.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithm && .venv/bin/python3.13 -m pytest tests/test_youtube_ingest.py::test_orientation_persists_to_sqlite -v`
Expected: FAIL — `sqlite3.OperationalError: no such column: orientation`

- [ ] **Step 3a: Add columns to both CREATE TABLE definitions**

In `_CREATE_FEED_VIDEOS_SQLITE` (after `duration_seconds INTEGER,` ~line 286) add:

```sql
    orientation         TEXT DEFAULT 'unknown',
    aspect_ratio        REAL,
```

In `_CREATE_FEED_VIDEOS_POSTGRES` (after `duration_seconds INTEGER,` ~line 330) add the
same two lines.

- [ ] **Step 3b: Add ADD COLUMN migrations**

In `_ensure_sqlite_feed_video_columns` (~line 439) add to the dict:

```python
        "orientation": "TEXT DEFAULT 'unknown'",
        "aspect_ratio": "REAL",
```

In `ensure_postgres_feed_videos_table` (~line 464, alongside the other ADD COLUMNs) add:

```python
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS orientation TEXT DEFAULT 'unknown'")
    cur.execute("ALTER TABLE feed_videos ADD COLUMN IF NOT EXISTS aspect_ratio REAL")
```

- [ ] **Step 3c: Add columns to both INSERT statements**

SQLite INSERT (~line 1478): bump the placeholder count and add the two columns.

Change `placeholders = ",".join(["?"] * 39)` → `["?"] * 41`.
In the column list, change the tail:
```sql
            source_type, popularity_score
```
to:
```sql
            source_type, popularity_score,
            orientation, aspect_ratio
```
Add to the `ON CONFLICT(youtube_video_id) DO UPDATE SET` block:
```sql
            orientation = excluded.orientation,
            aspect_ratio = excluded.aspect_ratio,
```
(place before the final line so trailing commas stay valid).

Postgres INSERT (~line 1537): change `placeholders = ["%s"] * 39` → `["%s"] * 41`, add
the same two columns to the column list tail and the same two `ON CONFLICT … DO UPDATE
SET` lines.

- [ ] **Step 3d: Add the two values to the value tuple**

In `_candidate_sqlite_values` (~line 1600), append after `candidate.popularity_score,`:

```python
        candidate.orientation,
        candidate.aspect_ratio,
```

(`_candidate_postgres_values` reuses `_candidate_sqlite_values`, so no separate change.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithm && .venv/bin/python3.13 -m pytest tests/test_youtube_ingest.py -v`
Expected: new test passes; existing ingest tests still pass.

- [ ] **Step 5: Commit**

```bash
git add algorithm/integrations/youtube_ingest.py algorithm/tests/test_youtube_ingest.py
git commit -m "feat: persist orientation + aspect_ratio columns to feed_videos"
```

---

## Task 4: Load + expose orientation in the feed payload

**Files:**
- Modify: `algorithm/integrations/youtube_ingest.py` — `_active_feed_video_rows_sql` (~1130), `_missing_optional_feed_video_column` (~1264)
- Modify: `algorithm/core/ranking/feed.py` — payload item build (~303)
- Test: `algorithm/tests/test_feed_orientation.py` (new)

- [ ] **Step 1: Write the failing test**

Create `algorithm/tests/test_feed_orientation.py`:

```python
import pytest
from core.ranking.feed import build_feed_payload


def _row(vid, orientation):
    return {
        "video_id": vid,
        "title": f"Title {vid}",
        "description": "A calm, supportive clip about student wellbeing and focus.",
        "orientation": orientation,
        "aspect_ratio": 0.5625 if orientation == "portrait" else 1.7777,
        "duration_seconds": 40,
        "thumbnail_url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        "embed_url": f"https://www.youtube-nocookie.com/embed/{vid}",
        "watch_url": f"https://www.youtube.com/watch?v={vid}",
    }


def test_payload_exposes_orientation():
    payload = build_feed_payload(
        [_row("aaa", "portrait"), _row("bbb", "landscape")],
        "flutter-feed",
        k=12,
    )
    by_id = {it["youtube_id"]: it for it in payload["items"]}
    assert by_id["aaa"]["orientation"] == "portrait"
    assert by_id["bbb"]["orientation"] == "landscape"
    assert by_id["bbb"]["aspect_ratio"] == pytest.approx(1.7777)
```

> Confirm `build_feed_payload`'s return shape (it returns a dict with an `items`
> list — see `api/index.py` usage). Adjust `payload["items"]` if the key differs.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithm && .venv/bin/python3.13 -m pytest tests/test_feed_orientation.py::test_payload_exposes_orientation -v`
Expected: FAIL — `KeyError: 'orientation'`

- [ ] **Step 3a: Emit fields in the payload item**

In `algorithm/core/ranking/feed.py`, in the `items.append({...})` block (~line 303),
add near `"duration_seconds": ...`:

```python
            "orientation": row.get("orientation") or "unknown",
            "aspect_ratio": row.get("aspect_ratio"),
```

- [ ] **Step 3b: Select the columns from the DB (optional-column group)**

In `algorithm/integrations/youtube_ingest.py`, `_active_feed_video_rows_sql`
(~line 1130): add a parameter `include_orientation_metadata: bool = True`, build the
group, and insert it into the SELECT.

Add the branch (near the other column groups):

```python
    if include_orientation_metadata:
        orientation_columns = "orientation,\n            aspect_ratio,"
    else:
        orientation_columns = (
            "'unknown' AS orientation,\n            NULL AS aspect_ratio,"
        )
```

In the returned SQL, add `{orientation_columns}` immediately after
`{popularity_columns}` (so it sits alongside the other optional groups).

Add `include_orientation_metadata` to every dict returned by
`_active_feed_video_column_attempts()` (~line 1213): set it `True` in the fully-featured
attempts and `False` in the most-degraded fallback attempt, matching how
`include_popularity_metadata` is toggled.

Extend `_missing_optional_feed_video_column` (~line 1264) to include:

```python
        or "orientation" in message
        or "aspect_ratio" in message
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithm && .venv/bin/python3.13 -m pytest tests/test_feed_orientation.py tests/test_youtube_ingest.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add algorithm/integrations/youtube_ingest.py algorithm/core/ranking/feed.py algorithm/tests/test_feed_orientation.py
git commit -m "feat: load and expose orientation/aspect_ratio in feed payload"
```

---

## Task 5: Orientation filter + feed split on the API

**Files:**
- Modify: `algorithm/api/index.py` — `chrysalis_feed` endpoint (~277–341)
- Test: `algorithm/tests/test_feed_orientation.py`

- [ ] **Step 1: Write the failing test**

Add to `algorithm/tests/test_feed_orientation.py` a unit test for a pure filter helper
(we filter rows before ranking, treating `unknown` as portrait):

```python
from api.index import _filter_rows_by_orientation


def test_filter_rows_by_orientation():
    rows = [
        {"video_id": "p1", "orientation": "portrait"},
        {"video_id": "l1", "orientation": "landscape"},
        {"video_id": "u1", "orientation": "unknown"},
        {"video_id": "n1"},  # missing -> treated as portrait
    ]
    portrait_ids = {r["video_id"] for r in _filter_rows_by_orientation(rows, "portrait")}
    assert portrait_ids == {"p1", "u1", "n1"}

    landscape_ids = {r["video_id"] for r in _filter_rows_by_orientation(rows, "landscape")}
    assert landscape_ids == {"l1"}

    # None / unrecognized -> no filtering
    assert _filter_rows_by_orientation(rows, None) == rows
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd algorithm && .venv/bin/python3.13 -m pytest tests/test_feed_orientation.py::test_filter_rows_by_orientation -v`
Expected: FAIL — `ImportError: cannot import name '_filter_rows_by_orientation'`

- [ ] **Step 3a: Add the filter helper**

In `algorithm/api/index.py` (near `_parse_exclude_ids`, ~line 256):

```python
def _filter_rows_by_orientation(rows: list[dict], orientation: str | None) -> list[dict]:
    """Keep only rows matching `orientation`. Rows with unknown/missing
    orientation count as portrait so nothing vanishes before the backfill runs.
    A None/unrecognized value applies no filter (backward compatible)."""
    if orientation not in ("portrait", "landscape"):
        return rows

    def _row_orientation(row: dict) -> str:
        value = (row.get("orientation") or "unknown").lower()
        return "portrait" if value in ("unknown", "square") else value

    return [row for row in rows if _row_orientation(row) == orientation]
```

- [ ] **Step 3b: Wire the query param into the endpoint**

In `chrysalis_feed` (~line 278) add `orientation: str | None = None` to the signature
(after `exclude_ids`). After `rows = merge_primary_rows(feed_rows, legacy_rows)`
(~line 315) — or immediately before the `build_feed_payload` call — apply:

```python
        rows = _filter_rows_by_orientation(rows, orientation)
```

Place it so the filter runs on the final `rows` list that is passed to
`build_feed_payload`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd algorithm && .venv/bin/python3.13 -m pytest tests/test_feed_orientation.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add algorithm/api/index.py algorithm/tests/test_feed_orientation.py
git commit -m "feat: orientation query filter on /api/feed (unknown treated as portrait)"
```

---

## Task 6: Frontend — retire the probe, drive from backend, portrait-only main feed

**Files:**
- Modify: `algorithm/website/src/components/reels/ReelCard.jsx` (lines 10, 104–105, 163–171)
- Delete: `algorithm/website/src/components/reels/useVideoOrientation.js`
- Modify: `algorithm/website/src/components/reels/ReelsPage.jsx` (`apiItemToCard` ~117, `loadPage` params ~370)

> This UI code has no unit test harness in-repo; verify by build + manual smoke.
> Do the edits, then run the frontend build to confirm nothing references the
> deleted module.

- [ ] **Step 1: Carry orientation through the item mapper**

In `ReelsPage.jsx` `apiItemToCard` (~line 165, inside the returned object), add:

```javascript
    orientation: item.orientation || 'unknown',
```

- [ ] **Step 2: Send `orientation=portrait` on the main feed fetch**

In `ReelsPage.jsx` `loadPage` (~line 370), after the other `params.set(...)` calls and
before the `fetch`, add:

```javascript
      params.set('orientation', 'portrait');
```

- [ ] **Step 3: Drive `ReelCard` from the backend field**

In `ReelCard.jsx`:

- Delete the import at line 10:
  `import { useVideoOrientation } from './useVideoOrientation';`
- Replace lines 104–105:
  ```javascript
    const orientation = useVideoOrientation(hasVideo ? ytId : null);
    const isLandscape = orientation === 'landscape';
  ```
  with:
  ```javascript
    const isLandscape = (reel.orientation ?? 'portrait') === 'landscape';
  ```

Leave the `reel-frame--landscape` layout and `reel-backdrop` block (lines 163–171)
unchanged — they are the correct renderer for landscape videos in the landscape feed.

- [ ] **Step 4: Delete the probe module**

```bash
git rm algorithm/website/src/components/reels/useVideoOrientation.js
```

- [ ] **Step 5: Verify build has no dangling references**

Run:
```bash
cd algorithm/website && npm run build
```
Expected: build succeeds, no "Could not resolve ./useVideoOrientation" error.
Also confirm: `grep -rn "useVideoOrientation" algorithm/website/src` returns nothing.

- [ ] **Step 6: Commit**

```bash
git add algorithm/website/src/components/reels/ReelCard.jsx algorithm/website/src/components/reels/ReelsPage.jsx
git commit -m "feat: main reel feed is portrait-only; ReelCard uses backend orientation"
```

---

## Task 7: Backfill script for existing rows

**Files:**
- Create: `algorithm/scripts/backfill_orientation.py`

> Existing rows have `orientation='unknown'`. This script re-queries the `player`
> part for their YouTube ids in batches of 50 and updates the columns. Idempotent.

- [ ] **Step 1: Write the script**

Create `algorithm/scripts/backfill_orientation.py`:

```python
"""Backfill orientation/aspect_ratio for existing feed_videos rows.

Re-queries videos.list?part=player&maxWidth=320 for rows still marked
orientation='unknown' and updates them. Safe to re-run.

Usage:
    .venv/bin/python3.13 scripts/backfill_orientation.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.youtube_ingest import _derive_orientation, _chunks
from integrations.youtube_service import request  # existing YouTube request helper


def _load_ids_needing_backfill(conn) -> list[str]:
    cur = conn.cursor()
    cur.execute(
        "SELECT youtube_video_id FROM feed_videos "
        "WHERE orientation IS NULL OR orientation = 'unknown'"
    )
    return [r[0] for r in cur.fetchall()]


def backfill(conn) -> int:
    ids = _load_ids_needing_backfill(conn)
    updated = 0
    for batch in _chunks(ids, 50):
        data = request("videos", {"part": "player", "id": ",".join(batch), "maxWidth": 320})
        for item in data.get("items", []):
            player = item.get("player") or {}
            aspect_ratio, orientation = _derive_orientation(
                player.get("embedWidth"), player.get("embedHeight")
            )
            if orientation == "unknown":
                continue
            conn.execute(
                "UPDATE feed_videos SET orientation = %s, aspect_ratio = %s "
                "WHERE youtube_video_id = %s",
                (orientation, aspect_ratio, item["id"]),
            )
            updated += 1
    conn.commit()
    return updated


if __name__ == "__main__":
    from api.index import get_db  # reuse the app's DB connection factory

    conn = get_db()
    try:
        count = backfill(conn)
        print(f"[backfill_orientation] updated {count} rows")
    finally:
        conn.close()
```

> Confirm the actual names of: the YouTube request helper (`request` — check
> `integrations/youtube_service.py`), the placeholder style for the target DB
> (Postgres uses `%s`; if run against SQLite use `?`), and `get_db` in
> `api/index.py`. Adjust imports/placeholders to match. If the request helper is
> not importable standalone, mirror the call style used in `fetch_youtube_candidates`.

- [ ] **Step 2: Smoke-run (dry check)**

Run: `cd algorithm && .venv/bin/python3.13 -c "import scripts.backfill_orientation"`
Expected: imports cleanly (no syntax/import errors).

- [ ] **Step 3: Commit**

```bash
git add algorithm/scripts/backfill_orientation.py
git commit -m "feat: backfill script for orientation on existing feed_videos rows"
```

---

## Final verification

- [ ] Run the full suite:
  `cd algorithm && .venv/bin/python3.13 -m pytest -q`
  Expected: all previously-green tests still pass, plus the new orientation tests.
- [ ] Frontend build clean: `cd algorithm/website && npm run build`.
- [ ] Manual smoke: run the app, confirm the main feed shows portrait videos and no
  console reference to `useVideoOrientation`.

## Deferred (not in this plan)

- The landscape feed's **navigation surface** (tab/route that fetches
  `orientation=landscape`). The API + data support it; the UI entry point is a fast
  follow-up.
- Any ranking-weight tuning beyond the portrait/landscape split.
