import assert from 'node:assert/strict';
import test from 'node:test';
import {
  createMeaningfulVisibilityTracker,
  IMPRESSION_DURATION_MS,
  VIEWED_DURATION_MS,
} from './meaningfulVisibility.js';

function fakeClock() {
  let time = 0;
  let nextId = 1;
  const timers = new Map();
  return {
    setTimer(callback, delay) {
      const id = nextId++;
      timers.set(id, { callback, at: time + delay });
      return id;
    },
    clearTimer(id) {
      timers.delete(id);
    },
    advance(ms) {
      const target = time + ms;
      while (true) {
        const due = [...timers.entries()]
          .filter(([, timer]) => timer.at <= target)
          .sort((a, b) => a[1].at - b[1].at)[0];
        if (!due) break;
        const [id, timer] = due;
        timers.delete(id);
        time = timer.at;
        timer.callback();
      }
      time = target;
    },
  };
}

test('does not log an impression until 60% visibility is continuous for one second', () => {
  const clock = fakeClock();
  const events = [];
  const tracker = createMeaningfulVisibilityTracker({
    setTimer: clock.setTimer,
    clearTimer: clock.clearTimer,
    onImpression: (event) => events.push(['impression', event]),
    onViewed: (event) => events.push(['viewed', event]),
  });

  tracker.update({ isIntersecting: true, ratio: 0.59 });
  clock.advance(5_000);
  assert.deepEqual(events, []);

  tracker.update({ isIntersecting: true, ratio: 0.6 });
  clock.advance(IMPRESSION_DURATION_MS - 1);
  assert.deepEqual(events, []);
  clock.advance(1);
  assert.equal(events[0][0], 'impression');
  assert.equal(events[0][1].visibleMs, 1_000);

  clock.advance(VIEWED_DURATION_MS - IMPRESSION_DURATION_MS);
  assert.equal(events[1][0], 'viewed');
  assert.equal(events[1][1].visibleMs, 3_000);
});

test('visibility timers reset when the card or page stops qualifying', () => {
  const clock = fakeClock();
  let impressions = 0;
  const tracker = createMeaningfulVisibilityTracker({
    setTimer: clock.setTimer,
    clearTimer: clock.clearTimer,
    onImpression: () => { impressions += 1; },
  });

  tracker.update({ isIntersecting: true, ratio: 0.8 });
  clock.advance(700);
  tracker.update({ isIntersecting: false, ratio: 0 });
  clock.advance(1_000);
  assert.equal(impressions, 0);

  tracker.update({ isIntersecting: true, ratio: 0.8 });
  clock.advance(500);
  tracker.setPageVisible(false);
  clock.advance(1_000);
  assert.equal(impressions, 0);

  tracker.setPageVisible(true);
  clock.advance(1_000);
  assert.equal(impressions, 1);
});
