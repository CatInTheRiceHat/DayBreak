export const INTENTIONAL_BREAK_PAGE_SIZE = 12;

export class IntentionalBreakFeedError extends Error {
  constructor(message, code = 'invalid_reserved_items') {
    super(message);
    this.name = 'IntentionalBreakFeedError';
    this.code = code;
    this.retryable = false;
  }
}

export function activeResumePosition(journey, pendingEvents = []) {
  const plannedTotal = journey?.planned_video_count;
  const highest = Number.isInteger(journey?.highest_reached_position)
    ? journey.highest_reached_position
    : 0;
  if (!Number.isInteger(plannedTotal) || plannedTotal < 1) {
    throw new IntentionalBreakFeedError('The active journey has an invalid planned total.');
  }
  if (highest < 0 || highest > plannedTotal) {
    throw new IntentionalBreakFeedError('The active journey has invalid progress.');
  }
  const authoritativeNext = Math.min(plannedTotal, highest > 0 ? highest + 1 : 1);
  const pendingPositions = pendingEvents
    .map((event) => event.session_position)
    .filter((position) => Number.isInteger(position) && position >= 1 && position <= plannedTotal);
  return pendingPositions.length
    ? Math.min(authoritativeNext, ...pendingPositions)
    : authoritativeNext;
}

export function validateReservedItemsPage(response, {
  plannedTotal,
  requestedStart,
  existingItems = [],
} = {}) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) {
    throw new IntentionalBreakFeedError('The reserved-item response is invalid.');
  }
  if (response.planned_total !== plannedTotal) {
    throw new IntentionalBreakFeedError('The reserved batch total changed unexpectedly.');
  }
  if (response.journey_state !== 'active') {
    throw new IntentionalBreakFeedError('The session is no longer active.', 'journey_not_active');
  }
  if (!Array.isArray(response.items)) {
    throw new IntentionalBreakFeedError('The reserved-item response is missing items.');
  }
  const existingPositions = new Set(existingItems.map((item) => item.session_position));
  const sorted = response.items.map((item) => ({ ...item })).sort(
    (left, right) => left.session_position - right.session_position,
  );
  const pagePositions = new Set();
  sorted.forEach((item, index) => {
    const position = item.session_position;
    if (!item.post_id || !Number.isInteger(position)) {
      throw new IntentionalBreakFeedError('A reserved item is missing its canonical identity.');
    }
    if (position < 1 || position > plannedTotal) {
      throw new IntentionalBreakFeedError('A reserved item position is outside the chosen session.');
    }
    if (pagePositions.has(position) || existingPositions.has(position)) {
      throw new IntentionalBreakFeedError('The reserved batch contains a duplicate position.');
    }
    if (position !== requestedStart + index) {
      throw new IntentionalBreakFeedError('The reserved batch contains a position gap.');
    }
    pagePositions.add(position);
  });
  if (sorted.length === 0 && requestedStart <= plannedTotal) {
    throw new IntentionalBreakFeedError('The active session returned no reserved items.');
  }
  const lastPosition = sorted.at(-1)?.session_position ?? requestedStart - 1;
  const hasMore = response.has_more === true;
  if (hasMore && (!Number.isInteger(response.next_position)
    || response.next_position !== lastPosition + 1
    || response.next_position > plannedTotal)) {
    throw new IntentionalBreakFeedError('The reserved batch returned an invalid next position.');
  }
  if (!hasMore && lastPosition < plannedTotal) {
    throw new IntentionalBreakFeedError('The reserved batch ended before the chosen boundary.');
  }
  if (lastPosition === plannedTotal && hasMore) {
    throw new IntentionalBreakFeedError('The reserved batch tried to continue past the boundary.');
  }
  return {
    items: [...existingItems, ...sorted].sort(
      (left, right) => left.session_position - right.session_position,
    ),
    nextPosition: hasMore ? response.next_position : null,
    hasMore,
  };
}

export function shouldLoadNextPage({
  currentPosition,
  loadedItems,
  hasMore,
  loading,
  boundaryPending,
  plannedTotal,
}) {
  if (!hasMore || loading || boundaryPending || !loadedItems.length) return false;
  const lastLoaded = loadedItems.at(-1).session_position;
  return lastLoaded < plannedTotal && currentPosition >= lastLoaded - 2;
}

export function createJourneySynchronizer({
  sessionId,
  onChange,
  BroadcastChannelImpl = globalThis.BroadcastChannel,
  windowObject = globalThis.window,
  storage = globalThis.localStorage,
  now = Date.now,
} = {}) {
  const channelName = 'daybreak-intentional-break-journey-v1';
  const storageKey = `${channelName}:${sessionId}`;
  let channel = null;
  const receive = (payload) => {
    const message = payload?.data ?? payload;
    if (message?.session_id === sessionId) onChange?.();
  };
  const onStorage = (event) => {
    if (event.key !== storageKey || !event.newValue) return;
    try { receive(JSON.parse(event.newValue)); } catch { /* Ignore unrelated malformed storage. */ }
  };
  if (typeof BroadcastChannelImpl === 'function') {
    channel = new BroadcastChannelImpl(channelName);
    channel.addEventListener?.('message', receive);
  } else {
    windowObject?.addEventListener?.('storage', onStorage);
  }
  return {
    signal() {
      const message = { session_id: sessionId, changed_at: now() };
      if (channel) channel.postMessage(message);
      else storage?.setItem?.(storageKey, JSON.stringify(message));
    },
    destroy() {
      channel?.removeEventListener?.('message', receive);
      channel?.close?.();
      windowObject?.removeEventListener?.('storage', onStorage);
    },
  };
}
