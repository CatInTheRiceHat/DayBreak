export const RESEARCH_PARTICIPANT_STORAGE_KEY = 'chrysalis-research-participant-v1';

const PARTICIPANT_FIELDS = Object.freeze([
  'participant_id',
  'access_token',
  'status',
  'assigned_condition',
]);

function readJson(storage, key) {
  try {
    return JSON.parse(storage?.getItem(key) || 'null');
  } catch {
    return null;
  }
}

function normalizeParticipant(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;

  const participant = {};
  for (const field of PARTICIPANT_FIELDS) {
    if (value[field] !== undefined) participant[field] = value[field];
  }
  return participant;
}

function hasCredential(participant) {
  return Boolean(participant?.participant_id && participant?.access_token);
}

async function parseParticipantResponse(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    // Status-based error below preserves the legacy participant-client behavior.
  }
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === 'string'
      ? detail
      : `Research API request failed (${response.status}).`;
    const error = new Error(message);
    error.name = 'ResearchApiError';
    error.status = response.status;
    throw error;
  }
  return body;
}

export function getStoredResearchParticipant({
  localStorage = globalThis.localStorage,
} = {}) {
  return normalizeParticipant(readJson(localStorage, RESEARCH_PARTICIPANT_STORAGE_KEY));
}

export function clearStoredResearchParticipant({
  localStorage = globalThis.localStorage,
} = {}) {
  localStorage?.removeItem(RESEARCH_PARTICIPANT_STORAGE_KEY);
}

export async function ensureResearchParticipant({
  apiUrl = '',
  fetchImpl = globalThis.fetch?.bind(globalThis),
  localStorage = globalThis.localStorage,
} = {}) {
  const stored = getStoredResearchParticipant({ localStorage });
  if (hasCredential(stored)) return stored;
  if (!fetchImpl) throw new Error('Fetch is unavailable.');

  const created = normalizeParticipant(await parseParticipantResponse(await fetchImpl(
    `${apiUrl}/api/research/participants`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    },
  )));
  if (!hasCredential(created)) {
    throw new Error('Research participant response did not include a credential.');
  }
  localStorage?.setItem(RESEARCH_PARTICIPANT_STORAGE_KEY, JSON.stringify(created));
  return created;
}
