import { useCallback, useEffect, useState } from 'react';
import {
  addSaved,
  isSavedId,
  normalizeSavedList,
  removeSaved,
  toSavedSnapshot,
} from './savedVideos.js';

const STORAGE_KEY = 'chrysalis-liked-videos';

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
 * The user's Liked videos, persisted to localStorage (same snapshot shape and
 * pure helpers as useSavedVideos — a like is just a second collection). No
 * backend exists, so this is the source of truth.
 *
 * Returns: liked (newest-first), isLiked(id), toggleLike(reel) → true when now
 * liked, and removeLike(id).
 */
export function useLikedVideos() {
  const [liked, setLiked] = useState(loadState);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(liked));
    } catch {
      /* storage is best-effort */
    }
  }, [liked]);

  const isLiked = useCallback((id) => isSavedId(liked, id), [liked]);

  const toggleLike = useCallback((reel) => {
    const snapshot = toSavedSnapshot(reel);
    if (!snapshot) return false;
    const willLike = !isSavedId(liked, snapshot.id);
    setLiked((list) => (
      isSavedId(list, snapshot.id)
        ? removeSaved(list, snapshot.id)
        : addSaved(list, snapshot)
    ));
    return willLike;
  }, [liked]);

  const removeLike = useCallback((id) => {
    setLiked((list) => removeSaved(list, id));
  }, []);

  return { liked, isLiked, toggleLike, removeLike };
}
