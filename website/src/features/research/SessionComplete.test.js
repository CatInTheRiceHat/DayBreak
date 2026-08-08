import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test, { after, before } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let vite;
let SessionComplete;

before(async () => {
  vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent' });
  ({ SessionComplete } = await vite.ssrLoadModule('/src/features/research/SessionComplete.jsx'));
});

after(async () => { await vite?.close(); });

function render(extra = {}) {
  return renderToStaticMarkup(createElement(SessionComplete, {
    journey: {
      journey_state: 'completed',
      planned_video_count: 20,
      finish_reason: 'boundary_reached',
      selected_cooldown_seconds: 1_200,
      cooldown_outcome: 'completed',
      ...extra,
    },
    onPlanAnother() {},
  }));
}

test('natural completion is neutral and factual', () => {
  const html = render();
  assert.ok(html.includes('Your DayBreak is complete'));
  assert.ok(html.includes('You finished the time away you chose.'));
  assert.ok(html.includes('20 videos'));
  assert.ok(html.includes('Reached boundary'));
  assert.ok(html.includes('20 minutes'));
  assert.ok(html.includes('Plan another DayBreak'));
  assert.doesNotMatch(html, /score|grade|success|failure|streak|reward|confetti/i);
});

test('override and finish-early outcomes use neutral summary labels', () => {
  const html = render({ finish_reason: 'finished_early', cooldown_outcome: 'overridden' });
  assert.ok(html.includes('You chose to return before your original reset ended.'));
  assert.ok(html.includes('Finished early'));
  assert.ok(html.includes('Ended early'));
  assert.doesNotMatch(html, /failed|broke your promise|gave up|penalty/i);
});

test('planning another delegates the required current-journey check and never creates a plan', async () => {
  const component = await readFile(new URL('./SessionComplete.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(component, /getCurrentJourney|createPlan|NOTICE_ACKNOWLEDGED/);
  const page = await readFile(new URL('./ResearchPage.jsx', import.meta.url), 'utf8');
  assert.match(page, /async function planAnother/);
  assert.match(page, /intentionalBreakApi\.getCurrentJourney\(\)/);
  assert.match(page, /isNonterminalState/);
  assert.doesNotMatch(page.match(/async function planAnother[\s\S]*?\n\s{2}}/)?.[0] ?? '', /createPlan/);
});
