# The Feed Has Hours — sunrise/sunset gateway

**Date:** 2026-07-02
**Status:** Design — awaiting review
**Scope:** `algorithm/website` (frontend-led). Phase 1 of a two-phase vision.

## Origin

From the Stanford youth-mental-health workshop (reference slides) two threads
converge: **scroll-to-sleep is the headline harm** (protect the night), and the
biggest positive finding is that **teens want real-world, in-person connection**
and would use digital less if the real world were there to step into.

The idea: retire the three intention "modes" and instead give the feed **hours**.
It opens with the sunrise and closes with the sunset — real local time. The close
is not a lockout; it is a doorway that hands you back to the real world exactly at
golden hour ("go catch the sunset"). This is the wellbeing thesis expressed as a
feeling, not a setting.

## Vision (two phases)

- **Phase 1 (this spec):** the feed's *hours* — the sun-timed open/close, the
  5-minute warning, and the closed **gateway** screen. Modes retire.
- **Phase 2 (separate spec, out of scope here):** the **sunset ritual** — when the
  feed closes, the community posts their actual sunset into a daily, ephemeral,
  authentic gallery (BeReal-meets-circadian, plugging into the existing Touch
  Grass community feature). Phase 1's gateway *teases* this ("the sunset gallery
  opens soon 🌅") but does not build it.

## Design

### When it's open

The feed follows the **real sun at the user's location, in local time** — no
clamping. It opens at sunrise and closes at sunset. Winter's early sunset is a
feature, not a bug: the app closing early *is* the prompt to go see the (early)
sunset.

- **No location, no permission prompt.** We do not ask for or store the user's
  location. Instead we read the device's **time zone** (free/ambient — no prompt)
  for correct local clock time, and compute an *approximate, seasonally drifting*
  sunrise/sunset with the standard NOAA formula (~30 lines, no network/library)
  using an **assumed temperate latitude** (~40°) and a longitude taken from the
  time-zone's central meridian (`offsetHours × 15°`). The close therefore still
  moves earlier in winter and later in summer — the seasonal feel is preserved —
  it is just not pinned to the user's exact horizon. (Exact, location-based sun
  times remain a possible future opt-in, not built here.)

### The 5-minute warning

While open, when the current time is within **5 minutes of sunset**, show a
gentle, dismissible banner over the feed: *"5 minutes till sunset — start
wrapping up 🌅"* with a live m:ss countdown. This softens the close and primes the
go-outside moment. Threshold is a constant (`CLOSE_WARNING_MINUTES = 5`).

### The closed gateway

Outside hours, the entry route (`/`) renders a calm **`ClosedGateway`** screen
*instead of* the feed:

- The butterfly at rest (cocoon). Copy adapts to the moment:
  - Just closed / evening: *"The sun set at 5:42pm 🌅 — go catch it."* + tease:
    *"The sunset gallery opens soon."* (phase 2)
  - Deep night / pre-dawn: *"Resting until sunrise."* + the exact next-open time.
- **Reopen** at sunrise with a soft *"Good morning ☀️"* the first time in.
- **Hard close.** No override — once closed, the feed stays closed until sunrise.
  The commitment is the point.

### Modes retire

- Remove the "Choose your Chrysalis algorithm" mode picker
  (`OnboardingStartScreen`). There is one feed.
- Under the hood, ranking keeps running a sensible default preset (the current
  `flutter-feed` / "Cruisin'" weights) — we simply stop surfacing the choice.
- **Survey stays intact; the mode UI is hidden.** The first-run diagnostic keeps
  running (it still gathers interests/personalization); we simply stop *surfacing*
  anything mode-related — no mode picker, no "recommended mode" screen. The
  diagnostic's internals are left untouched so the in-progress work is not broken;
  its mode output just goes unused.

## Components (Phase 1)

| Unit | Responsibility |
|---|---|
| `useSunTimes(lat, lng, date)` | Pure function: returns `{ sunrise, sunset }` Date objects for a lat/lng + day (NOAA formula). Callers pass the assumed latitude and the time-zone-derived longitude. Testable in isolation. |
| `useFeedHours()` | Resolves location → sun times → `{ isOpen, opensAt, closesAt, minutesUntilClose }`, re-evaluating on an interval and at the boundary. |
| `ClosedGateway` | The resting/gateway screen (copy varies by time-of-day; teases phase 2). |
| `CloseWarning` | The 5-minute countdown banner shown over the open feed. |
| Entry wire-in | `ReelsPage` (or the `/` gate) renders `ClosedGateway` when `!isOpen`, else the feed + `CloseWarning`. |
| Mode-picker removal | Delete/replace `OnboardingStartScreen`; feed defaults to the standard preset. |

## Data flow

```
device time zone ─► assumed latitude (~40°) + longitude (offsetHours×15°) ─► useSunTimes ─► sunrise/sunset
                                                                                 │
now (local clock time) ──────────────────────────────────────────────────────────┴─► useFeedHours
                                                    │  isOpen? minutesUntilClose?
                          ┌─────────────────────────┴───────────────────────┐
                      isOpen=false                                       isOpen=true
                   <ClosedGateway>                        <Feed> + (≤5min) <CloseWarning>
```

## Edge cases

- **Polar latitudes / no sunrise or sunset that day** → fall back to fixed hours
  (open 07:00, close 19:00 local) so the app is never permanently dark or open.
- **Time zone unavailable (rare)** → fall back to the fixed 07:00–19:00 local
  default.
- **DST / timezones** → always compute against the device's local time; sun times
  are in local time.
- **Clock/day rollover** → `useFeedHours` recomputes at the next boundary
  (sunrise, sunset, or midnight), not just on a fixed poll.

## Testing

- `useSunTimes`: assert sunrise/sunset for known lat/lng + date against reference
  values (within a minute or two).
- `useFeedHours`: with a mocked clock + fixed sun times, assert `isOpen` on both
  sides of sunrise and sunset, `minutesUntilClose` correctness, the 5-minute
  warning boundary, and the polar/unknown-location fallbacks.
- `ClosedGateway`: renders the right copy branch (evening vs deep-night vs
  pre-dawn) for a given clock.

## Out of scope (Phase 1)

- The sunset **ritual / photo gallery** (phase 2 — its own spec).
- Any change to feed ranking beyond dropping the user-facing mode choice.
- Precise GPS storage.

## Resolved decisions

1. **No location** — device time zone + assumed temperate latitude (~40°) and a
   time-zone-derived longitude for an approximate, seasonally drifting sunrise/
   sunset. No permission prompt, nothing stored; not pinned to the exact horizon.
2. **Hard close** — no override; closed until sunrise.
3. **Hide the mode UI** — keep the diagnostic survey running; stop surfacing the
   mode picker / recommended-mode; leave the diagnostic's internals untouched.
4. **Fallback hours 07:00–19:00** — used at polar/degenerate latitudes or if the
   time zone can't be read.
