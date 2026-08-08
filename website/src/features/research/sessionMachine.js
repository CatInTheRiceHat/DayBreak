import {
  ALLOWED_VIDEO_COUNTS,
  COOLDOWN_INCREMENT_SECONDS,
  INTENTIONS,
  LIFECYCLE_STATES,
  MAX_COOLDOWN_SECONDS,
  MIN_COOLDOWN_SECONDS,
  MOOD_VALUES,
  OVERRIDE_REASON_CODES,
  PERCEIVED_CONTROL_VALUES,
  WORTHWHILE_VALUES,
  calculateRecommendedCooldownSeconds,
  estimateDurationSeconds,
  isAllowedVideoCount,
  isValidCheckoutAnswers,
  isValidOverrideReason,
} from './sessionContract.js';

export const SESSION_MACHINE_STAGES = Object.freeze([
  'bootstrapping',
  'notice',
  'planning',
  'planned',
  'active',
  'checkout',
  'cooldown',
  'completed',
  'cancelled',
  'error',
]);

export const SESSION_COMMANDS = Object.freeze([
  'plan',
  'cancel',
  'start',
  'finishEarly',
  'checkout',
  'overrideStart',
  'overrideConfirm',
]);

const SERVER_STAGES = new Set(LIFECYCLE_STATES);

export class SessionMachineError extends Error {
  constructor(message, code = 'invalid_machine_action') {
    super(message);
    this.name = 'SessionMachineError';
    this.code = code;
  }
}

function emptyCommand() {
  return {
    idempotencyKey: null,
    pending: false,
    attempted: false,
    error: null,
  };
}

function initialCommands() {
  return Object.fromEntries(SESSION_COMMANDS.map((name) => [name, emptyCommand()]));
}

function emptyDraft() {
  return {
    intention: null,
    plannedVideoCount: null,
    estimatedDurationSeconds: null,
    recommendedCooldownSeconds: null,
    selectedCooldownSeconds: null,
  };
}

function emptyCheckoutDraft() {
  return {
    worthwhile: null,
    perceivedControl: null,
    mood: null,
  };
}

function emptyOverrideDraft() {
  return { reasonCode: null };
}

export function createInitialSessionState() {
  return {
    stage: 'bootstrapping',
    journey: null,
    draft: emptyDraft(),
    checkoutDraft: emptyCheckoutDraft(),
    overrideDraft: emptyOverrideDraft(),
    cooldown: null,
    serverTimestamp: null,
    ui: {
      currentVisiblePosition: null,
      items: [],
      feedRequestPending: false,
    },
    commands: initialCommands(),
    error: null,
    previousSafeStage: null,
  };
}

export function journeyStage(journey) {
  if (!journey || typeof journey !== 'object' || Array.isArray(journey)) {
    throw new SessionMachineError('A journey snapshot is required.', 'invalid_journey');
  }
  const stage = journey.journey_state;
  if (!SERVER_STAGES.has(stage)) {
    throw new SessionMachineError(
      `Unsupported server journey state: ${String(stage)}`,
      'unknown_lifecycle_state',
    );
  }
  return stage;
}

function cooldownSnapshot(journey) {
  return {
    startedAt: journey.cooldown_started_at ?? null,
    endsAt: journey.cooldown_ends_at ?? null,
    overrideStartedAt: journey.override_started_at ?? null,
    overrideAvailableAt: journey.override_available_at ?? null,
    remainingSeconds: journey.remaining_seconds ?? null,
  };
}

function machineError(error, kind = 'request') {
  const status = Number.isInteger(error?.status) ? error.status : 0;
  const participantCredentialFailure = status === 401 || status === 403;
  return {
    kind,
    status,
    errorCode: error?.errorCode
      ?? error?.error_code
      ?? error?.code
      ?? (participantCredentialFailure ? 'participant_credential_error' : 'unknown_error'),
    message: error?.message ?? 'An unexpected error occurred.',
    retryable: error?.retryable === true
      || status >= 500
      || (status === 0 && error?.name === 'TypeError'),
    details: error?.details ?? null,
    serverTimestamp: error?.serverTimestamp ?? error?.server_timestamp ?? null,
  };
}

function unknownJourneyState(state, error) {
  return {
    ...state,
    stage: 'error',
    error: machineError(error, 'lifecycle'),
    previousSafeStage: state.stage,
    journey: state.journey,
  };
}

function applyJourney(state, journey, { clearCommand = null, serverTimestamp } = {}) {
  if (journey === null) {
    return {
      ...state,
      stage: 'notice',
      journey: null,
      draft: emptyDraft(),
      checkoutDraft: emptyCheckoutDraft(),
      overrideDraft: emptyOverrideDraft(),
      cooldown: null,
      serverTimestamp: serverTimestamp ?? null,
      commands: initialCommands(),
      error: null,
      previousSafeStage: null,
    };
  }

  let stage;
  try {
    stage = journeyStage(journey);
  } catch (error) {
    return unknownJourneyState(state, error);
  }

  return {
    ...state,
    stage,
    journey: { ...journey },
    draft: null,
    checkoutDraft: stage === 'checkout' ? state.checkoutDraft : emptyCheckoutDraft(),
    overrideDraft: stage === 'cooldown' ? state.overrideDraft : emptyOverrideDraft(),
    cooldown: stage === 'cooldown' || stage === 'completed'
      ? cooldownSnapshot(journey)
      : null,
    serverTimestamp: serverTimestamp ?? state.serverTimestamp,
    commands: clearCommand
      ? { ...state.commands, [clearCommand]: emptyCommand() }
      : state.commands,
    error: null,
    previousSafeStage: null,
  };
}

function requireStage(state, allowedStages, actionType) {
  if (!allowedStages.includes(state.stage)) {
    throw new SessionMachineError(
      `${actionType} is not supported from ${state.stage}.`,
      'unsupported_stage_action',
    );
  }
}

function requireIdempotencyKey(action) {
  if (typeof action.idempotencyKey !== 'string' || !action.idempotencyKey) {
    throw new SessionMachineError(
      'An externally generated idempotency key is required.',
      'idempotency_key_required',
    );
  }
}

function beginCommand(state, commandName, action, allowedStages) {
  requireStage(state, allowedStages, action.type);
  requireIdempotencyKey(action);
  const current = state.commands[commandName];
  if (current.attempted && current.idempotencyKey !== action.idempotencyKey) {
    throw new SessionMachineError(
      `A retry of ${commandName} must reuse its idempotency key.`,
      'idempotency_key_changed',
    );
  }
  return {
    ...state,
    commands: {
      ...state.commands,
      [commandName]: {
        idempotencyKey: current.idempotencyKey ?? action.idempotencyKey,
        pending: true,
        attempted: true,
        error: null,
      },
    },
    error: null,
    previousSafeStage: null,
  };
}

function failCommand(state, commandName, action) {
  const error = machineError(action.error);
  return {
    ...state,
    commands: {
      ...state.commands,
      [commandName]: {
        ...state.commands[commandName],
        pending: false,
        attempted: true,
        error,
      },
    },
    error,
    serverTimestamp: error.serverTimestamp ?? state.serverTimestamp,
    previousSafeStage: state.stage,
  };
}

function validatePlanningDraft(draft) {
  if (!INTENTIONS.includes(draft?.intention)) {
    throw new SessionMachineError('A valid intention is required.', 'invalid_intention');
  }
  if (!isAllowedVideoCount(draft?.plannedVideoCount)) {
    throw new SessionMachineError('A valid planned video count is required.', 'invalid_video_count');
  }
  const cooldown = draft?.selectedCooldownSeconds;
  if (!Number.isInteger(cooldown)
    || cooldown < MIN_COOLDOWN_SECONDS
    || cooldown > MAX_COOLDOWN_SECONDS
    || cooldown % COOLDOWN_INCREMENT_SECONDS !== 0) {
    throw new SessionMachineError('A valid selected cooldown is required.', 'invalid_cooldown');
  }
}

export function isPlanningDraftComplete(draft) {
  try {
    validatePlanningDraft(draft);
    return true;
  } catch {
    return false;
  }
}

export function suggestLowerVideoCount(availableCount, requestedCount) {
  if (!Number.isInteger(availableCount) || !Number.isInteger(requestedCount)) return null;
  return ALLOWED_VIDEO_COUNTS
    .filter((count) => count < requestedCount && count <= availableCount)
    .at(-1) ?? null;
}

function updatePlanningDraft(state, draft) {
  return {
    ...state,
    draft,
    commands: {
      ...state.commands,
      plan: emptyCommand(),
    },
    error: null,
    previousSafeStage: null,
  };
}

function setIntention(state, intention) {
  requireStage(state, ['planning'], 'SET_INTENTION');
  if (!INTENTIONS.includes(intention)) {
    throw new SessionMachineError(`Unsupported intention: ${String(intention)}`, 'invalid_intention');
  }
  return updatePlanningDraft(state, { ...state.draft, intention });
}

function setVideoCount(state, plannedVideoCount) {
  requireStage(state, ['planning'], 'SET_VIDEO_COUNT');
  if (!ALLOWED_VIDEO_COUNTS.includes(plannedVideoCount)) {
    throw new SessionMachineError(
      `Unsupported planned video count: ${String(plannedVideoCount)}`,
      'invalid_video_count',
    );
  }
  const estimatedDurationSeconds = estimateDurationSeconds(plannedVideoCount);
  const recommendedCooldownSeconds = calculateRecommendedCooldownSeconds(
    estimatedDurationSeconds,
  );
  return updatePlanningDraft(
    state,
    {
      ...state.draft,
      plannedVideoCount,
      estimatedDurationSeconds,
      recommendedCooldownSeconds,
      selectedCooldownSeconds: recommendedCooldownSeconds,
    },
  );
}

function setSelectedCooldown(state, selectedCooldownSeconds) {
  requireStage(state, ['planning'], 'SET_SELECTED_COOLDOWN');
  if (!Number.isInteger(selectedCooldownSeconds)
    || selectedCooldownSeconds < MIN_COOLDOWN_SECONDS
    || selectedCooldownSeconds > MAX_COOLDOWN_SECONDS
    || selectedCooldownSeconds % COOLDOWN_INCREMENT_SECONDS !== 0) {
    throw new SessionMachineError(
      `Unsupported selected cooldown: ${String(selectedCooldownSeconds)}`,
      'invalid_cooldown',
    );
  }
  return updatePlanningDraft(state, { ...state.draft, selectedCooldownSeconds });
}

function editCancelledPlan(state, draft) {
  requireStage(state, ['cancelled'], 'EDIT_CANCELLED_PLAN');
  validatePlanningDraft(draft);
  return {
    ...state,
    stage: 'planning',
    journey: null,
    draft: { ...draft },
    checkoutDraft: emptyCheckoutDraft(),
    overrideDraft: emptyOverrideDraft(),
    cooldown: null,
    commands: initialCommands(),
    error: null,
    previousSafeStage: null,
  };
}

function setCheckoutAnswer(state, field, value) {
  requireStage(state, ['checkout'], 'SET_CHECKOUT_ANSWER');
  if (state.commands.checkout.pending) {
    throw new SessionMachineError('Checkout answers cannot change while submitting.', 'command_pending');
  }
  const allowed = {
    worthwhile: WORTHWHILE_VALUES,
    perceivedControl: PERCEIVED_CONTROL_VALUES,
    mood: MOOD_VALUES,
  }[field];
  if (!allowed?.includes(value)) {
    throw new SessionMachineError('Unsupported checkout answer.', 'invalid_checkout_answer');
  }
  return {
    ...state,
    checkoutDraft: { ...state.checkoutDraft, [field]: value },
    commands: { ...state.commands, checkout: emptyCommand() },
    error: null,
    previousSafeStage: null,
  };
}

function setOverrideReason(state, reasonCode) {
  requireStage(state, ['cooldown'], 'SET_OVERRIDE_REASON');
  if (state.commands.overrideConfirm.pending) {
    throw new SessionMachineError('Override reason cannot change while submitting.', 'command_pending');
  }
  if (!OVERRIDE_REASON_CODES.includes(reasonCode)) {
    throw new SessionMachineError('Unsupported override reason.', 'invalid_override_reason');
  }
  return {
    ...state,
    overrideDraft: { reasonCode },
    commands: { ...state.commands, overrideConfirm: emptyCommand() },
    error: null,
    previousSafeStage: null,
  };
}

const COMMAND_ACTIONS = Object.freeze({
  PLAN_CANCEL_STARTED: ['cancel', ['planned']],
  SESSION_START_STARTED: ['start', ['planned']],
  FINISH_EARLY_STARTED: ['finishEarly', ['active']],
  OVERRIDE_START_STARTED: ['overrideStart', ['cooldown']],
});

const COMMAND_FAILURES = Object.freeze({
  PLAN_CANCEL_FAILED: 'cancel',
  SESSION_START_FAILED: 'start',
  FINISH_EARLY_FAILED: 'finishEarly',
  CHECKOUT_SUBMIT_FAILED: 'checkout',
  OVERRIDE_START_FAILED: 'overrideStart',
  OVERRIDE_CONFIRM_FAILED: 'overrideConfirm',
});

const COMMAND_SUCCESSES = Object.freeze({
  PLAN_CANCELLED: 'cancel',
  SESSION_STARTED: 'start',
  FINISH_EARLY_SUCCEEDED: 'finishEarly',
  CHECKOUT_SUBMITTED: 'checkout',
  OVERRIDE_STARTED: 'overrideStart',
  OVERRIDE_CONFIRMED: 'overrideConfirm',
});

export function sessionMachineReducer(state, action) {
  switch (action.type) {
    case 'BOOTSTRAP_STARTED':
      return createInitialSessionState();
    case 'BOOTSTRAP_SUCCEEDED':
    case 'SERVER_JOURNEY_RECEIVED':
      return applyJourney(state, action.journey ?? null, {
        serverTimestamp: action.serverTimestamp,
      });
    case 'BOOTSTRAP_FAILED':
      return {
        ...state,
        stage: 'error',
        error: machineError(action.error, 'bootstrap'),
        previousSafeStage: 'bootstrapping',
      };
    case 'NOTICE_ACKNOWLEDGED':
      requireStage(state, ['notice'], action.type);
      return {
        ...state,
        stage: 'planning',
        draft: emptyDraft(),
        error: null,
        previousSafeStage: null,
      };
    case 'RETURN_TO_NOTICE':
      requireStage(state, ['completed', 'cancelled'], action.type);
      return applyJourney(state, null);
    case 'EDIT_CANCELLED_PLAN':
      return editCancelledPlan(state, action.draft);
    case 'SET_INTENTION':
      return setIntention(state, action.intention);
    case 'SET_VIDEO_COUNT':
      return setVideoCount(state, action.plannedVideoCount);
    case 'SET_SELECTED_COOLDOWN':
      return setSelectedCooldown(state, action.selectedCooldownSeconds);
    case 'SET_CHECKOUT_ANSWER':
      return setCheckoutAnswer(state, action.field, action.value);
    case 'SET_OVERRIDE_REASON':
      return setOverrideReason(state, action.reasonCode);
    case 'PLAN_SUBMIT_STARTED':
      validatePlanningDraft(state.draft);
      return beginCommand(state, 'plan', action, ['planning']);
    case 'PLAN_CREATED':
      return applyJourney(state, action.journey, {
        clearCommand: 'plan',
        serverTimestamp: action.serverTimestamp,
      });
    case 'PLAN_SUBMIT_FAILED':
      return failCommand(state, 'plan', action);
    case 'CHECKOUT_SUBMIT_STARTED':
      if (!isValidCheckoutAnswers(state.checkoutDraft)) {
        throw new SessionMachineError(
          'All checkout answers are required.',
          'invalid_checkout_answers',
        );
      }
      return beginCommand(state, 'checkout', action, ['checkout']);
    case 'OVERRIDE_CONFIRM_STARTED':
      if (!isValidOverrideReason(state.overrideDraft.reasonCode)) {
        throw new SessionMachineError(
          'A valid override reason is required.',
          'invalid_override_reason',
        );
      }
      return beginCommand(state, 'overrideConfirm', action, ['cooldown']);
    case 'REQUEST_FAILED': {
      const error = machineError(action.error);
      return {
        ...state,
        error,
        serverTimestamp: error.serverTimestamp ?? state.serverTimestamp,
        previousSafeStage: state.stage,
      };
    }
    case 'CLEAR_REQUEST_ERROR':
      return { ...state, error: null, previousSafeStage: null };
    default:
      break;
  }

  if (COMMAND_ACTIONS[action.type]) {
    const [commandName, stages] = COMMAND_ACTIONS[action.type];
    return beginCommand(state, commandName, action, stages);
  }
  if (COMMAND_FAILURES[action.type]) {
    return failCommand(state, COMMAND_FAILURES[action.type], action);
  }
  if (COMMAND_SUCCESSES[action.type]) {
    return applyJourney(state, action.journey, {
      clearCommand: COMMAND_SUCCESSES[action.type],
      serverTimestamp: action.serverTimestamp,
    });
  }
  return state;
}
