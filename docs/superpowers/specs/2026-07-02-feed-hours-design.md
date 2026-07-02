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

- **Sun times** are computed client-side from latitude/longitude with a standard
  NOAA sunrise/sunset formula (no network, no library needed — ~30 lines of
  astronomy math).
- **Location source (open question — see below):** we store a *coarse region*
  today (`preferences.py`: `region_code`, `location_city`, `location_country`),
  but not lat/long. Phase-1 plan: derive approximate lat/long from that region
  via a small centroid lookup, with an optional one-time browser geolocation
  (coarse) to sharpen it. Never store precise GPS.

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
- **Override (open question — see below):** default is closed. Option A: truly
  hard-closed (no entry until sunrise). Option B: one high-friction *"open for 5
  minutes"* with a visible countdown that then re-closes. Recommendation: B — keep
  agency, but the default is closed.

### Modes retire

- Remove the "Choose your Chrysalis algorithm" mode picker
  (`OnboardingStartScreen`). There is one feed.
- Under the hood, ranking keeps running a sensible default preset (the current
  `flutter-feed` / "Cruisin'" weights) — we simply stop surfacing the choice.
- **Survey interaction (open question — see below):** the first-run diagnostic
  currently ends by *recommending a mode*. With modes gone, keep the survey (still
  valuable for interests/personalization) but drop the recommended-mode output.
  This touches in-progress diagnostic work, so confirm before changing it.

## Components (Phase 1)

| Unit | Responsibility |
|---|---|
| `useSunTimes(lat, lng, date)` | Pure function/hook: returns `{ sunrise, sunset }` Date objects for a location + day (NOAA formula). Testable in isolation. |
| `useFeedHours()` | Resolves location → sun times → `{ isOpen, opensAt, closesAt, minutesUntilClose }`, re-evaluating on an interval and at the boundary. |
| `ClosedGateway` | The resting/gateway screen (copy varies by time-of-day; teases phase 2). |
| `CloseWarning` | The 5-minute countdown banner shown over the open feed. |
| Entry wire-in | `ReelsPage` (or the `/` gate) renders `ClosedGateway` when `!isOpen`, else the feed + `CloseWarning`. |
| Mode-picker removal | Delete/replace `OnboardingStartScreen`; feed defaults to the standard preset. |

## Data flow

```
coarse region (preferences) ─┐
optional coarse geolocation ─┴─► lat/lng ─► useSunTimes ─► sunrise/sunset
                                              │
now (local time) ────────────────────────────┴─► useFeedHours
                                                    │  isOpen? minutesUntilClose?
                          ┌─────────────────────────┴───────────────────────┐
                      isOpen=false                                       isOpen=true
                   <ClosedGateway>                        <Feed> + (≤5min) <CloseWarning>
```

## Edge cases

- **Polar latitudes / no sunrise or sunset that day** → fall back to fixed hours
  (open 07:00, close 19:00 local) so the app is never permanently dark or open.
- **Unknown/withheld location** → fall back to the device timezone with the same
  fixed 07:00–19:00 default, and invite the user to set a region.
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

## Open questions to confirm on review

1. **Location source:** region-centroid lookup vs. optional coarse browser
   geolocation (or both, geo sharpening the region).
2. **Override:** hard-closed vs. one high-friction "open 5 minutes" (recommend the
   latter).
3. **Survey:** OK to drop the recommended-mode output now (keeping the rest of the
   diagnostic), or keep modes alive under the hood for the survey's sake?
4. **Fixed-fallback hours:** 07:00–19:00 acceptable when the sun can't be computed?
