# Split #2: Portfolio (About Me) vs Chrysalis (full app + API)

**Date:** 2026-07-01
**Supersedes the deploy topology from** `2026-07-01-repo-split-design.md`.

## Goal

The first split cut frontend-vs-backend. The actual intent is **portfolio-vs-app**:

- **Portfolio site** (`Portfolio` repo) — the About Me / marketing landing page only.
  Pure static, **no API, no algorithm components**. Has a **link/button that sends
  visitors to the Chrysalis site** for the full demo.
- **Chrysalis site** (`Chrysalis` repo) — the full app (algorithm reels feed + all
  app pages) **served together with the Python backend API** as one full-stack
  deployment at `thechrysalisproject.vercel.app`. This recreates the original
  pre-split combined app, minus the marketing landing.

## Key findings from the code

- `RebootPage.jsx` (the `/` landing) imports **no local components** and makes
  **zero API calls** — it is already self-contained and API-free.
- `LiveDemo.jsx` (which pulls in `FlutterFeed`/`Metamorphosis`/`DailyDew`) is **not
  referenced anywhere** — dead/legacy code.
- `App.jsx` cleanly separates a **marketing shell** (`Navbar`, `IntroScreen`,
  `RebootPage`, Lenis smooth-scroll) from **app routes** (`ReelsPage`, `home/`,
  `community/`, `challenges/`, `saved/`, `profile/`, auth via `AuthProvider`).
- `RebootPage.jsx:823` has `<Link to="/algorithm">` — the "see the demo" button.
  This must become an **external link** to the Chrysalis site.

## Allocation

**Portfolio repo — keep (landing only):**
- `src/App.jsx` trimmed to just `/` → `RebootPage` inside the marketing shell
  (`Navbar`, `IntroScreen`, Lenis). Drop all app routes + `AuthProvider`.
- `src/components/RebootPage.jsx` (repoint the `/algorithm` link → Chrysalis URL),
  `Navbar.jsx`, `IntroScreen.jsx`
- `src/brand.js`, `src/App.css`, `src/index.css`, `src/main.jsx`, `public/`, assets
- Delete: `reels/`, `home/`, `community/`, `challenges/`, `saved/`, `profile/`,
  `src/lib/`, `FlutterFeed.jsx`, `Metamorphosis.jsx`, `DailyDew.jsx`, `FeedCard.jsx`,
  `LiveDemo.jsx`, `auth.css`, and any unused legacy marketing components.
- **No `VITE_API_URL`** needed. Stays Vite-only.

**Chrysalis repo — add (app frontend + existing backend):**
- The app frontend under a `web/` (or `frontend/`) folder: `App.jsx` (app routes),
  `ReelsPage`/`reels/`, `home/`, `community/`, `challenges/`, `saved/`, `profile/`,
  `AuthProvider`/`lib/`, `FlutterFeed`/`Metamorphosis`/`DailyDew`/`FeedCard`,
  `brand.js`, styles, `main.jsx`, `index.html`, `package.json`, Vite config.
- Combined **full-stack `vercel.json`**: build the Vite app, route `/api/*` →
  `api/index.py`, route everything else → `index.html` (the original pre-split
  config). Frontend calls **same-origin** `/api/*`, so `VITE_API_URL=""`.

## Deployment end state

| Site | Vercel project | Framework | Env |
|---|---|---|---|
| Portfolio (About Me) | Portfolio | Vite | none (static) |
| Chrysalis (full app + API) | thechrysalisproject | Other (build web + Python fn) | `DATABASE_URL`, `YOUTUBE_API_KEY`, `CRON_SECRET`, `FEED_INGEST_SECRET` |

The About Me page's demo button → `https://thechrysalisproject.vercel.app`.

## Notes / risks

- Verify `Navbar.jsx` / `IntroScreen.jsx` don't import app-only components before
  deleting the app set from Portfolio.
- The combined Chrysalis build reintroduces a Vite build step to that repo; the
  Python function + `requirements.txt` stay as-is.
- Backup bundle from split #1 still covers the original combined history.
