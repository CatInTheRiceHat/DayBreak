import { BRAND } from '../../brand.js';
import {
  Leaf,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Timer,
  X,
} from 'lucide-react';
import {
  FEED_BALANCE_COPY,
  getRecommendationInsight,
} from './feedTaxonomy';

const MODE_COPY = {
  'daily-dew': {
    label: 'Daily Dew',
    description: 'A short, gentle reset with calm and reflective content.',
    fallbackScores: {
      calm: 0.82,
      prosocial: 0.62,
      self_love: 0.58,
      reflection_value: 0.76,
      novelty: 0.28,
      comparison_risk: 0.08,
      shame_or_humiliation_risk: 0.06,
      ragebait: 0.04,
    },
  },
  metamorphosis: {
    label: 'Metamorphosis',
    description: 'A slower mode that prioritizes pauses, breaks, and scroll awareness.',
    fallbackScores: {
      calm: 0.9,
      prosocial: 0.42,
      self_love: 0.7,
      reflection_value: 0.8,
      novelty: 0.16,
      comparison_risk: 0.04,
      shame_or_humiliation_risk: 0.04,
      ragebait: 0.03,
    },
  },
  'flutter-feed': {
    label: "Cruisin'",
    description: 'A healthier personalized feed with more variety, control, and transparency.',
    fallbackScores: {
      calm: 0.48,
      prosocial: 0.58,
      self_love: 0.42,
      reflection_value: 0.5,
      novelty: 0.68,
      comparison_risk: 0.14,
      shame_or_humiliation_risk: 0.08,
      ragebait: 0.08,
    },
  },
};

const BALANCE_ROWS = [
  { key: 'calm', label: 'Calm' },
  { key: 'prosocial', label: 'Prosocial' },
  { key: 'self_love', label: 'Self-love' },
  { key: 'reflection_value', label: 'Reflection' },
  { key: 'novelty', label: 'Novelty' },
  { key: 'comparison_risk', label: 'Low comparison pressure', risk: true },
];

const TUNE_OPTIONS = [
  { key: 'calm', label: 'More calm' },
  { key: 'variety', label: 'More variety' },
  { key: 'comparison', label: 'Less comparison' },
  { key: 'shorter', label: 'Shorter session' },
  { key: 'uplifting', label: 'More uplifting' },
];

const TUNE_MESSAGES = {
  calm: 'Your algorithm is gently tuning toward calmer cards this session.',
  variety: 'Your algorithm is gently tuning toward a wider mix of sources and topics.',
  comparison: 'Your algorithm is gently tuning away from comparison-heavy signals.',
  uplifting: 'Your algorithm is gently tuning toward more prosocial and self-love signals.',
};

function clamp01(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(1, number));
}

function displayValue(value, isRisk = false) {
  const v = clamp01(value);
  return Math.round((isRisk ? 1 - v : v) * 100);
}

function statusLabel(feedStatus) {
  if (feedStatus === 'live') return 'Using live curated videos';
  if (feedStatus === 'mixed') return 'Mixed live videos + pause cards';
  return `Using sample ${BRAND} cards for now`;
}

function sessionPace(viewedCount) {
  if (viewedCount <= 1) return 'Settling in';
  if (viewedCount <= 5) return 'Gentle pace';
  return 'Pause soon';
}

function tuneMessages(selectedTunes, viewedCount) {
  const messages = selectedTunes
    .filter((key) => key !== 'shorter')
    .map((key) => TUNE_MESSAGES[key])
    .filter(Boolean);

  if (selectedTunes.includes('shorter')) {
    messages.push(viewedCount >= 3
      ? 'Want to take a cocoon break?'
      : 'Your algorithm is gently tuning toward a shorter, lighter session.');
  }

  return messages;
}

export function FeedCompassPanel({
  activeMode,
  activeCard,
  feedStatus,
  viewedCount,
  breakReminderCount,
  selectedTunes = [],
  onResetIntro,
  onTuneChange,
  onClose,
}) {
  const mode = MODE_COPY[activeMode] || MODE_COPY['flutter-feed'];
  const scores = activeCard?.chrysalis_scores || mode.fallbackScores;
  const recommendationInsight = getRecommendationInsight(activeCard);
  const whyText = recommendationInsight.detail
    || 'Shown because it matches your intention with lighter, calmer feed signals.';
  const shameRage = Math.max(
    clamp01(scores.shame_or_humiliation_risk),
    clamp01(scores.ragebait),
  );
  const lowShameRage = shameRage < 0.25;
  const sessionTuneMessages = tuneMessages(selectedTunes, viewedCount);

  return (
    <section className="feed-compass" aria-label="Feed details">
      <div className="feed-compass__head">
        <div>
          <span className="feed-compass__eyebrow">
            <Sparkles size={13} aria-hidden="true" />
            Feed details
          </span>
          <h2>{mode.label}</h2>
        </div>
        {onClose && (
          <button
            type="button"
            className="feed-compass__close"
            onClick={onClose}
            aria-label="Close feed details"
            autoFocus
          >
            <X size={16} aria-hidden="true" />
          </button>
        )}
      </div>

      <p className="feed-compass__mode-copy">{mode.description}</p>
      <p className="feed-compass__lede">Your feed is shaped around your intention — a softer scroll, designed with you in mind.</p>

      <div className="feed-compass__balance-copy">
        <Leaf size={15} aria-hidden="true" />
        <p>{FEED_BALANCE_COPY}</p>
      </div>

      <div className="feed-compass__section feed-compass__mode">
        <div>
          <span className="feed-compass__label">Your intention</span>
          <p>{mode.label}</p>
        </div>
        <button type="button" onClick={onResetIntro}>
          <RefreshCw size={13} aria-hidden="true" />
          Change intention
        </button>
      </div>

      <div className="feed-compass__status">
        <Leaf size={15} aria-hidden="true" />
        <span>{statusLabel(feedStatus)}</span>
      </div>

      <div className="feed-compass__section">
        <div className="feed-compass__section-title">
          <ShieldCheck size={15} aria-hidden="true" />
          <span>Healthy vs regular balance</span>
        </div>
        <div className="feed-compass__bars">
          {BALANCE_ROWS.map((row) => {
            const value = displayValue(scores[row.key], row.risk);
            return (
              <div className="feed-compass__bar-row" key={row.key}>
                <div className="feed-compass__bar-label">
                  <span>{row.label}</span>
                  <span>{value}%</span>
                </div>
                <div
                  className={`feed-compass__bar${row.risk ? ' feed-compass__bar--risk' : ''}`}
                  role="progressbar"
                  aria-label={row.label}
                  aria-valuemin="0"
                  aria-valuemax="100"
                  aria-valuenow={value}
                >
                  <span style={{ width: `${value}%` }} />
                </div>
              </div>
            );
          })}
        </div>
        <div className="feed-compass__risk-note">
          {lowShameRage ? 'Low shame/rage signal' : 'Some high-conflict signals flagged gently'}
        </div>
      </div>

      <div className="feed-compass__section">
        <span className="feed-compass__label">Why this video</span>
        <div className="feed-compass__why-card">
          {recommendationInsight.label && (
            <span className={`feed-compass__category feed-compass__category--${recommendationInsight.tone}`}>
              {recommendationInsight.label}
            </span>
          )}
          <p className="feed-compass__why-summary">{recommendationInsight.summary}</p>
          <p className="feed-compass__why">{whyText}</p>
        </div>
        {activeCard?.safety_reason && (
          <p className="feed-compass__safety">{activeCard.safety_reason}</p>
        )}
        {activeCard?.concern_reason && (
          <p className="feed-compass__concern">{activeCard.concern_reason}</p>
        )}
      </div>

      <div className="feed-compass__section">
        <div className="feed-compass__section-title">
          <Timer size={15} aria-hidden="true" />
          <span>Scroll awareness</span>
        </div>
        <div className="feed-compass__stats">
          <span>Posts viewed this session <strong>{viewedCount}</strong></span>
          <span>Current mode <strong>{mode.label}</strong></span>
          <span>Session pace <strong>{sessionPace(viewedCount)}</strong></span>
          <span>Break reminders shown <strong>{breakReminderCount}</strong></span>
        </div>
      </div>

      <div className="feed-compass__section">
        <div className="feed-compass__section-title">
          <SlidersHorizontal size={15} aria-hidden="true" />
          <span>Quick tune</span>
        </div>
        <div className="feed-compass__tunes" role="group" aria-label="Session algorithm tuning">
          {TUNE_OPTIONS.map((option) => {
            const selected = selectedTunes.includes(option.key);
            return (
              <button
                type="button"
                key={option.key}
                className={selected ? 'is-selected' : ''}
                aria-pressed={selected}
                onClick={() => onTuneChange(option.key)}
              >
                {option.label}
              </button>
            );
          })}
        </div>
        <p className="feed-compass__tune-note">
          {selectedTunes.length
            ? 'Saved for this session.'
            : 'Pick what you’d like more or less of this session.'}
        </p>
        {sessionTuneMessages.length > 0 && (
          <div className="feed-compass__tune-messages" aria-live="polite">
            {sessionTuneMessages.map((message) => (
              <p key={message}>{message}</p>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
