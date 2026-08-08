# Step 9 checkout and cooldown QA

Run on 2026-08-07 against the local Vite application with deterministic browser API responses. Evidence in this directory is new for Step 9 and does not overwrite Step 8 captures.

## Viewports

- 375 × 812
- 768 × 1024
- 1280 × 900

At all three widths, checkout, cooldown, override, and completion were checked for horizontal overflow, product navigation leakage, feed/video leakage, and interaction targets smaller than 44px. All checks passed.

The captures cover empty and answered checkout, checkout submission pending, cooldown start and mid-state, cooldown refresh, retryable cooldown error, override pause, selected override reason, natural completion, override completion, and mobile keyboard focus.

## Observations

- Checkout remains usable at 375px without horizontal overflow or button collision. On shorter phones, ordinary vertical page scrolling may still be needed to reach the final question and action.
- Cooldown and override contain no feed preview or product navigation.
- Countdown text remains visually stable and does not use an every-second live region.
- Programmatic stage focus moves to the heading without drawing a misleading interactive focus ring; keyboard-focused controls retain visible focus treatment.
- The final-card transition observed in Step 8 still feels abrupt under the frozen one-second meaningful-impression boundary. It was not changed in this step.

**Candidate v1.1 change: separate “boundary reached” measurement from the moment the final card is visually removed, so participants can finish interacting with the final post before checkout appears.**

## Local backend smoke

Two deterministic journeys passed against the real local test backend using temporary SQLite data:

1. Natural boundary: plan → start → reserved items → final impression → checkout → cooldown → server-time advance → completed.
2. Finish early and override: plan → start → first impression → finish early → checkout → cooldown → override start → early confirmation rejection → server-time advance → override confirmation → completed.

Canonical server event order was contiguous for both sessions. The natural stream ended with `cooldown_completed`; the override stream ended with `cooldown_overridden`.
