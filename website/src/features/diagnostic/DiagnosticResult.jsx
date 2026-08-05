import { ArrowRight } from 'lucide-react';
import { MODES } from '../reels/reelsData';
import { FEATURES, MODE_BLURB } from './diagnosticData';

/**
 * The diagnostic result — framed as a personalized setup ("here's what we've
 * turned on for you"), not a label. Lists the unlocked features and the
 * recommended mode, then hands off (to sign-in, then the feed).
 *
 * Props:
 *   result   — { unlockedFeatures: string[], recommendedMode: string }
 *   ctaLabel — button text (varies for signed-in vs signed-out)
 *   onStart  — proceed (to login, or the feed if already signed in)
 */
export function DiagnosticResult({ result, ctaLabel = 'Start My Algorithm', onStart }) {
  const { unlockedFeatures = [], recommendedMode } = result;
  const mode = MODES.find((m) => m.key === recommendedMode);
  const features = unlockedFeatures.map((k) => FEATURES[k]).filter(Boolean);

  return (
    <div className="cx-card cx-card--auth diag-result">
      <p className="diag-result__eyebrow">Your DayBreak setup is ready</p>
      <h1 className="cx-card__title">Here’s what we turned on for you.</h1>
      <p className="cx-card__lede">
        Based on your answers, we’ve tuned your starting feed while keeping your choices visible.
      </p>

      <ul className="diag-unlocks">
        {features.map((f) => (
          <li key={f.key} className="diag-unlock">
            <span className="diag-unlock__emoji" aria-hidden="true">{f.emoji}</span>
            <span className="diag-unlock__text">
              <span className="diag-unlock__name">{f.name}</span>
              <span className="diag-unlock__desc">{f.desc}</span>
            </span>
          </li>
        ))}
      </ul>

      {mode && (
        <div className="diag-mode">
          <span className="diag-mode__logo" aria-hidden="true">
            {mode.logo ? <img src={mode.logo} alt="" /> : '✨'}
          </span>
          <span className="diag-unlock__text">
            <span className="diag-mode__eyebrow">Your mode</span>
            <span className="diag-unlock__name">{mode.label}</span>
            <span className="diag-unlock__desc">{MODE_BLURB[recommendedMode] || mode.description}</span>
          </span>
        </div>
      )}

      <button type="button" className="cx-btn cx-btn--primary" onClick={onStart}>
        {ctaLabel}
        <ArrowRight size={16} aria-hidden="true" />
      </button>
    </div>
  );
}
