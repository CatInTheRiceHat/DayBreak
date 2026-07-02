import { useEffect, useRef, useState } from 'react';
import {
  DEFAULT_TIME_SCALE_MS,
  dueBreakTier,
  elapsedMsForNextBreak,
  isBreakPending,
  minutesFromElapsed,
} from './sessionBreaks';

const COMPLETIONS_KEY = 'chrysalis-break-completions';
const TICK_MS = 1000;

/** Append a break completion to localStorage (low-friction, no backend needed). */
export function recordBreakCompletion(entry) {
  if (typeof window === 'undefined') return;
  try {
    const raw = window.localStorage.getItem(COMPLETIONS_KEY);
    const list = raw ? JSON.parse(raw) : [];
    list.push(entry);
    window.localStorage.setItem(COMPLETIONS_KEY, JSON.stringify(list.slice(-50)));
  } catch {
    /* storage is best-effort; never block the break flow */
  }
}

export function getBreakCompletions() {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(COMPLETIONS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

/**
 * Tracks continuous active session time and surfaces when a progressive break is
 * due. Time only accumulates while `active` is true and the tab is visible, so a
 * backgrounded tab or an open break screen does not burn session minutes.
 *
 * Returns:
 *   elapsedMs, elapsedMin   cumulative active session time
 *   completedMin            highest break milestone already completed
 *   dueTier                 the break tier to show now, or null
 *   completeBreak(entry)    mark the current break done (advances the milestone)
 *   triggerBreakNow()       demo/dev: jump to the next break instantly
 *   reset()                 clear the session (e.g. on leaving the feed)
 */
export function useSessionTimer({ active = true, scaleMs = DEFAULT_TIME_SCALE_MS } = {}) {
  const [elapsedMs, setElapsedMs] = useState(0);
  const [completedMin, setCompletedMin] = useState(0);
  const lastTickRef = useRef(null);
  // Keep the latest completed milestone available inside the interval closure
  // without re-creating the interval every time it advances.
  const completedMinRef = useRef(completedMin);
  useEffect(() => { completedMinRef.current = completedMin; }, [completedMin]);

  useEffect(() => {
    if (!active) {
      lastTickRef.current = null;
      return undefined;
    }
    lastTickRef.current = Date.now();
    const id = window.setInterval(() => {
      const now = Date.now();
      // Don't accrue while the user is away: tab hidden (switched/minimized) OR
      // the window has lost focus (clicked off to another app). No creepy
      // background tracking, and the away-time never counts as session time.
      const away = typeof document !== 'undefined'
        && (document.hidden || (typeof document.hasFocus === 'function' && !document.hasFocus()));
      if (away) {
        lastTickRef.current = now;
        return;
      }
      const previous = lastTickRef.current ?? now;
      lastTickRef.current = now;
      setElapsedMs((value) => {
        // Freeze the clock while a break is already due — otherwise time keeps
        // burning behind the break screen and the next milestone fires the
        // instant the user finishes the current one.
        if (isBreakPending(value, completedMinRef.current, scaleMs)) return value;
        return value + (now - previous);
      });
    }, TICK_MS);
    return () => window.clearInterval(id);
  }, [active, scaleMs]);

  const elapsedMin = minutesFromElapsed(elapsedMs, scaleMs);
  const dueTier = dueBreakTier(elapsedMin, completedMin);

  function completeBreak(entry = {}) {
    const tier = dueBreakTier(minutesFromElapsed(elapsedMs, scaleMs), completedMin);
    if (tier) {
      setCompletedMin(tier.thresholdMin);
      recordBreakCompletion({
        ...entry,
        thresholdMin: tier.thresholdMin,
        breakMin: tier.breakMin,
        completedAt: new Date().toISOString(),
      });
    }
    lastTickRef.current = Date.now();
  }

  function triggerBreakNow() {
    setElapsedMs((value) => Math.max(value, elapsedMsForNextBreak(completedMin, scaleMs)));
  }

  function reset() {
    setElapsedMs(0);
    setCompletedMin(0);
    lastTickRef.current = Date.now();
  }

  return {
    elapsedMs,
    elapsedMin,
    completedMin,
    dueTier,
    completeBreak,
    triggerBreakNow,
    reset,
  };
}
