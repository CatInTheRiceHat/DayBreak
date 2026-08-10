import { LIFECYCLE_STATES } from '../features/research/sessionContract.js';
import { ensureResearchParticipant } from './researchParticipant.js';

export const INTENTIONAL_BREAK_CONTRACT_VERSION = 'intentional-break-v1';
const API_PATH = '/api/research/intentional-break/v1';
const JOURNEY_STATES = new Set(LIFECYCLE_STATES);
const CLIENT_METADATA_FIELDS = Object.freeze([
  'visibility_ratio',
  'visible_ms',
  'reason_code',
  'threshold_min',
  'break_min',
  'interaction_source',
  'impression_event_id',
]);

function redactString(value, secrets) {
  let result = value;
  for (const secret of secrets) {
    if (secret) result = result.split(secret).join('[redacted]');
  }
  return result;
}

function redactValue(value, secrets) {
  if (typeof value === 'string') return redactString(value, secrets);
  if (Array.isArray(value)) return value.map((item) => redactValue(item, secrets));
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, redactValue(item, secrets)]),
    );
  }
  return value;
}

export class IntentionalBreakApiError extends Error {
  constructor({
    status = 0,
    errorCode,
    message,
    retryable = false,
    details = null,
    serverTimestamp = null,
  }) {
    super(message);
    this.name = 'IntentionalBreakApiError';
    this.status = status;
    this.errorCode = errorCode;
    this.retryable = retryable;
    this.details = details;
    this.serverTimestamp = serverTimestamp;
  }
}

function invalidResponse(status, message) {
  return new IntentionalBreakApiError({
    status,
    errorCode: 'invalid_response',
    message,
    retryable: status >= 500,
  });
}

export function normalizeIntentionalBreakJourney(journey) {
  if (journey === null) return null;
  if (!journey || typeof journey !== 'object' || Array.isArray(journey)) {
    throw invalidResponse(0, 'Intentional Break API returned an invalid journey.');
  }
  if (!JOURNEY_STATES.has(journey.journey_state)) {
    throw invalidResponse(0, 'Intentional Break API returned an unknown journey state.');
  }
  return { ...journey };
}

function normalizeSuccess(body, status) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    throw invalidResponse(status, 'Intentional Break API returned a non-object response.');
  }
  if (body.ok !== true) {
    throw invalidResponse(status, 'Intentional Break API returned an invalid success envelope.');
  }
  if (body.contract_version !== INTENTIONAL_BREAK_CONTRACT_VERSION) {
    throw invalidResponse(status, 'Intentional Break API contract version is not supported.');
  }
  if (!Object.hasOwn(body, 'data') || !body.data || typeof body.data !== 'object'
    || Array.isArray(body.data)) {
    throw invalidResponse(status, 'Intentional Break API response is missing data.');
  }

  const data = { ...body.data };
  if (Object.hasOwn(data, 'journey')) {
    data.journey = normalizeIntentionalBreakJourney(data.journey);
  }
  return {
    ...data,
    serverTimestamp: body.server_timestamp ?? null,
    contractVersion: body.contract_version,
  };
}

function normalizeApiError(body, status, accessToken) {
  const secrets = [accessToken];
  const validEnvelope = body && typeof body === 'object' && !Array.isArray(body)
    && body.ok === false
    && body.contract_version === INTENTIONAL_BREAK_CONTRACT_VERSION;
  if (!validEnvelope) {
    return invalidResponse(status, `Intentional Break API request failed (${status}).`);
  }
  return new IntentionalBreakApiError({
    status,
    errorCode: body.error_code || 'api_error',
    message: redactString(
      typeof body.message === 'string'
        ? body.message
        : `Intentional Break API request failed (${status}).`,
      secrets,
    ),
    retryable: body.retryable === true,
    details: redactValue(body.details ?? null, secrets),
    serverTimestamp: body.server_timestamp ?? null,
  });
}

function idempotencyBody(idempotencyKey) {
  return { idempotency_key: idempotencyKey };
}

function sanitizeEvent(event) {
  const suppliedMetadata = event.metadata && typeof event.metadata === 'object'
    && !Array.isArray(event.metadata)
    ? event.metadata
    : {};
  const metadata = Object.fromEntries(
    CLIENT_METADATA_FIELDS
      .filter((field) => suppliedMetadata[field] !== undefined)
      .map((field) => [field, suppliedMetadata[field]]),
  );
  const result = {
    client_event_id: event.client_event_id ?? event.clientEventId,
    event_type: event.event_type ?? event.eventType,
    client_timestamp: event.client_timestamp ?? event.clientTimestamp,
    metadata,
  };
  const sequence = event.client_sequence_number ?? event.clientSequenceNumber;
  const postId = event.post_id ?? event.postId;
  if (sequence !== undefined) result.client_sequence_number = sequence;
  if (postId !== undefined) result.post_id = postId;
  return result;
}

export function createIdempotencyKey(cryptoImpl = globalThis.crypto) {
  if (typeof cryptoImpl?.randomUUID === 'function') return cryptoImpl.randomUUID();
  if (typeof cryptoImpl?.getRandomValues !== 'function') {
    throw new Error('Secure UUID generation is unavailable in this browser.');
  }
  const bytes = cryptoImpl.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, '0'));
  return [
    hex.slice(0, 4).join(''),
    hex.slice(4, 6).join(''),
    hex.slice(6, 8).join(''),
    hex.slice(8, 10).join(''),
    hex.slice(10).join(''),
  ].join('-');
}

export function createIntentionalBreakApiClient({
  apiUrl = '',
  fetchImpl = globalThis.fetch?.bind(globalThis),
  localStorage = globalThis.localStorage,
  participantProvider = ensureResearchParticipant,
} = {}) {
  if (!fetchImpl) throw new Error('Fetch is unavailable.');

  async function request(path, { method = 'GET', body } = {}) {
    let participant;
    try {
      participant = await participantProvider({ apiUrl, fetchImpl, localStorage });
    } catch (error) {
      if (error instanceof IntentionalBreakApiError) throw error;
      const status = Number.isInteger(error?.status) ? error.status : 0;
      throw new IntentionalBreakApiError({
        status,
        errorCode: status ? 'participant_credential_error' : 'network_error',
        message: status
          ? 'Unable to initialize the research participant credential.'
          : 'Unable to reach the research participant API.',
        retryable: status === 0 || status >= 500,
      });
    }
    const accessToken = participant?.access_token;
    if (!accessToken) throw new Error('Research participant credential is unavailable.');

    let response;
    try {
      response = await fetchImpl(`${apiUrl}${API_PATH}${path}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch {
      throw new IntentionalBreakApiError({
        status: 0,
        errorCode: 'network_error',
        message: 'Unable to reach the Intentional Break API.',
        retryable: true,
      });
    }

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      if (!response.ok) {
        throw invalidResponse(response.status, `Intentional Break API request failed (${response.status}).`);
      }
      throw invalidResponse(response.status, 'Intentional Break API returned invalid JSON.');
    }
    if (!response.ok) throw normalizeApiError(payload, response.status, accessToken);
    return normalizeSuccess(payload, response.status);
  }

  return Object.freeze({
    getCurrentJourney: () => request('/current'),
    getJourney: (sessionId) => request(`/sessions/${encodeURIComponent(sessionId)}`),
    createPlan: (input) => request('/plans', {
      method: 'POST',
      body: {
        intention: input.intention,
        planned_video_count: input.planned_video_count ?? input.plannedVideoCount,
        selected_cooldown_seconds: input.selected_cooldown_seconds
          ?? input.selectedCooldownSeconds,
        idempotency_key: input.idempotency_key ?? input.idempotencyKey,
        ...(input.previous_session_id ?? input.previousSessionId
          ? { previous_session_id: input.previous_session_id ?? input.previousSessionId }
          : {}),
        participant_notice_version: INTENTIONAL_BREAK_CONTRACT_VERSION,
        participant_notice_acknowledged: true,
      },
    }),
    cancelPlan: (sessionId, idempotencyKey) => request(
      `/sessions/${encodeURIComponent(sessionId)}/cancel`,
      { method: 'POST', body: idempotencyBody(idempotencyKey) },
    ),
    startSession: (sessionId, idempotencyKey) => request(
      `/sessions/${encodeURIComponent(sessionId)}/start`,
      { method: 'POST', body: idempotencyBody(idempotencyKey) },
    ),
    getItems: (sessionId, options = {}) => {
      const params = new URLSearchParams({
        start_position: String(options.start_position ?? options.startPosition ?? 1),
        limit: String(options.limit ?? 12),
      });
      return request(`/sessions/${encodeURIComponent(sessionId)}/items?${params}`);
    },
    appendEvents: (sessionId, events) => request(
      `/sessions/${encodeURIComponent(sessionId)}/events`,
      { method: 'POST', body: { events: events.map(sanitizeEvent) } },
    ),
    finishEarly: (sessionId, input) => request(
      `/sessions/${encodeURIComponent(sessionId)}/finish-early`,
      {
        method: 'POST',
        body: idempotencyBody(input.idempotency_key ?? input.idempotencyKey),
      },
    ),
    submitCheckout: (sessionId, input) => request(
      `/sessions/${encodeURIComponent(sessionId)}/checkout`,
      {
        method: 'POST',
        body: {
          ...idempotencyBody(input.idempotency_key ?? input.idempotencyKey),
          worthwhile: input.worthwhile,
          perceived_control: input.perceived_control ?? input.perceivedControl,
          mood: input.mood,
          checkout_version: INTENTIONAL_BREAK_CONTRACT_VERSION,
        },
      },
    ),
    getCooldown: (sessionId) => request(
      `/sessions/${encodeURIComponent(sessionId)}/cooldown`,
    ),
    startOverride: (sessionId, idempotencyKey) => request(
      `/sessions/${encodeURIComponent(sessionId)}/override/start`,
      { method: 'POST', body: idempotencyBody(idempotencyKey) },
    ),
    confirmOverride: (sessionId, input) => request(
      `/sessions/${encodeURIComponent(sessionId)}/override/confirm`,
      {
        method: 'POST',
        body: {
          ...idempotencyBody(input.idempotency_key ?? input.idempotencyKey),
          reason_code: input.reason_code ?? input.reasonCode,
        },
      },
    ),
  });
}

export function getCurrentJourneyForStoredParticipant(participant, {
  apiUrl = '',
  fetchImpl = globalThis.fetch?.bind(globalThis),
} = {}) {
  return createIntentionalBreakApiClient({
    apiUrl,
    fetchImpl,
    participantProvider: async () => participant,
  }).getCurrentJourney();
}

let browserClient;

function getBrowserClient() {
  if (!browserClient) {
    browserClient = createIntentionalBreakApiClient({
      apiUrl: import.meta.env?.VITE_API_URL ?? '',
    });
  }
  return browserClient;
}

export const getCurrentJourney = (...args) => getBrowserClient().getCurrentJourney(...args);
export const getJourney = (...args) => getBrowserClient().getJourney(...args);
export const createPlan = (...args) => getBrowserClient().createPlan(...args);
export const cancelPlan = (...args) => getBrowserClient().cancelPlan(...args);
export const startSession = (...args) => getBrowserClient().startSession(...args);
export const getItems = (...args) => getBrowserClient().getItems(...args);
export const appendEvents = (...args) => getBrowserClient().appendEvents(...args);
export const finishEarly = (...args) => getBrowserClient().finishEarly(...args);
export const submitCheckout = (...args) => getBrowserClient().submitCheckout(...args);
export const getCooldown = (...args) => getBrowserClient().getCooldown(...args);
export const startOverride = (...args) => getBrowserClient().startOverride(...args);
export const confirmOverride = (...args) => getBrowserClient().confirmOverride(...args);
