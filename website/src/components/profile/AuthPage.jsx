import { BRAND } from '../../brand.js';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-react';
import { useAuth } from '../../lib/authContext';
import { CxShell } from './CxShell';

/**
 * Combined sign-in / sign-up screen (mode = "login" | "signup").
 *
 * Email + password only. We deliberately do NOT ask for a phone number — Chrysalis
 * is teen-centered and keeps required data minimal. Email/phone are owned by
 * Supabase Auth, never written to the public profiles table.
 */
export function AuthPage({ mode = 'login' }) {
  const isSignup = mode === 'signup';
  const navigate = useNavigate();
  const { configured, signIn, signUp } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const { data, error: authError } = isSignup
        ? await signUp(email.trim(), password)
        : await signIn(email.trim(), password);
      if (authError) {
        setError(authError.message);
        return;
      }
      if (isSignup && data?.user && !data.session) {
        // Email confirmation is required before a session is issued.
        setNotice('Almost there — check your email to confirm your account, then log in.');
        return;
      }
      navigate('/profile');
    } catch (err) {
      setError(err?.message || 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <CxShell center>
      <Link to="/algorithm" className="cx-shell__back" aria-label="Back to your feed">
        <ArrowLeft size={18} aria-hidden="true" /> Back
      </Link>

      <div className="cx-card cx-card--auth">
        <div className="cx-brand">
          <span className="cx-brand__logo" aria-hidden="true"><img src="/images/logo.png" alt="" /></span>
          <span className="cx-brand__word">{BRAND}</span>
        </div>

        <h1 className="cx-card__title">
          {isSignup ? 'Your feed starts with you.' : 'Welcome back.'}
        </h1>
        <p className="cx-card__lede">
          {isSignup
            ? 'A profile for how you want to feel online. Less noise. More intention.'
            : 'Shape your scroll around your intention.'}
        </p>

        {!configured && (
          <p className="cx-form__notice" role="status">
            Sign-in is being set up for this space. You can keep exploring your feed in
            the meantime.
          </p>
        )}

        <form className="cx-form" onSubmit={submit}>
          <label className="cx-field">
            <span className="cx-field__label">Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={!configured || busy}
            />
          </label>
          <label className="cx-field">
            <span className="cx-field__label">Password</span>
            <input
              type="password"
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 6 characters"
              disabled={!configured || busy}
            />
          </label>

          {error && <p className="cx-form__error" role="alert">{error}</p>}
          {notice && <p className="cx-form__notice" role="status">{notice}</p>}

          <button type="submit" className="cx-btn cx-btn--primary" disabled={!configured || busy}>
            {busy ? <Loader2 size={16} className="cx-spin" aria-hidden="true" /> : null}
            {isSignup ? 'Create my space' : 'Log in'}
            {!busy && <ArrowRight size={16} aria-hidden="true" />}
          </button>
        </form>

        <p className="cx-card__switch">
          {isSignup ? (
            <>Already here? <Link to="/login">Log in</Link></>
          ) : (
            <>New to {BRAND}? <Link to="/signup">Create your space</Link></>
          )}
        </p>
      </div>
    </CxShell>
  );
}
