import { useCallback, useEffect, useState } from 'react';
import {
  STORAGE_KEY,
  addSaved,
  isSavedId,
  normalizeSavedList,
  removeSaved,
  toSavedSnapshot,
} from './savedVideos.js';

function loadState() {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return normalizeSavedList(raw ? JSON.parse(raw) : []);
  } catch {
    return [];
  }
}

/**
 * The signed-in (demo) user's Saved videos, persisted to localStorage. No backend
 * exists, so this is the source of truth — same pattern as useChallenges.
 *
 * Returns: saved (newest-first), isSaved(id), toggleSave(reel) → boolean for the
 * resulting state, and removeSave(id).
 */
export function useSavedVideos() {
  const [saved, setSaved] = useState(loadState);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
    } catch {
      /* storage is best-effort */
    }
  }, [saved]);

  const isSaved = useCallback((id) => isSavedId(saved, id), [saved]);

  // Returns the resulting saved-state (true = now saved) so callers can tailor
  // their toast copy. Decided from the current state, applied via a functional
  // update so concurrent toggles still resolve correctly.
  const toggleSave = useCallback((reel) => {
    const snapshot = toSavedSnapshot(reel);
    if (!snapshot) return false;
    const willSave = !isSavedId(saved, snapshot.id);
    setSaved((list) => (
      isSavedId(list, snapshot.id)
        ? removeSaved(list, snapshot.id)
        : addSaved(list, snapshot)
    ));
    return willSave;
  }, [saved]);

  const removeSave = useCallback((id) => {
    setSaved((list) => removeSaved(list, id));
  }, []);

  return { saved, isSaved, toggleSave, removeSave };
}
