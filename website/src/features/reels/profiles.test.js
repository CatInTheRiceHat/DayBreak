/** Unit tests for curated-profile helpers. Run: npm run test:unit */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  mergeProfile,
  toggleInArray,
  isConnected,
  toggleConnection,
  buildCommunity,
} from './profiles.js';
import { DEFAULT_PROFILE } from './profileData.js';

test('mergeProfile returns defaults for empty input', () => {
  assert.deepEqual(mergeProfile(null), DEFAULT_PROFILE);
  assert.deepEqual(mergeProfile(undefined), DEFAULT_PROFILE);
});

test('mergeProfile overlays stored fields and keeps array shapes', () => {
  const merged = mergeProfile({ bio: 'hi', goals: ['mindful'], interests: 'bad' });
  assert.equal(merged.bio, 'hi');
  assert.deepEqual(merged.goals, ['mindful']);
  // non-array interests falls back to default
  assert.deepEqual(merged.interests, DEFAULT_PROFILE.interests);
  assert.equal(merged.displayName, DEFAULT_PROFILE.displayName);
});

test('toggleInArray adds and removes immutably', () => {
  const a = toggleInArray([], 'walk');
  assert.deepEqual(a, ['walk']);
  const b = toggleInArray(a, 'walk');
  assert.deepEqual(b, []);
  assert.deepEqual(toggleInArray(undefined, 'x'), ['x']);
});

test('isConnected: friends always connected, others via connections list', () => {
  assert.equal(isConnected('maya'), true); // leaderboard friend
  assert.equal(isConnected('rin'), false);
  assert.equal(isConnected('rin', ['rin']), true);
});

test('toggleConnection toggles strangers but never drops friends', () => {
  assert.deepEqual(toggleConnection('rin', []), ['rin']);
  assert.deepEqual(toggleConnection('rin', ['rin']), []);
  // friend stays connected; list unchanged
  assert.deepEqual(toggleConnection('maya', []), []);
});

test('buildCommunity annotates friend + connection state', () => {
  const community = buildCommunity(['rin']);
  const maya = community.find((p) => p.id === 'maya');
  const rin = community.find((p) => p.id === 'rin');
  const theo = community.find((p) => p.id === 'theo');
  assert.equal(maya.isFriend, true);
  assert.equal(maya.isConnected, true);
  assert.equal(rin.isFriend, false);
  assert.equal(rin.isConnected, true);
  assert.equal(theo.isConnected, false);
});
