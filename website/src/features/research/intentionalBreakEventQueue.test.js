import assert from 'node:assert/strict';
import test from 'node:test';
import {
  createIntentionalBreakEventQueue,
  INTENTIONAL_BREAK_EVENT_QUEUE_PREFIX,
  MAX_TERMINAL_EVENTS,
  readIntentionalBreakQueueSnapshot,
  retryDelayMs,
} from './intentionalBreakEventQueue.js';

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
}

function event(overrides = {}) {
  return {
    eventType: 'post_impression',
    postId: 'post-1',
    onceKey: 'post_impression:post-1',
    sessionPosition: 1,
    metadata: { visibility_ratio: 0.8, visible_ms: 1_000 },
    ...overrides,
  };
}

test('queue persists under a v1 session key and restores stable event identity', async () => {
  const storage = new MemoryStorage();
  let resolveSend;
  const queue = createIntentionalBreakEventQueue({
    sessionId: 'session-1',
    storage,
    createId: () => 'event-uuid-1',
    now: () => '2026-08-07T12:00:00.000Z',
    send: () => new Promise((resolve) => { resolveSend = resolve; }),
  });
  queue.enqueue(event());
  const saved = readIntentionalBreakQueueSnapshot('session-1', storage);
  assert.equal(saved.pending[0].client_event_id, 'event-uuid-1');
  assert.equal(saved.pending[0].first_queued_at, '2026-08-07T12:00:00.000Z');
  assert.equal(storage.values.has(`${INTENTIONAL_BREAK_EVENT_QUEUE_PREFIX}session-1`), true);
  queue.destroy();

  const restored = createIntentionalBreakEventQueue({
    sessionId: 'session-1', storage, send: async () => ({ journey: { journey_state: 'active' } }),
  });
  assert.equal(restored.snapshot().pending[0].client_event_id, 'event-uuid-1');
  resolveSend?.({});
  restored.destroy();
});

test('retryable failure retains the same UUID and uses bounded exponential backoff', async () => {
  const calls = [];
  const delays = [];
  let attempts = 0;
  const queue = createIntentionalBreakEventQueue({
    sessionId: 'session-1',
    storage: new MemoryStorage(),
    createId: () => 'stable-event-id',
    setTimer: (_callback, delay) => { delays.push(delay); return delays.length; },
    clearTimer() {},
    send: async (events) => {
      calls.push(events[0]);
      attempts += 1;
      if (attempts === 1) throw Object.assign(new Error('offline'), { retryable: true });
      return { journey: { journey_state: 'active' } };
    },
  });
  queue.enqueue(event());
  await queue.flush();
  assert.equal(queue.snapshot().pending.length, 1);
  assert.equal(queue.snapshot().pending[0].retry_count, 1);
  assert.deepEqual(delays, [1_000]);
  await queue.flush();
  assert.equal(calls[0].client_event_id, calls[1].client_event_id);
  assert.equal(queue.snapshot().pending.length, 0);
  assert.deepEqual([1, 2, 3, 4, 5, 6, 20].map(retryDelayMs), [1_000, 2_000, 4_000, 8_000, 16_000, 30_000, 30_000]);
});

test('permanent failure becomes bounded terminal diagnostics and never auto-retries', async () => {
  let calls = 0;
  const queue = createIntentionalBreakEventQueue({
    sessionId: 'session-1',
    storage: new MemoryStorage(),
    createId: (() => { let id = 0; return () => `event-${++id}`; })(),
    send: async () => {
      calls += 1;
      throw Object.assign(new Error('rejected'), { retryable: false, errorCode: 'event_not_allowed' });
    },
  });
  for (let index = 0; index < MAX_TERMINAL_EVENTS + 5; index += 1) {
    queue.enqueue(event({ postId: `post-${index}`, onceKey: `impression:${index}` }));
    await queue.flush();
  }
  assert.equal(calls, MAX_TERMINAL_EVENTS + 5);
  assert.equal(queue.snapshot().pending.length, 0);
  assert.equal(queue.snapshot().terminal.length, MAX_TERMINAL_EVENTS);
  await queue.flush();
  assert.equal(calls, MAX_TERMINAL_EVENTS + 5);
});

test('acknowledged events are removed, once records prevent back-scroll duplicates, and journey is forwarded', async () => {
  const journeys = [];
  const queue = createIntentionalBreakEventQueue({
    sessionId: 'session-1',
    storage: new MemoryStorage(),
    createId: () => 'event-1',
    send: async () => ({ journey: { journey_state: 'checkout' }, events: [{ client_event_id: 'event-1' }] }),
    onJourney: (journey) => journeys.push(journey),
  });
  const first = queue.enqueue(event());
  await queue.flush();
  const duplicate = queue.enqueue(event());
  assert.equal(first.enqueued, true);
  assert.equal(duplicate.enqueued, false);
  assert.equal(duplicate.status, 'accepted');
  assert.equal(queue.snapshot().pending.length, 0);
  assert.equal(journeys[0].journey_state, 'checkout');
});

test('concurrent flush calls share one request and payload excludes authoritative fields', async () => {
  let resolve;
  const calls = [];
  const queue = createIntentionalBreakEventQueue({
    sessionId: 'session-1',
    storage: new MemoryStorage(),
    createId: () => 'event-1',
    send: (events) => {
      calls.push(events);
      return new Promise((done) => { resolve = done; });
    },
  });
  queue.enqueue(event());
  const first = queue.flush();
  const second = queue.flush();
  assert.equal(first, second);
  assert.equal(calls.length, 1);
  assert.deepEqual(Object.keys(calls[0][0]).sort(), [
    'client_event_id',
    'client_sequence_number',
    'client_timestamp',
    'event_type',
    'metadata',
    'post_id',
  ]);
  assert.equal(calls[0][0].session_position, undefined);
  assert.equal(calls[0][0].server_sequence_number, undefined);
  resolve({ journey: { journey_state: 'active' } });
  await first;
});
