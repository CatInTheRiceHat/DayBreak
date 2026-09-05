/**
 * Unit tests for the progressive screen-time break logic.
 * Run with: npm run test:unit   (uses Node's built-in test runner, no deps)
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  BREAK_TIERS,
  BREAK_ACTIVITIES,
  DEFAULT_TIME_SCALE_MS,
  DEMO_TIME_SCALE_MS,
  MINUTE_MS,
  minutesFromElapsed,
  nextBreakTier,
  dueBreakTier,
  msUntilNextBreak,
  elapsedMsForNextBreak,
  formatCountdown,
  activityById,
  isBreakPending,
} from './sessionBreaks.js';

test('break tiers match the progressive spec', () => {
  assert.deepEqual(
    BREAK_TIERS.map((t) => [t.thresholdMin, t.breakMin]),
    [[60, 10], [90, 15], [120, 20], [150, 30]],
  );
});

test('minutesFromElapsed converts using the time scale', () => {
  assert.equal(minutesFromElapsed(60 * MINUTE_MS), 60);
  assert.equal(minutesFromElapsed(90 * DEMO_TIME_SCALE_MS, DEMO_TIME_SCALE_MS), 90);
  assert.equal(minutesFromElapsed(0), 0);
  assert.equal(minutesFromElapsed(-5), 0);
});

test('nextBreakTier walks the tiers as milestones are completed', () => {
  assert.deepEqual(nextBreakTier(0), { thresholdMin: 60, breakMin: 10 });
  assert.deepEqual(nextBreakTier(60), { thresholdMin: 90, breakMin: 15 });
  assert.deepEqual(nextBreakTier(90), { thresholdMin: 120, breakMin: 20 });
  assert.deepEqual(nextBreakTier(120), { thresholdMin: 150, breakMin: 30 });
});

test('nextBreakTier recurs a 30-min reset beyond the top tier', () => {
  assert.deepEqual(nextBreakTier(150), { thresholdMin: 180, breakMin: 30 });
  assert.deepEqual(nextBreakTier(180), { thresholdMin: 210, breakMin: 30 });
});

test('no break is due before the first hour', () => {
  assert.equal(dueBreakTier(59.9, 0), null);
});

test('a 10-minute break is due at 60 cumulative minutes', () => {
  assert.deepEqual(dueBreakTier(60, 0), { thresholdMin: 60, breakMin: 10 });
  assert.deepEqual(dueBreakTier(75, 0), { thresholdMin: 60, breakMin: 10 });
});

test('breaks escalate: 15 at 90, 20 at 120, 30 at 150', () => {
  assert.equal(dueBreakTier(89, 60), null);
  assert.deepEqual(dueBreakTier(90, 60), { thresholdMin: 90, breakMin: 15 });
  assert.deepEqual(dueBreakTier(120, 90), { thresholdMin: 120, breakMin: 20 });
  assert.deepEqual(dueBreakTier(150, 120), { thresholdMin: 150, breakMin: 30 });
});

test('completing a milestone does not immediately re-trigger', () => {
  // Completed the 60-min break; still at ~60 cumulative min -> nothing due yet.
  assert.equal(dueBreakTier(61, 60), null);
});

test('isBreakPending freezes the clock only while a break is actually due', () => {
  // Demo scale: 1s == 1 "minute".
  const scale = DEMO_TIME_SCALE_MS;
  // Before the first hour, nothing pending -> clock should keep running.
  assert.equal(isBreakPending(30 * scale, 0, scale), false);
  // At 60 "minutes" with nothing completed, the tier-60 break is pending.
  assert.equal(isBreakPending(60 * scale, 0, scale), true);
  // Right after completing the 60 milestone, sitting at ~60 min, NOT pending
  // again (this is the regression that made breaks re-pop instantly).
  assert.equal(isBreakPending(61 * scale, 60, scale), false);
  // Only once the clock would reach the next threshold (90) is it pending again.
  assert.equal(isBreakPending(90 * scale, 60, scale), true);
});

test('msUntilNextBreak counts down to the next threshold (real scale)', () => {
  assert.equal(msUntilNextBreak(0, 0, DEFAULT_TIME_SCALE_MS), 60 * MINUTE_MS);
  assert.equal(msUntilNextBreak(30 * MINUTE_MS, 0, DEFAULT_TIME_SCALE_MS), 30 * MINUTE_MS);
  assert.equal(msUntilNextBreak(60 * MINUTE_MS, 0, DEFAULT_TIME_SCALE_MS), 0);
});

test('demo scale makes a break reachable in seconds', () => {
  // In demo mode 60 "minutes" == 60 seconds.
  assert.equal(elapsedMsForNextBreak(0, DEMO_TIME_SCALE_MS), 60 * 1000);
  const elapsed = elapsedMsForNextBreak(0, DEMO_TIME_SCALE_MS);
  const minutes = minutesFromElapsed(elapsed, DEMO_TIME_SCALE_MS);
  assert.deepEqual(dueBreakTier(minutes, 0), { thresholdMin: 60, breakMin: 10 });
});

test('formatCountdown renders M:SS', () => {
  assert.equal(formatCountdown(10 * 60 * 1000), '10:00');
  assert.equal(formatCountdown(65 * 1000), '1:05');
  assert.equal(formatCountdown(0), '0:00');
  assert.equal(formatCountdown(-5), '0:00');
});

test('activities are well-formed and non-invasive', () => {
  assert.ok(BREAK_ACTIVITIES.length >= 6);
  const ids = new Set(BREAK_ACTIVITIES.map((a) => a.id));
  for (const id of ['walk', 'water', 'journal', 'stretch', 'draw', 'snack', 'message-friend', 'creative']) {
    assert.ok(ids.has(id), `missing activity ${id}`);
  }
  for (const activity of BREAK_ACTIVITIES) {
    assert.equal(typeof activity.label, 'string');
    assert.ok(activity.label.length > 0);
  }
  assert.equal(activityById('walk').label, 'Take a short walk');
  assert.equal(activityById('nope'), null);
});
