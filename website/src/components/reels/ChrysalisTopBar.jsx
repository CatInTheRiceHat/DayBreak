import { BRAND } from '../../brand.js';
import { Link } from 'react-router-dom';
import { ArrowLeft, SlidersHorizontal, Trophy, UserCircle } from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';

/**
 * App-style top header for the Chrysalis algorithm feed.
 *
 * Reads like a real social app home screen: butterfly wordmark on the left, a
 * subtle "your intention" label in the middle, and a tidy row of round actions
 * on the right (Feed details, Challenges, Profile, theme). Nothing here exposes
 * raw algorithm internals — that lives behind the Feed details drawer.
 *
 * Props:
 *   intentionLabel — human label for the active intention/mode (e.g. "Daily Dew")
 *   intentionLogo  — small image for the active intention
 *   theme, onToggleTheme — light/dark control
 *   onOpenDetails, detailsOpen — Feed details drawer trigger + state
 *   onOpenChallenges, challengesOpen, streak — IRL challenges trigger
 *   onOpenProfile, profileOpen — profile trigger
 *   showBreakDemo, onTriggerBreak — dev-only screen-time break control
 */
export function ChrysalisTopBar({
  showActions = true,
  intentionLabel,
  intentionLogo,
  theme,
  onToggleTheme,
  onOpenDetails,
  detailsOpen,
  onOpenChallenges,
  challengesOpen,
  streak = 0,
  onOpenProfile,
  profileOpen,
  showBreakDemo = false,
  onTriggerBreak,
}) {
  return (
    <header className="app-topbar" data-algorithm-topbar>
      <div className="app-topbar__brand">
        <Link to="/home" className="app-topbar__home" aria-label={`Back to ${BRAND} home`}>
          <ArrowLeft size={18} aria-hidden="true" />
        </Link>
        <span className="app-topbar__logo" aria-hidden="true"><img src="/images/logo.png" alt="" /></span>
        <span className="app-topbar__wordmark">{BRAND}</span>
      </div>

      {showActions ? (
        <button
          type="button"
          className="app-topbar__intention"
          onClick={onOpenDetails}
          aria-label={`Your intention: ${intentionLabel}. Open feed details.`}
          aria-haspopup="dialog"
          aria-expanded={detailsOpen}
          title="Your intention — tap for feed details"
        >
          <span className="app-topbar__intention-logo" aria-hidden="true">
            <img src={intentionLogo || '/images/flutter-feed.png'} alt="" />
          </span>
          <span className="app-topbar__intention-text">
            <span className="app-topbar__intention-eyebrow">Your intention</span>
            <span className="app-topbar__intention-label">{intentionLabel}</span>
          </span>
        </button>
      ) : (
        <span className="app-topbar__spacer" aria-hidden="true" />
      )}

      <div className="app-topbar__actions">
        {showActions && (
        <>
        <button
          type="button"
          className="reels-fab app-topbar__details"
          onClick={onOpenDetails}
          aria-label="Open feed details"
          aria-haspopup="dialog"
          aria-expanded={detailsOpen}
          title="Feed details"
        >
          <SlidersHorizontal size={18} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="reels-fab"
          onClick={onOpenChallenges}
          aria-label="Open IRL Challenges"
          aria-haspopup="dialog"
          aria-expanded={challengesOpen}
          title="IRL Challenges"
        >
          <Trophy size={17} aria-hidden="true" />
          {streak > 0 && (
            <span className="reels-fab__badge" aria-label={`${streak} day streak`}>
              {streak}
            </span>
          )}
        </button>
        <button
          type="button"
          className="reels-fab"
          onClick={onOpenProfile}
          aria-label="Open your profile"
          aria-haspopup="dialog"
          aria-expanded={profileOpen}
          title="Your profile"
        >
          <UserCircle size={18} aria-hidden="true" />
        </button>
        {showBreakDemo && (
          <button
            type="button"
            className="reels-fab reels-fab--demo"
            onClick={onTriggerBreak}
            title="Demo: trigger a screen-time break now"
          >
            Trigger break
          </button>
        )}
        </>
        )}
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
    </header>
  );
}
