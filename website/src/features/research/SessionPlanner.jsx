import { Check, ChevronRight, Minus, Plus, RotateCcw } from 'lucide-react';
import {
  ALLOWED_VIDEO_COUNTS,
  COOLDOWN_INCREMENT_SECONDS,
  INTENTIONS,
  MAX_COOLDOWN_SECONDS,
  MIN_COOLDOWN_SECONDS,
  estimateDurationSeconds,
} from './sessionContract.js';
import { isPlanningDraftComplete, suggestLowerVideoCount } from './sessionMachine.js';

const INTENTION_DETAILS = Object.freeze([
  Object.freeze({
    value: INTENTIONS[0],
    label: 'Relax',
    description: 'Slow down for a little while.',
  }),
  Object.freeze({
    value: INTENTIONS[1],
    label: 'Learn',
    description: 'Find something interesting.',
  }),
  Object.freeze({
    value: INTENTIONS[2],
    label: 'Feel inspired',
    description: 'Find ideas, creativity, or motivation.',
  }),
  Object.freeze({
    value: INTENTIONS[3],
    label: 'Catch up',
    description: "See what you've been interested in lately.",
  }),
  Object.freeze({
    value: INTENTIONS[4],
    label: 'Take a quick break',
    description: 'A small reset before getting back to your day.',
  }),
]);

function intentionLabel(intention) {
  return INTENTION_DETAILS.find((option) => option.value === intention)?.label ?? 'Your intention';
}

function formatEstimatedDuration(seconds) {
  if (!Number.isFinite(seconds)) return 'estimated time unavailable';
  return `about ${Math.round(seconds / 60)} min`;
}

function minutes(seconds) {
  return Math.round(seconds / 60);
}

function PlannerError({ error, draft, onRetry, onClearError, onVideoCountChange }) {
  if (!error) return null;

  if ([
    'authentication_required',
    'invalid_credential',
    'participant_inactive',
    'participant_credential_error',
  ].includes(error.errorCode)) {
    return (
      <div className="study-error" id="plan-error" role="alert">
        <strong>Study initialization error</strong>
        <p>Your participant credential could not be verified. Your choices and stored credential have not been cleared.</p>
      </div>
    );
  }

  if (error.errorCode === 'insufficient_inventory') {
    const availableCount = error.details?.available_count;
    const requestedCount = error.details?.requested_count ?? draft.plannedVideoCount;
    const suggestion = suggestLowerVideoCount(availableCount, requestedCount);
    return (
      <div className="study-error" id="plan-error" role="alert">
        <strong>That session is a little too large right now.</strong>
        {suggestion ? (
          <>
            <p>DayBreak currently has enough unique videos for a smaller session.</p>
            <button type="button" className="study-text-action" onClick={() => onVideoCountChange(suggestion)}>
              Try {suggestion} videos instead
              <ChevronRight aria-hidden="true" />
            </button>
          </>
        ) : (
          <p>DayBreak doesn&apos;t have enough unique videos for a session right now. Try again later.</p>
        )}
      </div>
    );
  }

  if (error.retryable) {
    return (
      <div className="study-error" id="plan-error" role="alert">
        <strong>DayBreak couldn&apos;t reach the study service.</strong>
        <p>Your choices are still here. You can try again.</p>
        <button type="button" className="study-text-action" onClick={onRetry}>
          <RotateCcw aria-hidden="true" />
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="study-error" id="plan-error" role="alert">
      <strong>We couldn&apos;t save this plan.</strong>
      <p>{error.message || 'Check your choices and try again.'}</p>
      <button type="button" className="study-text-action" onClick={onClearError}>
        Back to plan
      </button>
    </div>
  );
}

export function SessionPlanner({
  draft,
  command,
  error,
  onIntentionChange,
  onVideoCountChange,
  onCooldownChange,
  onReview,
  onClearError,
}) {
  const isComplete = isPlanningDraftComplete(draft);
  const cooldownMinutes = draft.selectedCooldownSeconds
    ? minutes(draft.selectedCooldownSeconds)
    : null;
  const minCooldown = MIN_COOLDOWN_SECONDS / 60;
  const maxCooldown = MAX_COOLDOWN_SECONDS / 60;
  const step = COOLDOWN_INCREMENT_SECONDS / 60;

  function adjustCooldown(direction) {
    const nextMinutes = Math.min(
      maxCooldown,
      Math.max(minCooldown, cooldownMinutes + (direction * step)),
    );
    onCooldownChange(nextMinutes * 60);
  }

  return (
    <main className="study-flow study-flow--planner">
      <div className="study-flow__ambient" aria-hidden="true" />
      <form className="study-panel study-panel--planner" onSubmit={(event) => {
        event.preventDefault();
        if (isComplete && !command.pending) onReview();
      }}>
        <header className="study-panel__header study-panel__header--compact">
          <p className="study-eyebrow">Plan your DayBreak</p>
          <h1>A small choice before you scroll</h1>
          <p>Choose a boundary that feels right for this moment.</p>
        </header>

        <fieldset className="study-fieldset">
          <legend>What do you want from this break?</legend>
          <div className="study-intention-grid">
            {INTENTION_DETAILS.map((option) => (
              <label className="study-choice study-choice--intention" key={option.value}>
                <input
                  type="radio"
                  name="intention"
                  value={option.value}
                  checked={draft.intention === option.value}
                  disabled={command.pending}
                  onChange={() => onIntentionChange(option.value)}
                />
                <span className="study-choice__indicator" aria-hidden="true">
                  <Check />
                </span>
                <span>
                  <strong>{option.label}</strong>
                  <small>{option.description}</small>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        {draft.intention && (
          <fieldset className="study-fieldset study-reveal">
            <legend>How much do you want to scroll?</legend>
            <div className="study-count-grid">
              {ALLOWED_VIDEO_COUNTS.map((count) => {
                const estimatedSeconds = estimateDurationSeconds(count);
                return (
                  <label className="study-choice study-choice--count" key={count}>
                    <input
                      type="radio"
                      name="video-count"
                      value={count}
                      checked={draft.plannedVideoCount === count}
                      disabled={command.pending}
                      onChange={() => onVideoCountChange(count)}
                    />
                    <span className="study-choice__indicator" aria-hidden="true">
                      <Check />
                    </span>
                    <strong>{count} videos</strong>
                    <small>{formatEstimatedDuration(estimatedSeconds)}</small>
                  </label>
                );
              })}
            </div>
          </fieldset>
        )}

        {draft.plannedVideoCount && (
          <fieldset className="study-fieldset study-reveal">
            <legend>How long do you want to step away afterward?</legend>
            <p className="study-recommendation" id="cooldown-recommendation">
              DayBreak suggests <strong>{minutes(draft.recommendedCooldownSeconds)} minutes away</strong>{' '}
              after this session.
              <small>You can change this before you begin.</small>
            </p>
            <div
              className="study-stepper"
              role="group"
              aria-label="Cooldown duration in five-minute increments"
              aria-describedby="cooldown-recommendation"
            >
              <button
                type="button"
                aria-label="Decrease cooldown by 5 minutes"
                onClick={() => adjustCooldown(-1)}
                disabled={command.pending || cooldownMinutes <= minCooldown}
              >
                <Minus aria-hidden="true" />
              </button>
              <output aria-live="polite" htmlFor="cooldown-duration">
                <strong>{cooldownMinutes}</strong>
                <span>minutes away</span>
              </output>
              <button
                type="button"
                aria-label="Increase cooldown by 5 minutes"
                onClick={() => adjustCooldown(1)}
                disabled={command.pending || cooldownMinutes >= maxCooldown}
              >
                <Plus aria-hidden="true" />
              </button>
            </div>
            <input
              id="cooldown-duration"
              className="study-visually-hidden"
              tabIndex="-1"
              aria-hidden="true"
              readOnly
              value={cooldownMinutes}
            />
          </fieldset>
        )}

        {isComplete && (
          <section className="study-plan-summary study-reveal" aria-labelledby="draft-summary-title">
            <p className="study-eyebrow" id="draft-summary-title">Your DayBreak</p>
            <strong>{intentionLabel(draft.intention)}</strong>
            <span>
              {draft.plannedVideoCount} videos · {formatEstimatedDuration(draft.estimatedDurationSeconds)}
            </span>
            <span>Then {cooldownMinutes} minutes away</span>
          </section>
        )}

        <PlannerError
          error={error}
          draft={draft}
          onRetry={onReview}
          onClearError={onClearError}
          onVideoCountChange={onVideoCountChange}
        />

        <footer className="study-panel__footer study-panel__footer--sticky">
          <button
            className="study-button study-button--primary study-button--wide"
            type="submit"
            disabled={!isComplete || command.pending}
            aria-describedby={error ? 'plan-error' : undefined}
          >
            {command.pending ? 'Saving your choices…' : 'Review my plan'}
            {!command.pending && <ChevronRight aria-hidden="true" />}
          </button>
          {!isComplete && <small>Choose an intention, video count, and cooldown to continue.</small>}
          <span className="study-visually-hidden" role="status" aria-live="polite">
            {command.pending ? 'Saving your plan.' : ''}
          </span>
        </footer>
      </form>
    </main>
  );
}
