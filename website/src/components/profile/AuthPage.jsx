import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-react';
import { useAuth } from '../../lib/authContext';
import { CxShell } from './CxShell';
import { DayBreakAuthBrand } from './DayBreakAuthBrand';

/**
 * Combined sign-in / sign-up screen (mode = "login" | "signup").
 *
 * Email + password only. We deliberately do NOT ask for a phone number — DayBreak
 * is teen-centered and keeps required data minimal. Email/phone are owned by
 * Supabase Auth, never written to the public profiles table.
 */
export function AuthPage({ mode = 'login' }) {
  const isSignup = mode === 'signup';
  const navigate = useNavigate();
  const { configured, signIn, signUp, signInWithGoogle } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const google = async () => {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      // Redirects to Google on success; the returned session is picked up by
      // AuthProvider's onAuthStateChange listener, so no navigate() here.
      const { error: authError } = await signInWithGoogle();
      if (authError) {
        setError(authError.message);
        setBusy(false);
      }
    } catch (err) {
      setError(err?.message || 'Something went wrong. Please try again.');
      setBusy(false);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    setNotice(null);
    if (isSignup && password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
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
      // Login is the last first-run step: head to the feed. FirstRunGate saves any
      // pending diagnostic answers there and opens the recommended mode.
      navigate('/');
    } catch (err) {
      setError(err?.message || 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <CxShell center>
      <Link to="/" className="cx-shell__back" aria-label="Back to your feed">
        <ArrowLeft size={18} aria-hidden="true" /> Back
      </Link>

      <div className="cx-card cx-card--auth db-auth-card" aria-busy={busy}>
        <DayBreakAuthBrand />

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

        <button
          type="button"
          className="cx-btn cx-btn--google"
          onClick={google}
          disabled={!configured || busy}
        >
          <svg className="cx-google-icon" viewBox="0 0 18 18" width="18" height="18" aria-hidden="true">
            <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z" />
            <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z" />
            <path fill="#FBBC05" d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33z" />
            <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.46 3.44 1.35l2.58-2.58C13.47.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z" />
          </svg>
          Continue with Google
        </button>

        <div className="cx-divider" aria-hidden="true"><span>or</span></div>

        <form className="cx-form" onSubmit={submit} aria-describedby={error ? 'auth-error' : undefined}>
          <label className="cx-field">
            <span className="cx-field__label">Email</span>
            <input
              id={`${mode}-email`}
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={!configured || busy}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? 'auth-error' : undefined}
            />
          </label>
          <label className="cx-field">
            <span className="cx-field__label">Password</span>
            <input
              id={`${mode}-password`}
              type="password"
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 6 characters"
              disabled={!configured || busy}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? 'auth-error' : undefined}
            />
          </label>

          {isSignup && (
            <label className="cx-field">
              <span className="cx-field__label">Confirm password</span>
              <input
                id="signup-confirm-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={6}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Re-enter your password"
                disabled={!configured || busy}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? 'auth-error' : undefined}
              />
            </label>
          )}

          {!isSignup && (
            <p className="cx-form__forgot">
              <Link to="/forgot-password">Forgot password?</Link>
            </p>
          )}

          {error && <p id="auth-error" className="cx-form__error" role="alert">{error}</p>}
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
            <>New to DayBreak? <Link to="/signup">Create your space</Link></>
          )}
        </p>
      </div>
    </CxShell>
  );
}
