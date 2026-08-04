// ──────────────────────────────────────────────────────────────
// Brand-name source of truth.
//
// Single source of truth for the app's DISPLAY name. Kept as a
// constant so the wordmark, titles, aria-labels, system messages,
// and @handles all resolve to the public DayBreak brand in one place. Internal
// Chrysalis identifiers intentionally remain unchanged for compatibility.
// ──────────────────────────────────────────────────────────────
export const BRAND = 'DayBreak';

// Lowercase handle used in user-facing demo @mentions.
export const BRAND_HANDLE = 'daybreak';

// Skip the "choose your algorithm" start screen and drop straight
// into the feed on the default mode (Cruisin' / flutter-feed).
export const SKIP_ALGORITHM_ONBOARDING = false;

// While in the algorithm feed, disable navigating back to the Home
// screen (the Home nav item shows a notice instead).
export const LOCK_HOME_FROM_ALGORITHM = false;
