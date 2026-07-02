/**
 * Progressive screen-time break logic for the Chrysalis feed.
 *
 * Pure, side-effect-free helpers so the timing rules are unit-testable on their
 * own (see sessionBreaks.test.js). The React glue lives in useSessionTimer.js and
 * BreakScreen.jsx.
 *
 * Model: we track *cumulative active minutes* in a session (away-time during a
 * break does not count). Breaks trigger at escalating milestones, and the longer
 * someone keeps scrolling the longer the suggested reset becomes:
 *
 *    60 min  -> 10-min break
 *    90 min  -> 15-min break
 *   120 min  -> 20-min break
 *   150+ min -> 30-min break (recurring every 30 min beyond 150)
 *
 * This is a supportive nudge, not a lockout: the feed pauses and invites a real-
 * world reset, and the user returns when they have stepped away.
 */

export const MINUTE_MS = 60_000;

// Progressive tiers, ascending by threshold. Each: cumulative active minutes that
// trigger the break, and the suggested away-time in minutes.
export const BREAK_TIERS = [
  { thresholdMin: 60, breakMin: 10 },
  { thresholdMin: 90, breakMin: 15 },
  { thresholdMin: 120, breakMin: 20 },
  { thresholdMin: 150, breakMin: 30 },
];

// Beyond the top tier the 30-minute reset recurs every this-many cumulative mins.
export const RECURRING_INTERVAL_MIN = 30;
export const RECURRING_BREAK_MIN = 30;

// Time scale: how many real milliseconds count as one "minute" of session time.
//  - Normal:  one real minute  = one session minute.
//  - Demo:    one real second  = one session minute (so 60 "min" arrives in 60s),
//    used by the developer/test mode so a break can be demoed quickly.
export const DEFAULT_TIME_SCALE_MS = MINUTE_MS;
export const DEMO_TIME_SCALE_MS = 1_000;

// Activities offered on the break screen. Low-friction, real-world, never creepy:
// no GPS, health data, or camera requirements.
export const BREAK_ACTIVITIES = [
  { id: 'walk', label: 'Take a short walk', emoji: '🚶', blurb: 'Step outside and get some fresh air.' },
  { id: 'water', label: 'Drink some water', emoji: '💧', blurb: 'Grab a glass and hydrate.' },
  { id: 'stretch', label: 'Stretch it out', emoji: '🧘', blurb: 'Roll your shoulders and loosen up.' },
  { id: 'journal', label: 'Journal a moment', emoji: '📔', blurb: 'Jot down one thought or a small win.' },
  { id: 'draw', label: 'Draw something', emoji: '✏️', blurb: 'Doodle whatever comes to mind.' },
  { id: 'snack', label: 'Grab a snack', emoji: '🍎', blurb: 'Step away and have a bite.' },
  { id: 'message-friend', label: 'Message a friend', emoji: '💬', blurb: 'Say hi to someone you like.' },
  { id: 'creative', label: 'Quick creative thing', emoji: '🎨', blurb: 'Make or build something tiny.' },
];

const TOP_TIER = BREAK_TIERS[BREAK_TIERS.length - 1];

/** Convert elapsed real milliseconds into cumulative session minutes. */
export function minutesFromElapsed(elapsedMs, scaleMs = DEFAULT_TIME_SCALE_MS) {
  if (!Number.isFinite(elapsedMs) || elapsedMs <= 0) return 0;
  const scale = scaleMs > 0 ? scaleMs : DEFAULT_TIME_SCALE_MS;
  return elapsedMs / scale;
}

/**
 * The next break tier a user is working toward, given the highest milestone they
 * have already completed (0 if none). Returns { thresholdMin, breakMin }.
 */
export function nextBreakTier(completedMin = 0) {
  const completed = Number.isFinite(completedMin) ? completedMin : 0;
  const upcoming = BREAK_TIERS.find((tier) => tier.thresholdMin > completed);
  if (upcoming) return { ...upcoming };
  // Past the defined tiers: recur the top break every RECURRING_INTERVAL_MIN.
  const base = Math.max(completed, TOP_TIER.thresholdMin);
  return { thresholdMin: base + RECURRING_INTERVAL_MIN, breakMin: RECURRING_BREAK_MIN };
}

/**
 * Whether a break is due. `elapsedMin` is cumulative session minutes; `completedMin`
 * is the highest milestone already completed. Returns the due tier or null.
 */
export function dueBreakTier(elapsedMin, completedMin = 0) {
  const tier = nextBreakTier(completedMin);
  return elapsedMin >= tier.thresholdMin ? tier : null;
}

/**
 * Whether a break is currently due (pending) for the given elapsed time. While a
 * break is pending the session clock should freeze — otherwise time keeps burning
 * behind the break screen and, on demo scale especially, the *next* milestone is
 * already passed by the time the user finishes, making breaks re-pop instantly.
 */
export function isBreakPending(elapsedMs, completedMin = 0, scaleMs = DEFAULT_TIME_SCALE_MS) {
  return Boolean(dueBreakTier(minutesFromElapsed(elapsedMs, scaleMs), completedMin));
}

/** Milliseconds remaining until the next break triggers (0 if already due). */
export function msUntilNextBreak(elapsedMs, completedMin = 0, scaleMs = DEFAULT_TIME_SCALE_MS) {
  const scale = scaleMs > 0 ? scaleMs : DEFAULT_TIME_SCALE_MS;
  const tier = nextBreakTier(completedMin);
  return Math.max(0, tier.thresholdMin * scale - (elapsedMs || 0));
}

/** Elapsed ms required to reach the next break (used by the demo fast-forward). */
export function elapsedMsForNextBreak(completedMin = 0, scaleMs = DEFAULT_TIME_SCALE_MS) {
  const scale = scaleMs > 0 ? scaleMs : DEFAULT_TIME_SCALE_MS;
  return nextBreakTier(completedMin).thresholdMin * scale;
}

/** Format milliseconds as M:SS for the optional in-break countdown. */
export function formatCountdown(ms) {
  const total = Math.max(0, Math.ceil((ms || 0) / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

/** Find an activity definition by id. */
export function activityById(id) {
  return BREAK_ACTIVITIES.find((activity) => activity.id === id) || null;
}
