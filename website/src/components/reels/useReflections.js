import { useCallback, useEffect, useState } from 'react';
import { MAX_SAVED, toSavedSnapshot, removeSaved, normalizeSavedList } from './savedVideos.js';

const STORAGE_KEY = 'chrysalis-reflections';

function loadState() {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const list = normalizeSavedList(raw ? JSON.parse(raw) : []);
    // normalizeSavedList drops unknown fields, so re-attach the reflection label
    // from the raw rows by id.
    const parsed = raw ? JSON.parse(raw) : [];
    const byId = new Map(parsed.filter((r) => r && r.id != null).map((r) => [String(r.id), r.reflection]));
    return list.map((item) => ({ ...item, reflection: byId.get(item.id) || null }));
  } catch {
    return [];
  }
}

/**
 * The user's saved Reflections — the "how did this leave you feeling?" note a card
 * can capture (Calmer / Curious / Not for me). Each entry is a video snapshot plus
 * the chosen reflection, persisted to localStorage. Re-reflecting on the same video
 * updates its note and moves it to the front.
 *
 * Returns: reflections (newest-first), reflectionFor(id), setReflection(reel, label)
 * (label null/empty clears it), and removeReflection(id).
 */
export function useReflections() {
  const [reflections, setReflections] = useState(loadState);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(reflections));
    } catch {
      /* storage is best-effort */
    }
  }, [reflections]);

  const reflectionFor = useCallback(
    (id) => reflections.find((r) => String(r.id) === String(id))?.reflection || null,
    [reflections],
  );

  const setReflection = useCallback((reel, label) => {
    const snapshot = toSavedSnapshot(reel);
    if (!snapshot) return;
    setReflections((list) => {
      const rest = list.filter((r) => String(r.id) !== String(snapshot.id));
      if (!label) return rest; // clearing a reflection removes the entry
      return [{ ...snapshot, reflection: label }, ...rest].slice(0, MAX_SAVED);
    });
  }, []);

  const removeReflection = useCallback((id) => {
    setReflections((list) => removeSaved(list, id));
  }, []);

  return { reflections, reflectionFor, setReflection, removeReflection };
}
