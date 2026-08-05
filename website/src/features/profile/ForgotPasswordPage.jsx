import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-react';
import { useAuth } from '../../lib/authContext';
import { CxShell } from './CxShell';
import { DayBreakAuthBrand } from './DayBreakAuthBrand';

/**
 * Request a password reset. Enter your email and Supabase sends a reset link
 * that returns you to /reset-password to choose a new password.
 */
export function ForgotPasswordPage() {
  const { configured, resetPassword } = useAuth();
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { error: authError } = await resetPassword(email.trim());
      if (authError) {
        setError(authError.message);
        return;
      }
      setSent(true);
    } catch (err) {
      setError(err?.message || 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <CxShell center>
      <Link to="/login" className="cx-shell__back" aria-label="Back to log in">
        <ArrowLeft size={18} aria-hidden="true" /> Back
      </Link>

      <div className="cx-card cx-card--auth db-auth-card" aria-busy={busy}>
        <DayBreakAuthBrand />

        <h1 className="cx-card__title">Reset your password</h1>
        <p className="cx-card__lede">
          Enter your email and we'll send you a link to set a new one.
        </p>

        {!configured && (
          <p className="cx-form__notice" role="status">
            Sign-in is being set up for this space. Please check back soon.
          </p>
        )}

        {sent ? (
          <p className="cx-form__notice" role="status">
            Check your email — if an account exists for {email.trim() || 'that address'},
            a reset link is on its way. Open it to choose a new password.
          </p>
        ) : (
          <form className="cx-form" onSubmit={submit} aria-describedby={error ? 'forgot-password-error' : undefined}>
            <label className="cx-field">
              <span className="cx-field__label">Email</span>
              <input
                id="forgot-password-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={!configured || busy}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? 'forgot-password-error' : undefined}
              />
            </label>

            {error && <p id="forgot-password-error" className="cx-form__error" role="alert">{error}</p>}

            <button type="submit" className="cx-btn cx-btn--primary" disabled={!configured || busy}>
              {busy ? <Loader2 size={16} className="cx-spin" aria-hidden="true" /> : null}
              Send reset link
              {!busy && <ArrowRight size={16} aria-hidden="true" />}
            </button>
          </form>
        )}

        <p className="cx-card__switch">
          Remembered it? <Link to="/login">Log in</Link>
        </p>
      </div>
    </CxShell>
  );
}
