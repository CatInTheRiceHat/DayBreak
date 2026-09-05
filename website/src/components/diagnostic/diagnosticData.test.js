/**
 * Scoring tests for the social-media diagnostic. Run: npm run test:unit
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { scoreDiagnostic } from './diagnosticData.js';

test('all-low answers still return a baseline unlock and the healthy mode', () => {
  const r = scoreDiagnostic({ compulsive: 0, latenight: 0, comparison: 0, doomscroll: 0, goals: [] });
  assert.equal(r.unlockedFeatures.length >= 1, true);
  assert.deepEqual(r.unlockedFeatures, ['feed-compass']);
  assert.equal(r.recommendedMode, 'flutter-feed');
});

test('high late-night unlocks Night Wind-Down', () => {
  const r = scoreDiagnostic({ compulsive: 0, latenight: 3, comparison: 0, doomscroll: 0, goals: [] });
  assert.ok(r.unlockedFeatures.includes('night-wind-down'));
});

test('"Often" (2) counts as high; "Sometimes" (1) does not', () => {
  assert.ok(scoreDiagnostic({ comparison: 2 }).unlockedFeatures.includes('comparison-guard'));
  assert.ok(!scoreDiagnostic({ comparison: 1 }).unlockedFeatures.includes('comparison-guard'));
});

test('compulsive + late-night dominant → Metamorphosis', () => {
  const r = scoreDiagnostic({ compulsive: 3, latenight: 3, comparison: 0, doomscroll: 0, goals: [] });
  assert.equal(r.recommendedMode, 'metamorphosis');
  assert.ok(r.unlockedFeatures.includes('scroll-breaks'));
  assert.ok(r.unlockedFeatures.includes('night-wind-down'));
});

test('comparison + doomscroll dominant → Daily Dew (gentler)', () => {
  const r = scoreDiagnostic({ compulsive: 0, latenight: 0, comparison: 3, doomscroll: 3, goals: [] });
  assert.equal(r.recommendedMode, 'daily-dew');
  assert.ok(r.unlockedFeatures.includes('comparison-guard'));
  assert.ok(r.unlockedFeatures.includes('doomscroll-breaker'));
});

test('tie between awareness and distress breaks toward Daily Dew', () => {
  const r = scoreDiagnostic({ compulsive: 2, latenight: 2, comparison: 2, doomscroll: 2, goals: [] });
  assert.equal(r.recommendedMode, 'daily-dew');
});

test('goals unlock features and never duplicate', () => {
  const r = scoreDiagnostic({
    compulsive: 3, latenight: 3, comparison: 0, doomscroll: 0,
    goals: ['connection', 'control', 'fewer-late'],
  });
  assert.ok(r.unlockedFeatures.includes('prosocial-boost'));
  assert.ok(r.unlockedFeatures.includes('feed-compass'));
  // fewer-late maps to night-wind-down which late-night already unlocked → no dupe
  const count = r.unlockedFeatures.filter((f) => f === 'night-wind-down').length;
  assert.equal(count, 1);
});
