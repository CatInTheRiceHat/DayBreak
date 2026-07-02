import { BRAND } from '../../brand.js';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Inbox, Search, Bookmark } from 'lucide-react';
import { useAuth } from '../../lib/authContext';
import { AppSidebar } from '../reels/AppSidebar';
import { AppBottomNav } from '../reels/AppBottomNav';
import { ThemeToggle } from '../reels/ThemeToggle';
import { MODES, DEFAULT_MODE } from '../reels/reelsData';
import { NAV_SECTIONS } from '../reels/navSections';
import { useChallenges } from '../reels/useChallenges';
import '../../reels.css';
import '../../home.css';

/**
 * Shared chrome for the router-based "app" pages (Home, Community, Challenges,
 * Search, Saved, Profile-state cards, Inbox).
 *
 * Reuses the feed's design system: the `[data-algorithm]` token scope, the desktop
 * AppSidebar, and the mobile AppBottomNav — so every page feels like one app with
 * the feed. Theme + intention are read from the same localStorage keys the feed
 * uses, keeping them in sync.
 *
 * The seven main sections live in navSections.js. The desktop rail shows all seven;
 * the mobile bottom bar shows the five that fit (Home · Reels · Community ·
 * Challenges · Profile) and the mobile top bar carries Search + Saved (+ Inbox).
 */
const THEME_KEY = 'chrysalis-algorithm-theme';
const MODE_KEY = 'chrysalis-algorithm-mode';

function initialTheme() {
  if (typeof window === 'undefined') return 'light';
  const saved = window.localStorage.getItem(THEME_KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function currentIntention() {
  const mode = (typeof window !== 'undefined' && window.localStorage.getItem(MODE_KEY)) || DEFAULT_MODE;
  return MODES.find((item) => item.key === mode) || MODES.find((item) => item.key === DEFAULT_MODE);
}

const ROUTE_BY_KEY = Object.fromEntries(NAV_SECTIONS.map((s) => [s.key, s.route]));

export function HomeShell({ active = 'home', children }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [theme, setTheme] = useState(initialTheme);
  const intention = currentIntention();
  const { stats } = useChallenges();

  useEffect(() => {
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'));

  const go = (key) => {
    if (key === 'profile') {
      navigate(user ? '/profile' : '/login');
      return;
    }
    const route = ROUTE_BY_KEY[key];
    if (route) navigate(route);
  };

  const onInbox = () => navigate('/inbox');
  const onSearch = () => navigate('/search');
  const onSaved = () => navigate('/saved');

  return (
    <main className="reels-shell home-shell" data-algorithm data-theme={theme} data-onboarded="true">
      <AppSidebar
        active={active}
        intentionLabel={intention?.label ?? "Cruisin'"}
        intentionLogo={intention?.logo}
        onNavigate={go}
        onOpenDetails={() => navigate('/algorithm')}
        onInbox={onInbox}
        streak={stats?.streak ?? 0}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      {/* Mobile-only top bar: brand + Search + Saved + Inbox (the items kept out of
          the 5-slot bottom bar). */}
      <header className="home-topbar">
        <Link to="/home" className="home-topbar__brand" aria-label={`${BRAND} home`}>
          <span className="home-topbar__brandmark" aria-hidden="true"><img src="/images/logo.png" alt="" /></span>
          <span>{BRAND}</span>
        </Link>
        <div className="home-topbar__actions">
          <button type="button" className="home-iconbtn" onClick={onSearch} aria-label="Search">
            <Search size={20} aria-hidden="true" />
          </button>
          <button type="button" className="home-iconbtn" onClick={onSaved} aria-label="Saved">
            <Bookmark size={20} aria-hidden="true" />
          </button>
          <button type="button" className="home-iconbtn" onClick={onInbox} aria-label="Inbox">
            <Inbox size={20} aria-hidden="true" />
          </button>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
      </header>

      <div className="home-main">
        {children}
      </div>

      <AppBottomNav active={active} onNavigate={go} />
    </main>
  );
}
