import assert from 'node:assert/strict';
import test from 'node:test';
import {
  INTENTIONAL_BREAK_CONTRACT_VERSION,
  IntentionalBreakApiError,
  createIdempotencyKey,
  createIntentionalBreakApiClient,
  getCurrentJourneyForStoredParticipant,
} from './intentionalBreakApi.js';

const SESSION_ID = '22222222-2222-4222-8222-222222222222';
const IDEMPOTENCY_KEY = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const ACCESS_TOKEN = 'private-anonymous-bearer-token';

function journey(journeyState = 'planned') {
  return { session_id: SESSION_ID, journey_state: journeyState, supported_actions: [] };
}

function success(data = { journey: journey() }) {
  return {
    ok: true,
    data,
    server_timestamp: '2026-08-06T12:00:00+00:00',
    contract_version: INTENTIONAL_BREAK_CONTRACT_VERSION,
  };
}

function response(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

function makeClient(fetchImpl) {
  return createIntentionalBreakApiClient({
    apiUrl: 'https://daybreak.test',
    fetchImpl,
    participantProvider: async () => ({
      participant_id: '11111111-1111-4111-8111-111111111111',
      access_token: ACCESS_TOKEN,
      assigned_condition: 'regular',
    }),
  });
}

function recordingClient({ data } = {}) {
  const calls = [];
  return {
    calls,
    client: makeClient(async (url, options) => {
      calls.push({ url, options });
      return response(success(data ?? { journey: journey() }));
    }),
  };
}

function parsedBody(call) {
  return call.options.body ? JSON.parse(call.options.body) : undefined;
}

test('every API method uses the versioned path, expected method, and bearer credential', async () => {
  const { client, calls } = recordingClient();
  const commands = [
    [() => client.getCurrentJourney(), 'GET', '/current'],
    [() => client.getJourney(SESSION_ID), 'GET', `/sessions/${SESSION_ID}`],
    [() => client.createPlan({
      intention: 'learn',
      plannedVideoCount: 10,
      selectedCooldownSeconds: 600,
      idempotencyKey: IDEMPOTENCY_KEY,
    }), 'POST', '/plans'],
    [() => client.cancelPlan(SESSION_ID, IDEMPOTENCY_KEY), 'POST', `/sessions/${SESSION_ID}/cancel`],
    [() => client.startSession(SESSION_ID, IDEMPOTENCY_KEY), 'POST', `/sessions/${SESSION_ID}/start`],
    [() => client.getItems(SESSION_ID), 'GET', `/sessions/${SESSION_ID}/items?`],
    [() => client.appendEvents(SESSION_ID, [{
      client_event_id: IDEMPOTENCY_KEY,
      event_type: 'post_impression',
      post_id: 'post-1',
      client_timestamp: '2026-08-06T12:00:00.000Z',
    }]), 'POST', `/sessions/${SESSION_ID}/events`],
    [() => client.finishEarly(SESSION_ID, { idempotencyKey: IDEMPOTENCY_KEY }), 'POST', `/sessions/${SESSION_ID}/finish-early`],
    [() => client.submitCheckout(SESSION_ID, {
      idempotencyKey: IDEMPOTENCY_KEY,
      worthwhile: 'yes',
      perceivedControl: 4,
      mood: 'better',
    }), 'POST', `/sessions/${SESSION_ID}/checkout`],
    [() => client.getCooldown(SESSION_ID), 'GET', `/sessions/${SESSION_ID}/cooldown`],
    [() => client.startOverride(SESSION_ID, IDEMPOTENCY_KEY), 'POST', `/sessions/${SESSION_ID}/override/start`],
    [() => client.confirmOverride(SESSION_ID, {
      idempotencyKey: IDEMPOTENCY_KEY,
      reasonCode: 'change_plan',
    }), 'POST', `/sessions/${SESSION_ID}/override/confirm`],
  ];

  for (const [invoke] of commands) await invoke();

  assert.equal(calls.length, commands.length);
  calls.forEach((call, index) => {
    const [, method, path] = commands[index];
    assert.equal(call.options.method, method);
    assert.ok(call.url.startsWith('https://daybreak.test/api/research/intentional-break/v1'));
    assert.ok(call.url.includes(path));
    assert.equal(call.options.headers.Authorization, `Bearer ${ACCESS_TOKEN}`);
    const body = parsedBody(call);
    if (body) {
      assert.equal(body.participant_id, undefined);
      assert.doesNotMatch(JSON.stringify(body), /assigned_condition|regular/);
    }
  });
});

test('stored-participant current lookup never invokes participant creation', async () => {
  const calls = [];
  const result = await getCurrentJourneyForStoredParticipant({
    participant_id: '11111111-1111-4111-8111-111111111111',
    access_token: ACCESS_TOKEN,
  }, {
    apiUrl: 'https://daybreak.test',
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return response(success({ journey: journey('cooldown') }));
    },
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://daybreak.test/api/research/intentional-break/v1/current');
  assert.equal(calls[0].options.method, 'GET');
  assert.equal(calls[0].options.headers.Authorization, `Bearer ${ACCESS_TOKEN}`);
  assert.equal(result.journey.journey_state, 'cooldown');
});

test('createPlan sends only caller plan fields plus the fixed notice acknowledgement', async () => {
  const { client, calls } = recordingClient();
  await client.createPlan({
    intention: 'quick_break',
    planned_video_count: 20,
    selected_cooldown_seconds: 1_200,
    idempotency_key: IDEMPOTENCY_KEY,
    previous_session_id: '33333333-3333-4333-8333-333333333333',
    participant_id: 'do-not-send',
    feed_policy: 'regular-v1',
    seed: 'client-seed',
    items: ['client-inventory'],
    exclude_ids: ['post-1'],
  });

  assert.deepEqual(parsedBody(calls[0]), {
    intention: 'quick_break',
    planned_video_count: 20,
    selected_cooldown_seconds: 1_200,
    idempotency_key: IDEMPOTENCY_KEY,
    previous_session_id: '33333333-3333-4333-8333-333333333333',
    participant_notice_version: 'intentional-break-v1',
    participant_notice_acknowledged: true,
  });
});

test('getItems uses only start_position and limit query parameters', async () => {
  const { client, calls } = recordingClient({
    data: { items: [], journey_state: 'active', has_more: false },
  });
  await client.getItems(SESSION_ID, {
    startPosition: 7,
    limit: 10,
    excludeIds: ['post-1'],
  });

  const url = new URL(calls[0].url);
  assert.deepEqual([...url.searchParams.entries()], [
    ['start_position', '7'],
    ['limit', '10'],
  ]);
});

test('appendEvents allows client diagnostics and strips server-authoritative fields', async () => {
  const { client, calls } = recordingClient({ data: { events: [], journey: journey('active') } });
  await client.appendEvents(SESSION_ID, [{
    clientEventId: IDEMPOTENCY_KEY,
    clientSequenceNumber: 8,
    eventType: 'post_viewed',
    postId: 'post-8',
    clientTimestamp: '2026-08-06T12:00:00.000Z',
    metadata: {
      visibility_ratio: 0.8,
      session_position: 40,
      feed_position: 40,
      selection_reason: 'client-provenance',
      source_type: 'client-provenance',
    },
    server_sequence_number: 500,
    event_authority: 'client',
    session_position: 40,
    content_category: 'trusted-client-category',
    provenance: { source: 'client' },
  }]);

  assert.deepEqual(parsedBody(calls[0]), {
    events: [{
      client_event_id: IDEMPOTENCY_KEY,
      client_sequence_number: 8,
      event_type: 'post_viewed',
      post_id: 'post-8',
      client_timestamp: '2026-08-06T12:00:00.000Z',
      metadata: { visibility_ratio: 0.8 },
    }],
  });
});

test('command bodies keep finish authoritative and normalize checkout and override inputs', async () => {
  const { client, calls } = recordingClient();
  await client.finishEarly(SESSION_ID, { idempotencyKey: IDEMPOTENCY_KEY, currentPosition: 4 });
  await client.submitCheckout(SESSION_ID, {
    idempotencyKey: IDEMPOTENCY_KEY,
    worthwhile: 'mostly',
    perceivedControl: 3,
    mood: 'same',
  });
  await client.confirmOverride(SESSION_ID, {
    idempotencyKey: IDEMPOTENCY_KEY,
    reasonCode: 'want_another_session',
  });

  assert.deepEqual(parsedBody(calls[0]), {
    idempotency_key: IDEMPOTENCY_KEY,
  });
  assert.deepEqual(parsedBody(calls[1]), {
    idempotency_key: IDEMPOTENCY_KEY,
    worthwhile: 'mostly',
    perceived_control: 3,
    mood: 'same',
    checkout_version: 'intentional-break-v1',
  });
  assert.deepEqual(parsedBody(calls[2]), {
    idempotency_key: IDEMPOTENCY_KEY,
    reason_code: 'want_another_session',
  });
});

test('idempotency-only commands send only the retained command key', async () => {
  const { client, calls } = recordingClient();
  await client.cancelPlan(SESSION_ID, IDEMPOTENCY_KEY);
  await client.startSession(SESSION_ID, IDEMPOTENCY_KEY);
  await client.startOverride(SESSION_ID, IDEMPOTENCY_KEY);

  for (const call of calls) {
    assert.deepEqual(parsedBody(call), { idempotency_key: IDEMPOTENCY_KEY });
  }
});

test('successful responses are normalized and journey snapshots are copied', async () => {
  const rawJourney = journey('checkout');
  const { client } = recordingClient({ data: { journey: rawJourney, extra: 'value' } });
  const result = await client.getCurrentJourney();

  assert.deepEqual(result, {
    journey: rawJourney,
    extra: 'value',
    serverTimestamp: '2026-08-06T12:00:00+00:00',
    contractVersion: 'intentional-break-v1',
  });
  assert.notEqual(result.journey, rawJourney);
});

test('success validation rejects bad contract versions, missing data, and unknown lifecycles', async () => {
  const bodies = [
    { ...success(), contract_version: 'future-version' },
    { ...success(), data: undefined },
    success({ journey: journey('invented') }),
  ];
  for (const body of bodies) {
    const client = makeClient(async () => response(body));
    await assert.rejects(
      () => client.getCurrentJourney(),
      (error) => error instanceof IntentionalBreakApiError
        && error.errorCode === 'invalid_response',
    );
  }
});

test('API error status and retry classification are preserved for every mapped status', async () => {
  const expected = new Map([
    [400, false],
    [401, false],
    [403, false],
    [404, false],
    [409, false],
    [500, true],
    [503, true],
  ]);
  for (const [status, retryable] of expected) {
    const client = makeClient(async () => response({
      ok: false,
      error_code: `error_${status}`,
      message: `Failure ${status}`,
      retryable,
      details: { status },
      server_timestamp: '2026-08-06T12:00:00+00:00',
      contract_version: 'intentional-break-v1',
    }, status));
    await assert.rejects(
      () => client.getCurrentJourney(),
      (error) => error instanceof IntentionalBreakApiError
        && error.status === status
        && error.errorCode === `error_${status}`
        && error.retryable === retryable
        && error.details.status === status
        && error.serverTimestamp === '2026-08-06T12:00:00+00:00',
    );
  }
});

test('network failures become retryable network errors without automatic retries', async () => {
  let calls = 0;
  const client = makeClient(async () => {
    calls += 1;
    throw new TypeError('offline');
  });

  await assert.rejects(
    () => client.createPlan({
      intention: 'relax',
      plannedVideoCount: 5,
      selectedCooldownSeconds: 300,
      idempotencyKey: IDEMPOTENCY_KEY,
    }),
    (error) => error.errorCode === 'network_error' && error.retryable === true,
  );
  assert.equal(calls, 1);
});

test('participant initialization network failures use the same retryable network classification', async () => {
  let participantCalls = 0;
  let pilotCalls = 0;
  const client = createIntentionalBreakApiClient({
    fetchImpl: async () => {
      pilotCalls += 1;
      return response(success());
    },
    participantProvider: async () => {
      participantCalls += 1;
      throw new TypeError('offline');
    },
  });

  await assert.rejects(
    () => client.getCurrentJourney(),
    (error) => error.errorCode === 'network_error' && error.retryable === true,
  );
  assert.equal(participantCalls, 1);
  assert.equal(pilotCalls, 0);
});

test('normalized errors preserve override pause details while redacting bearer secrets', async () => {
  const client = makeClient(async () => response({
    ok: false,
    error_code: 'override_pause_active',
    message: `Wait before confirming ${ACCESS_TOKEN}`,
    retryable: false,
    details: {
      remaining_pause_seconds: 9,
      override_available_at: '2026-08-06T12:00:15+00:00',
      diagnostic: ACCESS_TOKEN,
    },
    server_timestamp: '2026-08-06T12:00:06+00:00',
    contract_version: 'intentional-break-v1',
  }, 409));

  await assert.rejects(
    () => client.confirmOverride(SESSION_ID, {
      idempotencyKey: IDEMPOTENCY_KEY,
      reasonCode: 'other',
    }),
    (error) => {
      assert.equal(error.errorCode, 'override_pause_active');
      assert.equal(error.details.remaining_pause_seconds, 9);
      assert.equal(error.details.override_available_at, '2026-08-06T12:00:15+00:00');
      assert.doesNotMatch(error.message, new RegExp(ACCESS_TOKEN));
      assert.doesNotMatch(JSON.stringify(error.details), new RegExp(ACCESS_TOKEN));
      assert.equal(Object.hasOwn(error, 'accessToken'), false);
      return true;
    },
  );
});

test('createIdempotencyKey prefers randomUUID and has a secure UUID-v4 fallback', () => {
  assert.equal(
    createIdempotencyKey({ randomUUID: () => IDEMPOTENCY_KEY }),
    IDEMPOTENCY_KEY,
  );
  const fallback = createIdempotencyKey({
    getRandomValues: (bytes) => {
      bytes.fill(0xab);
      return bytes;
    },
  });
  assert.match(fallback, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});
