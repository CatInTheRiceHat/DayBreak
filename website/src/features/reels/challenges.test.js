/**
 * Unit tests for the IRL challenges logic (streaks, points, badges, leaderboard).
 * Run with: npm run test:unit
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  dateKey,
  dayNumber,
  currentStreak,
  computeStats,
  todayCompletions,
  isCompletedToday,
  completeChallenge,
  earnedBadgeIds,
  badgeShelf,
  buildLeaderboard,
} from './challenges.js';

test('dateKey formats a Date as local YYYY-MM-DD', () => {
  assert.equal(dateKey(new Date(2026, 5, 16)), '2026-06-16');
  assert.match(dateKey(), /^\d{4}-\d{2}-\d{2}$/);
});

test('dayNumber gives consecutive integers for consecutive days', () => {
  assert.equal(dayNumber('2026-06-16') - dayNumber('2026-06-15'), 1);
  assert.equal(dayNumber('2026-07-01') - dayNumber('2026-06-30'), 1);
});

test('currentStreak is 0 with no completions', () => {
  assert.equal(currentStreak([], '2026-06-16'), 0);
  assert.equal(currentStreak(undefined, '2026-06-16'), 0);
});

test('currentStreak counts consecutive days ending today', () => {
  assert.equal(currentStreak(['2026-06-14', '2026-06-15', '2026-06-16'], '2026-06-16'), 3);
});

test('currentStreak keeps yesterday-only streak alive (grace day)', () => {
  // Completed through yesterday, not yet today -> streak still shown.
  assert.equal(currentStreak(['2026-06-14', '2026-06-15'], '2026-06-16'), 2);
});

test('currentStreak resets after a 2-day gap', () => {
  assert.equal(currentStreak(['2026-06-10', '2026-06-11'], '2026-06-16'), 0);
});

test('currentStreak ignores duplicate day keys', () => {
  assert.equal(currentStreak(['2026-06-16', '2026-06-16', '2026-06-15'], '2026-06-16'), 2);
});

test('computeStats sums points and totals across days', () => {
  const state = {
    completedByDate: {
      '2026-06-15': { walk: { points: 15 }, water: { points: 5 } },
      '2026-06-16': { journal: { points: 10 } },
    },
  };
  const stats = computeStats(state, '2026-06-16');
  assert.equal(stats.totalCompleted, 3);
  assert.equal(stats.points, 30);
  assert.equal(stats.streak, 2);
  assert.equal(stats.longestStreak, 2);
});

test('computeStats handles empty state', () => {
  const stats = computeStats(undefined, '2026-06-16');
  assert.deepEqual(stats, { totalCompleted: 0, points: 0, streak: 0, longestStreak: 0 });
});

test('completeChallenge adds a completion and is idempotent per day', () => {
  let state = { completedByDate: {} };
  state = completeChallenge(state, { challengeId: 'walk', points: 15, todayKey: '2026-06-16' });
  assert.ok(isCompletedToday(state, 'walk', '2026-06-16'));
  assert.equal(Object.keys(todayCompletions(state, '2026-06-16')).length, 1);

  // Re-completing the same challenge today does nothing (no point farming).
  const before = JSON.stringify(state);
  state = completeChallenge(state, { challengeId: 'walk', points: 15, todayKey: '2026-06-16' });
  assert.equal(JSON.stringify(state), before);

  state = completeChallenge(state, { challengeId: 'water', points: 5, reflection: 'felt good', todayKey: '2026-06-16' });
  assert.equal(computeStats(state, '2026-06-16').points, 20);
  assert.equal(todayCompletions(state, '2026-06-16').water.reflection, 'felt good');
});

test('completeChallenge ignores a missing challengeId', () => {
  const state = { completedByDate: {} };
  assert.equal(completeChallenge(state, {}), state);
});

test('earnedBadgeIds unlocks by total, streak, and points thresholds', () => {
  assert.deepEqual(earnedBadgeIds({ totalCompleted: 0, streak: 0, points: 0 }), []);
  assert.ok(earnedBadgeIds({ totalCompleted: 1, streak: 0, points: 0 }).includes('first-step'));
  assert.ok(earnedBadgeIds({ totalCompleted: 10, streak: 3, points: 0 }).includes('touch-grass'));
  assert.ok(earnedBadgeIds({ totalCompleted: 10, streak: 3, points: 0 }).includes('spark'));
  assert.ok(earnedBadgeIds({ totalCompleted: 0, streak: 0, points: 100 }).includes('centurion'));
});

test('badgeShelf marks earned vs locked', () => {
  const shelf = badgeShelf({ totalCompleted: 1, streak: 0, points: 0 });
  const first = shelf.find((b) => b.id === 'first-step');
  const locked = shelf.find((b) => b.id === 'centurion');
  assert.equal(first.earned, true);
  assert.equal(locked.earned, false);
});

test('buildLeaderboard inserts You, sorts by points, and ranks', () => {
  const board = buildLeaderboard({ points: 1000, streak: 9 });
  assert.equal(board[0].isYou, true);
  assert.equal(board[0].rank, 1);
  // ranks are sequential and unique
  assert.deepEqual(board.map((r) => r.rank), board.map((_, i) => i + 1));

  const low = buildLeaderboard({ points: 0, streak: 0 });
  assert.equal(low.find((r) => r.isYou).rank, low.length);
});
