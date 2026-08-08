export const LIFECYCLE_STATES = Object.freeze([
  'planned',
  'active',
  'checkout',
  'cooldown',
  'completed',
  'cancelled',
]);

export const NONTERMINAL_STATES = Object.freeze([
  'planned',
  'active',
  'checkout',
  'cooldown',
]);

export const VALID_TRANSITIONS = Object.freeze([
  Object.freeze({ from: null, to: 'planned' }),
  Object.freeze({ from: 'planned', to: 'active' }),
  Object.freeze({ from: 'planned', to: 'cancelled' }),
  Object.freeze({ from: 'active', to: 'checkout', reason: 'boundary_reached' }),
  Object.freeze({ from: 'active', to: 'checkout', reason: 'finished_early' }),
  Object.freeze({ from: 'checkout', to: 'cooldown' }),
  Object.freeze({ from: 'cooldown', to: 'completed', outcome: 'completed' }),
  Object.freeze({ from: 'cooldown', to: 'completed', outcome: 'overridden' }),
]);

export const INTENTIONS = Object.freeze([
  'relax',
  'learn',
  'inspired',
  'catch_up',
  'quick_break',
]);

export const ALLOWED_VIDEO_COUNTS = Object.freeze([5, 10, 20, 40]);

export const WORTHWHILE_VALUES = Object.freeze([
  'yes',
  'mostly',
  'not_really',
  'prefer_not_to_answer',
]);

export const PERCEIVED_CONTROL_VALUES = Object.freeze([
  1,
  2,
  3,
  4,
  5,
  'prefer_not_to_answer',
]);

export const MOOD_VALUES = Object.freeze([
  'better',
  'same',
  'worse',
  'prefer_not_to_answer',
]);

export const CHECKOUT_VALUES = Object.freeze({
  worthwhile: WORTHWHILE_VALUES,
  perceivedControl: PERCEIVED_CONTROL_VALUES,
  mood: MOOD_VALUES,
});

export const OVERRIDE_REASON_CODES = Object.freeze([
  'change_plan',
  'opened_automatically',
  'want_another_session',
  'other',
]);

export const SESSION_CONDITION = 'intentional_break_v1';
export const FEED_POLICY = 'balanced-v1';
export const FIXED_FEED_POLICY = Object.freeze({
  sessionCondition: SESSION_CONDITION,
  feedPolicy: FEED_POLICY,
});

export const SECONDS_PER_ESTIMATED_VIDEO = 30;
export const COOLDOWN_MULTIPLIER = 2;
export const COOLDOWN_INCREMENT_SECONDS = 300;
export const MIN_COOLDOWN_SECONDS = 300;
export const MAX_COOLDOWN_SECONDS = 7_200;
export const OVERRIDE_PAUSE_SECONDS = 15;

export function isAllowedVideoCount(videoCount) {
  return ALLOWED_VIDEO_COUNTS.includes(videoCount);
}

export function estimateDurationSeconds(plannedVideoCount) {
  if (!isAllowedVideoCount(plannedVideoCount)) {
    throw new RangeError(`Unsupported planned video count: ${plannedVideoCount}`);
  }
  return plannedVideoCount * SECONDS_PER_ESTIMATED_VIDEO;
}

export function calculateRecommendedCooldownSeconds(estimatedDurationSeconds) {
  if (!Number.isFinite(estimatedDurationSeconds) || estimatedDurationSeconds < 0) {
    throw new RangeError('Estimated duration must be a finite, non-negative number');
  }

  const unboundedRecommendation = estimatedDurationSeconds * COOLDOWN_MULTIPLIER;
  const roundedRecommendation = Math.ceil(
    unboundedRecommendation / COOLDOWN_INCREMENT_SECONDS,
  ) * COOLDOWN_INCREMENT_SECONDS;

  return Math.min(
    MAX_COOLDOWN_SECONDS,
    Math.max(MIN_COOLDOWN_SECONDS, roundedRecommendation),
  );
}

export function isValidLifecycleTransition(from, to, details = {}) {
  return VALID_TRANSITIONS.some((transition) => (
    transition.from === from
    && transition.to === to
    && (!Object.hasOwn(transition, 'reason') || transition.reason === details.reason)
    && (!Object.hasOwn(transition, 'outcome') || transition.outcome === details.outcome)
  ));
}

export function isValidCheckoutAnswers(answers) {
  if (answers === null || typeof answers !== 'object' || Array.isArray(answers)) {
    return false;
  }

  return WORTHWHILE_VALUES.includes(answers.worthwhile)
    && PERCEIVED_CONTROL_VALUES.includes(answers.perceivedControl)
    && MOOD_VALUES.includes(answers.mood);
}

export function isValidOverrideReason(reasonCode) {
  return OVERRIDE_REASON_CODES.includes(reasonCode);
}

export function isNonterminalState(state) {
  return NONTERMINAL_STATES.includes(state);
}
