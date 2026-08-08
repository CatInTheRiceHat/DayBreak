import { useEffect, useRef } from 'react';
import { ArrowRight, Check, LoaderCircle, RefreshCw } from 'lucide-react';
import { durationMinutes } from './cooldownTime.js';

function finishReasonLabel(reason) {
  if (reason === 'boundary_reached') return 'Reached boundary';
  if (reason === 'finished_early') return 'Finished early';
  return null;
}

function cooldownOutcomeLabel(outcome) {
  if (outcome === 'completed') return 'Completed';
  if (outcome === 'overridden') return 'Ended early';
  return null;
}

export function SessionComplete({ journey, pending = false, error = null, onPlanAnother }) {
  const headingRef = useRef(null);
  const overridden = journey.cooldown_outcome === 'overridden';
  const finishReason = finishReasonLabel(journey.finish_reason);
  const cooldownOutcome = cooldownOutcomeLabel(journey.cooldown_outcome);
  const cooldownMinutes = durationMinutes(journey.selected_cooldown_seconds);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <main className="study-flow study-flow--complete">
      <div className="study-flow__ambient" aria-hidden="true" />
      <section className="study-panel study-panel--complete" aria-labelledby="complete-title">
        <header className="study-panel__header">
          <div className="study-complete-mark" aria-hidden="true"><Check /></div>
          <p className="study-eyebrow">DayBreak pilot</p>
          <h1 id="complete-title" ref={headingRef} tabIndex="-1">Your DayBreak is complete</h1>
          <p>{overridden
            ? 'You chose to return before your original reset ended.'
            : 'You finished the time away you chose.'}</p>
        </header>

        <dl className="study-complete-summary" aria-label="Session summary">
          {Number.isInteger(journey.planned_video_count) && (
            <div><dt>Planned session</dt><dd>{journey.planned_video_count} videos</dd></div>
          )}
          {finishReason && <div><dt>Feed finish</dt><dd>{finishReason}</dd></div>}
          {cooldownMinutes !== null && (
            <div><dt>Time away selected</dt><dd>{cooldownMinutes} minutes</dd></div>
          )}
          {cooldownOutcome && <div><dt>Time away</dt><dd>{cooldownOutcome}</dd></div>}
        </dl>

        {error && (
          <div className="study-error" id="plan-another-error" role="alert">
            <strong>We couldn't check for another DayBreak yet.</strong>
            <p>Your completed session has not changed. Please try again.</p>
          </div>
        )}

        <footer className="study-panel__footer">
          <button
            className="study-button study-button--primary study-button--wide"
            type="button"
            onClick={onPlanAnother}
            disabled={pending}
            aria-describedby={error ? 'plan-another-error' : undefined}
          >
            {pending ? (
              <><LoaderCircle className="study-spinner" aria-hidden="true" /> Checking…</>
            ) : error ? (
              <><RefreshCw aria-hidden="true" /> Try again</>
            ) : (
              <>Plan another DayBreak <ArrowRight aria-hidden="true" /></>
            )}
          </button>
        </footer>
      </section>
    </main>
  );
}
