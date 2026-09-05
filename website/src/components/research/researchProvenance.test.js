import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildResearchExposureFields,
  researchProvenanceFromFeedItem,
} from './researchProvenance.js';
import {
  RESEARCH_PARTICIPANT_COPY,
  researchRecommendationSummary,
} from './researchParticipantCopy.js';

test('server-provided feed provenance is preserved for rendered cards', () => {
  const source = {
    feed_request_id: 'request-1',
    feed_position: 4,
    feed_policy_version: 'balanced-v1',
    selection_bucket: 'healthy',
    selection_reason: 'healthy_category_target',
  };
  assert.deepEqual(researchProvenanceFromFeedItem(source), source);
});

test('impression and viewed field builders attach feed provenance unchanged', () => {
  const provenance = {
    feed_request_id: 'request-2',
    feed_position: 3,
    feed_policy_version: 'regular-v1',
    selection_bucket: 'normal',
    selection_reason: 'existing_chrysalis_rank',
  };
  const fields = buildResearchExposureFields({
    postId: 'post-9',
    contentCategory: 'regular',
    position: 8,
    sourceType: 'search',
    provenance,
    visibilityRatio: 0.73333,
    visibleMs: 3_000,
  });

  assert.equal(fields.postId, 'post-9');
  assert.equal(fields.metadata.visibility_ratio, 0.733);
  assert.equal(fields.metadata.visible_ms, 3_000);
  for (const [key, value] of Object.entries(provenance)) {
    assert.equal(fields.metadata[key], value);
  }
});

test('research participant copy does not name experimental conditions', () => {
  const text = [
    ...Object.values(RESEARCH_PARTICIPANT_COPY),
    ...['healthy', 'positive', 'regular', 'perspective', 'reduced', 'unknown']
      .map(researchRecommendationSummary),
  ].join(' ');

  assert.doesNotMatch(text, /\b(regular|balanced|control)\b/i);
  assert.doesNotMatch(text, /healthy-feed condition/i);
});
