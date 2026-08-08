import { useCallback, useEffect, useRef, useState } from 'react';
import * as intentionalBreakApi from '../../lib/intentionalBreakApi.js';
import {
  createMeaningfulVisibilityTracker,
  RESEARCH_VISIBILITY_RATIO,
} from './meaningfulVisibility.js';
import {
  createIntentionalBreakEventQueue,
  readIntentionalBreakQueueSnapshot,
} from './intentionalBreakEventQueue.js';

export function useIntentionalBreakEvents({ sessionId, onJourney }) {
  const queueRef = useRef(null);
  const [initialSnapshot] = useState(() => readIntentionalBreakQueueSnapshot(sessionId));
  const initialPending = initialSnapshot.pending.length > 0;
  const [queueStatus, setQueueStatus] = useState({
    ready: false,
    reconciling: initialPending,
    pendingCount: initialSnapshot.pending.length,
    terminal: [],
  });

  useEffect(() => {
    let recovering = initialPending;
    const queue = createIntentionalBreakEventQueue({
      sessionId,
      send: (events) => intentionalBreakApi.appendEvents(sessionId, events),
      onJourney: (journey, event, response) => {
        onJourney?.(journey, event, response);
      },
      onStatus: (snapshot) => {
        if (recovering && snapshot.pending.length === 0) recovering = false;
        setQueueStatus({
          ready: true,
          reconciling: recovering,
          pendingCount: snapshot.pending.length,
          terminal: snapshot.terminal,
        });
      },
    });
    queueRef.current = queue;
    const flush = () => queue.flush();
    const onVisibility = () => {
      if (document.visibilityState === 'visible') flush();
    };
    window.addEventListener('online', flush);
    window.addEventListener('focus', flush);
    document.addEventListener('visibilitychange', onVisibility);
    queue.flush();
    return () => {
      window.removeEventListener('online', flush);
      window.removeEventListener('focus', flush);
      document.removeEventListener('visibilitychange', onVisibility);
      queue.destroy();
      if (queueRef.current === queue) queueRef.current = null;
    };
  }, [initialPending, onJourney, sessionId]);

  const enqueue = useCallback((event) => queueRef.current?.enqueue(event) ?? {
    enqueued: false,
    status: 'queue_not_ready',
  }, []);

  const flush = useCallback(() => queueRef.current?.flush(), []);

  return { enqueue, flush, queueStatus };
}

export function useIntentionalBreakItemVisibility({
  enabled,
  item,
  enqueue,
  onCurrent,
  onMeaningfulImpression,
}) {
  const elementRef = useRef(null);

  useEffect(() => {
    const element = elementRef.current;
    if (!enabled || !element || !item?.post_id || typeof IntersectionObserver === 'undefined') {
      return undefined;
    }
    const queueExposure = (eventType, details) => enqueue({
      eventType,
      postId: item.post_id,
      sessionPosition: item.session_position,
      onceKey: `${eventType}:${item.post_id}`,
      metadata: {
        visibility_ratio: details.visibilityRatio,
        visible_ms: details.visibleMs,
      },
    });
    const tracker = createMeaningfulVisibilityTracker({
      onImpression: (details) => {
        const result = queueExposure('post_impression', details);
        onMeaningfulImpression?.(item, result);
      },
      onViewed: (details) => queueExposure('post_viewed', details),
    });
    const observer = new IntersectionObserver(
      ([entry]) => {
        tracker.update({
          isIntersecting: entry.isIntersecting,
          ratio: entry.intersectionRatio,
        });
        if (entry.isIntersecting && entry.intersectionRatio >= RESEARCH_VISIBILITY_RATIO) {
          onCurrent?.(item.session_position);
        }
      },
      { threshold: [0, RESEARCH_VISIBILITY_RATIO, 1] },
    );
    const handleVisibility = () => tracker.setPageVisible(document.visibilityState === 'visible');
    observer.observe(element);
    document.addEventListener('visibilitychange', handleVisibility);
    handleVisibility();
    return () => {
      observer.disconnect();
      tracker.disconnect();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [enabled, enqueue, item, onCurrent, onMeaningfulImpression]);

  return elementRef;
}
