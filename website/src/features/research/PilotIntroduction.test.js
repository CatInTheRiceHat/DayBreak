import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test, { after, before } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { createInitialSessionState, sessionMachineReducer } from './sessionMachine.js';

let vite;
let PilotIntroduction;

before(async () => {
  vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent' });
  ({ PilotIntroduction } = await vite.ssrLoadModule('/src/features/research/PilotIntroduction.jsx'));
});

after(async () => {
  await vite?.close();
});

test('pilot introduction preserves every approved participant-facing claim', () => {
  const html = renderToStaticMarkup(createElement(PilotIntroduction, { onContinue() {} }));
  const claims = [
    'Welcome to the DayBreak pilot',
    'choosing a limited feed session can make scrolling feel more intentional',
    'answer three short questions and begin a break from the feed',
    'session choices, viewed posts, interactions',
    'whether the break was completed or ended early',
    'does not collect your name, government ID, precise location, private messages, or contacts',
    'Participation is voluntary',
    'has not been proven to improve mental health, sleep, or self-control',
  ];
  for (const claim of claims) assert.ok(html.includes(claim), claim);
});

test('rendering and continuing are local-only and enter planning without a plan command', async () => {
  let calls = 0;
  const html = renderToStaticMarkup(createElement(PilotIntroduction, {
    onContinue() { calls += 1; },
  }));
  assert.equal(calls, 0);
  assert.match(html, />Continue</);

  const notice = sessionMachineReducer(createInitialSessionState(), {
    type: 'BOOTSTRAP_SUCCEEDED',
    journey: null,
  });
  const planning = sessionMachineReducer(notice, { type: 'NOTICE_ACKNOWLEDGED' });
  assert.equal(planning.stage, 'planning');
  assert.equal(planning.commands.plan.attempted, false);

  const source = await readFile(new URL('./PilotIntroduction.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /createPlan|startSession|researchTracker/);
});
