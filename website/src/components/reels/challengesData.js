/**
 * Seed data for Chrysalis IRL challenges: the daily challenge list, milestone
 * badges, and a friendly (non-toxic) demo leaderboard.
 *
 * No real accounts exist yet, so friends + their scores are deterministic demo
 * data; the signed-in "You" row is filled from local challenge state at runtime.
 * Tone is a positive game — points and streaks, never guilt or shame.
 */

// Each challenge links to a BreakScreen activity id where it makes sense, so the
// break flow and the challenges panel reinforce the same real-world actions.
export const CHALLENGES = [
  { id: 'walk', label: 'Take a 10-minute walk', emoji: '🚶', points: 15, blurb: 'Step outside and move a little.', activityId: 'walk' },
  { id: 'water', label: 'Drink a glass of water', emoji: '💧', points: 5, blurb: 'Quick hydration win.', activityId: 'water' },
  { id: 'draw', label: 'Draw something', emoji: '✏️', points: 10, blurb: 'Doodles count.', activityId: 'draw' },
  { id: 'journal', label: 'Journal for 5 minutes', emoji: '📔', points: 10, blurb: 'One honest paragraph.', activityId: 'journal' },
  { id: 'snack', label: 'Grab a snack away from your phone', emoji: '🍎', points: 5, blurb: 'Eat, screen-free.', activityId: 'snack' },
  { id: 'compliment', label: 'Compliment someone', emoji: '💛', points: 10, blurb: 'Make a day brighter.', activityId: 'message-friend' },
  { id: 'message-friend', label: 'Message a friend', emoji: '💬', points: 10, blurb: 'Say hi to someone you like.', activityId: 'message-friend' },
  { id: 'study', label: 'Study or work for 20 minutes', emoji: '📚', points: 20, blurb: 'One focused sprint.', activityId: 'creative' },
  { id: 'creative', label: 'Try a creative activity', emoji: '🎨', points: 10, blurb: 'Make or build something.', activityId: 'creative' },
  { id: 'calm-reset', label: 'Do one calming reset', emoji: '🌿', points: 10, blurb: 'Breathe and slow down.', activityId: 'stretch' },
];

// Milestone badges. Data-driven: each unlocks when stats[metric] >= threshold.
export const BADGES = [
  { id: 'first-step', label: 'First Step', emoji: '🌱', metric: 'totalCompleted', threshold: 1, blurb: 'Completed your first challenge.' },
  { id: 'getting-going', label: 'Getting Going', emoji: '🚶', metric: 'totalCompleted', threshold: 5, blurb: '5 challenges done.' },
  { id: 'touch-grass', label: 'Touch Grass', emoji: '🌿', metric: 'totalCompleted', threshold: 10, blurb: '10 real-world resets.' },
  { id: 'spark', label: '3-Day Streak', emoji: '🔥', metric: 'streak', threshold: 3, blurb: 'Three days in a row.' },
  { id: 'week-warrior', label: 'Week Warrior', emoji: '⭐', metric: 'streak', threshold: 7, blurb: 'A full week streak.' },
  { id: 'centurion', label: '100 Points', emoji: '🏆', metric: 'points', threshold: 100, blurb: 'Earned 100 points.' },
];

// Friendly demo leaderboard. Points + streaks only — no follower counts, no
// public popularity ranking, just gentle encouragement among friends.
export const DEMO_FRIENDS = [
  { id: 'maya', name: 'Maya', emoji: '🌸', points: 140, streak: 5 },
  { id: 'liam', name: 'Liam', emoji: '🎧', points: 120, streak: 3 },
  { id: 'aria', name: 'Aria', emoji: '🌿', points: 95, streak: 6 },
  { id: 'noah', name: 'Noah', emoji: '⚡', points: 80, streak: 2 },
  { id: 'zoe', name: 'Zoe', emoji: '🎨', points: 60, streak: 4 },
];

export function challengeById(id) {
  return CHALLENGES.find((challenge) => challenge.id === id) || null;
}
