/**
 * Seed data for curated Chrysalis profiles: the option vocabularies (wellbeing
 * goals, interests, favorite activities), the signed-in user's default profile,
 * and a small set of community profiles to connect with.
 *
 * Profiles are intentionally about meaning, not popularity — there are no follower
 * counts, no popularity ranking, no comparison metrics. Community profile ids reuse
 * the challenge leaderboard friend ids so profiles, friends, and challenges link up.
 */

// Wellbeing goals (from the product spec).
export const WELLBEING_GOALS = [
  { id: 'mindful', label: 'Be more mindful', emoji: '🧘' },
  { id: 'less-doomscroll', label: 'Spend less time doomscrolling', emoji: '🌅' },
  { id: 'more-offline', label: 'Try more offline activities', emoji: '🌳' },
  { id: 'learn-perspectives', label: 'Learn new perspectives', emoji: '🔭' },
  { id: 'more-creative', label: 'Be more creative', emoji: '🎨' },
  { id: 'better-friendships', label: 'Build better friendships', emoji: '🤝' },
  { id: 'stay-motivated', label: 'Stay motivated', emoji: '⚡' },
];

export const INTERESTS = [
  { id: 'art', label: 'Art' },
  { id: 'music', label: 'Music' },
  { id: 'journaling', label: 'Journaling' },
  { id: 'walking', label: 'Walking' },
  { id: 'cooking', label: 'Cooking' },
  { id: 'reading', label: 'Reading' },
  { id: 'photography', label: 'Photography' },
  { id: 'gaming', label: 'Gaming' },
  { id: 'sports', label: 'Sports' },
  { id: 'nature', label: 'Nature' },
  { id: 'volunteering', label: 'Volunteering' },
  { id: 'learning', label: 'Learning' },
];

// Favorite activities reuse the break/challenge activity vocabulary so the whole
// app speaks the same "touch grass" language.
export const FAVORITE_ACTIVITIES = [
  { id: 'walk', label: 'Walking', emoji: '🚶' },
  { id: 'journal', label: 'Journaling', emoji: '📔' },
  { id: 'draw', label: 'Drawing', emoji: '✏️' },
  { id: 'stretch', label: 'Stretching', emoji: '🧘' },
  { id: 'creative', label: 'Making things', emoji: '🎨' },
  { id: 'message-friend', label: 'Catching up with friends', emoji: '💬' },
];

export const DEFAULT_PROFILE = {
  displayName: 'You',
  handle: '@you',
  emoji: '🌊',
  bio: 'Here for a calmer, kinder feed and more real-life moments.',
  goals: ['less-doomscroll', 'more-offline', 'better-friendships'],
  interests: ['journaling', 'walking', 'music'],
  activities: ['walk', 'journal'],
};

// Community profiles to discover and connect with. Friend ids (maya, liam, aria,
// noah, zoe) match the challenge leaderboard; the rest are connectable strangers.
export const COMMUNITY_PROFILES = [
  {
    id: 'maya', displayName: 'Maya', emoji: '🌸',
    bio: 'Morning walks and gratitude journaling. Always up for a calm chat.',
    goals: ['mindful', 'better-friendships'], interests: ['walking', 'journaling', 'nature'],
  },
  {
    id: 'liam', displayName: 'Liam', emoji: '🎧',
    bio: 'Lo-fi playlists, slow evenings, fewer hot takes.',
    goals: ['less-doomscroll', 'stay-motivated'], interests: ['music', 'reading'],
  },
  {
    id: 'aria', displayName: 'Aria', emoji: '🌿',
    bio: 'Plant person learning to log off and touch grass.',
    goals: ['more-offline', 'mindful'], interests: ['nature', 'photography'],
  },
  {
    id: 'rin', displayName: 'Rin', emoji: '🪴',
    bio: 'Sketchbook always open. Looking for creative friends.',
    goals: ['more-creative', 'better-friendships'], interests: ['art', 'photography'],
  },
  {
    id: 'theo', displayName: 'Theo', emoji: '📚',
    bio: 'Reading more, scrolling less. Curious about other perspectives.',
    goals: ['learn-perspectives', 'less-doomscroll'], interests: ['reading', 'learning'],
  },
];

const GOAL_BY_ID = Object.fromEntries(WELLBEING_GOALS.map((g) => [g.id, g]));
const INTEREST_BY_ID = Object.fromEntries(INTERESTS.map((i) => [i.id, i]));
const ACTIVITY_BY_ID = Object.fromEntries(FAVORITE_ACTIVITIES.map((a) => [a.id, a]));

export const goalById = (id) => GOAL_BY_ID[id] || null;
export const interestById = (id) => INTEREST_BY_ID[id] || null;
export const activityById = (id) => ACTIVITY_BY_ID[id] || null;
