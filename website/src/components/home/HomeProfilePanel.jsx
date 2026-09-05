import { BRAND } from '../../brand.js';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Compass, Pencil, Sparkles, UserCircle } from 'lucide-react';
import { useAuth } from '../../lib/authContext';
import { getMyProfile } from '../../lib/profileApi';
import { modeLabel } from './homeData';

/**
 * The signed-in user's profile area on Home (right column on desktop, compact card
 * near the top on mobile).
 *
 * Logged in  -> avatar, display name, @username, current intention/mode, and quick
 *               View / Edit profile links. Real data comes from the Supabase
 *               profiles row (via getMyProfile); the email is never shown here.
 * Logged out -> a calm sign-in card with Log in / Sign up.
 *
 * Degrades gracefully when Supabase isn't configured: it simply shows the signed-out
 * card, so the app never crashes waiting on auth.
 */
export function HomeProfilePanel() {
  const navigate = useNavigate();
  const { user, configured } = useAuth();
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    if (!configured) return undefined;
    // getMyProfile() resolves to null when signed out, so logging out clears the
    // profile through the (allowed) async callback — no synchronous setState here.
    let active = true;
    getMyProfile()
      .then((row) => { if (active) setProfile(row); })
      .catch(() => { if (active) setProfile(null); });
    return () => { active = false; };
  }, [user, configured]);

  if (!user) {
    return (
      <section className="home-signin" aria-label={`Sign in to ${BRAND}`}>
        <span className="home-signin__mark" aria-hidden="true"><img src="/images/logo.png" alt="" /></span>
        <h2 className="home-signin__title">Sign in to shape your {BRAND} profile</h2>
        <p className="home-signin__copy">
          Save your intention, share small wins, and connect a little more calmly.
        </p>
        <div className="home-signin__actions">
          <button type="button" className="home-btn home-btn--primary" onClick={() => navigate('/login')}>
            Log in
          </button>
          <button type="button" className="home-btn home-btn--soft" onClick={() => navigate('/signup')}>
            Sign up
          </button>
        </div>
      </section>
    );
  }

  const name = profile?.display_name || (profile?.username ? `@${profile.username}` : 'Your space');
  const username = profile?.username;
  const mode = modeLabel(profile?.current_mode);

  return (
    <section className="home-me" aria-label="Your profile">
      <Link to="/profile" className="home-me__id">
        <span className="cx-avatar cx-avatar--lg home-me__avatar">
          {profile?.avatar_url
            ? <img src={profile.avatar_url} alt="" aria-hidden="true" />
            : <span className="cx-avatar__fallback" aria-hidden="true">🌊</span>}
        </span>
        <span className="home-me__names">
          <span className="home-me__name">{name}</span>
          {username && <span className="home-me__handle">@{username}</span>}
        </span>
      </Link>

      <div className="home-me__chips">
        {profile?.intention && (
          <span className="cx-chip cx-chip--accent">
            <Sparkles size={13} aria-hidden="true" /> {profile.intention}
          </span>
        )}
        {mode && (
          <span className="cx-chip">
            <Compass size={13} aria-hidden="true" /> {mode}
          </span>
        )}
        {!profile?.intention && !mode && (
          <span className="cx-chip cx-chip--muted">Set your intention</span>
        )}
      </div>

      <div className="home-me__links">
        <Link to="/profile" className="home-me__link">
          <UserCircle size={15} aria-hidden="true" /> View profile
        </Link>
        <Link to="/profile/edit" className="home-me__link">
          <Pencil size={15} aria-hidden="true" /> Edit profile
        </Link>
      </div>
    </section>
  );
}
