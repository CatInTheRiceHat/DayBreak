export const RESEARCH_PARTICIPANT_COPY = Object.freeze({
  modeDescription: 'A varied short-form video feed for this test session.',
  modeLede: 'The ordering is fixed by the test session while the interface stays the same.',
  poolDescription: 'The feed includes several kinds of videos from the available content pool.',
  fixedOrdering: 'Content ordering is fixed for this test session.',
  genericRecommendation: 'A varied video from the available feed.',
});

export function researchRecommendationSummary(category) {
  if (category === 'perspective') return 'A perspective video included for variety.';
  if (category === 'healthy' || category === 'positive') {
    return 'A constructive video from the available feed.';
  }
  if (category === 'reduced') return 'A lower-priority video from the available feed.';
  return 'A general-interest video from the available feed.';
}
