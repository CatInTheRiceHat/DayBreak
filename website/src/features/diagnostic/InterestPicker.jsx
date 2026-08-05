import { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { INTERESTS } from '../reels/profileData';

const MIN_PICKS = 3;

/**
 * "What are you into?" — a grid of topic chips shown right after the diagnostic
 * result. Multi-select, at least three, then continue. The chosen interest ids
 * map straight onto profile.interests and drive the feed's interest boost.
 *
 * Props:
 *   ctaLabel — button text (varies for signed-in vs signed-out)
 *   onDone(interests) — continue with the chosen interest ids
 */
export function InterestPicker({ ctaLabel = 'Continue', onDone }) {
  const [picked, setPicked] = useState([]);
  const enough = picked.length >= MIN_PICKS;

  const toggle = (id) => {
    setPicked((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  };

  return (
    <div className="cx-card cx-card--auth">
      <p className="diag-result__eyebrow">One more thing</p>
      <h1 className="cx-card__title">What are you into?</h1>
      <p className="cx-card__lede">
        Pick at least {MIN_PICKS} — we’ll weave more of these into your feed.
      </p>

      <div className="interest-grid" role="group" aria-label="Choose your interests">
        {INTERESTS.map((it) => {
          const on = picked.includes(it.id);
          return (
            <button
              key={it.id}
              type="button"
              className={`interest-chip${on ? ' is-selected' : ''}`}
              aria-pressed={on}
              onClick={() => toggle(it.id)}
            >
              <span className="interest-chip__emoji" aria-hidden="true">{it.emoji}</span>
              {it.label}
            </button>
          );
        })}
      </div>

      <p className="diag-quiz__count" aria-live="polite">
        {picked.length}/{MIN_PICKS} chosen{enough ? ' ✓' : ''}
      </p>

      <button
        type="button"
        className="cx-btn cx-btn--primary"
        disabled={!enough}
        onClick={() => onDone(picked)}
      >
        {ctaLabel}
        <ArrowRight size={16} aria-hidden="true" />
      </button>
    </div>
  );
}
