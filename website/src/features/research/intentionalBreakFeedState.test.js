import assert from 'node:assert/strict';
import test from 'node:test';
import {
  activeResumePosition,
  createJourneySynchronizer,
  INTENTIONAL_BREAK_PAGE_SIZE,
  IntentionalBreakFeedError,
  shouldLoadNextPage,
  validateReservedItemsPage,
} from './intentionalBreakFeedState.js';

function journey(highest = 0, total = 20) {
  return { journey_state: 'active', planned_video_count: total, highest_reached_position: highest };
}

function items(from, to) {
  return Array.from({ length: to - from + 1 }, (_, index) => ({
    post_id: `post-${from + index}`,
    session_position: from + index,
  }));
}

function page(pageItems, total, hasMore, nextPosition = null) {
  return {
    items: pageItems,
    planned_total: total,
    journey_state: 'active',
    has_more: hasMore,
    next_position: nextPosition,
  };
}

test('active resume starts at one or highest plus one without session storage', () => {
  assert.equal(activeResumePosition(journey(null)), 1);
  assert.equal(activeResumePosition(journey(0)), 1);
  assert.equal(activeResumePosition(journey(7)), 8);
  assert.equal(activeResumePosition(journey(19)), 20);
});

test('pending local exposure reconciles before advancing beyond its position', () => {
  assert.equal(activeResumePosition(journey(7), [{ session_position: 8 }]), 8);
  assert.equal(activeResumePosition(journey(9), [{ session_position: 8 }]), 8);
});

test('reserved pages sort by canonical position and retain exact progress identity', () => {
  const first = validateReservedItemsPage(page([
    { post_id: 'post-2', session_position: 2 },
    { post_id: 'post-1', session_position: 1 },
  ], 3, true, 3), { plannedTotal: 3, requestedStart: 1 });
  assert.deepEqual(first.items.map((item) => item.session_position), [1, 2]);
  const final = validateReservedItemsPage(page(items(3, 3), 3, false), {
    plannedTotal: 3,
    requestedStart: 3,
    existingItems: first.items,
  });
  assert.deepEqual(final.items.map((item) => item.session_position), [1, 2, 3]);
  assert.equal(final.hasMore, false);
});

test('twelve-item page and final partial page stop at the chosen total', () => {
  assert.equal(INTENTIONAL_BREAK_PAGE_SIZE, 12);
  const first = validateReservedItemsPage(page(items(1, 12), 20, true, 13), {
    plannedTotal: 20,
    requestedStart: 1,
  });
  assert.equal(first.items.length, 12);
  const final = validateReservedItemsPage(page(items(13, 20), 20, false), {
    plannedTotal: 20,
    requestedStart: 13,
    existingItems: first.items,
  });
  assert.equal(final.items.length, 20);
  assert.equal(final.nextPosition, null);
});

test('duplicate, reset, gap, out-of-range, empty, and changed-total pages fail safely', () => {
  const cases = [
    () => validateReservedItemsPage(page([
      { post_id: 'a', session_position: 1 },
      { post_id: 'b', session_position: 1 },
    ], 5, true, 2), { plannedTotal: 5, requestedStart: 1 }),
    () => validateReservedItemsPage(page(items(1, 2), 5, true, 3), {
      plannedTotal: 5, requestedStart: 1, existingItems: items(1, 2),
    }),
    () => validateReservedItemsPage(page([{ post_id: 'a', session_position: 2 }], 5, true, 3), {
      plannedTotal: 5, requestedStart: 1,
    }),
    () => validateReservedItemsPage(page([{ post_id: 'a', session_position: 6 }], 5, false), {
      plannedTotal: 5, requestedStart: 6,
    }),
    () => validateReservedItemsPage(page([], 5, false), { plannedTotal: 5, requestedStart: 1 }),
    () => validateReservedItemsPage(page(items(1, 5), 10, false), {
      plannedTotal: 5, requestedStart: 1,
    }),
  ];
  for (const invoke of cases) assert.throws(invoke, IntentionalBreakFeedError);
});

test('lazy loading stops while final boundary is pending or after has_more false', () => {
  const base = {
    currentPosition: 10,
    loadedItems: items(1, 12),
    hasMore: true,
    loading: false,
    boundaryPending: false,
    plannedTotal: 20,
  };
  assert.equal(shouldLoadNextPage(base), true);
  assert.equal(shouldLoadNextPage({ ...base, boundaryPending: true }), false);
  assert.equal(shouldLoadNextPage({ ...base, hasMore: false }), false);
  assert.equal(shouldLoadNextPage({ ...base, loading: true }), false);
});

test('BroadcastChannel synchronization requests authoritative refresh for the same session', () => {
  class FakeChannel {
    static instances = [];
    constructor() { this.listeners = new Set(); FakeChannel.instances.push(this); }
    addEventListener(_type, listener) { this.listeners.add(listener); }
    removeEventListener(_type, listener) { this.listeners.delete(listener); }
    postMessage(message) {
      FakeChannel.instances.forEach((channel) => {
        if (channel !== this) channel.listeners.forEach((listener) => listener({ data: message }));
      });
    }
    close() {}
  }
  let refreshes = 0;
  const first = createJourneySynchronizer({ sessionId: 'session-1', BroadcastChannelImpl: FakeChannel });
  const second = createJourneySynchronizer({
    sessionId: 'session-1',
    BroadcastChannelImpl: FakeChannel,
    onChange: () => { refreshes += 1; },
  });
  const other = createJourneySynchronizer({
    sessionId: 'session-2',
    BroadcastChannelImpl: FakeChannel,
    onChange: () => { refreshes += 100; },
  });
  first.signal();
  assert.equal(refreshes, 1);
  first.destroy();
  second.destroy();
  other.destroy();
});
