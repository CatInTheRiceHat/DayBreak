import {
  RESEARCH_PARTICIPANT_STORAGE_KEY,
  ensureResearchParticipant,
  getStoredResearchParticipant,
} from './researchParticipant.js';

const SESSION_STORAGE_KEY = 'chrysalis-research-session-v1';
const QUEUE_STORAGE_PREFIX = 'chrysalis-research-events-v1:';
const RAPID_REPEAT_WINDOW_MS = 750;

const ALLOWED_CLIENT_EVENTS = new Set([
  'post_impression',
  'post_viewed',
  'post_liked',
  'post_unliked',
  'post_skipped',
  'post_reported',
  'break_prompt_shown',
  'break_prompt_accepted',
  'break_prompt_dismissed',
]);

function readJson(storage, key) {
  try {
    return JSON.parse(storage?.getItem(key) || 'null');
  } catch {
    return null;
  }
}

function writeJson(storage, key, value) {
  storage?.setItem(key, JSON.stringify(value));
}

function randomId(cryptoImpl) {
  if (!cryptoImpl?.randomUUID) {
    throw new Error('Secure UUID generation is unavailable in this browser.');
  }
  return cryptoImpl.randomUUID();
}

class ResearchApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ResearchApiError';
    this.status = status;
  }
}

async function parseResponse(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    // An empty or non-JSON error body is still reported by status below.
  }
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === 'string' ? detail : `Research API request failed (${response.status}).`;
    throw new ResearchApiError(message, response.status);
  }
  return body;
}

export function createResearchEventService({
  apiUrl = '',
  applicationVersion = 'development',
  fetchImpl = globalThis.fetch?.bind(globalThis),
  localStorage = globalThis.localStorage,
  sessionStorage = globalThis.sessionStorage,
  cryptoImpl = globalThis.crypto,
  now = () => new Date(),
  setTimer = globalThis.setTimeout,
  clearTimer = globalThis.clearTimeout,
} = {}) {
  if (!fetchImpl) throw new Error('Fetch is unavailable.');

  let participant = getStoredResearchParticipant({ localStorage });
  let session = readJson(sessionStorage, SESSION_STORAGE_KEY);
  let initializePromise = null;
  let flushPromise = null;
  let retryTimer = null;
  let retryDelayMs = 1_000;
  const recentEvents = new Map();

  const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${participant.access_token}`,
  });
  const queueKey = () => `${QUEUE_STORAGE_PREFIX}${session.session_id}`;
  const getQueue = () => readJson(localStorage, queueKey()) || [];
  const saveQueue = (events) => writeJson(localStorage, queueKey(), events);

  function saveSession() {
    writeJson(sessionStorage, SESSION_STORAGE_KEY, session);
  }

  function scheduleRetry() {
    if (retryTimer || typeof setTimer !== 'function') return;
    retryTimer = setTimer(() => {
      retryTimer = null;
      void flush();
    }, retryDelayMs);
    retryDelayMs = Math.min(retryDelayMs * 2, 30_000);
  }

  async function ensureParticipant() {
    if (participant?.participant_id && participant?.access_token) return participant;
    participant = await ensureResearchParticipant({ apiUrl, fetchImpl, localStorage });
    return participant;
  }

  async function initialize() {
    if (initializePromise) return initializePromise;
    initializePromise = (async () => {
      await ensureParticipant();
      if (session?.session_id) {
        try {
          const current = await parseResponse(await fetchImpl(
            `${apiUrl}/api/research/sessions/${session.session_id}`,
            { headers: authHeaders() },
          ));
          if (current.status === 'active') {
            session = { ...session, ...current, once_keys: session.once_keys || {} };
            saveSession();
            void flush();
            return { participant, session };
          }
          if (current.status === 'completed' && session.completion_event) {
            session = { ...session, ...current };
            sessionStorage?.removeItem(SESSION_STORAGE_KEY);
            return { participant, session, completed: true };
          }
        } catch (error) {
          // Only a confirmed missing session is stale. A temporary network/server
          // error must not silently create a second research session.
          if (error?.status !== 404) throw error;
        }
      }

      session = await parseResponse(await fetchImpl(`${apiUrl}/api/research/sessions`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          application_version: applicationVersion,
          client_timestamp: now().toISOString(),
        }),
      }));
      session.next_sequence_number = Number(session.next_sequence_number || 1);
      session.once_keys = session.once_keys || {};
      saveSession();
      return { participant, session };
    })();
    try {
      const result = await initializePromise;
      if (result.completed) {
        initializePromise = null;
        session = null;
      }
      return result;
    } catch (error) {
      initializePromise = null;
      throw error;
    }
  }

  async function flush() {
    if (flushPromise) return flushPromise;
    if (!participant?.access_token || !session?.session_id) return { accepted: 0, pending: 0 };
    if (!getQueue().length) return { accepted: 0, pending: 0 };

    flushPromise = (async () => {
      let acceptedTotal = 0;
      try {
        while (getQueue().length) {
          const batch = getQueue().slice(0, 100);
          const response = await parseResponse(await fetchImpl(`${apiUrl}/api/research/events/batch`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ session_id: session.session_id, events: batch }),
          }));
          const acknowledged = new Set([
            ...(response.accepted || []).map((item) => item.event_id),
            ...(response.duplicate_event_ids || []),
          ]);
          if (!acknowledged.size) throw new Error('Research API did not acknowledge the event batch.');
          saveQueue(getQueue().filter((event) => !acknowledged.has(event.event_id)));
          acceptedTotal += acknowledged.size;
        }
        retryDelayMs = 1_000;
        return { accepted: acceptedTotal, pending: 0 };
      } catch (error) {
        scheduleRetry();
        return { accepted: 0, pending: getQueue().length, error };
      } finally {
        flushPromise = null;
      }
    })();
    return flushPromise;
  }

  async function track(eventType, fields = {}, options = {}) {
    await initialize();
    if (session.completion_event || session.status !== 'active') return null;
    if (!ALLOWED_CLIENT_EVENTS.has(eventType)) {
      throw new Error(`Unsupported research event type: ${eventType}`);
    }

    const dedupeKey = options.onceKey || `${eventType}:${fields.postId || ''}`;
    if (options.onceKey && session.once_keys?.[options.onceKey]) return null;
    const currentTime = now();
    const lastTime = recentEvents.get(dedupeKey) || 0;
    if (!options.allowRapidRepeat && currentTime.getTime() - lastTime < RAPID_REPEAT_WINDOW_MS) return null;

    const event = {
      event_id: randomId(cryptoImpl),
      sequence_number: session.next_sequence_number,
      event_type: eventType,
      post_id: fields.postId || null,
      content_category: fields.contentCategory || null,
      client_timestamp: currentTime.toISOString(),
      metadata: fields.metadata || {},
    };
    session.next_sequence_number += 1;
    if (options.onceKey) session.once_keys[options.onceKey] = event.event_id;
    recentEvents.set(dedupeKey, currentTime.getTime());
    saveSession();
    saveQueue([...getQueue(), event]);
    void flush();
    return event;
  }

  async function complete() {
    await initialize();
    const flushed = await flush();
    if (flushed.pending > 0) {
      throw new Error('Some research events are still waiting to upload. Check the connection and try again.');
    }
    if (!session.completion_event) {
      session.completion_event = {
        event_id: randomId(cryptoImpl),
        sequence_number: session.next_sequence_number,
        client_timestamp: now().toISOString(),
        metadata: {},
      };
      session.next_sequence_number += 1;
      saveSession();
    }
    const completed = await parseResponse(await fetchImpl(
      `${apiUrl}/api/research/sessions/${session.session_id}/complete`,
      { method: 'POST', headers: authHeaders(), body: JSON.stringify(session.completion_event) },
    ));
    sessionStorage?.removeItem(SESSION_STORAGE_KEY);
    session = null;
    initializePromise = null;
    return completed;
  }

  async function fetchFeed({ k = 12, excludeIds = [] } = {}) {
    await initialize();
    if (!session?.session_id || session.status !== 'active') {
      throw new Error('An active research session is required to load the feed.');
    }
    const params = new URLSearchParams({ k: String(k) });
    if (excludeIds.length) params.set('exclude_ids', excludeIds.join(','));
    return parseResponse(await fetchImpl(
      `${apiUrl}/api/research/sessions/${session.session_id}/feed?${params.toString()}`,
      { headers: authHeaders() },
    ));
  }

  function startNetworkRecovery() {
    if (typeof window === 'undefined') return () => {};
    const retry = () => void flush();
    window.addEventListener('online', retry);
    window.addEventListener('visibilitychange', retry);
    return () => {
      window.removeEventListener('online', retry);
      window.removeEventListener('visibilitychange', retry);
      if (retryTimer) clearTimer(retryTimer);
    };
  }

  return {
    initialize,
    track,
    flush,
    complete,
    fetchFeed,
    startNetworkRecovery,
    getParticipant: () => participant,
    getSession: () => session,
    getPendingEvents: () => (session?.session_id ? getQueue() : []),
  };
}

let browserService;

export function getResearchEventService() {
  if (!browserService) {
    browserService = createResearchEventService({
      apiUrl: import.meta.env.VITE_API_URL ?? '',
      applicationVersion: import.meta.env.VITE_APP_VERSION || 'development',
    });
  }
  return browserService;
}

export const RESEARCH_STORAGE_KEYS = {
  participant: RESEARCH_PARTICIPANT_STORAGE_KEY,
  session: SESSION_STORAGE_KEY,
  queuePrefix: QUEUE_STORAGE_PREFIX,
};
