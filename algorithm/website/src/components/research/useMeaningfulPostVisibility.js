import { useEffect, useRef } from 'react';
import {
  createMeaningfulVisibilityTracker,
  RESEARCH_VISIBILITY_RATIO,
} from './meaningfulVisibility';
import { buildResearchExposureFields } from './researchProvenance';

export function useMeaningfulPostVisibility({
  enabled,
  postId,
  contentCategory,
  position,
  sourceType,
  researchTracker,
  provenance = {},
}) {
  const elementRef = useRef(null);
  const feedRequestId = provenance.feed_request_id;
  const feedPosition = provenance.feed_position;
  const feedPolicyVersion = provenance.feed_policy_version;
  const selectionBucket = provenance.selection_bucket;
  const selectionReason = provenance.selection_reason;

  useEffect(() => {
    const element = elementRef.current;
    if (!enabled || !element || !postId || !researchTracker || typeof IntersectionObserver === 'undefined') {
      return undefined;
    }

    const fields = (details) => buildResearchExposureFields({
      postId,
      contentCategory,
      position,
      sourceType,
      provenance: {
        feed_request_id: feedRequestId,
        feed_position: feedPosition,
        feed_policy_version: feedPolicyVersion,
        selection_bucket: selectionBucket,
        selection_reason: selectionReason,
      },
      visibilityRatio: details.visibilityRatio,
      visibleMs: details.visibleMs,
    });
    const tracker = createMeaningfulVisibilityTracker({
      onImpression: (details) => {
        researchTracker.track(
          'post_impression',
          fields(details),
          { onceKey: `post_impression:${postId}` },
        ).catch(() => {});
      },
      onViewed: (details) => {
        researchTracker.track(
          'post_viewed',
          fields(details),
          { onceKey: `post_viewed:${postId}` },
        ).catch(() => {});
      },
    });
    const observer = new IntersectionObserver(
      ([entry]) => tracker.update({
        isIntersecting: entry.isIntersecting,
        ratio: entry.intersectionRatio,
      }),
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
  }, [
    enabled,
    postId,
    contentCategory,
    position,
    sourceType,
    researchTracker,
    feedRequestId,
    feedPosition,
    feedPolicyVersion,
    selectionBucket,
    selectionReason,
  ]);

  return elementRef;
}
