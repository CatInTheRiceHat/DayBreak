import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test, { after, before } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let vite;
let CooldownScreen;

before(async () => {
  vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent' });
  ({ CooldownScreen } = await vite.ssrLoadModule('/src/features/research/CooldownScreen.jsx'));
});

after(async () => { await vite?.close(); });

function render(overrides = {}) {
  return renderToStaticMarkup(createElement(CooldownScreen, {
    journey: {
      session_id: 'session-1',
      journey_state: 'cooldown',
      selected_cooldown_seconds: 1_200,
      cooldown_ends_at: '2026-08-07T12:20:00.000Z',
      remaining_seconds: 1_200,
    },
    serverTimestamp: '2026-08-07T12:00:00.000Z',
    overrideCommand: { pending: false, error: null },
    onReconcile() {},
    onReturnEarly() {},
    ...overrides,
  }));
}

test('cooldown is quiet, factual, and keeps the feed out of view', () => {
  const html = render();
  for (const copy of [
    'Time for your reset', '20 minutes away', 'Time remaining',
    "You don&#x27;t need to keep this page open", 'Try something offline:',
    'I want to return early',
  ]) assert.ok(html.includes(copy), copy);
  assert.doesNotMatch(html, /video|thumbnail|feed preview|streak|reward|>points<|don&#x27;t fail/i);
});

test('return early remains visually secondary and retryable reconciliation never claims completion', () => {
  const html = render({
    reconcileError: { message: 'Offline', retryable: true },
  });
  assert.ok(html.includes("We&#x27;re having trouble checking your reset right now."));
  assert.ok(html.includes('Your feed stays unavailable'));
  assert.ok(html.includes('Try again'));
  assert.doesNotMatch(html, /DayBreak is complete/);
  assert.match(html, /study-text-action study-text-action--quiet/);
});

test('cooldown reconciles only through the provided server reader at mount, zero, focus, visibility, and cross-tab signals', async () => {
  const source = await readFile(new URL('./CooldownScreen.jsx', import.meta.url), 'utf8');
  assert.match(source, /remainingSeconds !== 0/);
  assert.match(source, /onReconcile\(\)/);
  assert.match(source, /window\.addEventListener\('focus'/);
  assert.match(source, /visibilitychange/);
  assert.match(source, /createJourneySynchronizer/);
  assert.doesNotMatch(source, /journey_state\s*=\s*['"]completed|setInterval[\s\S]*getCooldown/);
});

test('optional offline suggestion can be omitted without changing cooldown authority', () => {
  const html = render({ showSuggestion: false });
  assert.doesNotMatch(html, /Try something offline/);
  assert.ok(html.includes('Time for your reset'));
});
