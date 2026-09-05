import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildYouTubeEmbedUrl } from './youtubeEmbed.js';

const VIDEO_ID = 'dQw4w9WgXcQ';

test('muted: true sets mute=1 (required for mobile autoplay)', () => {
  const url = new URL(buildYouTubeEmbedUrl(VIDEO_ID, { muted: true }));
  assert.equal(url.searchParams.get('mute'), '1');
  assert.equal(url.searchParams.get('autoplay'), '1');
});

test('muted: false sets mute=0 (sound-on playback)', () => {
  const url = new URL(buildYouTubeEmbedUrl(VIDEO_ID, { muted: false }));
  assert.equal(url.searchParams.get('mute'), '0');
});

test('always plays inline so it does not go fullscreen on iOS', () => {
  const url = new URL(buildYouTubeEmbedUrl(VIDEO_ID, { muted: true }));
  assert.equal(url.searchParams.get('playsinline'), '1');
});

test('returns null for empty input', () => {
  assert.equal(buildYouTubeEmbedUrl('', { muted: true }), null);
});
