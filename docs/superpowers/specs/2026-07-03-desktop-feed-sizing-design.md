# Desktop feed sizing — fill large screens (A+B blend)

**Date:** 2026-07-03
**Status:** Approved design, pending implementation plan
**Area:** `algorithm/website/src/reels.css` (desktop tier only, `@media (min-width: 1100px)`)

## Problem

On large displays the reels feed leaves too much empty space. Everything in the
`≥1100px` tier is hard-capped and centered:

- The stage caps at `1280px` (`width: min(1280px, calc(100vw - 56px))`), so on a
  ~2560px monitor there is ~640px of dead margin on each side.
- The video frame caps at `410px` wide / `656px` tall and never grows past that
  regardless of display size.

Past ~1336px of window width nothing grows — the extra space becomes empty
gutter.

## Key constraint

Reels are portrait (9:16). Their rendered size is bounded by **height**
(`82dvh`), not width. On a wide-but-short monitor (e.g. 2560×1440) a portrait
video cannot get meaningfully wider without exceeding the viewport height.
Therefore filling the space requires two levers together, not just enlarging the
video:

1. Let the video grow on the dimension that matters (height on tall screens).
2. Absorb leftover **horizontal** space into the supporting side panels instead
   of dead margin.

## Design (A+B blend)

Fluid scaling (B) with a raised ceiling and a genuinely larger video (A), all
bounded so nothing overflows. Only the `@media (min-width: 1100px)` block
changes. The phone (`≤540px`) and mid (`540–1099px`) tiers are untouched.

### Changes

| Rule | From | To |
|---|---|---|
| `.reels-stage` width (ceiling) | `min(1280px, calc(100vw - 56px))` | `min(1600px, calc(100vw - 56px))` |
| `.reels-stage` compass rail column | `minmax(260px, 340px)` | `minmax(260px, 400px)` |
| `.reel-layout` caption column | `minmax(190px, 240px)` | `minmax(190px, 300px)` |
| `.reel-frame` width | `min(410px, 100%)` | `clamp(410px, 30vw, 520px)` |
| `.reel-frame` height governor | `min(82dvh, 656px)` | `min(86dvh, 760px)` |

- **Fluid, not stepped:** the raised ceiling plus `clamp`/`vw` values mean the
  layout breathes continuously as the window resizes rather than snapping at the
  1100px breakpoint. No new breakpoint tier is added.
- **Bounded:** every value has a hard ceiling (`1600px`, `520px`, `760px`,
  `86dvh`), so nothing grows unbounded on a giant display, and the `dvh` height
  cap keeps the portrait video fully on-screen.
- **Space absorbed by panels:** the widened compass rail and caption column take
  up horizontal room that would otherwise be empty gutter, framing the video
  rather than stranding it.

### Feed-column / inner-grid note

`.reel-layout` currently caps at `width: min(100%, 820px)` and the stage feed
column is `minmax(680px, 840px)`. With the wider video (`≤520px`) + widened
caption column (`≤300px`) + `58px` action rail + gaps, the inner grid must still
fit inside the feed column. During implementation, verify the feed column and
`.reel-layout` max-width are wide enough for the new columns (raise the `820px`
/ `840px` caps if the grid overflows). This is the one spot that needs a live
tuning pass.

## Non-goals

- No change to phone or mid-size tiers.
- No new content in the margins (that was Option C — rejected).
- No change to video aspect handling, cropping, or the `CroppedYouTubePlayer`.

## Verification

Eyeball the real render at representative widths and confirm no overflow /
horizontal scrollbar and that the video is visibly larger:

- ~1280px (13" laptop) — should look like today or slightly larger, no regression.
- ~1512px (14"/16" MacBook) — video and panels noticeably larger.
- ~1920px and ~2560px — space filled, video large, margins reasonable, nothing
  clipped, portrait video fully visible.

Exact `clamp` values (`30vw`, `520px`, `760px`) may need one tuning pass against
the live render.
