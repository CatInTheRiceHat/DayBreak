export const RESEARCH_VISIBILITY_RATIO = 0.6;
export const IMPRESSION_DURATION_MS = 1_000;
export const VIEWED_DURATION_MS = 3_000;

/**
 * Small, React-independent state machine for continuous meaningful visibility.
 * Timers reset whenever the page is hidden or less than 60% of a card is visible.
 */
export function createMeaningfulVisibilityTracker({
  onImpression,
  onViewed,
  setTimer = setTimeout,
  clearTimer = clearTimeout,
} = {}) {
  let ratio = 0;
  let intersecting = false;
  let pageVisible = true;
  let impressionTimer = null;
  let viewedTimer = null;
  let impressed = false;
  let viewed = false;

  function clearPending() {
    if (impressionTimer) clearTimer(impressionTimer);
    if (viewedTimer) clearTimer(viewedTimer);
    impressionTimer = null;
    viewedTimer = null;
  }

  function qualifies() {
    return pageVisible && intersecting && ratio >= RESEARCH_VISIBILITY_RATIO;
  }

  function schedule() {
    clearPending();
    if (!qualifies()) return;
    if (!impressed) {
      impressionTimer = setTimer(() => {
        impressionTimer = null;
        if (!qualifies() || impressed) return;
        impressed = true;
        onImpression?.({ visibilityRatio: ratio, visibleMs: IMPRESSION_DURATION_MS });
      }, IMPRESSION_DURATION_MS);
    }
    if (!viewed) {
      viewedTimer = setTimer(() => {
        viewedTimer = null;
        if (!qualifies() || viewed) return;
        viewed = true;
        onViewed?.({ visibilityRatio: ratio, visibleMs: VIEWED_DURATION_MS });
      }, VIEWED_DURATION_MS);
    }
  }

  return {
    update(next) {
      ratio = Number(next.ratio || 0);
      intersecting = Boolean(next.isIntersecting);
      schedule();
    },
    setPageVisible(visible) {
      pageVisible = Boolean(visible);
      schedule();
    },
    disconnect: clearPending,
  };
}
