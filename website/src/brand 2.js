// ──────────────────────────────────────────────────────────────
// Brand-name source of truth.
//
// Single source of truth for the app's DISPLAY name. Kept as a
// constant so the wordmark, titles, aria-labels, system messages,
// and @handles all resolve to "Chrysalis" in one place.
// ──────────────────────────────────────────────────────────────
export const BRAND = 'Chrysalis';

// Lowercase handle/slug form used in demo @mentions.
export const BRAND_HANDLE = 'chrysalis';

// Skip the "choose your algorithm" start screen and drop straight
// into the feed on the default mode (Cruisin' / flutter-feed).
export const SKIP_ALGORITHM_ONBOARDING = false;

// While in the algorithm feed, disable navigating back to the Home
// screen (the Home nav item shows a notice instead).
export const LOCK_HOME_FROM_ALGORITHM = false;
