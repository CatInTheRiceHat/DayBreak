// Lightweight session helper for the Chrysalis algorithm feed.
//
// Anonymous visitors are identified by a frontend-generated session_id (a UUID
// persisted in localStorage) used only to scope per-session state. Chrysalis does
// NOT ask for or use location: the demo feed is fixed to US/English entirely via
// backend config + feed filtering (see core/language_filter.py), never via the
// browser locale or any geolocation permission.

const SESSION_ID_KEY = 'chrysalis-session-id';

// Internal, fixed demo configuration — not user input, never prompted for.
export const DEFAULT_LANGUAGE = 'en';
export const DEFAULT_REGION = 'US';

function generateId() {
  if (typeof window !== 'undefined' && window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `sess-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Stable per-browser session id used to scope anonymous, non-location state. */
export function getSessionId() {
  if (typeof window === 'undefined') return null;
  let id = window.localStorage.getItem(SESSION_ID_KEY);
  if (!id) {
    id = generateId();
    window.localStorage.setItem(SESSION_ID_KEY, id);
  }
  return id;
}
