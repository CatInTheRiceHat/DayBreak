import { Sun, Moon } from 'lucide-react';

/**
 * Accessible light/dark toggle. Controlled — pass `theme` ("light" | "dark")
 * and an `onToggle` handler. Reusable anywhere inside a [data-algorithm] subtree.
 */
export function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === 'dark';
  return (
    <button
      type="button"
      className="reels-fab"
      onClick={onToggle}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={isDark}
      title={isDark ? 'Light mode' : 'Dark mode'}
    >
      {isDark ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
    </button>
  );
}
