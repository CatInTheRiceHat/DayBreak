import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Loader2 } from 'lucide-react';
import { useAuth } from '../../lib/authContext';
import { CxShell } from './CxShell';
import { DayBreakAuthBrand } from './DayBreakAuthBrand';

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
      <div className="cx-card cx-card--auth db-auth-card" aria-busy={busy}>
        <DayBreakAuthBrand />

        <h1 className="cx-card__title">Choose a new password</h1>
        <p className="cx-card__lede">Choose a secure password you will be comfortable using.</p>

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
          <form className="cx-form" onSubmit={submit} aria-describedby={error ? 'reset-password-error' : undefined}>
            <label className="cx-field">
              <span className="cx-field__label">New password</span>
              <input
                id="reset-password-new"
                type="password"
                autoComplete="new-password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
                disabled={!configured || busy}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? 'reset-password-error' : undefined}
              />
            </label>
            <label className="cx-field">
              <span className="cx-field__label">Confirm new password</span>
              <input
                id="reset-password-confirm"
                type="password"
                autoComplete="new-password"
                required
                minLength={6}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Re-enter your password"
                disabled={!configured || busy}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? 'reset-password-error' : undefined}
              />
            </label>

            {error && <p id="reset-password-error" className="cx-form__error" role="alert">{error}</p>}

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
