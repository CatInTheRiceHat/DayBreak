import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test, { after, before } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let vite;
let OverrideFlow;

before(async () => {
  vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent' });
  ({ OverrideFlow } = await vite.ssrLoadModule('/src/features/research/OverrideFlow.jsx'));
});

after(async () => { await vite?.close(); });

function render(overrides = {}) {
  return renderToStaticMarkup(createElement(OverrideFlow, {
    journey: {
      session_id: 'session-1',
      journey_state: 'cooldown',
      override_started_at: '2026-08-07T12:00:00.000Z',
      override_available_at: '2026-08-07T12:00:15.000Z',
    },
    serverTimestamp: '2026-08-07T12:00:00.000Z',
    reasonCode: null,
    command: { pending: false, error: null },
    onReasonChange() {},
    onConfirm() {},
    onKeepBreak() {},
    onReconcile() {},
    ...overrides,
  }));
}

test('override pause uses authoritative timing and every frozen reason', () => {
  const html = render();
  assert.ok(html.includes('Do you still want to come back?'));
  assert.ok(html.includes('Give it a few seconds before deciding.'));
  assert.ok(html.includes('0:15'));
  for (const reason of [
    'I need to change my plan', 'I opened DayBreak automatically',
    'I want another session', 'Something else',
  ]) assert.ok(html.includes(reason), reason);
  assert.equal((html.match(/name="override-reason"/g) || []).length, 4);
});

test('return confirmation requires both likely availability and a reason', () => {
  const waiting = render({ reasonCode: 'change_plan' });
  const waitingButton = waiting.match(/<button[^>]*>Return early<\/button>/)?.[0];
  assert.match(waitingButton, /disabled/);

  const available = render({
    journey: {
      session_id: 'session-1', journey_state: 'cooldown',
      override_started_at: '2026-08-07T12:00:00.000Z',
      override_available_at: '2026-08-07T12:00:15.000Z',
    },
    serverTimestamp: '2026-08-07T12:00:15.000Z',
    reasonCode: 'other',
  });
  const availableButton = available.match(/<button[^>]*>Return early<\/button>/)?.[0];
  assert.ok(availableButton);
  assert.doesNotMatch(availableButton, /disabled/);
  assert.ok(available.includes('Keep taking my break'));
});

test('pause-active is normal timing reconciliation and preserves the original attempt', () => {
  const html = render({
    reasonCode: 'want_another_session',
    command: {
      pending: false,
      error: {
        errorCode: 'override_pause_active',
        serverTimestamp: '2026-08-07T12:00:06.000Z',
        details: {
          override_available_at: '2026-08-07T12:00:15.000Z',
          remaining_pause_seconds: 9,
        },
      },
    },
  });
  assert.ok(html.includes('A few more seconds.'));
  assert.ok(html.includes('0:09'));
  assert.doesNotMatch(html, /scary|failed your break/i);
});

test('override presentation never starts or completes lifecycle locally', async () => {
  const source = await readFile(new URL('./OverrideFlow.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /startOverride|confirmOverride|journey_state\s*=|setTimeout\([^,]+,\s*15000/);
  const page = await readFile(new URL('./ResearchPage.jsx', import.meta.url), 'utf8');
  assert.match(page, /intentionalBreakApi\.startOverride/);
  assert.match(page, /intentionalBreakApi\.confirmOverride/);
  assert.match(page, /error\?\.errorCode !== 'override_pause_active'/);
});
