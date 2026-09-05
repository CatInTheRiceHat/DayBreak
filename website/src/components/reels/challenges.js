/**
 * Pure, testable logic for Chrysalis IRL challenges: streak calculation, points,
 * badge unlocks, and leaderboard assembly. No React, no storage, no Date.now in
 * the core math — the caller passes "today" so the rules are deterministic and
 * unit-testable (see challenges.test.js).
 */

import { BADGES, DEMO_FRIENDS } from './challengesData.js';

/** Local-time YYYY-MM-DD key for a Date (defaults to now). */
export function dateKey(date = new Date()) {
  const d = date instanceof Date ? date : new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/** Whole-day index for a YYYY-MM-DD key (UTC-based, so DST never shifts it). */
export function dayNumber(key) {
  const [year, month, day] = String(key).split('-').map(Number);
  return Math.floor(Date.UTC(year, month - 1, day) / 86_400_000);
}

/**
 * Consecutive-day streak ending today. Completing today extends the streak;
 * if today isn't done yet but yesterday was, the streak still stands (grace) so
 * the count doesn't visually reset before the user acts. A gap of 2+ days = 0.
 */
export function currentStreak(completedKeys, todayKeyStr = dateKey()) {
  const days = new Set((completedKeys || []).map(dayNumber));
  const today = dayNumber(todayKeyStr);
  let cursor;
  if (days.has(today)) cursor = today;
  else if (days.has(today - 1)) cursor = today - 1;
  else return 0;

  let streak = 0;
  while (days.has(cursor)) {
    streak += 1;
    cursor -= 1;
  }
  return streak;
}

const EMPTY_STATE = { completedByDate: {} };

/** Derive totals from raw state. `state.completedByDate[dateKey][challengeId] = {points,...}`. */
export function computeStats(state = EMPTY_STATE, todayKeyStr = dateKey()) {
  const completedByDate = state?.completedByDate || {};
  const keys = Object.keys(completedByDate);
  let totalCompleted = 0;
  let points = 0;
  for (const key of keys) {
    const day = completedByDate[key];
    for (const challengeId of Object.keys(day)) {
      totalCompleted += 1;
      points += Number(day[challengeId]?.points) || 0;
    }
  }
  const streak = currentStreak(keys, todayKeyStr);
  const longestStreak = computeLongestStreak(keys);
  return { totalCompleted, points, streak, longestStreak };
}

function computeLongestStreak(completedKeys) {
  const days = [...new Set((completedKeys || []).map(dayNumber))].sort((a, b) => a - b);
  let best = 0;
  let run = 0;
  let prev = null;
  for (const day of days) {
    run = prev !== null && day === prev + 1 ? run + 1 : 1;
    if (run > best) best = run;
    prev = day;
  }
  return best;
}

/** Today's completed challenge ids → details. */
export function todayCompletions(state = EMPTY_STATE, todayKeyStr = dateKey()) {
  return state?.completedByDate?.[todayKeyStr] || {};
}

export function isCompletedToday(state, challengeId, todayKeyStr = dateKey()) {
  return Boolean(todayCompletions(state, todayKeyStr)[challengeId]);
}

/**
 * Record a completion. Idempotent per (day, challenge): completing the same
 * challenge twice in a day is a no-op, so points can't be farmed by re-tapping.
 */
export function completeChallenge(state = EMPTY_STATE, { challengeId, points, reflection, todayKey = dateKey(), completedAt } = {}) {
  if (!challengeId) return state;
  const completedByDate = { ...(state?.completedByDate || {}) };
  const day = { ...(completedByDate[todayKey] || {}) };
  if (day[challengeId]) return state;
  day[challengeId] = {
    points: Number(points) || 0,
    reflection: reflection || null,
    completedAt: completedAt || new Date().toISOString(),
  };
  completedByDate[todayKey] = day;
  return { ...state, completedByDate };
}

/** Badge ids the given stats have unlocked. */
export function earnedBadgeIds(stats) {
  return BADGES.filter((badge) => (Number(stats?.[badge.metric]) || 0) >= badge.threshold).map((badge) => badge.id);
}

/** All badges annotated with `earned`, for rendering the badge shelf. */
export function badgeShelf(stats) {
  const earned = new Set(earnedBadgeIds(stats));
  return BADGES.map((badge) => ({ ...badge, earned: earned.has(badge.id) }));
}

/**
 * Friendly leaderboard: demo friends + the signed-in "You" row, sorted by points
 * then streak. Returns rows annotated with rank and isYou.
 */
export function buildLeaderboard(stats, friends = DEMO_FRIENDS) {
  const you = { id: 'you', name: 'You', emoji: '🌊', points: stats?.points || 0, streak: stats?.streak || 0, isYou: true };
  const rows = [...friends.map((f) => ({ ...f, isYou: false })), you]
    .sort((a, b) => (b.points - a.points) || (b.streak - a.streak) || a.name.localeCompare(b.name));
  return rows.map((row, index) => ({ ...row, rank: index + 1 }));
}
