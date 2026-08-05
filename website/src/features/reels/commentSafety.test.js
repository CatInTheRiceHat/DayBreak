/**
 * Unit tests for comment safety + friends-only messaging. Run: npm run test:unit
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SAFETY_OK,
  SAFETY_CAUTION,
  SAFETY_BLOCK,
  HEATED_COOLDOWN_MS,
  analyzeComment,
  isAggressive,
} from './commentSafety.js';
import { canMessage, isFriend, messageOutcome, FRIENDS_ONLY_MESSAGE } from './messaging.js';

// ── comment safety ──────────────────────────────────────────────────────────

test('normal positive comments post directly', () => {
  const result = analyzeComment('This made my day, thank you so much!');
  assert.equal(result.level, SAFETY_OK);
  assert.equal(result.canPostDirectly, true);
  assert.equal(result.suggestion, null);
  assert.ok(result.nudge, 'ok comments get a positive nudge');
});

test('empty comment is ok but not postable', () => {
  const result = analyzeComment('   ');
  assert.equal(result.level, SAFETY_OK);
  assert.equal(result.canPostDirectly, false);
});

test('harsh/insulting comments are caution with a rewrite prompt + cooldown', () => {
  const result = analyzeComment('you are such an idiot');
  assert.equal(result.level, SAFETY_CAUTION);
  assert.equal(result.canPostDirectly, false);
  assert.equal(result.allowPostAnyway, true);
  assert.equal(result.cooldownMs, HEATED_COOLDOWN_MS);
  assert.ok(result.suggestion && result.suggestion.length > 0);
});

test('all-caps shouting is treated as aggressive tone', () => {
  const result = analyzeComment('WHY ARE YOU SO WRONG!!!');
  assert.equal(result.level, SAFETY_CAUTION);
});

test('targeted harm / threats are blocked and ask to rephrase', () => {
  for (const text of ['kys', 'you should kill yourself', "i'll find you"]) {
    const result = analyzeComment(text);
    assert.equal(result.level, SAFETY_BLOCK, `expected block for: ${text}`);
    assert.equal(result.allowPostAnyway, false);
    assert.ok(result.suggestion);
  }
});

test('isAggressive is true only for caution/block', () => {
  assert.equal(isAggressive('love this!'), false);
  assert.equal(isAggressive('you are an idiot'), true);
  assert.equal(isAggressive('kys'), true);
});

test('word-boundary matching avoids false positives', () => {
  // "class" must not trip on a substring; "assignment" must not flag.
  assert.equal(analyzeComment('great class today, loved it').level, SAFETY_OK);
});

test('analysis is deterministic for the same input', () => {
  const a = analyzeComment('you are an idiot');
  const b = analyzeComment('you are an idiot');
  assert.equal(a.suggestion, b.suggestion);
});

// ── friends-only messaging ──────────────────────────────────────────────────

test('friends can be messaged, strangers cannot', () => {
  assert.equal(isFriend('maya'), true);
  assert.equal(canMessage('maya'), true);
  assert.equal(canMessage('stranger-jay'), false);
  assert.equal(isFriend('nobody'), false);
});

test('messageOutcome explains the friends-only block', () => {
  assert.deepEqual(messageOutcome('liam'), { allowed: true, reason: null });
  const blocked = messageOutcome('stranger-sam');
  assert.equal(blocked.allowed, false);
  assert.equal(blocked.reason, FRIENDS_ONLY_MESSAGE);
});

test('messaging respects a custom friends list', () => {
  const custom = [{ id: 'alex' }];
  assert.equal(canMessage('alex', custom), true);
  assert.equal(canMessage('maya', custom), false);
});
