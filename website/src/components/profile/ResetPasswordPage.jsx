import { BRAND } from '../../brand.js';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Loader2 } from 'lucide-react';
import { useAuth } from '../../lib/authContext';
import { CxShell } from './CxShell';

/**
 * Set a new password. Reached from the emailed reset link, which lands here with
 * a temporary recovery session (Supabase picks it up via detectSessionInUrl).
 * We simply update the password on the active session.
 */
export function ResetPasswordPage() {
  const navigate = useNavigate();
  const { configured, updatePassword } = useAuth();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      const { error: authError } = await updatePassword(password);
      if (authError) {
        setError(authError.message);
        return;
      }
      setDone(true);
      setTimeout(() => navigate('/profile'), 1200);
    } catch (err) {
      setError(err?.message || 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <CxShell center>
      <div className="cx-card cx-card--auth">
        <div className="cx-brand">
          <span className="cx-brand__logo" aria-hidden="true"><img src="/images/logo.png" alt="" /></span>
          <span className="cx-brand__word">{BRAND}</span>
        </div>

        <h1 className="cx-card__title">Choose a new password</h1>
        <p className="cx-card__lede">Pick something you'll remember this time.</p>

        {!configured && (
          <p className="cx-form__notice" role="status">
            Sign-in is being set up for this space. Please check back soon.
          </p>
        )}

        {done ? (
          <p className="cx-form__notice" role="status">
            Password updated — taking you to your profile…
          </p>
        ) : (
          <form className="cx-form" onSubmit={submit}>
            <label className="cx-field">
              <span className="cx-field__label">New password</span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
                disabled={!configured || busy}
              />
            </label>
            <label className="cx-field">
              <span className="cx-field__label">Confirm new password</span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={6}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Re-enter your password"
                disabled={!configured || busy}
              />
            </label>

            {error && <p className="cx-form__error" role="alert">{error}</p>}

            <button type="submit" className="cx-btn cx-btn--primary" disabled={!configured || busy}>
              {busy ? <Loader2 size={16} className="cx-spin" aria-hidden="true" /> : null}
              Update password
              {!busy && <ArrowRight size={16} aria-hidden="true" />}
            </button>
          </form>
        )}

        <p className="cx-card__switch">
          <Link to="/login">Back to log in</Link>
        </p>
      </div>
    </CxShell>
  );
}
