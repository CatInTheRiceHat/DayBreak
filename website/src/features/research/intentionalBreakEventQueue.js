export const INTENTIONAL_BREAK_EVENT_QUEUE_PREFIX = 'daybreak-intentional-break-events-v1:';
export const MAX_TERMINAL_EVENTS = 40;
export const MAX_ONCE_RECORDS = 160;

export function retryDelayMs(retryCount) {
  return Math.min(30_000, 1_000 * (2 ** Math.max(0, Math.min(retryCount - 1, 5))));
}

function queueKey(sessionId) {
  return `${INTENTIONAL_BREAK_EVENT_QUEUE_PREFIX}${sessionId}`;
}

function emptyState() {
  return { version: 1, next_sequence: 1, pending: [], terminal: [], once: {} };
}

function normalizedState(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return emptyState();
  return {
    version: 1,
    next_sequence: Number.isInteger(value.next_sequence) && value.next_sequence > 0
      ? value.next_sequence
      : 1,
    pending: Array.isArray(value.pending) ? value.pending : [],
    terminal: Array.isArray(value.terminal) ? value.terminal.slice(-MAX_TERMINAL_EVENTS) : [],
    once: value.once && typeof value.once === 'object' && !Array.isArray(value.once)
      ? value.once
      : {},
  };
}

export function readIntentionalBreakQueueSnapshot(sessionId, storage = globalThis.localStorage) {
  try {
    return normalizedState(JSON.parse(storage?.getItem(queueKey(sessionId)) || 'null'));
  } catch {
    return emptyState();
  }
}

function boundedOnce(once) {
  const entries = Object.entries(once);
  return Object.fromEntries(entries.slice(Math.max(0, entries.length - MAX_ONCE_RECORDS)));
}

function defaultCreateId() {
  if (typeof globalThis.crypto?.randomUUID !== 'function') {
    throw new Error('Secure event UUID generation is unavailable.');
  }
  return globalThis.crypto.randomUUID();
}

function publicSnapshot(state) {
  return {
    pending: state.pending.map((event) => ({ ...event, metadata: { ...event.metadata } })),
    terminal: state.terminal.map((event) => ({ ...event })),
    once: { ...state.once },
    nextSequence: state.next_sequence,
  };
}

export function createIntentionalBreakEventQueue({
  sessionId,
  storage = globalThis.localStorage,
  send,
  createId = defaultCreateId,
  now = () => new Date().toISOString(),
  setTimer = setTimeout,
  clearTimer = clearTimeout,
  onJourney,
  onTerminal,
  onStatus,
} = {}) {
  if (!sessionId || typeof send !== 'function') {
    throw new Error('A session id and event sender are required.');
  }
  let state = readIntentionalBreakQueueSnapshot(sessionId, storage);
  state = {
    version: 1,
    next_sequence: state.next_sequence,
    pending: state.pending,
    terminal: state.terminal,
    once: state.once,
  };
  let flushPromise = null;
  let retryTimer = null;
  let destroyed = false;

  function persist() {
    state.once = boundedOnce(state.once);
    state.terminal = state.terminal.slice(-MAX_TERMINAL_EVENTS);
    storage?.setItem?.(queueKey(sessionId), JSON.stringify(state));
    onStatus?.(publicSnapshot(state));
  }

  function scheduleRetry(event) {
    if (destroyed || retryTimer) return;
    const delay = retryDelayMs(event.retry_count);
    retryTimer = setTimer(() => {
      retryTimer = null;
      flush();
    }, delay);
  }

  async function performFlush() {
    while (!destroyed && state.pending.length) {
      const event = state.pending[0];
      try {
        const response = await send([{
          client_event_id: event.client_event_id,
          client_sequence_number: event.client_sequence_number,
          event_type: event.event_type,
          post_id: event.post_id,
          client_timestamp: event.client_timestamp,
          metadata: { ...event.metadata },
        }]);
        state.pending.shift();
        if (event.once_key) state.once[event.once_key] = 'accepted';
        persist();
        if (response?.journey) onJourney?.(response.journey, event, response);
      } catch (error) {
        event.retry_count += 1;
        event.last_error = {
          error_code: error?.errorCode ?? error?.code ?? 'unknown_error',
          message: error?.message ?? 'Event upload failed.',
          failed_at: now(),
        };
        if (error?.retryable === true) {
          persist();
          scheduleRetry(event);
          return { drained: false, retryScheduled: true };
        }
        state.pending.shift();
        const terminal = { ...event, terminal_at: now(), terminal_error: event.last_error };
        state.terminal.push(terminal);
        if (event.once_key) state.once[event.once_key] = 'terminal';
        persist();
        onTerminal?.(terminal, error);
      }
    }
    return { drained: state.pending.length === 0, retryScheduled: false };
  }

  function flush() {
    if (destroyed) return Promise.resolve({ drained: false, destroyed: true });
    if (flushPromise) return flushPromise;
    if (retryTimer) {
      clearTimer(retryTimer);
      retryTimer = null;
    }
    flushPromise = performFlush().finally(() => { flushPromise = null; });
    return flushPromise;
  }

  function enqueue({ eventType, postId, metadata = {}, onceKey, sessionPosition = null }) {
    if (onceKey && state.once[onceKey]) {
      return { enqueued: false, status: state.once[onceKey] };
    }
    const queuedAt = now();
    const event = {
      client_event_id: createId(),
      client_sequence_number: state.next_sequence,
      event_type: eventType,
      post_id: String(postId),
      client_timestamp: queuedAt,
      metadata: { ...metadata },
      first_queued_at: queuedAt,
      retry_count: 0,
      once_key: onceKey ?? null,
      session_position: sessionPosition,
    };
    state.next_sequence += 1;
    state.pending.push(event);
    if (onceKey) state.once[onceKey] = 'queued';
    persist();
    flush();
    return { enqueued: true, event: { ...event, metadata: { ...event.metadata } } };
  }

  persist();
  return {
    enqueue,
    flush,
    snapshot: () => publicSnapshot(state),
    destroy() {
      destroyed = true;
      if (retryTimer) clearTimer(retryTimer);
      retryTimer = null;
    },
  };
}
