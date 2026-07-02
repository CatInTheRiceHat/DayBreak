import { useEffect, useMemo, useState } from 'react';
import {
  badgeShelf,
  buildLeaderboard,
  completeChallenge as applyCompletion,
  computeStats,
  dateKey,
  earnedBadgeIds,
  todayCompletions,
} from './challenges';

const STORAGE_KEY = 'chrysalis-challenges';

function loadState() {
  if (typeof window === 'undefined') return { completedByDate: {} };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed === 'object' && parsed.completedByDate) return parsed;
  } catch {
    /* fall through to fresh state */
  }
  return { completedByDate: {} };
}

/**
 * Challenge state for the signed-in (demo) user, persisted to localStorage. No
 * backend / auth exists, so this is the source of truth for points and streaks.
 */
export function useChallenges() {
  const [state, setState] = useState(loadState);
  const [newlyEarned, setNewlyEarned] = useState([]);
  const today = dateKey();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      /* storage is best-effort */
    }
  }, [state]);

  const stats = useMemo(() => computeStats(state, today), [state, today]);
  const completedToday = useMemo(() => todayCompletions(state, today), [state, today]);
  const badges = useMemo(() => badgeShelf(stats), [stats]);
  const leaderboard = useMemo(() => buildLeaderboard(stats), [stats]);

  function complete(challenge, reflection) {
    setState((previous) => {
      const before = new Set(earnedBadgeIds(computeStats(previous, today)));
      const next = applyCompletion(previous, {
        challengeId: challenge.id,
        points: challenge.points,
        reflection,
        todayKey: today,
      });
      const after = earnedBadgeIds(computeStats(next, today));
      const fresh = after.filter((id) => !before.has(id));
      if (fresh.length) setNewlyEarned(fresh);
      return next;
    });
  }

  function clearNewlyEarned() {
    setNewlyEarned([]);
  }

  return { stats, completedToday, badges, leaderboard, complete, newlyEarned, clearNewlyEarned };
}
