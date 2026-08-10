import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  resolveIntentionalBreakRouteGuard,
  ROUTE_GUARD_OUTCOMES,
} from './intentionalBreakRouteGuard.js';

const PARTICIPANT = Object.freeze({
  participant_id: '11111111-1111-4111-8111-111111111111',
  access_token: 'stored-anonymous-bearer-token',
});

const PRODUCT_ROUTES = Object.freeze([
  '/',
  '/algorithm',
  '/reels',
  '/home',
  '/community',
  '/challenges',
  '/saved',
  '/search',
  '/inbox',
  '/login',
  '/signup',
  '/forgot-password',
  '/reset-password',
  '/diagnostic',
  '/profile',
  '/profile/edit',
  '/u/:username',
]);

function journey(journeyState) {
  return { journey: journeyState ? { journey_state: journeyState } : null };
}

test('every current normal product route is nested behind the guard and study is outside it', async () => {
  const source = await readFile(new URL('../../app/App.jsx', import.meta.url), 'utf8');
  const guardStart = source.indexOf('<Route element={<IntentionalBreakRouteGuard />}>');
  const guardEnd = source.indexOf('      </Route>\n    </Routes>', guardStart);
  assert.ok(guardStart > 0 && guardEnd > guardStart);
  const guardedRoutes = source.slice(guardStart, guardEnd);

  for (const route of PRODUCT_ROUTES) {
    assert.match(guardedRoutes, new RegExp(`path="${route.replace(/[/:]/g, '\\$&')}"`));
  }
  assert.doesNotMatch(guardedRoutes, /path="\/study"/);
  assert.match(source.slice(0, guardStart), /<Route path="\/study" element={<StudyShell \/>} \/>/);
  assert.doesNotMatch(source, /path="\*"/);
});

test('no stored credential allows every product route without a request or participant creation', async () => {
  for (const route of PRODUCT_ROUTES) {
    let currentCalls = 0;
    const result = await resolveIntentionalBreakRouteGuard({
      getStoredParticipant: () => null,
      getCurrentJourney: async () => { currentCalls += 1; },
    });
    assert.deepEqual(result, { outcome: ROUTE_GUARD_OUTCOMES.ALLOW, reason: 'no_credential' }, route);
    assert.equal(currentCalls, 0, route);
  }
});

test('stored credential with no current, completed, or cancelled journey allows product routing', async () => {
  for (const state of [null, 'completed', 'cancelled']) {
    let calls = 0;
    const result = await resolveIntentionalBreakRouteGuard({
      getStoredParticipant: () => PARTICIPANT,
      getCurrentJourney: async (participant) => {
        calls += 1;
        assert.equal(participant, PARTICIPANT);
        return journey(state);
      },
    });
    assert.equal(result.outcome, ROUTE_GUARD_OUTCOMES.ALLOW);
    assert.equal(calls, 1);
  }
});

test('planned, active, checkout, and cooldown journeys redirect every representative route class', async () => {
  const cases = [
    ['planned', ['/', '/challenges', '/profile']],
    ['active', ['/', '/reels', '/saved', '/u/example']],
    ['checkout', ['/community', '/search', '/inbox']],
    ['cooldown', ['/', '/diagnostic', '/login']],
  ];
  for (const [state, routes] of cases) {
    for (const route of routes) {
      const result = await resolveIntentionalBreakRouteGuard({
        getStoredParticipant: () => PARTICIPANT,
        getCurrentJourney: async () => journey(state),
      });
      assert.deepEqual(
        result,
        { outcome: ROUTE_GUARD_OUTCOMES.REDIRECT, reason: 'nonterminal_journey' },
        `${state} at ${route}`,
      );
    }
  }
});

test('retryable authority failure fails closed and retry reuses the stored participant', async () => {
  const seen = [];
  let attempt = 0;
  const getCurrentJourney = async (participant) => {
    seen.push(participant);
    attempt += 1;
    if (attempt === 1) {
      throw Object.assign(new Error('offline'), { retryable: true, errorCode: 'network_error' });
    }
    return journey('active');
  };
  const dependencies = {
    getStoredParticipant: () => PARTICIPANT,
    getCurrentJourney,
  };
  assert.deepEqual(await resolveIntentionalBreakRouteGuard(dependencies), {
    outcome: ROUTE_GUARD_OUTCOMES.ERROR,
    reason: 'authority_unavailable',
  });
  assert.deepEqual(await resolveIntentionalBreakRouteGuard(dependencies), {
    outcome: ROUTE_GUARD_OUTCOMES.REDIRECT,
    reason: 'nonterminal_journey',
  });
  assert.deepEqual(seen, [PARTICIPANT, PARTICIPANT]);
});

test('a successful retry with no journey releases the original product route', async () => {
  let attempt = 0;
  const dependencies = {
    getStoredParticipant: () => PARTICIPANT,
    getCurrentJourney: async () => {
      attempt += 1;
      if (attempt === 1) throw Object.assign(new Error('unavailable'), { status: 503 });
      return journey(null);
    },
  };
  assert.equal(
    (await resolveIntentionalBreakRouteGuard(dependencies)).outcome,
    ROUTE_GUARD_OUTCOMES.ERROR,
  );
  assert.equal(
    (await resolveIntentionalBreakRouteGuard(dependencies)).outcome,
    ROUTE_GUARD_OUTCOMES.ALLOW,
  );
});

test('invalid or inactive credentials allow recovery without clearing or replacing them', async () => {
  for (const error of [
    { status: 401, errorCode: 'invalid_credential' },
    { status: 403, errorCode: 'participant_inactive' },
  ]) {
    const result = await resolveIntentionalBreakRouteGuard({
      getStoredParticipant: () => PARTICIPANT,
      getCurrentJourney: async (participant) => {
        assert.equal(participant, PARTICIPANT);
        throw Object.assign(new Error('credential rejected'), error);
      },
    });
    assert.deepEqual(result, {
      outcome: ROUTE_GUARD_OUTCOMES.ALLOW,
      reason: 'unusable_credential',
    });
  }
});

test('guard UI hides product outlets while checking or failed and uses replacement redirects', async () => {
  const source = await readFile(new URL('./IntentionalBreakRouteGuard.jsx', import.meta.url), 'utf8');
  assert.ok(source.includes('Checking your DayBreak…'));
  assert.ok(source.includes("We couldn&apos;t check your DayBreak session."));
  assert.ok(source.includes('Try again, or return to your study session.'));
  assert.match(source, /<Navigate to="\/study" replace \/>/);
  assert.match(source, /to="\/study" replace/);
  assert.match(source, /window\.addEventListener\('focus', checkAuthority\)/);
  assert.match(source, /visibilityState === 'visible'/);
  assert.doesNotMatch(source, /ensureResearchParticipant|clearStoredResearchParticipant|access_token|participant_id/);
});
