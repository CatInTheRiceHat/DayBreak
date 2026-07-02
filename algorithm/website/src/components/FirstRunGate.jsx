import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'motion/react';
import { IntroScreen } from './IntroScreen';
import { useAuth } from '../lib/authContext';
import { saveDiagnostic, getLatestDiagnostic } from '../lib/diagnostics';

// First-run flow: 🦋 intro → 📋 survey → ✨ result → 🔑 login → 📱 feed.
// The survey runs BEFORE login, so its answers are held locally (PENDING_KEY) and
// persisted to Supabase the moment the user signs in. Browser-local flags keep a
// finished first-timer from re-seeing any of it.
const INTRO_DONE_KEY = 'chrysalis-intro-done';
const DIAG_DONE_KEY = 'chrysalis-diagnostic-done';
const PENDING_KEY = 'chrysalis-diagnostic-pending';
const ONBOARDED_KEY = 'chrysalis-algorithm-onboarded';

// Local-dev only: set VITE_SKIP_AUTH=true in website/.env.local to skip the whole
// intro → survey → login funnel and land straight on the feed. Compiled out of
// production builds (import.meta.env.DEV is false there), so it can never ship.
const DEV_SKIP_AUTH = import.meta.env.DEV && import.meta.env.VITE_SKIP_AUTH === 'true';

/**
 * Orchestrates the first-run ribbon from the entry route ('/'):
 *  - brand-new visitor → intro → survey
 *  - finished the survey but not signed in → login (login is last)
 *  - just signed in with a survey waiting → persist it, then feed
 *  - returning, onboarded user → straight to feed
 */
export function FirstRunGate() {
  const { loading, user } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [showIntro, setShowIntro] = useState(false);

  useEffect(() => {
    if (loading || typeof window === 'undefined') return;
    if (pathname !== '/') return; // only orchestrate from the entry screen

    // Local-dev shortcut: mark the funnel complete and stay on the feed. No
    // intro, no survey, no login. (Never runs in production — see DEV_SKIP_AUTH.)
    if (DEV_SKIP_AUTH) {
      window.localStorage.setItem(INTRO_DONE_KEY, '1');
      window.localStorage.setItem(DIAG_DONE_KEY, '1');
      window.localStorage.setItem(ONBOARDED_KEY, '1');
      setShowIntro(false);
      return;
    }

    const introDone = window.localStorage.getItem(INTRO_DONE_KEY) === '1';
    const diagDone = window.localStorage.getItem(DIAG_DONE_KEY) === '1';
    const pendingRaw = window.localStorage.getItem(PENDING_KEY);
    const pending = pendingRaw ? JSON.parse(pendingRaw) : null;

    // 1. Just signed in with a survey waiting → persist it under their account.
    if (user && pending) {
      window.localStorage.setItem(DIAG_DONE_KEY, '1'); // don't re-run the funnel
      saveDiagnostic({ userId: user.id, ...pending }).then(({ error }) => {
        // Keep the pending answers if the save failed (e.g. table not created yet)
        // so a later visit retries; only clear once they're safely stored.
        if (!error) window.localStorage.removeItem(PENDING_KEY);
      });
      return; // stay on the feed (mode was already set at survey completion)
    }

    // 2. Survey not done yet → run the funnel.
    if (!diagDone) {
      if (user) {
        // Returning user on a fresh device: trust the server before re-surveying.
        getLatestDiagnostic(user.id).then(({ data }) => {
          if (data) window.localStorage.setItem(DIAG_DONE_KEY, '1');
          else navigate('/diagnostic', { replace: true });
        });
        return;
      }
      if (!introDone) setShowIntro(true); // brand-new → play the opening
      else navigate('/diagnostic', { replace: true });
      return;
    }

    // 3. Survey done but not signed in → login is the last step.
    if (diagDone && !user) navigate('/login', { replace: true });
    // 4. diagDone && user → feed (nothing to do).
  }, [loading, user, pathname, navigate]);

  const finishIntro = () => {
    window.localStorage.setItem(INTRO_DONE_KEY, '1');
    setShowIntro(false);
    navigate('/diagnostic');
  };

  return (
    <AnimatePresence>
      {showIntro && <IntroScreen key="intro" onDone={finishIntro} />}
    </AnimatePresence>
  );
}
