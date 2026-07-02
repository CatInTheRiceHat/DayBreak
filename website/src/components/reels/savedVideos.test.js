/**
 * Unit tests for the Saved videos store logic (snapshot, add/remove, de-dupe, cap).
 * Run with: npm run test:unit
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  MAX_SAVED,
  toSavedSnapshot,
  isSavedId,
  addSaved,
  removeSaved,
  normalizeSavedList,
} from './savedVideos.js';

const reel = {
  id: 'abc123',
  title: 'A calm walk',
  source: 'Quiet Channel',
  thumbnail: 'https://img/abc.jpg',
  embed_url: 'https://youtu.be/abc123',
};

test('toSavedSnapshot keeps only the display fields and stamps savedAt', () => {
  const snap = toSavedSnapshot(reel, 1000);
  assert.deepEqual(snap, {
    id: 'abc123',
    title: 'A calm walk',
    source: 'Quiet Channel',
    thumbnail: 'https://img/abc.jpg',
    embedUrl: 'https://youtu.be/abc123',
    youtubeId: null,
    savedAt: 1000,
  });
});

test('toSavedSnapshot falls back across field name variants', () => {
  const snap = toSavedSnapshot({ id: 7, image: 'i.jpg', youtubeId: 'yt7' });
  assert.equal(snap.id, '7');
  assert.equal(snap.title, 'Saved video');
  assert.equal(snap.thumbnail, 'i.jpg');
  assert.equal(snap.youtubeId, 'yt7');
});

test('toSavedSnapshot returns null without a usable id', () => {
  assert.equal(toSavedSnapshot({ title: 'no id' }), null);
  assert.equal(toSavedSnapshot(null), null);
});

test('addSaved prepends newest-first and isSavedId reflects membership', () => {
  let list = [];
  list = addSaved(list, toSavedSnapshot({ id: 'a' }, 1));
  list = addSaved(list, toSavedSnapshot({ id: 'b' }, 2));
  assert.deepEqual(list.map((x) => x.id), ['b', 'a']);
  assert.equal(isSavedId(list, 'a'), true);
  assert.equal(isSavedId(list, 'z'), false);
});

test('addSaved de-dupes by id and moves a re-save to the front', () => {
  let list = [toSavedSnapshot({ id: 'a' }, 1), toSavedSnapshot({ id: 'b' }, 2)];
  list = addSaved(list, toSavedSnapshot({ id: 'a' }, 3));
  assert.deepEqual(list.map((x) => x.id), ['a', 'b']);
  assert.equal(list.length, 2);
});

test('addSaved caps the list at MAX_SAVED, dropping the oldest', () => {
  let list = [];
  for (let i = 0; i < MAX_SAVED + 25; i += 1) {
    list = addSaved(list, toSavedSnapshot({ id: `id-${i}` }, i));
  }
  assert.equal(list.length, MAX_SAVED);
  assert.equal(list[0].id, `id-${MAX_SAVED + 24}`); // newest
  assert.equal(isSavedId(list, 'id-0'), false); // oldest dropped
});

test('addSaved does not mutate the input array', () => {
  const original = [toSavedSnapshot({ id: 'a' }, 1)];
  const copy = [...original];
  addSaved(original, toSavedSnapshot({ id: 'b' }, 2));
  assert.deepEqual(original, copy);
});

test('removeSaved drops the matching id and leaves the rest', () => {
  const list = [toSavedSnapshot({ id: 'a' }, 1), toSavedSnapshot({ id: 'b' }, 2)];
  assert.deepEqual(removeSaved(list, 'a').map((x) => x.id), ['b']);
  assert.deepEqual(removeSaved(list, 'missing').map((x) => x.id), ['a', 'b']);
});

test('normalizeSavedList drops junk, de-dupes, and caps', () => {
  assert.deepEqual(normalizeSavedList('nope'), []);
  const dirty = [
    { id: 'a', title: 'A' },
    null,
    { title: 'no id' },
    { id: 'a', title: 'dupe' },
    { id: 'b' },
  ];
  const clean = normalizeSavedList(dirty);
  assert.deepEqual(clean.map((x) => x.id), ['a', 'b']);
  assert.equal(clean[1].title, 'Saved video');
});
