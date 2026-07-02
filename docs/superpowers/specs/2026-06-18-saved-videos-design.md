# Chrysalis "Saved" Feature — Design

**Date:** 2026-06-18
**Scope:** Save / unsave videos from the Flutter Feed, persist them, and view them in a Saved panel.

---

## 1. Problem / current behavior (root cause)

The Save button in `website/src/components/reels/ReelActionRail.jsx` is **purely visual**: it
holds a local `useState(false)`, flips a bookmark icon, and shows a toast ("Saved to your
session collection"). Nothing is persisted. The "Saved" nav slot already exists in both
`AppBottomNav` and `AppSidebar`, but its `onSaved` handler is wired to a "coming soon" toast
(`ReelsPage.jsx` lines ~510 / ~582). Result: no storage, no Saved view, no hydration across
refreshes.

## 2. Goals

Users can save videos from the feed, see saved videos later in a Saved panel, and unsave them.
Saved state persists across refreshes, is clearly reflected in the UI, never creates duplicate
rows, and keeps enough metadata to render nicely. A friendly empty state appears when nothing
is saved.

## 3. Decisions

- **Persistence:** Backend (Postgres in production via `api/index.py`, SQLite locally via
  `api.py`), mirroring the existing `/api/preferences` pattern. Not localStorage.
- **User key:** The existing anonymous `session_id` (a localStorage UUID from
  `preferences.js#getSessionId`), already passed to `/api/feed`. No auth is built. The schema
  is trivially upgradeable to a real `user_id` later (same column name conventions as
  preferences).
- **Saved view surface:** An overlay panel (`SavedPanel.jsx`) matching the existing
  `CommentsPanel` / `ProfilePanel` pattern, opened from the already-present "Saved" nav slot.
  No new routing.

## 4. Data model

New table `saved_videos`:

```
saved_videos(
  id              PK (autoincrement / serial),
  session_id      TEXT NOT NULL,
  video_id        TEXT NOT NULL,
  title           TEXT,
  channel_title   TEXT,
  thumbnail       TEXT,
  source_category TEXT,
  wellbeing       TEXT,           -- wellbeing badge / chip text, nullable
  saved_at        TIMESTAMP DEFAULT now(),
  UNIQUE(session_id, video_id)
)
```

The `UNIQUE(session_id, video_id)` constraint guarantees idempotency: a repeated save updates
metadata + `saved_at` instead of inserting a duplicate row.

## 5. Backend

New module `core/saved_videos.py` (mirrors `core/preferences.py`), providing both SQLite and
Postgres variants:

- `ensure_saved_videos_table(conn)` / `ensure_postgres_saved_videos_table(conn)`
- `upsert_saved_video(conn, session_id, video)` / `..._postgres(...)` —
  `INSERT ... ON CONFLICT(session_id, video_id) DO UPDATE`
- `delete_saved_video(conn, session_id, video_id)` / `..._postgres(...)`
- `list_saved_videos(conn, session_id)` / `..._postgres(...)` — newest first

Routes added to **both** `api.py` (SQLite) and `api/index.py` (Postgres), keeping the two
backends at parity exactly as they are for `/api/preferences` and `/api/feed`:

| Method | Route | Behavior |
|---|---|---|
| `POST` | `/api/saved` | Body `{session_id, video_id, title, channel_title, thumbnail, source_category, wellbeing}` → upsert → returns saved row |
| `DELETE` | `/api/saved/{video_id}?session_id=…` | Remove the row for that session + video |
| `GET` | `/api/saved?session_id=…` | List saved rows for the session, newest first |

Validation: `session_id` and `video_id` are required; missing/invalid input returns a 4xx, not
a 500. No secrets are exposed; the feed's language/safety filters are untouched.

Migration `migrations/013_saved_videos.sql` (Postgres, additive only). The SQLite table is
auto-created on first call via `ensure_saved_videos_table`, matching the preferences pattern.

## 6. Frontend

- **`savedVideos.js`** (new helper, alongside `preferences.js`): thin `fetch` wrappers
  `listSaved(sessionId)`, `saveVideo(sessionId, payload)`, `unsaveVideo(sessionId, videoId)`,
  plus a `cardToSavePayload(card)` normalizer. Single source of truth — no duplicate state.
- **`ReelsPage.jsx`:**
  - New state `savedIds` (a `Set` of `video_id`) and `savedCards` (array).
  - Hydrate both from `GET /api/saved` on mount (next to the existing feed fetch). If this
    fails, saved state stays empty and the feed still renders.
  - `handleToggleSaved(card)`: optimistic update of `savedIds`/`savedCards`, then backend call;
    on failure, revert and show a non-crashing toast.
  - New `savedPanelOpen` state; rewire the existing `onSaved` nav handler (lines ~510 / ~582)
    to open `SavedPanel` instead of the "coming soon" toast.
  - Pass `saved`/`onToggleSaved` down through `ReelCard` to `ReelActionRail`.
- **`ReelActionRail.jsx`:** replace the internal `useState(false)` with a **controlled**
  `saved` prop + `onToggleSaved` callback. Keep the existing toast copy.
- **`SavedPanel.jsx`** (new): overlay matching the `CommentsPanel` signature
  (`{ onClose, onStatus, savedCards, onUnsave }`). Renders each saved card with thumbnail,
  title, channel, `source_category`, wellbeing chip (when present), and `saved_at`; each row has
  an unsave button (optimistic). Friendly empty state when there are none.
- **CSS:** reuse existing panel CSS patterns; add a small `saved-panel` block.

## 7. Data flow

1. Mount → `GET /api/saved?session_id` → hydrate `savedIds` + `savedCards`.
2. Tap Save on a card → optimistic add → `POST /api/saved` → revert + toast on failure.
3. Tap Saved nav → open `SavedPanel`, rendering `savedCards`.
4. Tap unsave (panel or rail) → optimistic remove → `DELETE /api/saved/{video_id}` → revert on
   failure.
5. Refresh → re-hydrate from backend → state persists (proves persistence).

## 8. Error handling

Every fetch is wrapped. Failures revert the optimistic state and surface a non-crashing toast.
A failed hydrate leaves saved state empty without breaking the feed. Backend input errors return
4xx, not 500.

## 9. Testing / verification

- **Backend** `tests/test_saved_videos.py` (FastAPI `TestClient` + temp SQLite):
  - save a video
  - unsave a video
  - duplicate save does not create a duplicate row
  - saved list returns saved videos
  - empty saved list works
- **Frontend:** a save-toggle test (vitest is already present, e.g. `challenges.test.js`).
- **Build:** `cd website && npm run build`.
- **Smoke:** open feed → save a video → refresh → still saved → open Saved panel → appears →
  unsave → disappears.

## 10. Out of scope (must stay untouched)

- Theme / color-toggle work.
- Trust-source importer and its migrations.
- Feed language/safety filters for recommendations.

## 11. Limitations

- Saved state is scoped to the anonymous `session_id` (per browser); clearing localStorage or
  switching browsers yields a fresh saved list until real auth replaces `session_id` with
  `user_id`.
