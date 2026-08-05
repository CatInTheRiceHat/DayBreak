# DayBreak study route QA

Date: 2026-08-03

## Scope

This pass covers the `/study` route presentation and read-only route-level checks. Research identity, credentials, browser storage, session reuse, assignment, event capture, queues, retries, ordering, thresholds, feed selection, and completion behavior were not changed.

## Study presentation

- The loading, unavailable, and completion states use one calm, responsive DayBreak treatment.
- The active feed has a persistent, labelled study-session control with a 44px minimum target, visible focus treatment, mobile safe-area spacing, and an announced upload error.
- A route-level heading is available to assistive technology without changing the feed framing.
- Motion on the loading indicator is removed when `prefers-reduced-motion: reduce` is active.
- Study condition and assignment details remain absent from participant-facing copy.

## Study text change log

No existing study instruction, consent, disclosure, or completion sentence was rewritten. The following presentation labels were added:

- `DayBreak research`
- `Preparing your session`
- `Session unavailable`
- `Study session`
- `DayBreak anonymous research session` (screen-reader route heading)

The existing strings `Starting anonymous research session…`, `We could not start the anonymous research session.`, `Try again`, `Session complete`, `Your anonymous research events were saved.`, `Complete test session`, and `Saving…` are preserved verbatim.

## Automated checks

`npm run qa:study -- [baseURL]` uses the existing Playwright dependency and deterministic API mocks. It covers 320×568, 375×667, 768×1024, 1024×768, and 1440×900 and checks:

- Horizontal overflow and clipped study controls
- A single route-level `h1` and a main landmark
- Duplicate IDs
- Accidental study-condition disclosure
- Accessible button names and 44px completion/retry targets
- Visible keyboard focus
- Reduced-motion loading behavior
- Error/retry and completion transitions
- Completion endpoint call count
- Browser runtime errors

Screenshots are written to `assets/qa/responsive/study/` at the repository root.

Result: all five viewport scenarios passed with 0px document overflow. Loading, reduced motion, retry, focus, hidden-condition, and completion checks also passed. Completion and retry controls measured at least 44px high at every size.

## Validation result

- Focused ESLint (`ResearchPage.jsx` and `study-check.mjs`): passed
- Unit tests: 90 passed
- Production build: passed; Vite reported the existing large-chunk advisory
- Study Playwright QA: passed at all five target widths
- Repository-wide ESLint: blocked by 23 pre-existing errors and one warning in files outside Prompt 5 ownership
- Formatter/type checker: no dedicated project commands are configured

## Cross-route issues reported, not edited

These are outside Prompt 5 file ownership and should be addressed by the owning branch:

- Feed details, comments, and break dialogs declare `aria-modal="true"` but do not consistently trap focus, move initial focus into the dialog, or restore focus to the opener.
- The comments dialog has no Escape-key close handling in its route-level wrapper.
- The feed-end refresh button renders `Refresh feed` twice.
- Several global/feed controls use 36–38px visual targets on mobile and need a 44px hit-area review.
- Global font imports depend on Google Fonts without a route-owned fallback loading strategy; the app-shell/design-system owners should confirm resilient loading and final typography tokens.

## Remaining study issue

The existing `/study` route starts its anonymous session on mount and does not contain a consent or instruction screen to restyle. This branch does not invent consent language or insert a new gate because either change requires approved research wording and flow behavior. The research owner should supply that material if a participant consent step is required here.

## Merge notes

The study stylesheet consumes semantic DayBreak token names with palette fallbacks. After the design-system branch merges, reconcile any final token spelling centrally and remove fallbacks only when all required semantic variables are guaranteed.
