import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test, { after, before } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let vite;
let SessionPlanConfirmation;

before(async () => {
  vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent' });
  ({ SessionPlanConfirmation } = await vite.ssrLoadModule('/src/features/research/SessionPlanConfirmation.jsx'));
});

after(async () => {
  await vite?.close();
});

function render(journey, overrides = {}) {
  return renderToStaticMarkup(createElement(SessionPlanConfirmation, {
    journey,
    startCommand: { pending: false },
    cancelCommand: { pending: false },
    error: null,
    onBegin() {},
    onChangePlan() {},
    onClearError() {},
    ...overrides,
  }));
}

test('confirmation displays only authoritative server plan values', () => {
  const html = render({
    intention: 'inspired',
    planned_video_count: 40,
    estimated_duration_seconds: 1_230,
    selected_cooldown_seconds: 3_300,
  });
  assert.ok(html.includes('Ready for your DayBreak?'));
  assert.ok(html.includes('Feel inspired'));
  assert.ok(html.includes('40 videos · about 21 minutes'));
  assert.ok(html.includes('Afterward: 55 minutes away'));
  assert.ok(html.includes('You chose the boundary. DayBreak will stop the session when you reach it.'));
  assert.ok(html.includes('Begin my break'));
  assert.ok(html.includes('Change my plan'));
});

test('pending start and cancellation keep the saved confirmation in place', () => {
  const journey = {
    intention: 'learn',
    planned_video_count: 10,
    estimated_duration_seconds: 300,
    selected_cooldown_seconds: 600,
  };
  const starting = render(journey, { startCommand: { pending: true } });
  assert.ok(starting.includes('Starting your DayBreak…'));
  assert.ok(starting.includes('Ready for your DayBreak?'));
  const cancelling = render(journey, { cancelCommand: { pending: true } });
  assert.ok(cancelling.includes('Reopening your plan…'));
  assert.ok(cancelling.includes('Ready for your DayBreak?'));
});

test('presentation component does not force lifecycle transitions or call APIs', async () => {
  const source = await readFile(new URL('./SessionPlanConfirmation.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /startSession|cancelPlan|journey_state\s*=|SESSION_STARTED|PLAN_CANCELLED/);
});
