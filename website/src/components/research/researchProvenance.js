const PROVENANCE_FIELDS = [
  'feed_request_id',
  'feed_position',
  'feed_policy_version',
  'selection_bucket',
  'selection_reason',
];

export function researchProvenanceFromFeedItem(item = {}) {
  return {
    feed_request_id: item.feed_request_id || null,
    feed_position: Number.isInteger(item.feed_position) ? item.feed_position : null,
    feed_policy_version: item.feed_policy_version || null,
    selection_bucket: item.selection_bucket || null,
    selection_reason: item.selection_reason || null,
  };
}

export function researchProvenanceMetadata(item = {}) {
  return Object.fromEntries(PROVENANCE_FIELDS.map((field) => [field, item[field] ?? null]));
}

export function buildResearchExposureFields({
  postId,
  contentCategory,
  position,
  sourceType,
  provenance,
  visibilityRatio,
  visibleMs,
}) {
  return {
    postId: String(postId),
    contentCategory: contentCategory || 'unknown',
    metadata: {
      position,
      visibility_ratio: Number(visibilityRatio.toFixed(3)),
      visible_ms: visibleMs,
      source_type: sourceType || 'unknown',
      ...researchProvenanceMetadata(provenance),
    },
  };
}
