import assert from 'node:assert/strict';
import test, { after, before } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import {
  createInitialSessionState,
  sessionMachineReducer,
} from './sessionMachine.js';

let vite;
let SessionPlanner;

before(async () => {
  vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent' });
  ({ SessionPlanner } = await vite.ssrLoadModule('/src/features/research/SessionPlanner.jsx'));
});

after(async () => {
  await vite?.close();
});

const handlers = {
  onIntentionChange() {},
  onVideoCountChange() {},
  onCooldownChange() {},
  onReview() {},
  onClearError() {},
};

function stateFor({ intention = null, count = null, cooldown = null } = {}) {
  let state = sessionMachineReducer(createInitialSessionState(), {
    type: 'BOOTSTRAP_SUCCEEDED', journey: null,
  });
  state = sessionMachineReducer(state, { type: 'NOTICE_ACKNOWLEDGED' });
  if (intention) state = sessionMachineReducer(state, { type: 'SET_INTENTION', intention });
  if (count) state = sessionMachineReducer(state, { type: 'SET_VIDEO_COUNT', plannedVideoCount: count });
  if (cooldown) {
    state = sessionMachineReducer(state, {
      type: 'SET_SELECTED_COOLDOWN', selectedCooldownSeconds: cooldown,
    });
  }
  return state;
}

function render(state, error = null) {
  return renderToStaticMarkup(createElement(SessionPlanner, {
    draft: state.draft,
    command: state.commands.plan,
    error,
    ...handlers,
  }));
}

test('planner presents all five intentions as accessible radio choices', () => {
  const html = render(stateFor());
  for (const copy of [
    'Relax',
    'Slow down for a little while.',
    'Learn',
    'Find something interesting.',
    'Feel inspired',
    'Find ideas, creativity, or motivation.',
    'Catch up',
    'Take a quick break',
    'A small reset before getting back to your day.',
  ]) assert.ok(html.includes(copy), copy);
  assert.equal((html.match(/name="intention"/g) || []).length, 5);
  assert.doesNotMatch(html, /Cruisin|Flutter Feed|Metamorph|Daily Dew/);
});

test('selecting an intention reveals every frozen count and friendly estimate', () => {
  const html = render(stateFor({ intention: 'relax' }));
  for (const copy of [
    '5 videos', 'about 3 min',
    '10 videos', 'about 5 min',
    '20 videos', 'about 10 min',
    '40 videos', 'about 20 min',
  ]) assert.ok(html.includes(copy), copy);
  assert.equal((html.match(/name="video-count"/g) || []).length, 4);
});

test('count selection derives cooldown and a deliberate adjustment updates the summary', () => {
  const recommended = stateFor({ intention: 'relax', count: 20 });
  assert.equal(recommended.draft.estimatedDurationSeconds, 600);
  assert.equal(recommended.draft.recommendedCooldownSeconds, 1_200);
  assert.match(render(recommended), /suggests <strong>20 minutes away<\/strong>/);

  const adjusted = sessionMachineReducer(recommended, {
    type: 'SET_SELECTED_COOLDOWN', selectedCooldownSeconds: 1_500,
  });
  const html = render(adjusted);
  assert.ok(html.includes('Relax'));
  assert.ok(html.includes('20 videos · about 10 min'));
  assert.ok(html.includes('Then 25 minutes away'));
});

test('changing count recalculates the default recommendation', () => {
  let state = stateFor({ intention: 'learn', count: 40, cooldown: 3_000 });
  assert.equal(state.draft.selectedCooldownSeconds, 3_000);
  state = sessionMachineReducer(state, { type: 'SET_VIDEO_COUNT', plannedVideoCount: 10 });
  assert.equal(state.draft.recommendedCooldownSeconds, 600);
  assert.equal(state.draft.selectedCooldownSeconds, 600);
});

test('review is disabled until the machine considers every value valid', () => {
  const incomplete = render(stateFor({ intention: 'learn' }));
  assert.match(incomplete, /disabled=""[^>]*>Review my plan/);
  const complete = render(stateFor({ intention: 'learn', count: 10 }));
  const reviewButton = complete.match(/<button[^>]*type="submit"[^>]*>.*?Review my plan.*?<\/button>/)?.[0];
  assert.ok(reviewButton);
  assert.doesNotMatch(reviewButton, /disabled/);
});

test('insufficient inventory suggests but never selects the largest lower count', () => {
  const cases = [
    [40, 27, 20],
    [20, 13, 10],
    [10, 6, 5],
  ];
  for (const [requested, available, suggestion] of cases) {
    const state = stateFor({ intention: 'relax', count: requested });
    const html = render(state, {
      errorCode: 'insufficient_inventory',
      details: { requested_count: requested, available_count: available },
    });
    assert.ok(html.includes('That session is a little too large right now.'));
    assert.ok(html.includes(`Try ${suggestion} videos instead`));
    const requestedInput = html.match(new RegExp(`<input[^>]*value="${requested}"[^>]*>`))?.[0];
    const suggestedInput = html.match(new RegExp(`<input[^>]*value="${suggestion}"[^>]*>`))?.[0];
    assert.match(requestedInput, /checked=""/);
    assert.doesNotMatch(suggestedInput, /checked=""/);
  }
});

test('inventory below the pilot minimum asks the participant to return later', () => {
  const state = stateFor({ intention: 'relax', count: 5 });
  const html = render(state, {
    errorCode: 'insufficient_inventory',
    details: { requested_count: 5, available_count: 4 },
  });
  assert.ok(html.includes("doesn&#x27;t have enough unique videos for a session right now"));
  assert.doesNotMatch(html, /Try [0-9]+ videos instead/);
});

test('retryable errors preserve the complete summary and expose an explicit retry', () => {
  const html = render(stateFor({ intention: 'quick_break', count: 5 }), {
    errorCode: 'network_error',
    message: 'Offline.',
    retryable: true,
  });
  assert.ok(html.includes("DayBreak couldn&#x27;t reach the study service."));
  assert.ok(html.includes('Your choices are still here. You can try again.'));
  assert.ok(html.includes('Try again'));
  assert.ok(html.includes('Take a quick break'));
});
