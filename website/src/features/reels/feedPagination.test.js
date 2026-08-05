/**
 * Unit tests for the feed pagination dedupe contract.
 * Run: npm run test:unit
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { cardVideoId, selectFreshCards } from './feedPagination.js';

test('cardVideoId prefers the raw youtube id, falls back to id', () => {
  assert.equal(cardVideoId({ raw_youtube_id: 'abc', id: 'xyz' }), 'abc');
  assert.equal(cardVideoId({ id: 'xyz' }), 'xyz');
  assert.equal(cardVideoId({}), null);
  assert.equal(cardVideoId(null), null);
});

test('selectFreshCards drops cards already seen and records every returned id', () => {
  const seen = new Set(['a']);
  const page = [
    { raw_youtube_id: 'a' }, // already seen → skipped
    { raw_youtube_id: 'b' },
    { raw_youtube_id: 'c' },
  ];
  const { fresh, returnedIds } = selectFreshCards(seen, page);
  assert.deepEqual(fresh.map(cardVideoId), ['b', 'c']);
  assert.deepEqual(returnedIds, ['a', 'b', 'c']);
  assert.deepEqual([...seen].sort(), ['a', 'b', 'c']);
});

test('selectFreshCards dedupes within a single page', () => {
  const seen = new Set();
  const page = [{ id: 'x' }, { id: 'x' }, { id: 'y' }];
  const { fresh } = selectFreshCards(seen, page);
  assert.deepEqual(fresh.map(cardVideoId), ['x', 'y']);
});

test('appending pages never produces a duplicate id', () => {
  const seen = new Set();
  const page1 = [{ id: '1' }, { id: '2' }, { id: '3' }];
  const page2 = [{ id: '3' }, { id: '4' }]; // '3' overlaps and must be dropped
  const out = [];
  for (const page of [page1, page2]) {
    out.push(...selectFreshCards(seen, page).fresh);
  }
  const ids = out.map(cardVideoId);
  assert.deepEqual(ids, ['1', '2', '3', '4']);
  assert.equal(ids.length, new Set(ids).size);
});

test('a card with no id is never appended', () => {
  const seen = new Set();
  const { fresh, returnedIds } = selectFreshCards(seen, [{}, { id: 'ok' }]);
  assert.deepEqual(fresh.map(cardVideoId), ['ok']);
  assert.deepEqual(returnedIds, ['ok']);
});
