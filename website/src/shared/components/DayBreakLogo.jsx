import { BRAND } from '../../brand.js';

/**
 * Central wrapper for the public DayBreak mark. Keeping the asset reference in
 * one component makes a future production-logo swap a one-line change.
 */
export function DayBreakLogo({ className = '', labelled = false }) {
  return (
    <img
      className={className}
      src="/favicon.svg?v=4"
      alt={labelled ? `${BRAND} logo` : ''}
      aria-hidden={labelled ? undefined : 'true'}
    />
  );
}
