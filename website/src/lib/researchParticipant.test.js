import assert from 'node:assert/strict';
import test from 'node:test';
import {
  RESEARCH_PARTICIPANT_STORAGE_KEY,
  clearStoredResearchParticipant,
  ensureResearchParticipant,
  getStoredResearchParticipant,
} from './researchParticipant.js';

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

const participant = Object.freeze({
  participant_id: '11111111-1111-4111-8111-111111111111',
  access_token: 'anonymous-bearer-token',
  status: 'active',
  assigned_condition: 'regular',
});

function response(body, status = 201) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

test('reuses the participant stored under the unchanged legacy key', async () => {
  const localStorage = new MemoryStorage();
  localStorage.setItem(RESEARCH_PARTICIPANT_STORAGE_KEY, JSON.stringify(participant));
  let fetchCalls = 0;

  const result = await ensureResearchParticipant({
    localStorage,
    fetchImpl: async () => { fetchCalls += 1; },
  });

  assert.equal(RESEARCH_PARTICIPANT_STORAGE_KEY, 'chrysalis-research-participant-v1');
  assert.deepEqual(result, participant);
  assert.equal(fetchCalls, 0);
});

test('creates and stores a missing participant with its bearer token and legacy condition', async () => {
  const localStorage = new MemoryStorage();
  const calls = [];
  const result = await ensureResearchParticipant({
    apiUrl: 'https://daybreak.test',
    localStorage,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return response({ ...participant, ignored_server_field: 'not-a-client-credential-field' });
    },
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://daybreak.test/api/research/participants');
  assert.equal(calls[0].options.method, 'POST');
  assert.equal(result.access_token, participant.access_token);
  assert.equal(result.assigned_condition, 'regular');
  assert.equal(result.ignored_server_field, undefined);
  assert.deepEqual(getStoredResearchParticipant({ localStorage }), participant);
});

test('clears only the shared participant credential', () => {
  const localStorage = new MemoryStorage();
  localStorage.setItem(RESEARCH_PARTICIPANT_STORAGE_KEY, JSON.stringify(participant));
  localStorage.setItem('unrelated', 'keep');

  clearStoredResearchParticipant({ localStorage });

  assert.equal(getStoredResearchParticipant({ localStorage }), null);
  assert.equal(localStorage.getItem('unrelated'), 'keep');
});

test('participant creation preserves legacy status errors', async () => {
  await assert.rejects(
    () => ensureResearchParticipant({
      localStorage: new MemoryStorage(),
      fetchImpl: async () => response({ detail: 'participant unavailable' }, 503),
    }),
    (error) => error.name === 'ResearchApiError'
      && error.status === 503
      && error.message === 'participant unavailable',
  );
});
