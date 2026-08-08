import { ArrowLeft, ArrowRight, Check, LoaderCircle } from 'lucide-react';
import { INTENTIONS } from './sessionContract.js';

const INTENTION_LABELS = Object.freeze([
  'Relax',
  'Learn',
  'Feel inspired',
  'Catch up',
  'Take a quick break',
]);

function intentionLabel(intention) {
  const index = INTENTIONS.indexOf(intention);
  return index >= 0 ? INTENTION_LABELS[index] : 'Your intention';
}

function estimatedDuration(seconds) {
  return Number.isFinite(seconds)
    ? `about ${Math.round(seconds / 60)} minutes`
    : 'estimated time unavailable';
}

function minutes(seconds) {
  return Number.isFinite(seconds) ? Math.round(seconds / 60) : '—';
}

export function SessionPlanConfirmation({
  journey,
  startCommand,
  cancelCommand,
  error,
  onBegin,
  onChangePlan,
  onClearError,
}) {
  const pending = startCommand.pending || cancelCommand.pending;
  const errorId = error ? 'confirmation-error' : undefined;
  const authError = [
    'authentication_required',
    'invalid_credential',
    'participant_inactive',
    'participant_credential_error',
  ].includes(error?.errorCode);

  return (
    <main className="study-flow">
      <div className="study-flow__ambient" aria-hidden="true" />
      <section className="study-panel study-panel--confirmation" aria-labelledby="confirmation-title">
        <header className="study-panel__header">
          <div className="study-confirmation-mark" aria-hidden="true">
            <Check />
          </div>
          <p className="study-eyebrow">Your plan is saved</p>
          <h1 id="confirmation-title">Ready for your DayBreak?</h1>
        </header>

        <div className="study-authoritative-summary">
          <strong>{intentionLabel(journey.intention)}</strong>
          <span>
            {journey.planned_video_count} videos · {estimatedDuration(journey.estimated_duration_seconds)}
          </span>
          <span>Afterward: {minutes(journey.selected_cooldown_seconds)} minutes away</span>
        </div>

        <p className="study-boundary-copy">
          You chose the boundary. DayBreak will stop the session when you reach it.
        </p>

        {error && (
          <div className="study-error" id="confirmation-error" role="alert">
            <strong>
              {authError
                ? 'Study initialization error'
                : error.retryable
                ? "DayBreak couldn't reach the study service."
                : 'Your saved plan has not changed.'}
            </strong>
            <p>
              {authError
                ? 'Your participant credential could not be verified. Your saved plan and credential have not been cleared.'
                : error.retryable
                ? 'Your plan is still here. You can try again.'
                : (error.message || 'Please try again when you are ready.')}
            </p>
            <button className="study-text-action" type="button" onClick={onClearError}>
              Dismiss message
            </button>
          </div>
        )}

        <footer className="study-panel__footer study-confirmation-actions" aria-busy={pending ? 'true' : undefined}>
          <button
            className="study-button study-button--primary study-button--wide"
            type="button"
            onClick={onBegin}
            disabled={pending}
            aria-describedby={errorId}
          >
            {startCommand.pending ? (
              <>
                <LoaderCircle className="study-spinner" aria-hidden="true" />
                Starting your DayBreak…
              </>
            ) : (
              <>
                Begin my break
                <ArrowRight aria-hidden="true" />
              </>
            )}
          </button>
          <button
            className="study-button study-button--secondary study-button--wide"
            type="button"
            onClick={onChangePlan}
            disabled={pending}
            aria-describedby={errorId}
          >
            {cancelCommand.pending ? (
              <>
                <LoaderCircle className="study-spinner" aria-hidden="true" />
                Reopening your plan…
              </>
            ) : (
              <>
                <ArrowLeft aria-hidden="true" />
                Change my plan
              </>
            )}
          </button>
          <span className="study-visually-hidden" role="status" aria-live="polite">
            {startCommand.pending
              ? 'Starting your saved session.'
              : cancelCommand.pending
                ? 'Cancelling the saved plan before reopening the planner.'
                : ''}
          </span>
        </footer>
      </section>
    </main>
  );
}
