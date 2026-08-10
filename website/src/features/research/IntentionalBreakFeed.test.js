import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test, { after, before } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { finishEarlyAfterBestEffortFlush } from './intentionalBreakEventQueue.js';

let vite;
let IntentionalBreakFeed;

before(async () => {
  vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent' });
  ({ IntentionalBreakFeed } = await vite.ssrLoadModule('/src/features/research/IntentionalBreakFeed.jsx'));
});

after(async () => { await vite?.close(); });

function render(highest = 0) {
  return renderToStaticMarkup(createElement(IntentionalBreakFeed, {
    journey: {
      session_id: 'session-1',
      journey_state: 'active',
      planned_video_count: 20,
      highest_reached_position: highest,
    },
    finishCommand: { pending: false, error: null },
    commandError: null,
    onServerJourney() {},
    onReconcileJourney() {},
    onFinishEarly: async () => null,
  }));
}

test('active feed chrome shows canonical resume progress without gamification', () => {
  const untouched = render(0);
  assert.ok(untouched.includes('<strong>1</strong> of 20'));
  const resumed = render(7);
  assert.ok(resumed.includes('<strong>8</strong> of 20'));
  assert.ok(resumed.includes('Your chosen session'));
  assert.ok(resumed.includes('Finish early'));
  assert.doesNotMatch(resumed, /XP|streak|percentage|leaderboard/i);
});

test('feed loads only reserved pages and has no product or synthetic fallback path', async () => {
  const source = await readFile(new URL('./IntentionalBreakFeed.jsx', import.meta.url), 'utf8');
  assert.match(source, /intentionalBreakApi\.getItems\(sessionId/);
  assert.match(source, /limit: INTENTIONAL_BREAK_PAGE_SIZE/);
  assert.match(source, /item\.session_position/);
  assert.doesNotMatch(source, /ReelsPage|researchTracker|researchEvents|feedPagination|excludeIds/);
  assert.doesNotMatch(source, /fallback posts|seedCards|regenerate|refresh feed|all caught up/i);
});

test('pilot feed isolates every product social and navigation feature', async () => {
  const source = await readFile(new URL('./IntentionalBreakFeed.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /ReelActionRail|Comments|Messaging|Share|Save|Challenge|Leaderboard|AppBottomNav|ProfilePanel|useLikedVideos|useSavedVideos/);
  assert.doesNotMatch(source, /post_liked|post_unliked/);
});

test('only the current canonical card mounts a player and unmount cleanup pauses it', async () => {
  const source = await readFile(new URL('./IntentionalBreakFeed.jsx', import.meta.url), 'utf8');
  assert.match(source, /isActive && embedSrc/);
  assert.match(source, /currentPosition === item\.session_position/);
  assert.match(source, /postPlayerCommand\(iframeRef\.current, 'pauseVideo'\)/);
  assert.match(source, /CroppedYouTubePlayer/);
});

test('final impression waits for the event journey and blocks further pagination locally', async () => {
  const source = await readFile(new URL('./IntentionalBreakFeed.jsx', import.meta.url), 'utf8');
  assert.match(source, /item\.session_position !== plannedTotal/);
  assert.match(source, /setBoundaryPending\(true\)/);
  assert.match(source, /onServerJourney\(authoritativeJourney\)/);
  assert.ok(source.includes('Finishing your DayBreak…'));
  assert.doesNotMatch(source, /journey_state:\s*'checkout'|SESSION_FINISHED|boundary endpoint/i);
});

test('finish early remains a confirmed server command with neutral copy', async () => {
  const source = await readFile(new URL('./IntentionalBreakFeed.jsx', import.meta.url), 'utf8');
  assert.ok(source.includes('Finish your session here?'));
  assert.ok(source.includes('It&apos;s okay to stop before that.'));
  assert.ok(source.includes('Finish here'));
  assert.ok(source.includes('Keep scrolling'));
  assert.match(source, /finishEarlyAfterBestEffortFlush\(\{/);
  assert.doesNotMatch(source, /onFinishEarly\(currentPosition\)|current_position|client_current_position/);
  assert.doesNotMatch(source, /addictive|detox|healthy score|mental health improvement|self-control score/i);
});

test('finish early waits for an accepted pending impression before issuing the command', async () => {
  const calls = [];
  const journey = await finishEarlyAfterBestEffortFlush({
    flush: async () => { calls.push('impression-accepted'); },
    onFinishEarly: (...args) => {
      calls.push('finish-early');
      assert.deepEqual(args, []);
      return { journey_state: 'checkout', highest_reached_position: 4 };
    },
  });
  assert.deepEqual(calls, ['impression-accepted', 'finish-early']);
  assert.equal(journey.highest_reached_position, 4);
});

test('finish early remains available after a bounded offline queue flush', async () => {
  let finishCalls = 0;
  const journey = await finishEarlyAfterBestEffortFlush({
    flush: () => new Promise(() => {}),
    onFinishEarly: (...args) => {
      finishCalls += 1;
      assert.deepEqual(args, []);
      return { journey_state: 'checkout', highest_reached_position: 2 };
    },
    timeoutMs: 5,
  });
  assert.equal(finishCalls, 1);
  assert.equal(journey.highest_reached_position, 2);
});

test('initial, later-page, and corrupt-session errors never claim the boundary', async () => {
  const source = await readFile(new URL('./IntentionalBreakFeed.jsx', import.meta.url), 'utf8');
  assert.ok(source.includes("We couldn't load your DayBreak yet."));
  assert.ok(source.includes("We couldn't load the rest of your session."));
  assert.ok(source.includes("We couldn't restore this session safely."));
  assert.doesNotMatch(source, /session complete|all caught up/i);
});
