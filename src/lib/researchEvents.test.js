import assert from 'node:assert/strict';
import test from 'node:test';
import { createResearchEventService, RESEARCH_STORAGE_KEYS } from './researchEvents.js';

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
  clear() { this.values.clear(); }
}

function response(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

function apiMock({ failFirstBatch = false, failFeed = false, condition = 'balanced' } = {}) {
  let participantCreates = 0;
  let sessionCreates = 0;
  let batchCalls = 0;
  let feedCalls = 0;
  let activeSession = null;
  const calls = [];
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url, options });
    if (url.endsWith('/participants')) {
      participantCreates += 1;
      return response({
        participant_id: '11111111-1111-4111-8111-111111111111',
        access_token: 'anonymous-bearer-token',
        assigned_condition: condition,
      }, 201);
    }
    if (url.endsWith('/sessions') && options.method === 'POST') {
      sessionCreates += 1;
      activeSession = {
        session_id: `22222222-2222-4222-8222-${String(sessionCreates).padStart(12, '0')}`,
        participant_id: '11111111-1111-4111-8111-111111111111',
        feed_condition: condition,
        feed_policy_version: `${condition}-v1`,
        application_version: 'test',
        status: 'active',
        next_sequence_number: 1,
      };
      return response(activeSession, 201);
    }
    if (url.includes('/sessions/') && url.includes('/feed?')) {
      feedCalls += 1;
      if (failFeed) return response({ detail: 'feed unavailable' }, 503);
      return response({
        feed_request_id: '33333333-3333-4333-8333-333333333333',
        policy_version: `${condition}-v1`,
        has_more: false,
        items: [{
          post_id: 'video-1',
          youtube_id: 'video-1',
          content_category: 'healthy',
          feed_position: 0,
          feed_policy_version: `${condition}-v1`,
          selection_bucket: 'healthy',
          selection_reason: 'healthy_category_target',
          feed_request_id: '33333333-3333-4333-8333-333333333333',
        }],
      });
    }
    if (url.includes('/sessions/') && !url.endsWith('/complete')) return response(activeSession);
    if (url.endsWith('/events/batch')) {
      batchCalls += 1;
      if (failFirstBatch && batchCalls === 1) return response({ detail: 'temporary' }, 503);
      const payload = JSON.parse(options.body);
      return response({
        ok: true,
        accepted: payload.events.map((event) => ({ event_id: event.event_id })),
        duplicate_event_ids: [],
      });
    }
    if (url.endsWith('/complete')) return response({ ...activeSession, status: 'completed' });
    throw new Error(`Unexpected request: ${options.method || 'GET'} ${url}`);
  };
  return {
    fetchImpl,
    calls,
    counts: () => ({ participantCreates, sessionCreates, batchCalls, feedCalls }),
  };
}

function serviceOptions(api, localStorage, sessionStorage) {
  let uuid = 0;
  return {
    fetchImpl: api.fetchImpl,
    localStorage,
    sessionStorage,
    applicationVersion: 'test',
    cryptoImpl: { randomUUID: () => `aaaaaaaa-aaaa-4aaa-8aaa-${String(++uuid).padStart(12, '0')}` },
    now: () => new Date('2026-08-03T12:00:00.000Z'),
    setTimer: () => 1,
    clearTimer: () => {},
  };
}

test('creates an anonymous participant once and reuses it and its active session after refresh', async () => {
  const localStorage = new MemoryStorage();
  const sessionStorage = new MemoryStorage();
  const api = apiMock();
  const first = createResearchEventService(serviceOptions(api, localStorage, sessionStorage));
  const initial = await first.initialize();

  const refreshed = createResearchEventService(serviceOptions(api, localStorage, sessionStorage));
  const reused = await refreshed.initialize();

  assert.equal(reused.participant.participant_id, initial.participant.participant_id);
  assert.equal(reused.session.session_id, initial.session.session_id);
  assert.deepEqual(api.counts(), {
    participantCreates: 1, sessionCreates: 1, batchCalls: 0, feedCalls: 0,
  });
  assert.ok(localStorage.getItem(RESEARCH_STORAGE_KEYS.participant));
});

test('creates a separate research session while retaining the anonymous participant', async () => {
  const localStorage = new MemoryStorage();
  const firstTab = new MemoryStorage();
  const api = apiMock();
  const first = createResearchEventService(serviceOptions(api, localStorage, firstTab));
  const initial = await first.initialize();

  const newTab = new MemoryStorage();
  const second = createResearchEventService(serviceOptions(api, localStorage, newTab));
  const next = await second.initialize();

  assert.notEqual(next.session.session_id, initial.session.session_id);
  assert.equal(next.participant.participant_id, initial.participant.participant_id);
  assert.equal(api.counts().participantCreates, 1);
  assert.equal(api.counts().sessionCreates, 2);
});

test('a completed session is followed by a new session without changing participant', async () => {
  const localStorage = new MemoryStorage();
  const sessionStorage = new MemoryStorage();
  const api = apiMock();
  const service = createResearchEventService(serviceOptions(api, localStorage, sessionStorage));
  const first = await service.initialize();
  await service.complete();
  const second = await service.initialize();

  assert.notEqual(second.session.session_id, first.session.session_id);
  assert.equal(second.participant.participant_id, first.participant.participant_id);
  assert.equal(api.counts().sessionCreates, 2);
});

test('keeps a queued event after temporary failure and removes it after retry succeeds', async () => {
  const localStorage = new MemoryStorage();
  const sessionStorage = new MemoryStorage();
  const api = apiMock({ failFirstBatch: true });
  const service = createResearchEventService(serviceOptions(api, localStorage, sessionStorage));
  await service.initialize();
  await service.track('post_liked', {
    postId: 'video-1',
    contentCategory: 'healthy',
    metadata: { interaction_source: 'action_rail' },
  });
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(service.getPendingEvents().length, 1);
  const result = await service.flush();
  assert.equal(result.pending, 0);
  assert.equal(service.getPendingEvents().length, 0);
  assert.equal(api.counts().batchCalls, 2);
});

test('once keys and rapid-click protection prevent duplicate client events', async () => {
  const localStorage = new MemoryStorage();
  const sessionStorage = new MemoryStorage();
  const api = apiMock({ failFirstBatch: true });
  const service = createResearchEventService(serviceOptions(api, localStorage, sessionStorage));
  await service.initialize();
  const first = await service.track(
    'post_impression',
    { postId: 'video-2', contentCategory: 'positive' },
    { onceKey: 'post_impression:video-2' },
  );
  const duplicate = await service.track(
    'post_impression',
    { postId: 'video-2', contentCategory: 'positive' },
    { onceKey: 'post_impression:video-2' },
  );

  assert.ok(first.event_id);
  assert.equal(duplicate, null);
  assert.equal(service.getPendingEvents().length, 1);
});

test('research feed requests use the authenticated server-owned session path', async () => {
  const localStorage = new MemoryStorage();
  const sessionStorage = new MemoryStorage();
  const api = apiMock({ condition: 'regular' });
  const service = createResearchEventService(serviceOptions(api, localStorage, sessionStorage));
  const payload = await service.fetchFeed({ k: 12, excludeIds: ['already-seen'] });

  const request = api.calls.find((call) => call.url.includes('/feed?'));
  assert.match(request.url, /\/api\/research\/sessions\/[^/]+\/feed\?k=12/);
  assert.match(request.url, /exclude_ids=already-seen/);
  assert.doesNotMatch(request.url, /condition|policy|seed/);
  assert.equal(request.options.headers.Authorization, 'Bearer anonymous-bearer-token');
  assert.equal(payload.items[0].feed_policy_version, 'regular-v1');
});

test('both assigned conditions use the same research feed request interface', async () => {
  for (const condition of ['regular', 'balanced']) {
    const api = apiMock({ condition });
    const service = createResearchEventService(serviceOptions(
      api,
      new MemoryStorage(),
      new MemoryStorage(),
    ));
    await service.fetchFeed();
    const request = api.calls.find((call) => call.url.includes('/feed?'));
    assert.doesNotMatch(request.url, /regular|balanced/);
    assert.equal(api.counts().feedCalls, 1);
  }
});

test('feed errors do not remove already queued research events', async () => {
  const localStorage = new MemoryStorage();
  const sessionStorage = new MemoryStorage();
  const api = apiMock({ failFirstBatch: true, failFeed: true });
  const service = createResearchEventService(serviceOptions(api, localStorage, sessionStorage));
  await service.initialize();
  await service.track('post_liked', {
    postId: 'video-queued',
    contentCategory: 'regular',
    metadata: { interaction_source: 'action_rail' },
  });
  await new Promise((resolve) => setTimeout(resolve, 0));

  await assert.rejects(() => service.fetchFeed(), /feed unavailable/);
  assert.equal(service.getPendingEvents().length, 1);
});
