# Step 10 — Intentional Break route isolation

Captured on 2026-08-09 from a temporary Vite production build using deterministic
Playwright API mocks and an existing anonymous research credential. No production
participant or database data was used.

Command:

```bash
node qa/route-isolation-check.mjs http://127.0.0.1:4317
```

Verified:

- Active journeys redirected `/`, `/challenges`, `/saved`, `/profile`, and
  `/diagnostic` to `/study`.
- Cooldown journeys redirected `/`, `/reels`, and `/community` to `/study`.
- The guard displayed only its neutral checking state while `/current` was delayed;
  normal product UI and navigation did not mount underneath it.
- Browser Back resolved to `/study` with replacement semantics and did not create a
  redirect loop.
- A direct refresh-style load of `/profile` during cooldown resumed the unchanged
  server cooldown on `/study`.
- Retryable `/current` failure failed closed; retry reused the stored credential and
  redirected after the server returned an active journey.
- A second product tab redirected after receiving a planned-journey lifecycle signal.
- A later product navigation was allowed after `/current` returned no journey.
- No-credential browsing made no research API request and created no participant.
- An invalid stored credential was preserved, created no replacement participant,
  exposed no credential value, and allowed normal product recovery.

Evidence:

- `active-challenges-redirect.png`
- `browser-back-active-redirect.png`
- `cooldown-community-redirect.png`
- `cross-tab-planned-redirect.png`
- `refresh-profile-cooldown-redirect.png`
- `retryable-error-fails-closed.png`
