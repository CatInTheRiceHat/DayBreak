import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test, { after, before } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { createInitialSessionState, sessionMachineReducer } from './sessionMachine.js';

let vite;
let CheckoutForm;

before(async () => {
  vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent' });
  ({ CheckoutForm } = await vite.ssrLoadModule('/src/features/research/CheckoutForm.jsx'));
});

after(async () => { await vite?.close(); });

const handlers = { onAnswer() {}, onSubmit() {}, onReconcile() {} };

function render(draft, overrides = {}) {
  return renderToStaticMarkup(createElement(CheckoutForm, {
    sessionId: 'session-1',
    draft,
    command: { pending: false, error: null },
    error: null,
    ...handlers,
    ...overrides,
  }));
}

test('checkout renders exact three-question answer mappings with native radios', () => {
  const html = render({ worthwhile: null, perceivedControl: null, mood: null });
  for (const copy of [
    'How was that break?', 'Was this break worth your time?', 'Yes', 'Mostly', 'Not really',
    'How in control did you feel?', 'Not at all', 'Completely',
    'How do you feel now?', 'Better', 'About the same', 'Worse', 'Prefer not to answer',
  ]) assert.ok(html.includes(copy), copy);
  assert.equal((html.match(/type="radio"/g) || []).length, 14);
  assert.doesNotMatch(html, /textarea|type="text"/);
});

test('submission remains disabled until all three answers are valid', () => {
  const incomplete = render({ worthwhile: 'yes', perceivedControl: 4, mood: null });
  assert.match(incomplete, /type="submit" disabled=""/);
  const complete = render({ worthwhile: 'yes', perceivedControl: 4, mood: 'same' });
  const submit = complete.match(/<button[^>]*type="submit"[^>]*>[\s\S]*?<\/button>/)?.[0];
  assert.ok(submit);
  assert.doesNotMatch(submit, /disabled/);
});

test('prefer-not-to-answer is valid for every question and pending prevents duplicates', () => {
  const draft = {
    worthwhile: 'prefer_not_to_answer',
    perceivedControl: 'prefer_not_to_answer',
    mood: 'prefer_not_to_answer',
  };
  const ready = render(draft);
  assert.doesNotMatch(ready.match(/<button[^>]*type="submit"[^>]*>/)?.[0] ?? '', /disabled/);
  const pending = render(draft, { command: { pending: true, error: null } });
  assert.ok(pending.includes('Starting your time away…'));
  assert.match(pending.match(/<button[^>]*type="submit"[^>]*>/)?.[0] ?? '', /disabled/);
});

test('checkout command retains its key, answers, and stage through a retryable failure', () => {
  let state = sessionMachineReducer(createInitialSessionState(), {
    type: 'BOOTSTRAP_SUCCEEDED', journey: { session_id: 'session-1', journey_state: 'checkout' },
  });
  for (const [field, value] of [['worthwhile', 'yes'], ['perceivedControl', 5], ['mood', 'better']]) {
    state = sessionMachineReducer(state, { type: 'SET_CHECKOUT_ANSWER', field, value });
  }
  state = sessionMachineReducer(state, { type: 'CHECKOUT_SUBMIT_STARTED', idempotencyKey: 'key-1' });
  state = sessionMachineReducer(state, {
    type: 'CHECKOUT_SUBMIT_FAILED', error: { message: 'Offline', retryable: true },
  });
  assert.equal(state.stage, 'checkout');
  assert.equal(state.commands.checkout.idempotencyKey, 'key-1');
  assert.deepEqual(state.checkoutDraft, { worthwhile: 'yes', perceivedControl: 5, mood: 'better' });
});

test('checkout presentation delegates lifecycle and API authority to ResearchPage', async () => {
  const source = await readFile(new URL('./CheckoutForm.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /submitCheckout|journey_state\s*=|checkout_version/);
  const page = await readFile(new URL('./ResearchPage.jsx', import.meta.url), 'utf8');
  assert.match(page, /intentionalBreakApi\.submitCheckout/);
  assert.match(page, /CHECKOUT_SUBMITTED/);
  assert.match(page, /bestEffortQueueFlush\(lifecycleQueueRef\.current\)/);
});
