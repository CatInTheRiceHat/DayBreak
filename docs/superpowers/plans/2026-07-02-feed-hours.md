# The Feed Has Hours — Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the intention modes and give the feed *hours* — it opens at (approximate) sunrise and hard-closes at (approximate) sunset in the device's local time, with a 5-minute warning and a calm closed "gateway" screen.

**Architecture:** A pure logic module (`src/lib/feedHours.js`) computes sun times from the device time zone + an assumed latitude and evaluates open/closed. A thin hook (`useFeedHours`) exposes it to React and re-evaluates on an interval. `ReelsPage` renders a `ClosedGateway` when closed, or the feed plus a `CloseWarning` banner when open. The mode picker is hidden via the existing `SKIP_ALGORITHM_ONBOARDING` flag.

**Tech Stack:** React (Vite), `motion/react` (Framer Motion), Node's built-in test runner (`node --test`, run via `npm run test:unit`). No new dependencies.

## Global Constraints

- All work is under `algorithm/website/`. Run commands from there.
- Tests use Node's built-in runner: `import test from 'node:test'; import assert from 'node:assert/strict';`. Run with `npm run test:unit`.
- No location, no permission prompt, nothing stored. Sun times are **approximate**: assumed latitude `ASSUMED_LATITUDE = 40.4` (northern), longitude from the time-zone central meridian (`-(new Date).getTimezoneOffset()/60 * 15`). Southern-hemisphere seasonal drift will be inverted — accepted.
- `CLOSE_WARNING_MINUTES = 5`.
- Fallback when the sun can't be computed (polar / degenerate): fixed local `FALLBACK_OPEN_HOUR = 7`, `FALLBACK_CLOSE_HOUR = 19`.
- **Hard close** — no override; closed until the next sunrise.
- Do **not** modify the diagnostic survey internals; only stop surfacing modes.
- No new npm dependencies.

---

### Task 1: Pure feed-hours logic + tests

**Files:**
- Create: `algorithm/website/src/lib/feedHours.js`
- Test: `algorithm/website/src/lib/feedHours.test.js`
- Modify: `algorithm/website/package.json` (extend the `test:unit` glob)

**Interfaces:**
- Produces:
  - `sunTimes({ date: Date, latitude: number, longitude: number }) -> { sunrise: Date, sunset: Date } | null` (null = sun never rises/sets that day).
  - `evaluateFeedHours({ now: Date, sunrise: Date, sunset: Date, nextSunrise: Date, warningMinutes?: number }) -> { isOpen: boolean, closesAt: Date, nextOpen: Date, minutesUntilClose: number, inWarning: boolean }`.
  - `feedHoursNow(now: Date) -> { isOpen, closesAt, nextOpen, minutesUntilClose, inWarning }` — composes the two using the time-zone longitude + assumed latitude, with the fixed-hours fallback.
  - Constants `CLOSE_WARNING_MINUTES`, `ASSUMED_LATITUDE`, `FALLBACK_OPEN_HOUR`, `FALLBACK_CLOSE_HOUR`.

- [ ] **Step 1: Extend the test glob**

In `algorithm/website/package.json`, change the `test:unit` script from:
```json
"test:unit": "node --test src/components/reels/*.test.js src/components/diagnostic/*.test.js",
```
to:
```json
"test:unit": "node --test src/lib/*.test.js src/components/reels/*.test.js src/components/diagnostic/*.test.js",
```

- [ ] **Step 2: Write the failing tests**

Create `algorithm/website/src/lib/feedHours.test.js`:
```js
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  sunTimes,
  evaluateFeedHours,
  CLOSE_WARNING_MINUTES,
} from './feedHours.js';

const hours = (a, b) => (b.getTime() - a.getTime()) / 3600000;

test('sunrise is before sunset at a temperate latitude', () => {
  const { sunrise, sunset } = sunTimes({
    date: new Date('2026-06-21T12:00:00Z'), latitude: 40.4, longitude: -75,
  });
  assert.ok(sunrise < sunset);
});

test('days are long in summer and short in winter at 40N', () => {
  const summer = sunTimes({ date: new Date('2026-06-21T12:00:00Z'), latitude: 40.4, longitude: 0 });
  const winter = sunTimes({ date: new Date('2026-12-21T12:00:00Z'), latitude: 40.4, longitude: 0 });
  assert.ok(hours(summer.sunrise, summer.sunset) > 14, 'summer day > 14h');
  assert.ok(hours(winter.sunrise, winter.sunset) < 10, 'winter day < 10h');
});

test('the equator is ~12h of daylight year-round', () => {
  const d = sunTimes({ date: new Date('2026-06-21T12:00:00Z'), latitude: 0, longitude: 0 });
  const len = hours(d.sunrise, d.sunset);
  assert.ok(len > 11.5 && len < 12.5, `equator day length ${len}`);
});

test('polar latitudes return null (no sunrise/sunset)', () => {
  assert.equal(sunTimes({ date: new Date('2026-12-21T12:00:00Z'), latitude: 80, longitude: 0 }), null);
  assert.equal(sunTimes({ date: new Date('2026-06-21T12:00:00Z'), latitude: 80, longitude: 0 }), null);
});

test('evaluateFeedHours: open between sunrise and sunset', () => {
  const sunrise = new Date('2026-06-21T06:00:00Z');
  const sunset = new Date('2026-06-21T20:00:00Z');
  const nextSunrise = new Date('2026-06-22T06:00:00Z');
  const r = evaluateFeedHours({ now: new Date('2026-06-21T12:00:00Z'), sunrise, sunset, nextSunrise });
  assert.equal(r.isOpen, true);
  assert.equal(r.minutesUntilClose, 8 * 60);
  assert.equal(r.inWarning, false);
  assert.equal(r.closesAt.getTime(), sunset.getTime());
});

test('evaluateFeedHours: inWarning within the last 5 minutes', () => {
  const sunrise = new Date('2026-06-21T06:00:00Z');
  const sunset = new Date('2026-06-21T20:00:00Z');
  const nextSunrise = new Date('2026-06-22T06:00:00Z');
  const r = evaluateFeedHours({ now: new Date('2026-06-21T19:57:00Z'), sunrise, sunset, nextSunrise });
  assert.equal(r.isOpen, true);
  assert.equal(r.inWarning, true);
  assert.equal(r.minutesUntilClose, 3);
});

test('evaluateFeedHours: before sunrise → closed, next open is today sunrise', () => {
  const sunrise = new Date('2026-06-21T06:00:00Z');
  const sunset = new Date('2026-06-21T20:00:00Z');
  const nextSunrise = new Date('2026-06-22T06:00:00Z');
  const r = evaluateFeedHours({ now: new Date('2026-06-21T04:00:00Z'), sunrise, sunset, nextSunrise });
  assert.equal(r.isOpen, false);
  assert.equal(r.nextOpen.getTime(), sunrise.getTime());
});

test('evaluateFeedHours: after sunset → closed, next open is tomorrow sunrise', () => {
  const sunrise = new Date('2026-06-21T06:00:00Z');
  const sunset = new Date('2026-06-21T20:00:00Z');
  const nextSunrise = new Date('2026-06-22T06:00:00Z');
  const r = evaluateFeedHours({ now: new Date('2026-06-21T21:00:00Z'), sunrise, sunset, nextSunrise });
  assert.equal(r.isOpen, false);
  assert.equal(r.nextOpen.getTime(), nextSunrise.getTime());
});

test('CLOSE_WARNING_MINUTES is 5', () => {
  assert.equal(CLOSE_WARNING_MINUTES, 5);
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd /Users/elaine/Documents/Chrysalis/algorithm/website && npm run test:unit`
Expected: FAIL — `Cannot find module './feedHours.js'` (or export errors).

- [ ] **Step 4: Implement `src/lib/feedHours.js`**

Create `algorithm/website/src/lib/feedHours.js`:
```js
// The feed's hours. Pure, no React, no network. Sun times are approximate:
// we never ask for location — latitude is assumed, longitude is derived from
// the device time-zone offset. See the phase-1 spec.

export const CLOSE_WARNING_MINUTES = 5;
export const ASSUMED_LATITUDE = 40.4;   // northern temperate; southern drift is inverted
export const FALLBACK_OPEN_HOUR = 7;    // used when the sun can't be computed
export const FALLBACK_CLOSE_HOUR = 19;

const DEG = Math.PI / 180;
const toJulian = (date) => date.valueOf() / 86400000 + 2440587.5;
const fromJulian = (j) => new Date((j - 2440587.5) * 86400000);

/**
 * Sunrise/sunset for the UTC calendar day of `date` at a lat/lng, via the
 * standard "sunrise equation" (accurate to ~1-2 min). Returns Date objects
 * (correct real instants), or null when the sun never rises/sets that day.
 */
export function sunTimes({ date, latitude, longitude }) {
  const lw = -longitude; // west-positive
  const jd = toJulian(date);
  const n = Math.round(jd - 2451545.0 - 0.0009 - lw / 360);
  const meanAnomalyDeg = (357.5291 + 0.98560028 * n) % 360;
  const M = meanAnomalyDeg * DEG;
  const center =
    1.9148 * Math.sin(M) + 0.02 * Math.sin(2 * M) + 0.0003 * Math.sin(3 * M);
  const eclipticLonDeg = (meanAnomalyDeg + center + 180 + 102.9372) % 360;
  const L = eclipticLonDeg * DEG;
  const transit =
    2451545.0 +
    n +
    0.0009 +
    lw / 360 +
    0.0053 * Math.sin(M) -
    0.0069 * Math.sin(2 * L);
  const declination = Math.asin(Math.sin(L) * Math.sin(23.4397 * DEG));
  const latRad = latitude * DEG;
  const cosH =
    (Math.sin(-0.833 * DEG) - Math.sin(latRad) * Math.sin(declination)) /
    (Math.cos(latRad) * Math.cos(declination));
  if (cosH > 1 || cosH < -1) return null; // polar night / midnight sun
  const H = Math.acos(cosH) / DEG / 360; // fraction of a day
  return {
    sunrise: fromJulian(transit - H),
    sunset: fromJulian(transit + H),
  };
}

/**
 * Given `now` plus today's sunrise/sunset and tomorrow's sunrise, decide whether
 * the feed is open and when it next changes.
 */
export function evaluateFeedHours({
  now,
  sunrise,
  sunset,
  nextSunrise,
  warningMinutes = CLOSE_WARNING_MINUTES,
}) {
  const isOpen = now >= sunrise && now < sunset;
  const minutesUntilClose = isOpen
    ? Math.round((sunset.getTime() - now.getTime()) / 60000)
    : 0;
  const nextOpen = now < sunrise ? sunrise : nextSunrise;
  return {
    isOpen,
    closesAt: sunset,
    nextOpen,
    minutesUntilClose,
    inWarning: isOpen && minutesUntilClose <= warningMinutes,
  };
}

// Longitude implied by the device time-zone offset (central meridian).
function timezoneLongitude(now) {
  return -(now.getTimezoneOffset() / 60) * 15;
}

// A local-time Date at HH:00 on the same calendar day as `ref`.
function localHour(ref, hour) {
  const d = new Date(ref);
  d.setHours(hour, 0, 0, 0);
  return d;
}

/**
 * The live open/closed state for `now`, using the time-zone longitude + assumed
 * latitude, and falling back to fixed hours when the sun can't be computed.
 */
export function feedHoursNow(now = new Date()) {
  const longitude = timezoneLongitude(now);
  const today = sunTimes({ date: now, latitude: ASSUMED_LATITUDE, longitude });
  const tomorrow = sunTimes({
    date: new Date(now.getTime() + 86400000),
    latitude: ASSUMED_LATITUDE,
    longitude,
  });

  if (!today || !tomorrow) {
    const sunrise = localHour(now, FALLBACK_OPEN_HOUR);
    const sunset = localHour(now, FALLBACK_CLOSE_HOUR);
    const nextSunrise = new Date(sunrise.getTime() + 86400000);
    return evaluateFeedHours({ now, sunrise, sunset, nextSunrise });
  }

  return evaluateFeedHours({
    now,
    sunrise: today.sunrise,
    sunset: today.sunset,
    nextSunrise: tomorrow.sunrise,
  });
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /Users/elaine/Documents/Chrysalis/algorithm/website && npm run test:unit`
Expected: PASS — the new `feedHours.test.js` cases plus all pre-existing tests.
If a `sunTimes` property test fails, the formula is off — debug the astronomy, do not weaken the assertion.

- [ ] **Step 6: Commit**

```bash
git add algorithm/website/src/lib/feedHours.js algorithm/website/src/lib/feedHours.test.js algorithm/website/package.json
git commit -m "feat: feed-hours logic — approximate sun times + open/close evaluation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `useFeedHours` hook

**Files:**
- Create: `algorithm/website/src/lib/useFeedHours.js`

**Interfaces:**
- Consumes: `feedHoursNow(now)` (Task 1).
- Produces: `useFeedHours() -> { isOpen, closesAt, nextOpen, minutesUntilClose, inWarning }` — recomputed every 30s and immediately on mount.

*(No unit test: the project has no React test harness. The logic is covered by Task 1; this hook is a thin wrapper verified by build + the manual check in Task 4.)*

- [ ] **Step 1: Implement the hook**

Create `algorithm/website/src/lib/useFeedHours.js`:
```js
import { useEffect, useState } from 'react';
import { feedHoursNow } from './feedHours.js';

/**
 * Live feed-hours state. Recomputes on mount and every 30 seconds so the
 * 5-minute warning counts down and the gate flips at sunrise/sunset without a
 * reload. Cheap (pure math), so a simple interval is fine.
 */
export function useFeedHours() {
  const [state, setState] = useState(() => feedHoursNow());

  useEffect(() => {
    const tick = () => setState(feedHoursNow());
    tick(); // resync immediately in case mount was stale
    const id = window.setInterval(tick, 30000);
    return () => window.clearInterval(id);
  }, []);

  return state;
}
```

- [ ] **Step 2: Verify it builds**

Run: `cd /Users/elaine/Documents/Chrysalis/algorithm/website && npm run build`
Expected: BUILD OK (no import/lint errors).

- [ ] **Step 3: Commit**

```bash
git add algorithm/website/src/lib/useFeedHours.js
git commit -m "feat: useFeedHours hook (live open/closed state)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `ClosedGateway` + `CloseWarning` components + styles

**Files:**
- Create: `algorithm/website/src/components/reels/ClosedGateway.jsx`
- Create: `algorithm/website/src/components/reels/CloseWarning.jsx`
- Modify: `algorithm/website/src/reels.css` (append styles)

**Interfaces:**
- Consumes: the `useFeedHours()` shape (Task 2) — `nextOpen: Date`, `closesAt: Date`, `minutesUntilClose: number`.
- Produces:
  - `<ClosedGateway nextOpen={Date} closesAt={Date} />`
  - `<CloseWarning minutesUntilClose={number} />`

- [ ] **Step 1: Implement `ClosedGateway.jsx`**

Create `algorithm/website/src/components/reels/ClosedGateway.jsx`:
```jsx
import { motion as MOTION } from 'motion/react';
import { PhaseIconCarousel } from '../PhaseIconCarousel';

const fmtTime = (d) =>
  d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

// Split the day so the copy matches the moment.
function gatewayCopy(now, nextOpen, closesAt) {
  const justSetRecently =
    now.getTime() - closesAt.getTime() >= 0 &&
    now.getTime() - closesAt.getTime() < 90 * 60000; // within ~90 min of sunset
  if (justSetRecently) {
    return {
      title: `The sun set at ${fmtTime(closesAt)} \u{1F305}`,
      body: 'Go catch it. The feed is resting for the night.',
      tease: 'The sunset gallery opens soon.',
    };
  }
  return {
    title: 'Resting until sunrise \u{1F319}',
    body: `The feed opens again at ${fmtTime(nextOpen)}.`,
    tease: null,
  };
}

export function ClosedGateway({ nextOpen, closesAt }) {
  const copy = gatewayCopy(new Date(), nextOpen, closesAt);
  return (
    <MOTION.main
      className="feed-gateway"
      data-algorithm
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="feed-gateway__inner">
        <PhaseIconCarousel className="feed-gateway__butterfly" />
        <h1 className="feed-gateway__title">{copy.title}</h1>
        <p className="feed-gateway__body">{copy.body}</p>
        {copy.tease && <p className="feed-gateway__tease">{copy.tease}</p>}
      </div>
    </MOTION.main>
  );
}
```

- [ ] **Step 2: Implement `CloseWarning.jsx`**

Create `algorithm/website/src/components/reels/CloseWarning.jsx`:
```jsx
import { motion as MOTION, AnimatePresence } from 'motion/react';

/**
 * A gentle banner over the open feed during the final minutes before sunset.
 * Renders nothing when there's more than the warning window left.
 */
export function CloseWarning({ minutesUntilClose }) {
  const show = minutesUntilClose > 0;
  return (
    <AnimatePresence>
      {show && (
        <MOTION.div
          className="feed-close-warning"
          role="status"
          aria-live="polite"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        >
          {minutesUntilClose === 1
            ? '1 minute till sunset \u{1F305} — start wrapping up'
            : `${minutesUntilClose} minutes till sunset \u{1F305} — start wrapping up`}
        </MOTION.div>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 3: Append styles to `reels.css`**

Append to `algorithm/website/src/reels.css`:
```css
/* ── Feed hours: closed gateway + close warning ───────────────────────────── */
.feed-gateway {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: var(--text);
  background:
    radial-gradient(circle at 50% 38%, color-mix(in srgb, var(--accent-soft) 20%, transparent), transparent 30rem),
    var(--bg);
}
.feed-gateway__inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 14px;
  max-width: 30rem;
}
.feed-gateway__butterfly { width: 96px; height: 96px; }
.feed-gateway__title {
  margin: 0;
  font-family: var(--font-reels-heading, 'Abril Fatface', serif);
  font-size: clamp(1.8rem, 6vw, 2.8rem);
  line-height: 1.1;
}
.feed-gateway__body { margin: 0; color: var(--text-muted); font-size: 1.05rem; line-height: 1.5; }
.feed-gateway__tease {
  margin: 6px 0 0;
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--accent);
}
.feed-close-warning {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 40;
  padding: 9px 18px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  background: color-mix(in srgb, var(--card) 88%, transparent);
  border: 1px solid var(--border);
  backdrop-filter: blur(8px);
  box-shadow: 0 10px 30px rgba(43, 38, 49, 0.16);
  pointer-events: none;
}
```

- [ ] **Step 4: Verify it builds**

Run: `cd /Users/elaine/Documents/Chrysalis/algorithm/website && npm run build`
Expected: BUILD OK.

- [ ] **Step 5: Commit**

```bash
git add algorithm/website/src/components/reels/ClosedGateway.jsx algorithm/website/src/components/reels/CloseWarning.jsx algorithm/website/src/reels.css
git commit -m "feat: closed gateway + 5-minute close-warning components

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Wire into `ReelsPage` + hide the mode picker

**Files:**
- Modify: `algorithm/website/src/components/reels/ReelsPage.jsx`
- Modify: `algorithm/website/src/brand.js` (flip `SKIP_ALGORITHM_ONBOARDING`)

**Interfaces:**
- Consumes: `useFeedHours()` (Task 2), `ClosedGateway`, `CloseWarning` (Task 3).

- [ ] **Step 1: Hide the mode picker**

In `algorithm/website/src/brand.js`, set the existing flag to `true` (find the current declaration and change its value):
```js
export const SKIP_ALGORITHM_ONBOARDING = true;
```
This makes `initialOnboarded()` return true, so `ReelsPage` skips `OnboardingStartScreen` and opens straight into the feed at `DEFAULT_MODE`. (If the flag is defined elsewhere with a different value, change it to `true` there. Do not touch the diagnostic survey.)

- [ ] **Step 2: Import the hook + components in `ReelsPage.jsx`**

Add near the other imports at the top of `algorithm/website/src/components/reels/ReelsPage.jsx`:
```jsx
import { useFeedHours } from '../../lib/useFeedHours';
import { ClosedGateway } from './ClosedGateway';
import { CloseWarning } from './CloseWarning';
```

- [ ] **Step 3: Call the hook and short-circuit when closed**

In the `ReelsPage` component body, near the other hook calls (e.g. just after `const { user } = useAuth();` around line 323), add:
```jsx
  const feedHours = useFeedHours();
```
Then, immediately before the component's main `return (` (the one that renders `<main className="reels-shell" ...>`), add the closed-state short-circuit:
```jsx
  if (!feedHours.isOpen) {
    return <ClosedGateway nextOpen={feedHours.nextOpen} closesAt={feedHours.closesAt} />;
  }
```

- [ ] **Step 4: Render the warning banner inside the open feed**

Inside that main `return`, right after the opening `<main className="reels-shell" ...>` tag (before `{onboarded && (`), add:
```jsx
      <CloseWarning minutesUntilClose={feedHours.inWarning ? feedHours.minutesUntilClose : 0} />
```

- [ ] **Step 5: Verify build + drive it**

Run: `cd /Users/elaine/Documents/Chrysalis/algorithm/website && npm run build`
Expected: BUILD OK.

Then drive it in the running dev app (see "Manual verification" below): confirm the feed renders when open, the mode picker no longer appears, and — by temporarily forcing closed hours (below) — the `ClosedGateway` shows with the right copy.

- [ ] **Step 6: Commit**

```bash
git add algorithm/website/src/components/reels/ReelsPage.jsx algorithm/website/src/brand.js
git commit -m "feat: feed opens/closes with the sun; hide the mode picker

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Full-suite check

**Files:** none (verification only)

- [ ] **Step 1: Run the frontend unit tests**

Run: `cd /Users/elaine/Documents/Chrysalis/algorithm/website && npm run test:unit`
Expected: PASS — all suites, including the new `feedHours.test.js`.

- [ ] **Step 2: Production build**

Run: `cd /Users/elaine/Documents/Chrysalis/algorithm/website && npm run build`
Expected: BUILD OK.

---

## Manual verification (how to actually see it)

The gate depends on the wall clock, so to see the *closed* state on demand,
temporarily hard-force it while the dev server runs:

- Quick way: at the top of `feedHoursNow` in `src/lib/feedHours.js`, temporarily
  `return { isOpen: false, closesAt: new Date(), nextOpen: new Date(Date.now()+3600000), minutesUntilClose: 0, inWarning: false };`
  → the `ClosedGateway` should render at `/`. **Revert this before committing.**
- To see the **warning**, temporarily return `{ isOpen: true, inWarning: true, minutesUntilClose: 3, ... }`.
- Open state is the default during daytime hours.

## Notes for the implementer

- Southern-hemisphere users get northern seasonal drift (assumed latitude). This
  is an accepted limitation of the no-location decision — do not add a location
  prompt to "fix" it.
- The `ClosedGateway` reuses `PhaseIconCarousel` (already in the repo) for the
  butterfly. Do not create a new loader.
- The 30-second poll in `useFeedHours` is intentional and sufficient; do not add
  precise boundary timers unless a reviewer asks.
- Phase 2 (the communal sunset ritual) is a separate spec — the gateway only
  *teases* it here.
- The spec's soft "Good morning ☀️" greeting on reopen is intentionally deferred
  as polish — not built in phase 1. The gate correctly reopens at sunrise; the
  greeting can be added later without touching this structure.
