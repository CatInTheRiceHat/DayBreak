import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { createMeaningfulVisibilityTracker } from './meaningfulVisibility.js';
import { createIntentionalBreakEventQueue } from './intentionalBreakEventQueue.js';

function fakeClock() {
  let time = 0;
  let nextId = 1;
  const timers = new Map();
  return {
    setTimer(callback, delay) {
      const id = nextId++;
      timers.set(id, { callback, at: time + delay });
      return id;
    },
    clearTimer(id) { timers.delete(id); },
    advance(ms) {
      const target = time + ms;
      while (true) {
        const due = [...timers.entries()]
          .filter(([, timer]) => timer.at <= target)
          .sort((left, right) => left[1].at - right[1].at)[0];
        if (!due) break;
        const [id, timer] = due;
        timers.delete(id);
        time = timer.at;
        timer.callback();
      }
      time = target;
    },
  };
}

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
}

test('meaningful impression and view use the frozen continuous thresholds and once semantics', async () => {
  const clock = fakeClock();
  const sent = [];
  const queue = createIntentionalBreakEventQueue({
    sessionId: 'session-1',
    storage: new MemoryStorage(),
    createId: (() => { let id = 0; return () => `event-${++id}`; })(),
    send: async (events) => { sent.push(...events); return { journey: { journey_state: 'active' } }; },
  });
  const tracker = createMeaningfulVisibilityTracker({
    setTimer: clock.setTimer,
    clearTimer: clock.clearTimer,
    onImpression: (details) => queue.enqueue({
      eventType: 'post_impression', postId: 'post-7', onceKey: 'post_impression:post-7',
      sessionPosition: 7, metadata: { visibility_ratio: details.visibilityRatio, visible_ms: details.visibleMs },
    }),
    onViewed: (details) => queue.enqueue({
      eventType: 'post_viewed', postId: 'post-7', onceKey: 'post_viewed:post-7',
      sessionPosition: 7, metadata: { visibility_ratio: details.visibilityRatio, visible_ms: details.visibleMs },
    }),
  });
  tracker.update({ isIntersecting: true, ratio: 0.59 });
  clock.advance(4_000);
  assert.deepEqual(sent, []);
  tracker.update({ isIntersecting: true, ratio: 0.6 });
  clock.advance(1_000);
  await queue.flush();
  assert.equal(sent[0].event_type, 'post_impression');
  assert.equal(sent[0].metadata.visible_ms, 1_000);
  clock.advance(2_000);
  await queue.flush();
  assert.equal(sent[1].event_type, 'post_viewed');
  assert.equal(sent[1].metadata.visible_ms, 3_000);
  tracker.update({ isIntersecting: false, ratio: 0 });
  tracker.update({ isIntersecting: true, ratio: 1 });
  clock.advance(4_000);
  await queue.flush();
  assert.equal(sent.length, 2);
});

test('page-hidden interruption resets exposure timing', () => {
  const clock = fakeClock();
  let impressions = 0;
  const tracker = createMeaningfulVisibilityTracker({
    setTimer: clock.setTimer,
    clearTimer: clock.clearTimer,
    onImpression: () => { impressions += 1; },
  });
  tracker.update({ isIntersecting: true, ratio: 0.8 });
  clock.advance(700);
  tracker.setPageVisible(false);
  clock.advance(1_000);
  assert.equal(impressions, 0);
  tracker.setPageVisible(true);
  clock.advance(999);
  assert.equal(impressions, 0);
  clock.advance(1);
  assert.equal(impressions, 1);
});

test('v1 hook flushes on enqueue, online, focus, and visible-page recovery without legacy tracker', async () => {
  const source = await readFile(new URL('./useIntentionalBreakEvents.js', import.meta.url), 'utf8');
  assert.match(source, /appendEvents\(sessionId, events\)/);
  assert.match(source, /addEventListener\('online', flush\)/);
  assert.match(source, /addEventListener\('focus', flush\)/);
  assert.match(source, /visibilitychange/);
  assert.doesNotMatch(source, /researchTracker|\.track\(/);
  assert.doesNotMatch(source, /session_position.*metadata|content_category.*metadata|server_sequence/);
});
