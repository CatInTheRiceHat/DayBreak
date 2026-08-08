import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, Check, LoaderCircle, TimerReset } from 'lucide-react';
import { OVERRIDE_REASON_CODES, isValidOverrideReason } from './sessionContract.js';
import { createJourneySynchronizer } from './intentionalBreakFeedState.js';
import {
  createServerTimeReference,
  formatCountdown,
  remainingSecondsAt,
} from './cooldownTime.js';

const REASON_LABELS = Object.freeze({
  change_plan: 'I need to change my plan',
  opened_automatically: 'I opened DayBreak automatically',
  want_another_session: 'I want another session',
  other: 'Something else',
});

export function OverrideFlow({
  journey,
  serverTimestamp,
  reasonCode,
  command,
  onReasonChange,
  onConfirm,
  onKeepBreak,
  onReconcile,
}) {
  const headingRef = useRef(null);
  const pauseError = command?.error?.errorCode === 'override_pause_active'
    ? command.error
    : null;
  const availableAt = pauseError?.details?.override_available_at
    ?? journey.override_available_at;
  const reference = useMemo(() => createServerTimeReference({
    serverTimestamp: pauseError?.serverTimestamp ?? serverTimestamp,
    endsAt: availableAt,
    remainingSeconds: pauseError?.details?.remaining_pause_seconds,
  }), [availableAt, pauseError?.details?.remaining_pause_seconds, pauseError?.serverTimestamp, serverTimestamp]);
  const [clientNowMs, setClientNowMs] = useState(() => Date.now());
  const remainingSeconds = remainingSecondsAt(reference, clientNowMs);
  const available = remainingSeconds === 0;
  const validReason = isValidOverrideReason(reasonCode);

  useEffect(() => {
    headingRef.current?.focus();
    onReconcile();
  }, [onReconcile]);

  useEffect(() => {
    if (!reference) return undefined;
    const timer = window.setInterval(() => setClientNowMs(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, [reference]);

  useEffect(() => {
    const synchronizer = createJourneySynchronizer({
      sessionId: journey.session_id,
      onChange: onReconcile,
    });
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
  }, [journey.session_id, onReconcile]);

  return (
    <main className="study-flow study-flow--cooldown">
      <div className="study-flow__ambient" aria-hidden="true" />
      <section className="study-panel study-panel--override" aria-labelledby="override-title">
        <header className="study-panel__header">
          <div className="study-cooldown-mark" aria-hidden="true"><TimerReset /></div>
          <p className="study-eyebrow">A deliberate return</p>
          <h1 id="override-title" ref={headingRef} tabIndex="-1">Do you still want to come back?</h1>
          <p>Give it a few seconds before deciding.</p>
        </header>

        <div className="study-override-pause" aria-describedby="override-pause-copy">
          <span id="override-pause-copy">Pause before returning</span>
          <time aria-hidden="true">{formatCountdown(remainingSeconds)}</time>
          <span className="study-visually-hidden" role="status" aria-live="polite">
            {available ? 'The return option is now available.' : 'The deliberate return pause is active.'}
          </span>
        </div>

        <fieldset className="study-fieldset study-override-reasons">
          <legend>What brought you back?</legend>
          <div className="study-override-options">
            {OVERRIDE_REASON_CODES.map((value) => (
              <label className="study-checkout-choice" key={value}>
                <input
                  type="radio"
                  name="override-reason"
                  checked={reasonCode === value}
                  disabled={command?.pending}
                  onChange={() => onReasonChange(value)}
                />
                <span className="study-checkout-choice__mark" aria-hidden="true"><Check /></span>
                <span>{REASON_LABELS[value]}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {pauseError && (
          <div className="study-timing-note" role="status">
            <strong>A few more seconds.</strong>
            <span>The study service is keeping the original pause time.</span>
          </div>
        )}

        {command?.error && !pauseError && (
          <div className="study-error" id="override-confirm-error" role="alert">
            <strong>We couldn't confirm that yet.</strong>
            <p>{command.error.retryable
              ? 'Your choice is still here. You can try again.'
              : 'DayBreak will check the current reset before anything changes.'}</p>
          </div>
        )}

        <footer className="study-panel__footer study-override-actions">
          <button
            className="study-button study-button--primary study-button--wide"
            type="button"
            onClick={() => onConfirm(reasonCode)}
            disabled={!available || !validReason || command?.pending}
            aria-describedby={command?.error && !pauseError ? 'override-confirm-error' : undefined}
          >
            {command?.pending ? (
              <><LoaderCircle className="study-spinner" aria-hidden="true" /> Confirming…</>
            ) : command?.error?.retryable ? 'Try returning early again' : 'Return early'}
          </button>
          <button
            className="study-button study-button--secondary study-button--wide"
            type="button"
            onClick={onKeepBreak}
            disabled={command?.pending}
          >
            <ArrowLeft aria-hidden="true" /> Keep taking my break
          </button>
          {!validReason && <small>Choose one reason before returning.</small>}
        </footer>
      </section>
    </main>
  );
}
