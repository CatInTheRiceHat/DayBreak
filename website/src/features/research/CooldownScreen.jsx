import { useEffect, useMemo, useRef, useState } from 'react';
import { Clock3, Coffee, LoaderCircle, RefreshCw } from 'lucide-react';
import { createJourneySynchronizer } from './intentionalBreakFeedState.js';
import {
  createServerTimeReference,
  durationMinutes,
  formatCountdown,
  remainingSecondsAt,
} from './cooldownTime.js';

export function CooldownScreen({
  journey,
  serverTimestamp,
  reconcilePending = false,
  reconcileError = null,
  overrideCommand,
  onReconcile,
  onReturnEarly,
  showSuggestion = true,
}) {
  const headingRef = useRef(null);
  const zeroReconciled = useRef(false);
  const reference = useMemo(() => createServerTimeReference({
    serverTimestamp,
    endsAt: journey.cooldown_ends_at,
    remainingSeconds: journey.remaining_seconds,
  }), [journey.cooldown_ends_at, journey.remaining_seconds, serverTimestamp]);
  const [clientNowMs, setClientNowMs] = useState(() => Date.now());
  const remainingSeconds = remainingSecondsAt(reference, clientNowMs);
  const selectedMinutes = durationMinutes(journey.selected_cooldown_seconds);

  useEffect(() => {
    headingRef.current?.focus();
    onReconcile();
  }, [onReconcile]);

  useEffect(() => {
    zeroReconciled.current = false;
    if (!reference) return undefined;
    const timer = window.setInterval(() => {
      setClientNowMs(Date.now());
    }, 1_000);
    return () => window.clearInterval(timer);
  }, [reference]);

  useEffect(() => {
    if (remainingSeconds !== 0 || zeroReconciled.current || reconcilePending) return;
    zeroReconciled.current = true;
    onReconcile();
  }, [onReconcile, reconcilePending, remainingSeconds]);

  useEffect(() => {
    const sessionId = journey.session_id;
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
  }, [journey.session_id, onReconcile]);

  return (
    <main className="study-flow study-flow--cooldown">
      <div className="study-flow__ambient" aria-hidden="true" />
      <section className="study-panel study-panel--cooldown" aria-labelledby="cooldown-title">
        <header className="study-panel__header">
          <div className="study-cooldown-mark" aria-hidden="true"><Clock3 /></div>
          <p className="study-eyebrow">Your reset is underway</p>
          <h1 id="cooldown-title" ref={headingRef} tabIndex="-1">Time for your reset</h1>
          <p>You chose <strong>{selectedMinutes ?? 'a few'} minutes away</strong> after this DayBreak.</p>
        </header>

        <div className="study-cooldown-time">
          <span>Time remaining</span>
          <time aria-hidden="true">{formatCountdown(remainingSeconds)}</time>
          <span className="study-visually-hidden">Your cooldown is active.</span>
        </div>

        <p className="study-cooldown-leave">You don't need to keep this page open. DayBreak will remember your reset.</p>

        {showSuggestion && (
          <aside className="study-offline-suggestion">
            <Coffee aria-hidden="true" />
            <p><strong>Try something offline:</strong> get some water, stretch, or do one small thing away from the feed.</p>
          </aside>
        )}

        {reconcileError && (
          <div className="study-error" id="cooldown-error" role="alert">
            <strong>We're having trouble checking your reset right now.</strong>
            <p>Your feed stays unavailable. DayBreak will wait for the study service to confirm what comes next.</p>
            <button className="study-text-action" type="button" onClick={onReconcile} disabled={reconcilePending}>
              <RefreshCw aria-hidden="true" /> Try again
            </button>
          </div>
        )}

        {overrideCommand?.error && (
          <div className="study-error" id="override-start-error" role="alert">
            <strong>We couldn't start the return pause yet.</strong>
            <p>Your reset is still active. You can try again.</p>
          </div>
        )}

        <footer className="study-cooldown-actions">
          <button
            className="study-text-action study-text-action--quiet"
            type="button"
            onClick={onReturnEarly}
            disabled={overrideCommand?.pending}
            aria-describedby={overrideCommand?.error ? 'override-start-error' : undefined}
          >
            {overrideCommand?.pending ? (
              <><LoaderCircle className="study-spinner" aria-hidden="true" /> Starting a short pause…</>
            ) : overrideCommand?.error?.retryable ? 'Try returning early again' : 'I want to return early'}
          </button>
        </footer>
      </section>
    </main>
  );
}
