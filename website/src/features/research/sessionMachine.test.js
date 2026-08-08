import assert from 'node:assert/strict';
import test from 'node:test';
import {
  INTENTIONS,
  calculateRecommendedCooldownSeconds,
  estimateDurationSeconds,
} from './sessionContract.js';
import {
  SESSION_MACHINE_STAGES,
  SessionMachineError,
  createInitialSessionState,
  isPlanningDraftComplete,
  journeyStage,
  sessionMachineReducer,
  suggestLowerVideoCount,
} from './sessionMachine.js';

const SESSION_ID = '22222222-2222-4222-8222-222222222222';
const FIRST_KEY = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const SECOND_KEY = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';

function journey(journeyState, extra = {}) {
  return { session_id: SESSION_ID, journey_state: journeyState, ...extra };
}

function reduce(state, type, fields = {}) {
  return sessionMachineReducer(state, { type, ...fields });
}

function planningState() {
  let state = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', { journey: null });
  state = reduce(state, 'NOTICE_ACKNOWLEDGED');
  state = reduce(state, 'SET_INTENTION', { intention: 'learn' });
  return reduce(state, 'SET_VIDEO_COUNT', { plannedVideoCount: 10 });
}

test('initial state is a frontend-only bootstrapping stage', () => {
  const state = createInitialSessionState();
  assert.equal(state.stage, 'bootstrapping');
  assert.equal(state.journey, null);
  assert.ok(SESSION_MACHINE_STAGES.includes('bootstrapping'));
  assert.equal(SESSION_MACHINE_STAGES.includes('invented'), false);
});

test('bootstrap with no current journey presents notice and never creates a plan', () => {
  const state = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', { journey: null });
  assert.equal(state.stage, 'notice');
  assert.equal(state.journey, null);
  assert.equal(state.commands.plan.attempted, false);
});

test('authoritative bootstrap and refresh snapshots map every frozen lifecycle', () => {
  for (const lifecycle of ['planned', 'active', 'checkout', 'cooldown', 'completed', 'cancelled']) {
    const state = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', {
      journey: journey(lifecycle),
    });
    assert.equal(state.stage, lifecycle);
    assert.equal(state.journey.journey_state, lifecycle);
    assert.equal(journeyStage(state.journey), lifecycle);
  }
});

test('unknown server lifecycle values fail safely instead of becoming active', () => {
  assert.throws(
    () => journeyStage(journey('invented')),
    (error) => error instanceof SessionMachineError
      && error.code === 'unknown_lifecycle_state',
  );
  const active = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', {
    journey: journey('active'),
  });
  const rejected = reduce(active, 'SERVER_JOURNEY_RECEIVED', {
    journey: journey('invented'),
  });
  assert.equal(rejected.stage, 'error');
  assert.equal(rejected.error.errorCode, 'unknown_lifecycle_state');
  assert.equal(rejected.journey.journey_state, 'active');
});

test('notice acknowledgement enters planning with an in-memory blank draft', () => {
  const notice = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', { journey: null });
  const planning = reduce(notice, 'NOTICE_ACKNOWLEDGED');
  assert.equal(planning.stage, 'planning');
  assert.deepEqual(planning.draft, {
    intention: null,
    plannedVideoCount: null,
    estimatedDurationSeconds: null,
    recommendedCooldownSeconds: null,
    selectedCooldownSeconds: null,
  });
});

test('planning accepts every frozen intention and rejects unsupported intentions', () => {
  const base = reduce(
    reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', { journey: null }),
    'NOTICE_ACKNOWLEDGED',
  );
  for (const intention of INTENTIONS) {
    assert.equal(reduce(base, 'SET_INTENTION', { intention }).draft.intention, intention);
  }
  assert.throws(
    () => reduce(base, 'SET_INTENTION', { intention: 'scroll_forever' }),
    (error) => error.code === 'invalid_intention',
  );
});

test('planning derives duration and cooldown from shared contract helpers for 5/10/20/40', () => {
  const base = reduce(
    reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', { journey: null }),
    'NOTICE_ACKNOWLEDGED',
  );
  for (const plannedVideoCount of [5, 10, 20, 40]) {
    const state = reduce(base, 'SET_VIDEO_COUNT', { plannedVideoCount });
    const duration = estimateDurationSeconds(plannedVideoCount);
    const cooldown = calculateRecommendedCooldownSeconds(duration);
    assert.equal(state.draft.estimatedDurationSeconds, duration);
    assert.equal(state.draft.recommendedCooldownSeconds, cooldown);
    assert.equal(state.draft.selectedCooldownSeconds, cooldown);
  }
  for (const plannedVideoCount of [0, 6, 15, 80, '10']) {
    assert.throws(
      () => reduce(base, 'SET_VIDEO_COUNT', { plannedVideoCount }),
      (error) => error.code === 'invalid_video_count',
    );
  }
});

test('planning accepts only five-minute cooldown increments in the frozen range', () => {
  const base = planningState();
  for (const selectedCooldownSeconds of [300, 900, 7_200]) {
    assert.equal(
      reduce(base, 'SET_SELECTED_COOLDOWN', { selectedCooldownSeconds })
        .draft.selectedCooldownSeconds,
      selectedCooldownSeconds,
    );
  }
  for (const selectedCooldownSeconds of [0, 299, 301, 7_500, '600']) {
    assert.throws(
      () => reduce(base, 'SET_SELECTED_COOLDOWN', { selectedCooldownSeconds }),
      (error) => error.code === 'invalid_cooldown',
    );
  }
});

test('planning completeness uses the machine contract instead of component validation', () => {
  const complete = planningState();
  assert.equal(isPlanningDraftComplete(complete.draft), true);
  assert.equal(isPlanningDraftComplete({ ...complete.draft, intention: 'unknown' }), false);
  assert.equal(isPlanningDraftComplete({ ...complete.draft, plannedVideoCount: 100 }), false);
  assert.equal(isPlanningDraftComplete({ ...complete.draft, selectedCooldownSeconds: 301 }), false);
});

test('editing a failed draft starts a new logical plan command', () => {
  const draft = planningState();
  const pending = reduce(draft, 'PLAN_SUBMIT_STARTED', { idempotencyKey: FIRST_KEY });
  const failed = reduce(pending, 'PLAN_SUBMIT_FAILED', {
    error: { errorCode: 'network_error', message: 'Offline.', retryable: true },
  });
  const edited = reduce(failed, 'SET_VIDEO_COUNT', { plannedVideoCount: 5 });
  assert.equal(edited.commands.plan.idempotencyKey, null);
  assert.equal(edited.commands.plan.attempted, false);
  assert.equal(edited.error, null);
  assert.equal(edited.draft.selectedCooldownSeconds, 300);
});

test('inventory suggestions select only the largest supported lower count', () => {
  assert.equal(suggestLowerVideoCount(27, 40), 20);
  assert.equal(suggestLowerVideoCount(13, 20), 10);
  assert.equal(suggestLowerVideoCount(6, 10), 5);
  assert.equal(suggestLowerVideoCount(4, 5), null);
  assert.equal(suggestLowerVideoCount(20, 20), 10);
  assert.equal(suggestLowerVideoCount('20', 40), null);
});

test('plan submission requires an external key, retains it on retry, and preserves draft on failure', () => {
  const draft = planningState();
  assert.throws(
    () => reduce(draft, 'PLAN_SUBMIT_STARTED'),
    (error) => error.code === 'idempotency_key_required',
  );

  const pending = reduce(draft, 'PLAN_SUBMIT_STARTED', { idempotencyKey: FIRST_KEY });
  assert.equal(pending.stage, 'planning');
  assert.deepEqual(pending.commands.plan, {
    idempotencyKey: FIRST_KEY,
    pending: true,
    attempted: true,
    error: null,
  });

  const failed = reduce(pending, 'PLAN_SUBMIT_FAILED', {
    error: { errorCode: 'insufficient_inventory', message: 'Not enough posts.', retryable: false },
  });
  assert.equal(failed.stage, 'planning');
  assert.equal(failed.draft, draft.draft);
  assert.equal(failed.commands.plan.idempotencyKey, FIRST_KEY);
  assert.equal(failed.commands.plan.error.retryable, false);

  const retry = reduce(failed, 'PLAN_SUBMIT_STARTED', { idempotencyKey: FIRST_KEY });
  assert.equal(retry.commands.plan.pending, true);
  assert.throws(
    () => reduce(failed, 'PLAN_SUBMIT_STARTED', { idempotencyKey: SECOND_KEY }),
    (error) => error.code === 'idempotency_key_changed',
  );
});

test('plan success transitions only from the authoritative returned journey and clears draft assumptions', () => {
  const pending = reduce(planningState(), 'PLAN_SUBMIT_STARTED', { idempotencyKey: FIRST_KEY });
  assert.equal(pending.stage, 'planning');

  const planned = reduce(pending, 'PLAN_CREATED', {
    journey: journey('planned', {
      intention: 'learn',
      planned_video_count: 10,
      selected_cooldown_seconds: 600,
    }),
  });
  assert.equal(planned.stage, 'planned');
  assert.equal(planned.draft, null);
  assert.deepEqual(planned.commands.plan, {
    idempotencyKey: null,
    pending: false,
    attempted: false,
    error: null,
  });
});

test('start remains planned while pending or failed and becomes active only from server state', () => {
  const planned = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', {
    journey: journey('planned'),
  });
  const pending = reduce(planned, 'SESSION_START_STARTED', { idempotencyKey: FIRST_KEY });
  assert.equal(pending.stage, 'planned');
  assert.equal(pending.commands.start.pending, true);

  const failed = reduce(pending, 'SESSION_START_FAILED', {
    error: { errorCode: 'invalid_transition', message: 'Cannot start.', retryable: false },
  });
  assert.equal(failed.stage, 'planned');
  assert.equal(failed.journey.journey_state, 'planned');

  const replayedPlan = reduce(pending, 'SESSION_STARTED', { journey: journey('planned') });
  assert.equal(replayedPlan.stage, 'planned');
  const active = reduce(pending, 'SESSION_STARTED', { journey: journey('active') });
  assert.equal(active.stage, 'active');
  assert.equal(active.commands.start.attempted, false);
});

test('cancelled authoritative plans can reopen planning with the previous valid choices', () => {
  const plannedJourney = journey('planned', {
    intention: 'relax',
    planned_video_count: 20,
    estimated_duration_seconds: 600,
    suggested_cooldown_seconds: 1_200,
    selected_cooldown_seconds: 1_500,
  });
  const planned = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', {
    journey: plannedJourney,
  });
  const pending = reduce(planned, 'PLAN_CANCEL_STARTED', { idempotencyKey: FIRST_KEY });
  const cancelled = reduce(pending, 'PLAN_CANCELLED', {
    journey: { ...plannedJourney, journey_state: 'cancelled' },
  });
  assert.equal(cancelled.stage, 'cancelled');

  const editing = reduce(cancelled, 'EDIT_CANCELLED_PLAN', {
    draft: {
      intention: 'relax',
      plannedVideoCount: 20,
      estimatedDurationSeconds: 600,
      recommendedCooldownSeconds: 1_200,
      selectedCooldownSeconds: 1_500,
    },
  });
  assert.equal(editing.stage, 'planning');
  assert.equal(editing.journey, null);
  assert.equal(editing.draft.plannedVideoCount, 20);
  assert.equal(editing.draft.selectedCooldownSeconds, 1_500);
  assert.equal(editing.commands.cancel.attempted, false);
});

test('authoritative lifecycle updates drive active through checkout, cooldown, and completed', () => {
  let state = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', {
    journey: journey('active'),
  });
  state = reduce(state, 'SERVER_JOURNEY_RECEIVED', { journey: journey('checkout') });
  assert.equal(state.stage, 'checkout');

  state = reduce(state, 'SERVER_JOURNEY_RECEIVED', {
    journey: journey('cooldown', {
      cooldown_started_at: '2026-08-06T12:00:00+00:00',
      cooldown_ends_at: '2026-08-06T12:10:00+00:00',
      override_started_at: '2026-08-06T12:01:00+00:00',
      override_available_at: '2026-08-06T12:01:15+00:00',
      remaining_seconds: 540,
    }),
  });
  assert.equal(state.stage, 'cooldown');
  assert.deepEqual(state.cooldown, {
    startedAt: '2026-08-06T12:00:00+00:00',
    endsAt: '2026-08-06T12:10:00+00:00',
    overrideStartedAt: '2026-08-06T12:01:00+00:00',
    overrideAvailableAt: '2026-08-06T12:01:15+00:00',
    remainingSeconds: 540,
  });

  const localAttempt = reduce(state, 'CLIENT_COOLDOWN_COMPLETED');
  assert.equal(localAttempt.stage, 'cooldown');
  state = reduce(state, 'SERVER_JOURNEY_RECEIVED', { journey: journey('completed') });
  assert.equal(state.stage, 'completed');
});

test('request errors preserve active and cooldown authority with retry classification', () => {
  for (const lifecycle of ['active', 'cooldown']) {
    const original = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', {
      journey: journey(lifecycle),
    });
    const failed = reduce(original, 'REQUEST_FAILED', {
      error: { errorCode: 'network_error', message: 'Offline.', retryable: true },
    });
    assert.equal(failed.stage, lifecycle);
    assert.equal(failed.journey, original.journey);
    assert.equal(failed.error.retryable, true);
    assert.equal(failed.previousSafeStage, lifecycle);
  }
});

test('bootstrap errors use the error stage and retain bootstrap-specific classification', () => {
  const failed = reduce(createInitialSessionState(), 'BOOTSTRAP_FAILED', {
    error: { errorCode: 'network_error', message: 'Offline.', retryable: true },
  });
  assert.equal(failed.stage, 'error');
  assert.equal(failed.error.kind, 'bootstrap');
  assert.equal(failed.error.retryable, true);
  assert.equal(failed.previousSafeStage, 'bootstrapping');
});

test('participant bootstrap failures classify retry and authentication without clearing authority', () => {
  const unavailable = reduce(createInitialSessionState(), 'BOOTSTRAP_FAILED', {
    error: { name: 'ResearchApiError', status: 503, message: 'Unavailable.' },
  });
  assert.equal(unavailable.error.retryable, true);
  assert.equal(unavailable.error.status, 503);

  const auth = reduce(createInitialSessionState(), 'BOOTSTRAP_FAILED', {
    error: { name: 'ResearchApiError', status: 401, message: 'Invalid credential.' },
  });
  assert.equal(auth.error.errorCode, 'participant_credential_error');
  assert.equal(auth.error.retryable, false);
  assert.equal(auth.stage, 'error');

  const network = reduce(createInitialSessionState(), 'BOOTSTRAP_FAILED', {
    error: new TypeError('offline'),
  });
  assert.equal(network.error.retryable, true);
});

test('successful command clears its key so a later logical command may use another key', () => {
  const planned = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', {
    journey: journey('planned'),
  });
  const firstPending = reduce(planned, 'SESSION_START_STARTED', { idempotencyKey: FIRST_KEY });
  const firstSuccess = reduce(firstPending, 'SESSION_STARTED', { journey: journey('active') });
  assert.equal(firstSuccess.commands.start.idempotencyKey, null);

  const nextPlanned = reduce(firstSuccess, 'SERVER_JOURNEY_RECEIVED', {
    journey: journey('planned', { session_id: 'new-session' }),
  });
  const secondPending = reduce(nextPlanned, 'SESSION_START_STARTED', {
    idempotencyKey: SECOND_KEY,
  });
  assert.equal(secondPending.commands.start.idempotencyKey, SECOND_KEY);
});

test('all lifecycle command records use the same external-key pending model', () => {
  const cases = [
    ['planned', 'PLAN_CANCEL_STARTED', 'cancel'],
    ['planned', 'SESSION_START_STARTED', 'start'],
    ['active', 'FINISH_EARLY_STARTED', 'finishEarly'],
    ['checkout', 'CHECKOUT_SUBMIT_STARTED', 'checkout'],
    ['cooldown', 'OVERRIDE_START_STARTED', 'overrideStart'],
    ['cooldown', 'OVERRIDE_CONFIRM_STARTED', 'overrideConfirm'],
  ];
  for (const [lifecycle, actionType, command] of cases) {
    let state = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', {
      journey: journey(lifecycle),
    });
    if (command === 'checkout') {
      state = reduce(state, 'SET_CHECKOUT_ANSWER', { field: 'worthwhile', value: 'yes' });
      state = reduce(state, 'SET_CHECKOUT_ANSWER', { field: 'perceivedControl', value: 4 });
      state = reduce(state, 'SET_CHECKOUT_ANSWER', { field: 'mood', value: 'same' });
    }
    if (command === 'overrideConfirm') {
      state = reduce(state, 'SET_OVERRIDE_REASON', { reasonCode: 'change_plan' });
    }
    const pending = reduce(state, actionType, { idempotencyKey: FIRST_KEY });
    assert.equal(pending.commands[command].idempotencyKey, FIRST_KEY);
    assert.equal(pending.commands[command].pending, true);
    assert.equal(pending.stage, lifecycle);
  }
});

test('checkout draft accepts exact contract values and changing an answer starts a new logical command', () => {
  let state = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', {
    journey: journey('checkout'),
    serverTimestamp: '2026-08-07T12:00:00.000Z',
  });
  state = reduce(state, 'SET_CHECKOUT_ANSWER', { field: 'worthwhile', value: 'mostly' });
  state = reduce(state, 'SET_CHECKOUT_ANSWER', {
    field: 'perceivedControl', value: 'prefer_not_to_answer',
  });
  state = reduce(state, 'SET_CHECKOUT_ANSWER', { field: 'mood', value: 'better' });
  const pending = reduce(state, 'CHECKOUT_SUBMIT_STARTED', { idempotencyKey: FIRST_KEY });
  const failed = reduce(pending, 'CHECKOUT_SUBMIT_FAILED', {
    error: { message: 'Offline.', retryable: true },
  });
  assert.equal(failed.commands.checkout.idempotencyKey, FIRST_KEY);
  assert.deepEqual(failed.checkoutDraft, {
    worthwhile: 'mostly',
    perceivedControl: 'prefer_not_to_answer',
    mood: 'better',
  });
  const edited = reduce(failed, 'SET_CHECKOUT_ANSWER', { field: 'mood', value: 'same' });
  assert.equal(edited.commands.checkout.idempotencyKey, null);
  assert.equal(edited.serverTimestamp, '2026-08-07T12:00:00.000Z');
  assert.throws(
    () => reduce(edited, 'SET_CHECKOUT_ANSWER', { field: 'mood', value: 'excellent' }),
    (error) => error.code === 'invalid_checkout_answer',
  );
});

test('override reason and command key survive pause-active reconciliation', () => {
  let state = reduce(createInitialSessionState(), 'BOOTSTRAP_SUCCEEDED', {
    journey: journey('cooldown'),
  });
  state = reduce(state, 'SET_OVERRIDE_REASON', { reasonCode: 'want_another_session' });
  state = reduce(state, 'OVERRIDE_CONFIRM_STARTED', { idempotencyKey: FIRST_KEY });
  state = reduce(state, 'OVERRIDE_CONFIRM_FAILED', {
    error: {
      errorCode: 'override_pause_active',
      message: 'Pause active.',
      retryable: false,
      serverTimestamp: '2026-08-07T12:00:06.000Z',
      details: {
        override_available_at: '2026-08-07T12:00:15.000Z',
        remaining_pause_seconds: 9,
      },
    },
  });
  assert.equal(state.stage, 'cooldown');
  assert.equal(state.overrideDraft.reasonCode, 'want_another_session');
  assert.equal(state.commands.overrideConfirm.idempotencyKey, FIRST_KEY);
  assert.equal(state.commands.overrideConfirm.error.details.remaining_pause_seconds, 9);
  assert.equal(state.serverTimestamp, '2026-08-07T12:00:06.000Z');
});
