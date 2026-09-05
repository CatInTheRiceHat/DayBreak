/**
 * Local demo data for the Chrysalis Community page.
 *
 * Like homeData.js, everything here is clearly UI/demo seed data — not backed by
 * any Supabase table yet. It deliberately avoids popularity signals: no follower
 * counts, no likes, no "most-watched" ranking. People are surfaced by shared
 * goals, interests, and healthy habits; the leaderboard ranks *positive actions*
 * (offline resets, kind messages, wellness challenges) measured in Dewdrops.
 *
 * Profiles are avatar-first (emoji + initial) — never real photos. When real
 * tables land (connections, challenges, dewdrop_ledger), these arrays are the
 * seams to replace.
 */

/** Header copy + small stat cards for the top of the page. */
export const COMMUNITY_HEADER = {
  title: 'Community',
  subtitle: 'Find people who help you grow offline, not just scroll online.',
  stats: [
    { id: 'dewdrops', value: 128, label: 'Dewdrops earned this week', emoji: '💧' },
    { id: 'challenges', value: 4, label: 'wellness challenges completed', emoji: '🌿' },
    { id: 'matches', value: 2, label: 'new circle matches', emoji: '🤝' },
    { id: 'resets', value: 1, label: 'offline reset today', emoji: '🌅' },
  ],
};

/**
 * Friend-discovery deck (swipe-style cards). Avatar-first; the emphasis is on
 * goals, interests, and shared values — never appearance or popularity.
 */
export const FRIEND_CANDIDATES = [
  {
    id: 'maya',
    name: 'Maya',
    emoji: '🌸',
    age: '16',
    goal: 'Spend less time doomscrolling',
    interests: ['art', 'wellness', 'study vlogs', 'film'],
    lookingFor: 'a weekly reset buddy',
    shared: ['less toxic scrolling', 'creative videos'],
    why: 'You both want less toxic scrolling and like creative videos.',
    circleGoal: 'Weekly reset buddy',
    activity: 'Try a 10-minute walk together',
  },
  {
    id: 'jordan',
    name: 'Jordan',
    emoji: '🌎',
    age: '17',
    goal: 'Hear more than one point of view',
    interests: ['documentaries', 'debate', 'history', 'hiking'],
    lookingFor: 'someone to swap perspective videos with',
    shared: ['perspective videos', 'touching grass'],
    why: 'You both like perspective-shifting videos and getting outside.',
    circleGoal: 'Perspective buddy',
    activity: 'Exchange one new idea this week',
  },
  {
    id: 'anika',
    name: 'Anika',
    emoji: '🌿',
    age: '18',
    goal: 'Build a calmer evening routine',
    interests: ['journaling', 'tea', 'lo-fi', 'plants'],
    lookingFor: 'a wind-down accountability friend',
    shared: ['no-phone wind down', 'journaling'],
    why: 'You both want calmer nights and like to journal.',
    circleGoal: 'Wellness buddy',
    activity: 'Do a wind-down challenge tonight',
  },
  {
    id: 'theo',
    name: 'Theo',
    emoji: '📚',
    age: '16',
    goal: 'Study without my phone in reach',
    interests: ['study vlogs', 'chess', 'coffee', 'running'],
    lookingFor: 'a focus-sprint partner',
    shared: ['study sprints', 'phone-free focus'],
    why: 'You both want phone-free focus time and like study routines.',
    circleGoal: 'Focus buddy',
    activity: 'Do a 25-minute study sprint together',
  },
  {
    id: 'sol',
    name: 'Sol',
    emoji: '🌅',
    age: '17',
    goal: 'Touch grass more this month',
    interests: ['cycling', 'photography', 'cooking', 'music'],
    lookingFor: 'a weekend outdoors buddy',
    shared: ['touch grass challenges', 'getting offline'],
    why: 'You both want more offline time and joined the touch-grass challenge.',
    circleGoal: 'Touch grass buddy',
    activity: 'Plan one outdoor reset this weekend',
  },
];

/**
 * "Good Things" leaderboard. Ranked by Dewdrops earned through healthy actions —
 * NOT followers, likes, matches, comments, watch time, or videos watched.
 * The `isSelf` row is the current demo user; their score updates live as they
 * complete challenges on this page.
 */
export const LEADERBOARD = [
  { id: 'lina', name: 'Lina', emoji: '🌷', dewdrops: 420, topAction: 'Completed 5 offline resets' },
  { id: 'jordan', name: 'Jordan', emoji: '🌎', dewdrops: 390, topAction: 'Sent 8 kind messages' },
  { id: 'avery', name: 'Avery', emoji: '🍃', dewdrops: 360, topAction: 'Joined 3 wellness challenges' },
  { id: 'you', name: 'You', emoji: '🌊', dewdrops: 310, topAction: 'Took 2 touch grass breaks', isSelf: true },
  { id: 'maya', name: 'Maya', emoji: '🌸', dewdrops: 280, topAction: 'Watched 4 perspective videos' },
];

/** Actions that earn Dewdrops — shown as gentle "how to earn" copy. */
export const POSITIVE_ACTIONS = [
  'Taking breaks',
  'Doing IRL activities',
  'Completing wellness challenges',
  'Sending kind messages',
  'Watching perspective videos',
  'Reflecting after scrolling',
  'Helping a friend',
  'Exploring new content categories',
  'Joining touch grass challenges',
];

/**
 * Touch Grass challenges. Each rewards Dewdrops for a small, real-life action.
 * `category` maps to a token-tinted tag (IRL / Wellness / Friendship /
 * Perspective / Focus).
 */
export const CHALLENGES = [
  {
    id: 'walk',
    title: '10-Minute Walk',
    description: 'Step away from your phone and walk outside.',
    reward: 20,
    category: 'IRL',
    emoji: '🚶',
  },
  {
    id: 'kind-message',
    title: 'Kind Message',
    description: 'Send one encouraging message to a friend.',
    reward: 15,
    category: 'Friendship',
    emoji: '💌',
  },
  {
    id: 'perspective',
    title: 'Perspective Check',
    description: 'Watch one video from a new viewpoint.',
    reward: 15,
    category: 'Perspective',
    emoji: '🔭',
  },
  {
    id: 'creative-reset',
    title: 'Creative Reset',
    description: 'Draw, journal, or make something offline.',
    reward: 20,
    category: 'Wellness',
    emoji: '🎨',
  },
  {
    id: 'study-sprint',
    title: 'Study Sprint',
    description: 'Do a 25-minute focus session.',
    reward: 25,
    category: 'Focus',
    emoji: '⏳',
  },
  {
    id: 'wind-down',
    title: 'No-Phone Wind Down',
    description: 'Put your phone away before bed.',
    reward: 20,
    category: 'Wellness',
    emoji: '🌙',
  },
];

/** Maps a challenge category to a Chrysalis tone token for the tag tint. */
export const CATEGORY_TONE = {
  IRL: 'healthy',
  Wellness: 'reset',
  Friendship: 'positive',
  Perspective: 'perspective',
  Focus: 'creative',
};

/**
 * "Your Circle" — people already matched. Guided actions only (Invite to
 * Challenge / Send Encouragement); no open DMs in this first pass.
 */
export const STARTER_CIRCLE = [
  {
    id: 'maya',
    name: 'Maya',
    emoji: '🌸',
    circleGoal: 'Weekly reset buddy',
    activity: 'Try a 10-minute walk together',
  },
  {
    id: 'jordan',
    name: 'Jordan',
    emoji: '🌎',
    circleGoal: 'Perspective buddy',
    activity: 'Exchange one new idea this week',
  },
  {
    id: 'anika',
    name: 'Anika',
    emoji: '🌿',
    circleGoal: 'Wellness buddy',
    activity: 'Do a wind-down challenge tonight',
  },
];

/** Safety / intentional-design notes for the footer card. */
export const SAFETY_NOTES = [
  'Avatar-first profiles',
  'Goal-based matching',
  'No follower counts',
  'No popularity scores',
  'Limited friend discovery',
  'Guided messaging',
  'Dewdrops reward healthy actions, not engagement addiction',
];

export const SAFETY_COPY =
  'Community is designed to make connection feel lower-pressure. Chrysalis uses '
  + 'avatar-based profiles, goal-based matching, and guided actions so users can '
  + 'build friendships without turning themselves into content.';
