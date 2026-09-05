/**
 * Pure helpers for the "Saved videos" collection.
 *
 * The feed is ephemeral — cards are regenerated on the fly and never re-fetched by
 * id — so we cannot re-derive a reel after it scrolls away. Instead we snapshot the
 * few display fields we need at save time and persist that. No backend / auth
 * exists, so localStorage (via useSavedVideos) is the source of truth.
 *
 * All functions here are pure and side-effect free so they can be unit tested
 * without React or a DOM (mirrors challenges.js / sessionBreaks).
 */

export const STORAGE_KEY = 'chrysalis-saved-videos';

/** Keep the list bounded; newest-first, oldest dropped (mirrors useSessionTimer). */
export const MAX_SAVED = 200;

/** First non-empty string among the candidates, else null. */
function firstString(...values) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

/**
 * Build a minimal, serializable snapshot of a reel for the Saved collection.
 * Returns null when the reel has no usable id (nothing we could key or de-dupe on).
 */
export function toSavedSnapshot(reel, now = Date.now()) {
  if (!reel || typeof reel !== 'object') return null;
  const id = firstString(reel.id != null ? String(reel.id) : null);
  if (!id) return null;

  return {
    id,
    title: firstString(reel.title) || 'Saved video',
    source: firstString(reel.source),
    thumbnail: firstString(reel.thumbnail, reel.image),
    embedUrl: firstString(reel.embed_url, reel.embedUrl),
    youtubeId: firstString(reel.youtube_id, reel.youtubeId),
    savedAt: now,
  };
}

/** True when a snapshot with this id is already in the list. */
export function isSavedId(list, id) {
  if (!Array.isArray(list) || id == null) return false;
  const key = String(id);
  return list.some((item) => item && String(item.id) === key);
}

/**
 * Add a snapshot to the list: de-duped by id (re-saving moves it to the front),
 * newest-first, capped at MAX_SAVED. Returns a new array; never mutates input.
 */
export function addSaved(list, snapshot) {
  if (!snapshot || !snapshot.id) return Array.isArray(list) ? list : [];
  const rest = (Array.isArray(list) ? list : []).filter(
    (item) => item && String(item.id) !== String(snapshot.id),
  );
  return [snapshot, ...rest].slice(0, MAX_SAVED);
}

/** Remove the snapshot with this id. Returns a new array; never mutates input. */
export function removeSaved(list, id) {
  if (!Array.isArray(list) || id == null) return Array.isArray(list) ? list : [];
  const key = String(id);
  return list.filter((item) => item && String(item.id) !== key);
}

/** Sanitize a parsed localStorage value into a clean snapshot list. */
export function normalizeSavedList(raw) {
  if (!Array.isArray(raw)) return [];
  const seen = new Set();
  const clean = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const id = item.id != null ? String(item.id) : null;
    if (!id || seen.has(id)) continue;
    seen.add(id);
    clean.push({
      id,
      title: typeof item.title === 'string' && item.title ? item.title : 'Saved video',
      source: typeof item.source === 'string' ? item.source : null,
      thumbnail: typeof item.thumbnail === 'string' ? item.thumbnail : null,
      embedUrl: typeof item.embedUrl === 'string' ? item.embedUrl : null,
      youtubeId: typeof item.youtubeId === 'string' ? item.youtubeId : null,
      savedAt: Number.isFinite(item.savedAt) ? item.savedAt : 0,
    });
  }
  return clean.slice(0, MAX_SAVED);
}
