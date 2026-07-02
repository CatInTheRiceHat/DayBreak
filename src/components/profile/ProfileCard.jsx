import { Compass, Lock, Sparkles, Pencil } from 'lucide-react';

/**
 * Presentational profile header — avatar, display name, @username, bio, and the
 * Chrysalis intention / current-mode chips. No raw DB fields, no email/phone, no
 * internal flags (e.g. profile_completed) are ever shown here.
 */
const MODE_LABELS = {
  'daily-dew': 'Daily Dew',
  'flutter-feed': "Cruisin'",
  metamorphosis: 'Metamorphosis',
};

function modeLabel(mode) {
  if (!mode) return null;
  return MODE_LABELS[mode] || mode;
}

export function ProfileCard({ profile, isOwner = false, onEdit }) {
  if (!profile) return null;
  const name = profile.display_name || `@${profile.username}`;
  const mode = modeLabel(profile.current_mode);

  return (
    <section className="cx-profilecard" aria-label="Profile">
      <div className="cx-profilecard__top">
        <span className="cx-avatar cx-avatar--lg">
          {profile.avatar_url
            ? <img src={profile.avatar_url} alt={`${name}'s avatar`} />
            : <span className="cx-avatar__fallback" aria-hidden="true">🌊</span>}
        </span>

        <div className="cx-profilecard__meta">
          <div className="cx-profilecard__namerow">
            <h1 className="cx-profilecard__name">{name}</h1>
            {profile.is_private && (
              <span className="cx-chip cx-chip--muted" title="Private profile">
                <Lock size={12} aria-hidden="true" /> Private
              </span>
            )}
          </div>
          <p className="cx-profilecard__handle">@{profile.username}</p>
          {profile.pronouns && (
            <p className="cx-profilecard__pronouns">{profile.pronouns}</p>
          )}
          {isOwner && (
            <button type="button" className="cx-btn cx-btn--soft cx-profilecard__edit" onClick={onEdit}>
              <Pencil size={14} aria-hidden="true" /> Edit profile
            </button>
          )}
        </div>
      </div>

      {profile.bio && <p className="cx-profilecard__bio">{profile.bio}</p>}

      <div className="cx-profilecard__chips">
        {profile.intention && (
          <span className="cx-chip cx-chip--accent">
            <Sparkles size={13} aria-hidden="true" /> {profile.intention}
          </span>
        )}
        {mode && (
          <span className="cx-chip">
            <Compass size={13} aria-hidden="true" /> {mode}
          </span>
        )}
        {profile.location_label && (
          <span className="cx-chip cx-chip--muted">{profile.location_label}</span>
        )}
        {profile.website_url && (
          <a
            className="cx-chip cx-chip--link"
            href={profile.website_url}
            target="_blank"
            rel="noreferrer noopener"
          >
            {profile.website_url.replace(/^https?:\/\//, '')}
          </a>
        )}
      </div>
    </section>
  );
}
