import { BRAND } from '../../brand.js';
import { BOTTOM_NAV_SECTIONS } from './navSections';

/**
 * App-style bottom navigation for mobile.
 *
 * A calm floating pill with the five sections that fit a phone bar, in the same
 * order as the desktop rail: Home · Reels · Community · Challenges · Profile.
 * Search + Saved live in the mobile top bar (see HomeShell) so the bar stays
 * uncrowded. Every tab is a real destination — no dead links.
 *
 * Props:
 *   active     — key of the current screen
 *   onNavigate — (key) => void, called with the tapped section key
 */
export function AppBottomNav({ active = 'home', onNavigate }) {
  return (
    <nav className="app-bottomnav" aria-label={`${BRAND} navigation`}>
      <ul className="app-bottomnav__list">
        {BOTTOM_NAV_SECTIONS.map((item) => {
          const isActive = item.key === active;
          const ItemIcon = item.Icon;
          return (
            <li key={item.key}>
              <button
                type="button"
                className={`app-bottomnav__item${isActive ? ' is-active' : ''}`}
                onClick={() => onNavigate?.(item.key)}
                aria-current={isActive ? 'page' : undefined}
                aria-label={item.label}
                title={item.label}
              >
                <ItemIcon size={20} aria-hidden="true" />
                <span className="app-bottomnav__label">{item.label}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
