import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeft, Check, Loader2 } from 'lucide-react';
import { useAuth } from '../../lib/authContext';
import { getMyProfile, updateMyProfile } from '../../lib/profileApi';
import { CxShell } from './CxShell';
import { AvatarUploader } from './AvatarUploader';

const MODE_OPTIONS = [
  { value: '', label: 'Not set' },
  { value: 'daily-dew', label: 'Daily Dew' },
  { value: 'flutter-feed', label: "Cruisin'" },
  { value: 'metamorphosis', label: 'Metamorphosis' },
];

const USERNAME_RE = /^[a-z0-9_.]{3,30}$/;
const EMPTY = {
  username: '', display_name: '', bio: '', avatar_url: '', pronouns: '',
  location_label: '', website_url: '', intention: '', current_mode: '',
  is_private: false, allow_messages: true,
};

export function EditProfileForm() {
  const navigate = useNavigate();
  const { configured, user, loading: authLoading } = useAuth();
  const [form, setForm] = useState(EMPTY);
  const [status, setStatus] = useState('loading'); // loading | ready | unconfigured
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const canLoad = configured && !authLoading && Boolean(user);

  useEffect(() => {
    if (!canLoad) return undefined;
    let active = true;
    getMyProfile()
      .then((data) => {
        if (!active) return;
        setForm({ ...EMPTY, ...Object.fromEntries(
          Object.keys(EMPTY).map((k) => [k, data?.[k] ?? EMPTY[k]]),
        ) });
        setStatus('ready');
      })
      .catch(() => { if (active) setStatus('ready'); });
    return () => { active = false; };
  }, [canLoad]);

  const set = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
  };

  const save = async (event) => {
    event.preventDefault();
    setError(null);
    const username = form.username.trim().toLowerCase();
    if (!USERNAME_RE.test(username)) {
      setError('Username must be 3–30 characters: lowercase letters, numbers, “.” or “_”.');
      return;
    }
    setSaving(true);
    try {
      await updateMyProfile({ ...form, username, profile_completed: true });
      navigate('/profile');
    } catch (err) {
      // Friendly message for the unique-username constraint.
      const msg = /duplicate|unique/i.test(err?.message || '')
        ? 'That username is taken — try another.'
        : (err?.message || 'Could not save your profile. Please try again.');
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (!configured) {
    return (
      <CxShell>
        <div className="cx-card cx-state-card">
          <h1 className="cx-card__title">Profiles are being set up.</h1>
          <Link to="/algorithm" className="cx-btn cx-btn--primary">Back to your feed</Link>
        </div>
      </CxShell>
    );
  }
  if (authLoading) {
    return (
      <CxShell>
        <div className="cx-state"><Loader2 size={22} className="cx-spin" aria-hidden="true" /> Loading…</div>
      </CxShell>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <CxShell wide>
      <Link to="/profile" className="cx-shell__back" aria-label="Back to your profile">
        <ArrowLeft size={18} aria-hidden="true" /> Profile
      </Link>

      <div className="cx-card cx-card--form">
        <h1 className="cx-card__title">Shape your scroll around your intention.</h1>
        <p className="cx-card__lede">A profile for how you want to feel online.</p>

        {status === 'loading' ? (
          <div className="cx-state"><Loader2 size={22} className="cx-spin" aria-hidden="true" /> Loading…</div>
        ) : (
          <form className="cx-form" onSubmit={save}>
            <AvatarUploader
              currentUrl={form.avatar_url}
              displayName={form.display_name}
              onUploaded={(url) => setForm((f) => ({ ...f, avatar_url: url }))}
            />

            <label className="cx-field">
              <span className="cx-field__label">Username</span>
              <input value={form.username} onChange={set('username')} placeholder="yourname"
                autoCapitalize="none" autoCorrect="off" maxLength={30} />
              <span className="cx-field__hint">This is your @handle. Lowercase letters, numbers, “.” or “_”.</span>
            </label>

            <label className="cx-field">
              <span className="cx-field__label">Display name</span>
              <input value={form.display_name} onChange={set('display_name')} maxLength={50}
                placeholder="What should we call you?" />
            </label>

            <label className="cx-field">
              <span className="cx-field__label">Bio</span>
              <textarea value={form.bio} onChange={set('bio')} rows={3} maxLength={280}
                placeholder="A line about how you want your feed to feel…" />
            </label>

            <div className="cx-field-row">
              <label className="cx-field">
                <span className="cx-field__label">Pronouns <em>(optional)</em></span>
                <input value={form.pronouns} onChange={set('pronouns')} maxLength={40} placeholder="she/her, they/them…" />
              </label>
              <label className="cx-field">
                <span className="cx-field__label">Location <em>(optional)</em></span>
                <input value={form.location_label} onChange={set('location_label')} maxLength={60} placeholder="A city or vibe" />
              </label>
            </div>

            <label className="cx-field">
              <span className="cx-field__label">Intention</span>
              <input value={form.intention} onChange={set('intention')} maxLength={60}
                placeholder="e.g. Calmer mornings, less comparison" />
            </label>

            <div className="cx-field-row">
              <label className="cx-field">
                <span className="cx-field__label">Current mode</span>
                <select value={form.current_mode} onChange={set('current_mode')}>
                  {MODE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </label>
              <label className="cx-field">
                <span className="cx-field__label">Website <em>(optional)</em></span>
                <input type="url" value={form.website_url} onChange={set('website_url')} placeholder="https://" />
              </label>
            </div>

            <label className="cx-toggle">
              <input type="checkbox" checked={form.is_private} onChange={set('is_private')} />
              <span>
                <strong>Private profile</strong>
                <small>Only you can see your profile. Less noise. More intention.</small>
              </span>
            </label>
            <label className="cx-toggle">
              <input type="checkbox" checked={form.allow_messages} onChange={set('allow_messages')} />
              <span>
                <strong>Allow messages</strong>
                <small>Let connected friends reach out.</small>
              </span>
            </label>

            {error && <p className="cx-form__error" role="alert">{error}</p>}

            <div className="cx-form__actions">
              <Link to="/profile" className="cx-btn cx-btn--soft">Cancel</Link>
              <button type="submit" className="cx-btn cx-btn--primary" disabled={saving}>
                {saving ? <Loader2 size={16} className="cx-spin" aria-hidden="true" /> : <Check size={16} aria-hidden="true" />}
                Save profile
              </button>
            </div>
          </form>
        )}
      </div>
    </CxShell>
  );
}
