import { useCallback, useEffect, useState } from 'react';

/**
 * App-wide light/dark theme, shared by the auth/profile pages (CxShell) and any
 * control that wants to flip it. The feed (ReelsPage) owns the same localStorage
 * key, so toggling here and navigating back to the feed stays consistent.
 *
 * Sync: `storage` covers other tabs, a custom in-tab event covers components in
 * this tab (the storage event does not fire in the tab that wrote it), and the
 * OS `prefers-color-scheme` is the fallback when no explicit theme is saved.
 */
const THEME_KEY = 'chrysalis-algorithm-theme';
const LEGACY_THEME_KEY = 'chrysalis-reels-theme';
const THEME_EVENT = 'chrysalis-theme-change';

export function readAppTheme() {
  if (typeof window === 'undefined') return 'light';
  const saved =
    window.localStorage.getItem(THEME_KEY) ||
    window.localStorage.getItem(LEGACY_THEME_KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function useAppTheme() {
  const [theme, setTheme] = useState(readAppTheme);

  useEffect(() => {
    const update = () => setTheme(readAppTheme());
    window.addEventListener('storage', update);
    window.addEventListener(THEME_EVENT, update);
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
    mq?.addEventListener?.('change', update);
    return () => {
      window.removeEventListener('storage', update);
      window.removeEventListener(THEME_EVENT, update);
      mq?.removeEventListener?.('change', update);
    };
  }, []);

  const toggleTheme = useCallback(() => {
    const next = readAppTheme() === 'dark' ? 'light' : 'dark';
    try { window.localStorage.setItem(THEME_KEY, next); } catch { /* storage may be unavailable */ }
    setTheme(next);
    window.dispatchEvent(new Event(THEME_EVENT)); // notify CxShell + others in this tab
  }, []);

  return { theme, toggleTheme };
}
