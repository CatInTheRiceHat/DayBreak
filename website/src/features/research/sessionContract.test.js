import assert from 'node:assert/strict';
import test from 'node:test';
import {
  ALLOWED_VIDEO_COUNTS,
  CHECKOUT_VALUES,
  COOLDOWN_INCREMENT_SECONDS,
  FIXED_FEED_POLICY,
  INTENTIONS,
  LIFECYCLE_STATES,
  MAX_COOLDOWN_SECONDS,
  MIN_COOLDOWN_SECONDS,
  NONTERMINAL_STATES,
  OVERRIDE_REASON_CODES,
  VALID_TRANSITIONS,
  calculateRecommendedCooldownSeconds,
  estimateDurationSeconds,
  isAllowedVideoCount,
  isNonterminalState,
  isValidCheckoutAnswers,
  isValidLifecycleTransition,
  isValidOverrideReason,
} from './sessionContract.js';

test('every frozen lifecycle transition is accepted with its required qualifier', () => {
  for (const transition of VALID_TRANSITIONS) {
    assert.equal(
      isValidLifecycleTransition(transition.from, transition.to, transition),
      true,
      JSON.stringify(transition),
    );
  }
});

test('representative invalid lifecycle transitions are rejected', () => {
  const invalidTransitions = [
    ['planned', 'checkout'],
    ['active', 'completed'],
    ['checkout', 'completed'],
    ['cooldown', 'active'],
    ['completed', 'planned'],
    ['cancelled', 'planned'],
    ['active', 'checkout'],
    ['active', 'checkout', { reason: 'unknown' }],
    ['cooldown', 'completed'],
    ['cooldown', 'completed', { outcome: 'unknown' }],
  ];

  for (const [from, to, details] of invalidTransitions) {
    assert.equal(isValidLifecycleTransition(from, to, details), false);
  }
});

test('nonterminal-state detection recognizes only planned through cooldown', () => {
  for (const state of NONTERMINAL_STATES) {
    assert.equal(isNonterminalState(state), true);
  }
  for (const state of ['completed', 'cancelled', 'unknown', null, undefined]) {
    assert.equal(isNonterminalState(state), false);
  }
});

test('all and only the pilot video counts are allowed', () => {
  assert.deepEqual(ALLOWED_VIDEO_COUNTS, [5, 10, 20, 40]);
  for (const count of ALLOWED_VIDEO_COUNTS) {
    assert.equal(isAllowedVideoCount(count), true);
  }
  for (const count of [0, 4, 6, 15, 80, '10', null]) {
    assert.equal(isAllowedVideoCount(count), false);
    assert.throws(() => estimateDurationSeconds(count), RangeError);
  }
});

test('duration estimates cover every pilot count', () => {
  const expected = new Map([
    [5, 150],
    [10, 300],
    [20, 600],
    [40, 1_200],
  ]);
  for (const [count, seconds] of expected) {
    assert.equal(estimateDurationSeconds(count), seconds);
  }
});

test('recommended cooldowns cover every pilot count', () => {
  const expected = new Map([
    [5, 300],
    [10, 600],
    [20, 1_200],
    [40, 2_400],
  ]);
  for (const [count, seconds] of expected) {
    assert.equal(
      calculateRecommendedCooldownSeconds(estimateDurationSeconds(count)),
      seconds,
    );
  }
});

test('recommended cooldown enforces its minimum and maximum', () => {
  assert.equal(calculateRecommendedCooldownSeconds(0), MIN_COOLDOWN_SECONDS);
  assert.equal(calculateRecommendedCooldownSeconds(1), MIN_COOLDOWN_SECONDS);
  assert.equal(calculateRecommendedCooldownSeconds(3_600), MAX_COOLDOWN_SECONDS);
  assert.equal(calculateRecommendedCooldownSeconds(100_000), MAX_COOLDOWN_SECONDS);
  assert.throws(() => calculateRecommendedCooldownSeconds(-1), RangeError);
  assert.throws(() => calculateRecommendedCooldownSeconds(Number.NaN), RangeError);
});

test('recommended cooldown rounds upward to five-minute increments', () => {
  assert.equal(COOLDOWN_INCREMENT_SECONDS, 300);
  assert.equal(calculateRecommendedCooldownSeconds(151), 600);
  assert.equal(calculateRecommendedCooldownSeconds(300), 600);
  assert.equal(calculateRecommendedCooldownSeconds(301), 900);
});

test('checkout validation accepts every allowed value and requires all questions', () => {
  for (const worthwhile of CHECKOUT_VALUES.worthwhile) {
    for (const perceivedControl of CHECKOUT_VALUES.perceivedControl) {
      for (const mood of CHECKOUT_VALUES.mood) {
        assert.equal(isValidCheckoutAnswers({ worthwhile, perceivedControl, mood }), true);
      }
    }
  }

  const invalidAnswers = [
    null,
    [],
    {},
    { worthwhile: 'yes', perceivedControl: 3 },
    { worthwhile: 'sometimes', perceivedControl: 3, mood: 'same' },
    { worthwhile: 'yes', perceivedControl: 0, mood: 'same' },
    { worthwhile: 'yes', perceivedControl: 6, mood: 'same' },
    { worthwhile: 'yes', perceivedControl: '3', mood: 'same' },
    { worthwhile: 'yes', perceivedControl: 3, mood: 'mixed' },
  ];
  for (const answers of invalidAnswers) {
    assert.equal(isValidCheckoutAnswers(answers), false);
  }
});

test('override reason validation accepts only the frozen reason codes', () => {
  for (const reason of OVERRIDE_REASON_CODES) {
    assert.equal(isValidOverrideReason(reason), true);
  }
  for (const reason of ['', 'unknown', 'prefer_not_to_answer', null, 1]) {
    assert.equal(isValidOverrideReason(reason), false);
  }
});

test('exported collections and their nested values are immutable', () => {
  const collections = [
    LIFECYCLE_STATES,
    NONTERMINAL_STATES,
    VALID_TRANSITIONS,
    INTENTIONS,
    ALLOWED_VIDEO_COUNTS,
    CHECKOUT_VALUES,
    CHECKOUT_VALUES.worthwhile,
    CHECKOUT_VALUES.perceivedControl,
    CHECKOUT_VALUES.mood,
    OVERRIDE_REASON_CODES,
    FIXED_FEED_POLICY,
  ];
  for (const collection of collections) {
    assert.equal(Object.isFrozen(collection), true);
  }
  for (const transition of VALID_TRANSITIONS) {
    assert.equal(Object.isFrozen(transition), true);
  }

  assert.throws(() => ALLOWED_VIDEO_COUNTS.push(80), TypeError);
  assert.throws(() => { VALID_TRANSITIONS[0].to = 'active'; }, TypeError);
  assert.throws(() => { CHECKOUT_VALUES.mood = []; }, TypeError);
});
