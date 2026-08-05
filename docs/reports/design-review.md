# Design Review: Butterfly / Chrysalis Graphic Audit

Reviewed against: the requested removal/replacement of butterfly, chrysalis, caterpillar, wing, and metamorphosis-themed graphics

Date: 2026-08-04

## Summary

The active DayBreak app is mostly clear of butterfly imagery outside the feed system. The current sunrise/horizon brand mark, onboarding, diagnostic, authentication, profile, saved-state, challenges, and research visuals can stay. The definite replacement work is concentrated in six raster assets: the four butterfly lifecycle frames plus the `Metamorphosis` and `Cruisin'` mode marks.

The dormant marketing implementation contains another butterfly hero, lifecycle timeline, and inline butterfly footer icon. Those are not reachable from the current router, but they should be replaced before that experience is restored.

## Active Graphics: Make New Versions

| Priority | Current asset | Why it needs changing | Where it appears |
| --- | --- | --- | --- |
| Must | `website/public/images/journey-egg.png` | First frame of an explicitly butterfly-lifecycle animation. | Every fallback/non-video feed card and the infinite-feed loading state through `PhaseIconCarousel`. |
| Must | `website/public/images/journey-caterpillar.png` | Explicit caterpillar. | Same shared phase carousel. |
| Must | `website/public/images/journey-chrysalis.png` | Explicit chrysalis. | Same shared phase carousel. |
| Must | `website/public/images/journey-emerged.png` | Explicit emerged butterfly. | Same shared phase carousel. |
| Must | `website/public/images/metamorphosis.png` | A chrysalis opening into butterfly wings. | Mode picker plus the top/side intention badge whenever Metamorphosis is active. |
| Must | `website/public/images/flutter-feed.png` | An explicit butterfly/wing mark. | The default `Cruisin'` intention badge across the feed, Challenges, and Saved, and the mode picker. |
| Should | `website/public/images/daily-dew.png` | Not literally an insect, but it shares the old low-poly lifecycle/leaf visual language and looks like part of the same asset family. | Daily Dew mode picker and intention badge. Keep it only if that visual continuity is intentional. |

The four lifecycle images are wired together in `website/src/components/PhaseIconCarousel.jsx:6`. A single neutral DayBreak loading graphic could replace all four; alternatively, make a new four-frame sequence based on sunrise/daybreak rather than metamorphosis.

The three mode marks are declared together in `website/src/components/reels/reelsData.js:22`. Replacing those files updates the picker, desktop sidebar, mobile top bar, Challenges, and Saved without needing separate graphics for each page.

## Important Rendering Finding

The nine fallback cards declare an `image` in `website/src/components/reels/reelsData.js:55`, but those images do not currently render as card artwork. `ReelCard` treats cards without a video source as loaders and shows `PhaseIconCarousel` instead (`website/src/components/reels/ReelCard.jsx:106` and `website/src/components/reels/ReelCard.jsx:245`). This is why all three feed modes show the same lifecycle graphic in the captured feed screenshots.

This means there are two sensible production directions:

1. Replace the lifecycle carousel with one new universal DayBreak loader, which is the smallest graphic task.
2. Update `ReelCard` to display each fallback card's declared artwork, then commission distinct art for the nine cards. If this path is chosen, the currently declared butterfly/lifecycle images still need replacement first.

## Dormant / Unreachable Graphic Debt

These do not affect the current routed app, because `/` renders `ReelsPage` and the marketing `MainPage` is never mounted (`website/src/App.jsx:28` and `website/src/App.jsx:92`). They still need attention before the marketing experience is re-enabled.

| Asset or element | Theme | Source location |
| --- | --- | --- |
| `website/public/images/hero-butterfly.png` | Large explicit butterfly hero. It is also referenced by fallback-card data, although those card images are currently ignored. | `website/src/components/RebootPage.jsx:780`, `website/src/components/reels/reelsData.js:81` |
| `website/public/images/butterfly.png` | Explicit butterfly split into animated left/right wings. | `website/src/components/ButterflyCanvas.jsx:42` |
| `journey-egg.png`, `journey-caterpillar.png`, `journey-chrysalis.png`, `journey-emerged.png` | Full lifecycle timeline. | `website/src/components/RebootPage.jsx:45` |
| Inline `ButterflyFooterIcon` SVG | Explicit four-wing butterfly. | `website/src/components/Contact.jsx:50` |
| Marketing lifecycle structure | Ova, Larva, DayBreak/Chrysalis, and Imago phases. | `website/src/components/RebootPage.jsx:45` and `website/src/components/RebootPage.jsx:995` |

`Hero.jsx` and `Contact.jsx` are older alternate marketing components and are not imported by the current route tree. They contain the same butterfly debt but do not require separate raster assets if they are removed rather than revived.

## Graphics That Can Stay

- `website/public/favicon.svg` and `website/public/images/logo.png`: sunrise/horizon DayBreak mark, not butterfly-themed.
- The CSS-built mark on login/signup: horizon/sun motif.
- Intro orbit and progress bar: abstract DayBreak/sunrise language.
- Diagnostic background arcs, auth background arcs, and research background curves: sunrise/horizon geometry.
- Challenges, Saved, and Profile empty-state icons: generic product icons.
- `newspaper.png`, `poster.png`, `synopsys-poster.jpeg`, `award.png`, `code.png`, `future.png`, and `me.png`: content artifacts rather than butterfly graphics.

## Related Copy Cleanup (No New Graphic Required)

If the goal is a complete thematic removal rather than graphics only, user-visible copy also remains:

- `Metamorphosis` and `Take a cocoon break` in `website/src/components/reels/reelsData.js:31` and `website/src/components/reels/reelsData.js:87`.
- `Want to take a cocoon break?` in `website/src/components/reels/FeedCompassPanel.jsx:117`.
- Dormant marketing copy: `Flutter Feed`, `Metamorphosis`, `Ova Phase`, `Larva Phase`, `Imago Phase`, and the butterfly-lifecycle explanation in `website/src/components/RebootPage.jsx:45` and `website/src/components/RebootPage.jsx:995`.
- Dormant Home copy: `Daily Wings`, `Share a wing`, and `Open Flutter` in `website/src/components/home/`.

Internal `chrysalis-*` local-storage keys, class names, comments, and component names do not create visible theme debt and should not be renamed solely for this graphic pass.

## Prioritized Production List

### Must fix

1. Replace the shared four-frame lifecycle carousel, or replace it with one neutral DayBreak loader.
2. Replace the `Metamorphosis` mode mark.
3. Replace the `Cruisin'`/Flutter Feed butterfly mark.

### Should fix

1. Decide whether Daily Dew's low-poly leaf/dewdrop belongs in the new graphic family; redraw it if the visual system is changing, even though it is not literally butterfly-themed.
2. Decide whether fallback cards should show their declared images or intentionally share a loader. Make that choice before commissioning nine card illustrations.

### Could improve

1. Remove or rebrand the dormant marketing components and assets so the old theme cannot accidentally return later.
2. Rename the remaining visible cocoon/metamorphosis/wing copy during the same content pass.

## What Works Well

The new DayBreak sunrise mark is already consistently used across onboarding, navigation, and browser favicon. The warm horizon arcs on diagnostic and auth pages form a coherent non-insect visual language that can guide the replacement graphics. The asset wiring is also centralized: one loader component and one mode configuration object control nearly all active appearances.

## Screenshots Captured

All captures are under `assets/qa/product-audits/butterfly-chrysalis-audit/`.

| Files | Breakpoints | Views |
| --- | --- | --- |
| `review-{intro,diagnostic,challenges,saved,login,signup,forgot-password,reset-password,profile,profile-edit,study}-{desktop-1280,tablet-768,mobile-375}.png` | 1280x800, 768x1024, 375x812 | 33 route captures |
| `review-feed-cruisin-{desktop-1280,tablet-768,mobile-375}.png` | 1280x800, 768x1024, 375x812 | Default feed and shared lifecycle loader |
| `review-mode-picker-{desktop-1280,tablet-768,mobile-375}.png` | 1280x800, 768x1024, 375x812 | All three mode marks |
| `review-feed-daily-dew-desktop-1280.png` | 1280x800 | Daily Dew feed state |
| `review-feed-metamorphosis-desktop-1280.png` | 1280x800 | Metamorphosis feed state |
