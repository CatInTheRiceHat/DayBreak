/**
 * Tests for interest-based feed boosting. Run: npm run test:unit
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { rankByInterests, interestMatchScore } from './interestRanking.js';

const cards = [
  { id: 'a', title: 'Morning stretch routine', description: 'a calm reset' },
  { id: 'b', title: 'Lo-fi guitar session', description: 'chill music to study to' },
  { id: 'c', title: 'Watercolor painting basics', content_category: 'art' },
  { id: 'd', title: 'Trending news recap', description: 'headlines' },
];

test('no interests → original order preserved', () => {
  const out = rankByInterests(cards, []);
  assert.deepEqual(out.map((c) => c.id), ['a', 'b', 'c', 'd']);
});

test('matching cards rise; non-matching keep relative order', () => {
  const out = rankByInterests(cards, ['music', 'art']);
  // b (music) and c (art) match → front; a and d unchanged among themselves.
  assert.deepEqual(out.map((c) => c.id), ['b', 'c', 'a', 'd']);
});

test('score counts distinct interests matched', () => {
  const card = { title: 'painting and guitar', content_category: 'art' };
  assert.equal(interestMatchScore(card, ['art', 'music']), 2);
  assert.equal(interestMatchScore(card, ['art', 'gaming']), 1);
  assert.equal(interestMatchScore(card, ['gaming']), 0);
});

test('matches against hashtags too', () => {
  const card = { title: 'clip', display_hashtags: ['#photography', '#sunset'] };
  assert.equal(interestMatchScore(card, ['photography']), 1);
});

test('is a stable sort — equal scores keep backend order', () => {
  const eq = [
    { id: 'x', title: 'music one' },
    { id: 'y', title: 'music two' },
  ];
  assert.deepEqual(rankByInterests(eq, ['music']).map((c) => c.id), ['x', 'y']);
});
