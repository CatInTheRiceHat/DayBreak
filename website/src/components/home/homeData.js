/**
 * Local demo data for the Chrysalis Home screen.
 *
 * Everything here is clearly UI/demo seed data — not backed by any Supabase table
 * yet. It deliberately avoids popularity signals (no follower counts, no likes as a
 * ranking, no "hot" lists). Statuses are small wellbeing actions ("Daily Wings"),
 * and suggested people surface a gentle *reason*, never a popularity metric.
 *
 * When real tables land (activity_statuses, connections, messages, saved_items),
 * these arrays are the seams to replace.
 */

export const DAILY_WINGS_TITLE = 'Daily Wings';

/**
 * Activity / status notes shown in the Daily Wings row. Each is a small, real-life
 * wellbeing action — the opposite of a flex.
 */
export const DAILY_WINGS = [
  {
    id: 'you',
    isSelf: true,
    firstName: 'You',
    emoji: '🌊',
    activity: 'Share a wing',
    note: 'Add a small win from today.',
    hasImage: false,
  },
  {
    id: 'maya',
    firstName: 'Maya',
    emoji: '🌸',
    activity: 'Drinking water 💧',
    note: 'Third glass today. Small wins count.',
    hasImage: false,
  },
  {
    id: 'liam',
    firstName: 'Liam',
    emoji: '🎧',
    activity: 'Taking a screen break 🌊',
    note: 'Stepping away for 20. Back later.',
    hasImage: true,
  },
  {
    id: 'aria',
    firstName: 'Aria',
    emoji: '🌿',
    activity: 'On a walk 🌿',
    note: 'Found a new path by the river.',
    hasImage: true,
  },
  {
    id: 'theo',
    firstName: 'Theo',
    emoji: '📚',
    activity: 'Studying 25 min 📚',
    note: 'One pomodoro down, phone in the drawer.',
    hasImage: false,
  },
  {
    id: 'rin',
    firstName: 'Rin',
    emoji: '🎨',
    activity: 'Making art 🎨',
    note: 'Messy sketch, happy brain.',
    hasImage: true,
  },
  {
    id: 'zoe',
    firstName: 'Zoe',
    emoji: '✍️',
    activity: 'Journaling ✍️',
    note: 'Three lines about today. That is enough.',
    hasImage: false,
  },
  {
    id: 'noah',
    firstName: 'Noah',
    emoji: '🌬️',
    activity: 'Breathing reset 🌬️',
    note: 'Box breathing before bed.',
    hasImage: false,
  },
  {
    id: 'sol',
    firstName: 'Sol',
    emoji: '🌙',
    activity: 'Resting offline 🌙',
    note: 'Logging off early tonight.',
    hasImage: false,
  },
];

/** Supportive-only reactions for a Daily Wing — never competitive likes. */
export const WING_REACTIONS = [
  { id: 'proud', label: 'proud of you', emoji: '💜' },
  { id: 'same', label: 'same here', emoji: '🤝' },
  { id: 'inspired', label: 'inspired', emoji: '✨' },
  { id: 'join', label: 'join reset', emoji: '🌬️' },
];

/**
 * "Suggested for you" people. The `reason` is intention-based, never popularity.
 * `action` is "connect" or "wave" — gentle, non-competitive verbs.
 */
export const SUGGESTED_PROFILES = [
  {
    id: 'maya',
    displayName: 'Maya',
    username: 'maya',
    emoji: '🌸',
    reason: 'Same intention today',
    action: 'connect',
  },
  {
    id: 'theo',
    displayName: 'Theo',
    username: 'theo',
    emoji: '📚',
    reason: 'Also choosing less comparison',
    action: 'connect',
  },
  {
    id: 'rin',
    displayName: 'Rin',
    username: 'rin',
    emoji: '🎨',
    reason: 'Into creativity + calm',
    action: 'wave',
  },
  {
    id: 'aria',
    displayName: 'Aria',
    username: 'aria',
    emoji: '🌿',
    reason: 'Similar reset goals',
    action: 'connect',
  },
  {
    id: 'noah',
    displayName: 'Noah',
    username: 'noah',
    emoji: '🌬️',
    reason: 'Friend of a friend',
    action: 'wave',
  },
];

/** A single calm "Today's reset" prompt for the center column. */
export const TODAYS_RESET = {
  title: "Today's reset",
  prompt: 'Take one slow screen break before your next scroll.',
  minutes: 5,
  emoji: '🌬️',
};

/**
 * A few gentle activity cards for the center feed — wellbeing moments, not
 * performance posts. These are demo content only.
 */
export const ACTIVITY_CARDS = [
  {
    id: 'card-walk',
    firstName: 'Aria',
    emoji: '🌿',
    activity: 'On a walk',
    body: 'Left my phone on the shelf and just listened to the birds for a while. 10/10 would touch grass again.',
    accent: 'healthy',
  },
  {
    id: 'card-journal',
    firstName: 'Zoe',
    emoji: '✍️',
    activity: 'Journaling',
    body: 'Wrote down three things that went okay today. Turns out the day was kinder than it felt.',
    accent: 'creative',
  },
  {
    id: 'card-break',
    firstName: 'Liam',
    emoji: '🎧',
    activity: 'Screen break',
    body: 'Did the 20-minute reset instead of doomscrolling. My eyes (and brain) say thanks.',
    accent: 'reset',
  },
];

/** Suggested searches for the Search page (demo). */
export const SUGGESTED_SEARCHES = [
  'screen break',
  'study reset',
  'less comparison',
  'creative reset',
];

/** Activity topics that the demo search can match against. */
export const SEARCH_ACTIVITIES = [
  { id: 'screen-break', label: 'Screen break', emoji: '🌊' },
  { id: 'study-reset', label: 'Study reset', emoji: '📚' },
  { id: 'on-a-walk', label: 'On a walk', emoji: '🌿' },
  { id: 'journaling', label: 'Journaling', emoji: '✍️' },
  { id: 'breathing', label: 'Breathing reset', emoji: '🌬️' },
  { id: 'making-art', label: 'Making art', emoji: '🎨' },
  { id: 'less-comparison', label: 'Less comparison', emoji: '🌅' },
  { id: 'resting-offline', label: 'Resting offline', emoji: '🌙' },
];

/** Demo people the search can match (reuses the suggested + wings cast). */
export const SEARCH_PEOPLE = SUGGESTED_PROFILES.map(({ id, displayName, username, emoji, reason }) => ({
  id,
  displayName,
  username,
  emoji,
  reason,
}));

/** Mock inbox preview cards — demo only; no real messaging is wired up. */
export const INBOX_PREVIEWS = [
  {
    id: 'maya',
    firstName: 'Maya',
    emoji: '🌸',
    preview: 'Loved your walk note 🌿',
    when: 'now',
  },
  {
    id: 'theo',
    firstName: 'Theo',
    emoji: '📚',
    preview: 'Study reset at 7? phones away',
    when: '2h',
  },
];

/** Map a Chrysalis mode key to a friendly label (mirrors ProfileCard). */
const MODE_LABELS = {
  'daily-dew': 'Daily Dew',
  'flutter-feed': "Cruisin'",
  metamorphosis: 'Metamorphosis',
};

export function modeLabel(mode) {
  if (!mode) return null;
  return MODE_LABELS[mode] || mode;
}
