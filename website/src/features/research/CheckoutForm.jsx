import { useEffect, useRef } from 'react';
import { ArrowRight, Check, LoaderCircle } from 'lucide-react';
import {
  MOOD_VALUES,
  PERCEIVED_CONTROL_VALUES,
  WORTHWHILE_VALUES,
  isValidCheckoutAnswers,
} from './sessionContract.js';
import { createJourneySynchronizer } from './intentionalBreakFeedState.js';

const WORTHWHILE_LABELS = Object.freeze({
  yes: 'Yes',
  mostly: 'Mostly',
  not_really: 'Not really',
  prefer_not_to_answer: 'Prefer not to answer',
});

const MOOD_LABELS = Object.freeze({
  better: 'Better',
  same: 'About the same',
  worse: 'Worse',
  prefer_not_to_answer: 'Prefer not to answer',
});

function Choice({ name, value, checked, disabled, onChange, children }) {
  return (
    <label className="study-checkout-choice">
      <input
        type="radio"
        name={name}
        checked={checked}
        disabled={disabled}
        onChange={() => onChange(value)}
      />
      <span className="study-checkout-choice__mark" aria-hidden="true"><Check /></span>
      <span>{children}</span>
    </label>
  );
}

export function CheckoutForm({
  sessionId,
  draft,
  command,
  error,
  onAnswer,
  onSubmit,
  onReconcile,
}) {
  const headingRef = useRef(null);
  const complete = isValidCheckoutAnswers(draft);
  const pending = command?.pending === true;

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!sessionId || typeof onReconcile !== 'function') return undefined;
    const synchronizer = createJourneySynchronizer({ sessionId, onChange: onReconcile });
    const reconcileVisible = () => {
      if (document.visibilityState === 'visible') onReconcile();
    };
    window.addEventListener('focus', onReconcile);
    document.addEventListener('visibilitychange', reconcileVisible);
    return () => {
      synchronizer.destroy();
      window.removeEventListener('focus', onReconcile);
      document.removeEventListener('visibilitychange', reconcileVisible);
    };
  }, [onReconcile, sessionId]);

  function submit(event) {
    event.preventDefault();
    if (complete && !pending) onSubmit(draft);
  }

  return (
    <main className="study-flow study-flow--checkout">
      <div className="study-flow__ambient" aria-hidden="true" />
      <form className="study-panel study-panel--checkout" onSubmit={submit} aria-busy={pending || undefined}>
        <header className="study-panel__header study-panel__header--compact">
          <p className="study-eyebrow">Your session is complete</p>
          <h1 id="checkout-title" ref={headingRef} tabIndex="-1">How was that break?</h1>
          <p>Three quick questions before you step away.</p>
        </header>

        <fieldset className="study-fieldset study-checkout-question">
          <legend>Was this break worth your time?</legend>
          <div className="study-checkout-options study-checkout-options--four">
            {WORTHWHILE_VALUES.map((value) => (
              <Choice
                key={value}
                name="worthwhile"
                value={value}
                checked={draft.worthwhile === value}
                disabled={pending}
                onChange={(answer) => onAnswer('worthwhile', answer)}
              >
                {WORTHWHILE_LABELS[value]}
              </Choice>
            ))}
          </div>
        </fieldset>

        <fieldset className="study-fieldset study-checkout-question">
          <legend>How in control did you feel?</legend>
          <div className="study-control-scale">
            <span>Not at all</span>
            <span>Completely</span>
          </div>
          <div className="study-checkout-options study-checkout-options--scale">
            {PERCEIVED_CONTROL_VALUES.map((value) => (
              <Choice
                key={value}
                name="perceived-control"
                value={value}
                checked={draft.perceivedControl === value}
                disabled={pending}
                onChange={(answer) => onAnswer('perceivedControl', answer)}
              >
                {value === 'prefer_not_to_answer' ? 'Prefer not to answer' : value}
              </Choice>
            ))}
          </div>
        </fieldset>

        <fieldset className="study-fieldset study-checkout-question">
          <legend>How do you feel now?</legend>
          <div className="study-checkout-options study-checkout-options--four">
            {MOOD_VALUES.map((value) => (
              <Choice
                key={value}
                name="mood"
                value={value}
                checked={draft.mood === value}
                disabled={pending}
                onChange={(answer) => onAnswer('mood', answer)}
              >
                {MOOD_LABELS[value]}
              </Choice>
            ))}
          </div>
        </fieldset>

        {error && (
          <div className="study-error" id="checkout-error" role="alert">
            <strong>{error.retryable ? "We couldn't submit that yet." : 'Your answers were not submitted.'}</strong>
            <p>{error.retryable ? 'Your answers are still here.' : (error.message || 'Please review your answers and try again.')}</p>
          </div>
        )}

        <footer className="study-panel__footer study-checkout-footer">
          <button
            className="study-button study-button--primary study-button--wide"
            type="submit"
            disabled={!complete || pending}
            aria-describedby={error ? 'checkout-error' : undefined}
          >
            {pending ? (
              <><LoaderCircle className="study-spinner" aria-hidden="true" /> Starting your time away…</>
            ) : error?.retryable ? (
              <>Try again <ArrowRight aria-hidden="true" /></>
            ) : (
              <>Start my time away <ArrowRight aria-hidden="true" /></>
            )}
          </button>
          {!complete && <small>Choose one answer for each question to continue.</small>}
          <span className="study-visually-hidden" role="status" aria-live="polite">
            {pending ? 'Submitting your three checkout answers.' : ''}
          </span>
        </footer>
      </form>
    </main>
  );
}
