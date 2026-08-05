import { useAppTheme } from '../../lib/useAppTheme';

/**
 * Shared full-screen shell for the Chrysalis auth/profile pages. Provides the
 * calm gradient background and a centered content column. Kept separate from the
 * marketing site and the feed so these pages can own their own layout.
 *
 * Theme: these pages mirror the app-wide light/dark choice the feed owns (see
 * useAppTheme) onto `data-theme`. auth.css keys its dark tokens off that
 * attribute, so the profile/auth pages stay in sync with the rest of the app
 * instead of tracking the OS preference independently.
 */
export function CxShell({ children, wide = false, center = false }) {
  const { theme } = useAppTheme();

  return (
    <main className={`cx-shell${center ? ' cx-shell--center' : ''}`} data-cx data-theme={theme}>
      <div className={`cx-shell__inner${wide ? ' cx-shell__inner--wide' : ''}`}>
        {children}
      </div>
    </main>
  );
}
