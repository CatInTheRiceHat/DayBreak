import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { createInitialSessionState, sessionMachineReducer } from './sessionMachine.js';

const PAGE_URL = new URL('./ResearchPage.jsx', import.meta.url);

function journey(journeyState, extra = {}) {
  return {
    session_id: '22222222-2222-4222-8222-222222222222',
    journey_state: journeyState,
    intention: 'relax',
    planned_video_count: 20,
    estimated_duration_seconds: 600,
    suggested_cooldown_seconds: 1_200,
    selected_cooldown_seconds: 1_200,
    ...extra,
  };
}

test('bootstrap and refresh always map the authoritative current journey', () => {
  const expected = new Map([
    [null, 'notice'],
    ['planned', 'planned'],
    ['active', 'active'],
    ['checkout', 'checkout'],
    ['cooldown', 'cooldown'],
    ['completed', 'completed'],
    ['cancelled', 'cancelled'],
  ]);
  for (const [serverState, stage] of expected) {
    const state = sessionMachineReducer(createInitialSessionState(), {
      type: 'BOOTSTRAP_SUCCEEDED',
      journey: serverState ? journey(serverState) : null,
    });
    assert.equal(state.stage, stage);
    assert.equal(state.commands.plan.attempted, false);
  }
});

test('ResearchPage boot uses participant initialization and GET current without legacy startup', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.match(source, /ensureResearchParticipant/);
  assert.match(source, /intentionalBreakApi\.getCurrentJourney\(\)/);
  assert.doesNotMatch(source, /getResearchEventService|researchTracker|\.initialize\(\)|Complete test session/);
  assert.doesNotMatch(source, /sessionStorage/);
});

test('the visible study route renders the finite pilot feed but never the legacy feed', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.doesNotMatch(source, /ReelsPage|ReelCard|CroppedYouTubePlayer/);
  assert.doesNotMatch(source, /Regular|Balanced|assigned_condition|experimental condition/i);
  assert.match(source, /IntentionalBreakFeed/);
  assert.doesNotMatch(source, /ActiveSessionHandoff/);
});

test('plan command payload carries draft values and one retained key', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.match(source, /state\.commands\.plan\.idempotencyKey\s*\n\s*\?\? intentionalBreakApi\.createIdempotencyKey/);
  assert.match(source, /planRequestInFlight\.current/);
  assert.match(source, /intentionalBreakApi\.createPlan\(\{[\s\S]*intention: state\.draft\.intention/);
  assert.match(source, /plannedVideoCount: state\.draft\.plannedVideoCount/);
  assert.match(source, /selectedCooldownSeconds: state\.draft\.selectedCooldownSeconds/);
  assert.match(source, /type: 'PLAN_CREATED'/);
  assert.match(source, /journey: response\.journey/);
});

test('start and change-plan commands wait for server journeys and retain separate keys', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.match(source, /state\.commands\.start\.idempotencyKey/);
  assert.match(source, /intentionalBreakApi\.startSession/);
  assert.match(source, /type: 'SESSION_STARTED'/);
  assert.match(source, /state\.commands\.cancel\.idempotencyKey/);
  assert.match(source, /intentionalBreakApi\.cancelPlan/);
  assert.match(source, /type: 'PLAN_CANCELLED'/);
  assert.match(source, /EDIT_CANCELLED_PLAN/);
});

test('finish early retains one command key and waits for the authoritative response', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.match(source, /state\.commands\.finishEarly\.idempotencyKey/);
  assert.match(source, /intentionalBreakApi\.finishEarly\(state\.journey\.session_id/);
  assert.match(source, /currentPosition/);
  assert.match(source, /type: 'FINISH_EARLY_SUCCEEDED'/);
  assert.doesNotMatch(source, /journey_state\s*=\s*['"]checkout/);
});

test('cross-tab and focus reconciliation only read the current server journey', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.match(source, /intentionalBreakApi\.getCurrentJourney\(\)/);
  assert.match(source, /SERVER_JOURNEY_RECEIVED/);
  assert.doesNotMatch(source, /createPlan.*reconcileJourney|startSession.*reconcileJourney/);
});

test('checkout, cooldown, override, and completion replace every temporary resume placeholder', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  for (const component of ['CheckoutForm', 'CooldownScreen', 'OverrideFlow', 'SessionComplete']) {
    assert.match(source, new RegExp(`<${component}`));
  }
  assert.doesNotMatch(source, /CheckoutResume|CooldownResume|being connected in the next implementation stage/);
  assert.doesNotMatch(source, /completeSession|researchTracker\.complete/);
});

test('checkout and cooldown attempt delayed v1 event flush without deleting queued diagnostics', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.match(source, /\['checkout', 'cooldown', 'completed'\]/);
  assert.match(source, /readIntentionalBreakQueueSnapshot\(sessionId\)\.pending/);
  assert.match(source, /intentionalBreakApi\.appendEvents\(sessionId, events\)/);
  assert.doesNotMatch(source, /removeItem.*intentional-break-events|clearStored.*Event/);
});

test('bootstrap failures retain credentials and unknown state fails safely', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.ok(source.includes('DayBreak has not replaced or cleared it.'));
  assert.doesNotMatch(source, /clearStoredResearchParticipant|localStorage\.removeItem/);
  const failed = sessionMachineReducer(createInitialSessionState(), {
    type: 'BOOTSTRAP_SUCCEEDED', journey: journey('invented'),
  });
  assert.equal(failed.stage, 'error');
  assert.equal(failed.error.errorCode, 'unknown_lifecycle_state');
});

test('checkout command best-effort flushes events, retains one key, and waits for cooldown authority', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.match(source, /state\.commands\.checkout\.idempotencyKey[\s\S]*?createIdempotencyKey/);
  assert.match(source, /checkoutRequestInFlight\.current/);
  assert.match(source, /await bestEffortQueueFlush\(lifecycleQueueRef\.current\)/);
  assert.match(source, /function bestEffortQueueFlush\(queue, timeoutMs = 750\)/);
  assert.match(source, /intentionalBreakApi\.submitCheckout\(state\.journey\.session_id/);
  assert.match(source, /CHECKOUT_SUBMITTED/);
  assert.doesNotMatch(source, /journey_state:\s*['"]cooldown/);
});

test('cooldown reads server state and neither timer nor buttons invent completion', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.match(source, /intentionalBreakApi\.getCooldown\(sessionId\)/);
  assert.match(source, /SERVER_JOURNEY_RECEIVED/);
  assert.doesNotMatch(source, /CLIENT_COOLDOWN_COMPLETED|journey_state:\s*['"]completed/);
});

test('override start and confirmation use separate retained idempotency keys', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  assert.match(source, /state\.commands\.overrideStart\.idempotencyKey/);
  assert.match(source, /intentionalBreakApi\.startOverride/);
  assert.match(source, /OVERRIDE_STARTED/);
  assert.match(source, /state\.commands\.overrideConfirm\.idempotencyKey/);
  assert.match(source, /intentionalBreakApi\.confirmOverride/);
  assert.match(source, /OVERRIDE_CONFIRMED/);
  assert.match(source, /state\.journey\.override_started_at/);
});

test('plan another verifies current authority and creates no plan automatically', async () => {
  const source = await readFile(PAGE_URL, 'utf8');
  const handler = source.match(/async function planAnother\(\)[\s\S]*?\n\s{2}}/)?.[0] ?? '';
  assert.match(handler, /getCurrentJourney/);
  assert.match(handler, /isNonterminalState/);
  assert.match(handler, /RETURN_TO_NOTICE/);
  assert.doesNotMatch(handler, /createPlan|startSession/);
});
