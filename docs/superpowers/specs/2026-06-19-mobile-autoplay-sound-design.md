# Mobile feed autoplay with sound — design

## Problem

On phones the active feed video does not play. `ReelCard.jsx` builds its YouTube
embed with `muted: false` and `autoplay: true`. Every mobile browser (iOS Safari,
Chrome Android) blocks autoplay when sound is on, so the embed loads but never
starts. Desktop works because desktop allows sound-on autoplay.

## Constraint (non-negotiable, browser-enforced)

- Muted autoplay is always permitted.
- Sound-on autoplay is blocked until the user makes at least one gesture (tap)
  on the page. No code/flag bypasses this — it is browser policy.

After the first user gesture in a session, sticky user activation lets
subsequent videos autoplay with sound.

## Goal

Closest-to-"autoplays with audio" experience a phone allows:

1. First active video autoplays **muted** with an obvious 🔊 "tap for sound" cue.
2. User taps the cue once → audio unlocks for the rest of the session.
3. Every later video scrolled to autoplays **with sound** automatically.

Desktop behavior is unchanged (sound-on autoplay as today).

## Design

### Session sound state (lifted to `ReelsPage`)

- New state `soundOn`, initialized from device type:
  - desktop (pointer: fine / not coarse) → `true`
  - mobile (pointer: coarse) → `false`
- Detection via `matchMedia('(pointer: coarse)')` in a small `useIsTouch` helper.
- `soundOn` and a `setSoundOn` callback are passed to every `ReelCard`.
- Once flipped to `true` it stays `true` for the session (covers all later cards).

### `ReelCard` changes

- Build the embed with `muted: !soundOn` instead of hardcoded `false`.
- The embed `src`/`key` already includes the mute param, so flipping `soundOn`
  remounts the active iframe with `mute=0` + `autoplay=1`. Because the flip is
  driven by the user's tap (a gesture), that remount autoplays **with sound** from
  the start — acceptable UX for "turn sound on" (clip restarts).
- New cards reached while `soundOn === true` mount with `mute=0` and autoplay with
  sound under sticky user activation.
- Add an unmute/mute toggle control overlaid on the media:
  - Shown when `hasVideo` and the embed is rendering.
  - Muted state shows 🔇 + "Tap for sound"; calling it sets `soundOn = true`.
  - Once unlocked, shows a normal 🔊/🔇 toggle that flips `soundOn`.

### Desktop

- `soundOn` starts `true`; the toggle still appears (lets desktop mute), but
  nothing about current autoplay-with-sound behavior changes.

## Out of scope (YAGNI)

- Per-video persisted mute preference across reloads.
- Volume slider.
- Reduced-motion / data-saver autoplay opt-out (separate concern).

## Testing

- Unit: `buildYouTubeEmbedUrl` sets `mute=1` when `muted: true` and `mute=0`
  otherwise (extend coverage around the embed builder).
- Manual: on a phone, first card autoplays silently with the cue; tapping the cue
  plays sound; scrolling to the next card autoplays with sound and no extra tap.
