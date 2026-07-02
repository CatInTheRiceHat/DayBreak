import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Bookmark, Loader2, LogOut, Moon, NotebookPen, Sun } from 'lucide-react';
import { useAuth } from '../../lib/authContext';
import { useAppTheme } from '../../lib/useAppTheme';
import { getMyProfile, getProfileByUsername } from '../../lib/profileApi';
import { CxShell } from './CxShell';
import { ProfileCard } from './ProfileCard';

/**
 * Profile page for both the owner (/profile) and public viewers (/u/:username).
 * `mode` = "me" | "public".
 *
 * Render-time gates handle the "not configured" and "signed out" cases so the
 * data effect only ever does the async fetch (no synchronous setState in effects).
 */
export function ProfilePage({ mode = 'me' }) {
  const isMe = mode === 'me';
  const navigate = useNavigate();
  const { username } = useParams();
  const { configured, user, loading: authLoading, signOut } = useAuth();
  const { theme, toggleTheme } = useAppTheme();

  const handleSignOut = async () => {
    await signOut();
    navigate('/login');
  };

  const [profile, setProfile] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | ok | empty | private
  const [error, setError] = useState(null);

  // Only fetch once we know who is asking (own profile needs a signed-in user).
  const canLoad = configured && (!isMe || (!authLoading && Boolean(user)));

  useEffect(() => {
    if (!canLoad) return undefined;
    let active = true;
    const load = isMe ? getMyProfile() : getProfileByUsername(username);
    load
      .then((data) => {
        if (!active) return;
        if (!data) { setStatus('empty'); return; }
        if (data.is_private && data.id !== user?.id) { setStatus('private'); return; }
        setProfile(data);
        setStatus('ok');
      })
      .catch((err) => {
        if (!active) return;
        setError(err?.message || 'Could not load this profile.');
        setStatus('empty');
      });
    return () => { active = false; };
  }, [canLoad, isMe, username, user]);

  // Render-time gates (kept out of effects).
  if (!configured) {
    return (
      <CxShell wide>
        <div className="cx-card cx-state-card">
          <h1 className="cx-card__title">Profiles are being set up.</h1>
          <p className="cx-card__lede">Your feed is ready — sign-in and profiles arrive soon.</p>
          <Link to="/algorithm" className="cx-btn cx-btn--primary">Back to your feed</Link>
        </div>
      </CxShell>
    );
  }
  if (isMe && authLoading) {
    return (
      <CxShell wide>
        <div className="cx-state"><Loader2 size={22} className="cx-spin" aria-hidden="true" /> Loading…</div>
      </CxShell>
    );
  }
  if (isMe && !user) {
    return <Navigate to="/login" replace />;
  }

  const isOwner = isMe || Boolean(profile && user && profile.id === user.id);

  // Return to wherever the user came from, so opening Profile from Home lands them
  // back on Home (which carries the Search/Inbox chrome) rather than always on the
  // feed. Falls back to the feed when Profile was the entry point (deep link / fresh
  // tab) and there's no in-app history to pop. React Router tracks position in
  // history.state.idx; idx > 0 means there's an in-session page behind us.
  const goBack = () => {
    if ((window.history.state?.idx ?? 0) > 0) navigate(-1);
    else navigate('/algorithm');
  };

  return (
    <CxShell wide>
      <div className="cx-profilebar">
        <button type="button" onClick={goBack} className="cx-shell__back" aria-label="Go back">
          <ArrowLeft size={18} aria-hidden="true" /> Back
        </button>
        <div className="cx-profilebar__actions">
          <button
            type="button"
            className="cx-iconbtn"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-pressed={theme === 'dark'}
            title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
          >
            {theme === 'dark'
              ? <Sun size={18} aria-hidden="true" />
              : <Moon size={18} aria-hidden="true" />}
          </button>
        </div>
      </div>

      {status === 'loading' && (
        <div className="cx-state"><Loader2 size={22} className="cx-spin" aria-hidden="true" /> Loading…</div>
      )}

      {status === 'private' && (
        <div className="cx-card cx-state-card">
          <h1 className="cx-card__title">This profile is private.</h1>
          <p className="cx-card__lede">Only its owner can see it right now.</p>
        </div>
      )}

      {status === 'empty' && (
        <div className="cx-card cx-state-card">
          <h1 className="cx-card__title">
            {isMe ? 'Let’s shape your space.' : 'This profile doesn’t exist yet.'}
          </h1>
          <p className="cx-card__lede">
            {isMe
              ? 'A profile for how you want to feel online.'
              : 'The page you’re looking for isn’t here.'}
          </p>
          {error && <p className="cx-form__error" role="alert">{error}</p>}
          {isMe
            ? <Link to="/profile/edit" className="cx-btn cx-btn--primary">Create my profile</Link>
            : <Link to="/algorithm" className="cx-btn cx-btn--primary">Back to your feed</Link>}
        </div>
      )}

      {status === 'ok' && profile && (
        <>
          <ProfileCard profile={profile} isOwner={isOwner} onEdit={() => navigate('/profile/edit')} />

          {/* Gentle "your space" preview sections — owner only, calm placeholders. */}
          {isOwner && (
            <div className="cx-spaces">
              <div className="cx-space">
                <span className="cx-space__title"><Bookmark size={15} aria-hidden="true" /> Saved</span>
                <p className="cx-space__empty">Videos you keep will gather here.</p>
              </div>
              <div className="cx-space">
                <span className="cx-space__title"><NotebookPen size={15} aria-hidden="true" /> Reflections</span>
                <p className="cx-space__empty">Your quiet notes, just for you.</p>
              </div>
            </div>
          )}
        </>
      )}

      {/* Plain log-out for the signed-in owner (the account menu that used to
          hold this was removed from the chrome). Shows across the ok/empty
          states so it's always reachable from your own profile. */}
      {isMe && user && (
        <button type="button" className="cx-logout" onClick={handleSignOut}>
          <LogOut size={15} aria-hidden="true" /> Log out
        </button>
      )}
    </CxShell>
  );
}
