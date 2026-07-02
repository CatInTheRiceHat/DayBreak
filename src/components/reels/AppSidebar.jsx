import { BRAND } from '../../brand.js';
import { SlidersHorizontal, Inbox } from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';
import { NAV_SECTIONS } from './navSections';

/**
 * Desktop-only left navigation rail, in the spirit of a social-app home screen.
 *
 * Collapses to an icon-only rail on narrower desktops and expands with labels on
 * wide screens (driven entirely by CSS via the --app-sidebar-w token). On mobile
 * it is hidden — the top bar + bottom tab bar take over there.
 *
 * Shows all seven main sections in the canonical order (see navSections.js). A
 * secondary group exposes Feed details (Algorithm Compass) and Inbox, which are
 * not top-level sections. Nothing here leaks raw algorithm internals.
 *
 * Navigation is delegated to `onNavigate(key)` so the feed and the router pages
 * can each handle a tap their own way (the feed scrolls instead of routing).
 */
export function AppSidebar({
  active = 'home',
  intentionLabel,
  intentionLogo,
  onNavigate,
  onOpenDetails,
  detailsOpen,
  onInbox,
  streak = 0,
  theme,
  onToggleTheme,
  showBreakDemo = false,
  onTriggerBreak,
}) {
  return (
    <>
    <aside className="app-sidebar" aria-label={`${BRAND} navigation`}>
      <div className="app-sidebar__brand">
        <span className="app-sidebar__logo" aria-hidden="true"><img src="/images/logo.png" alt="" /></span>
        <span className="app-sidebar__wordmark">{BRAND}</span>
      </div>

      {onOpenDetails && (
        <button
          type="button"
          className="app-sidebar__intention"
          onClick={onOpenDetails}
          aria-label={`Your intention: ${intentionLabel}. Open feed details.`}
          aria-haspopup="dialog"
          aria-expanded={detailsOpen}
          title="Your intention — open feed details"
        >
          <span className="app-sidebar__intention-logo" aria-hidden="true">
            <img src={intentionLogo || '/images/flutter-feed.png'} alt="" />
          </span>
          <span className="app-sidebar__intention-text">
            <span className="app-sidebar__intention-eyebrow">Your intention</span>
            <span className="app-sidebar__intention-label">{intentionLabel}</span>
          </span>
        </button>
      )}

      <nav className="app-sidebar__nav">
        {NAV_SECTIONS.map((item) => {
          const isActive = item.key === active;
          const ItemIcon = item.Icon;
          const showStreak = item.key === 'challenges' && streak > 0;
          return (
            <button
              key={item.key}
              type="button"
              className={`app-sidebar__item${isActive ? ' is-active' : ''}`}
              onClick={() => onNavigate?.(item.key)}
              aria-current={isActive ? 'page' : undefined}
              title={item.label}
            >
              <span className="app-sidebar__item-icon">
                <ItemIcon size={22} aria-hidden="true" />
                {showStreak && (
                  <span className="app-sidebar__badge" aria-label={`${streak} day streak`}>
                    {streak}
                  </span>
                )}
              </span>
              <span className="app-sidebar__label">{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="app-sidebar__spacer" aria-hidden="true" />

      {(onOpenDetails || onInbox) && (
        <nav className="app-sidebar__nav app-sidebar__nav--secondary">
          {onInbox && (
            <button
              type="button"
              className={`app-sidebar__item${active === 'inbox' ? ' is-active' : ''}`}
              onClick={onInbox}
              aria-current={active === 'inbox' ? 'page' : undefined}
              title="Inbox"
            >
              <Inbox size={22} aria-hidden="true" />
              <span className="app-sidebar__label">Inbox</span>
            </button>
          )}
          {onOpenDetails && (
            <button
              type="button"
              className="app-sidebar__item"
              onClick={onOpenDetails}
              aria-haspopup="dialog"
              aria-expanded={detailsOpen}
              title="Feed details"
            >
              <SlidersHorizontal size={22} aria-hidden="true" />
              <span className="app-sidebar__label">Feed details</span>
            </button>
          )}
        </nav>
      )}

      {showBreakDemo && (
        <div className="app-sidebar__footer">
          <button
            type="button"
            className="app-sidebar__demo"
            onClick={onTriggerBreak}
            title="Demo: trigger a screen-time break now"
          >
            Trigger break
          </button>
        </div>
      )}
    </aside>

    {/* Theme toggle floats at the screen's bottom-right. Rendered as a sibling
        of the rail (not inside it) so `position: fixed` resolves to the viewport
        rather than the sidebar's backdrop-filter context. Hidden on mobile via
        CSS, where the top bar carries the theme toggle instead. */}
    <div className="app-sidebar__theme-dock">
      <ThemeToggle theme={theme} onToggle={onToggleTheme} />
    </div>
    </>
  );
}
