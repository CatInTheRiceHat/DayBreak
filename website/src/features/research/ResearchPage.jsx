import { createElement, useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { LoaderCircle, LockKeyhole, RefreshCw } from 'lucide-react';
import { CheckoutForm } from './CheckoutForm';
import { CooldownScreen } from './CooldownScreen';
import { IntentionalBreakFeed } from './IntentionalBreakFeed';
import { OverrideFlow } from './OverrideFlow';
import { PilotIntroduction } from './PilotIntroduction';
import { SessionPlanConfirmation } from './SessionPlanConfirmation';
import { SessionComplete } from './SessionComplete';
import { SessionPlanner } from './SessionPlanner';
import {
  createInitialSessionState,
  sessionMachineReducer,
} from './sessionMachine.js';
import {
  createIntentionalBreakEventQueue,
  readIntentionalBreakQueueSnapshot,
} from './intentionalBreakEventQueue.js';
import { createJourneySynchronizer } from './intentionalBreakFeedState.js';
import { isNonterminalState } from './sessionContract.js';
import { ensureResearchParticipant } from '../../lib/researchParticipant.js';
import * as intentionalBreakApi from '../../lib/intentionalBreakApi.js';
import './research.css';

function isAuthenticationError(error) {
  return error?.status === 401
    || error?.status === 403
    || [
      'authentication_required',
      'invalid_credential',
      'participant_inactive',
      'participant_credential_error',
    ].includes(error?.errorCode);
}

function LoadingScreen() {
  return (
    <main className="study-flow">
      <section className="study-panel study-state-card" aria-busy="true" aria-labelledby="study-loading-title">
        <div className="study-state-icon" aria-hidden="true"><LoaderCircle className="study-spinner" /></div>
        <p className="study-eyebrow">DayBreak pilot</p>
        <h1 id="study-loading-title">Finding your DayBreak</h1>
        <p role="status" aria-live="polite">Checking for a saved session…</p>
      </section>
    </main>
  );
}

function BootstrapError({ error, onRetry }) {
  const authError = isAuthenticationError(error);
  const retryable = error?.retryable === true;
  return (
    <main className="study-flow">
      <section className="study-panel study-state-card" aria-labelledby="study-error-title">
        <div className="study-state-icon study-state-icon--error" aria-hidden="true">
          {authError ? <LockKeyhole /> : <RefreshCw />}
        </div>
        <p className="study-eyebrow">DayBreak pilot</p>
        <h1 id="study-error-title">
          {authError
            ? 'Study initialization error'
            : retryable
              ? "DayBreak couldn't reach the study service."
              : 'This study journey could not be opened.'}
        </h1>
        <p role="alert">
          {authError
            ? 'Your participant credential could not be verified. DayBreak has not replaced or cleared it.'
            : retryable
              ? 'No session was created or changed. You can try again.'
              : (error?.message || 'The service returned a journey state this version cannot safely display.')}
        </p>
        {retryable && (
          <button className="study-button study-button--primary" type="button" onClick={onRetry}>
            <RefreshCw aria-hidden="true" />
            Try again
          </button>
        )}
      </section>
    </main>
  );
}

function ResumeStateCard({ icon, eyebrow, title, children, action }) {
  return (
    <main className="study-flow">
      <div className="study-flow__ambient" aria-hidden="true" />
      <section className="study-panel study-state-card" aria-labelledby="resume-state-title">
        <div className="study-state-icon" aria-hidden="true">{createElement(icon)}</div>
        <p className="study-eyebrow">{eyebrow}</p>
        <h1 id="resume-state-title">{title}</h1>
        <div className="study-state-card__copy">{children}</div>
        {action}
      </section>
    </main>
  );
}

function draftFromJourney(journey) {
  return {
    intention: journey.intention,
    plannedVideoCount: journey.planned_video_count,
    estimatedDurationSeconds: journey.estimated_duration_seconds,
    recommendedCooldownSeconds: journey.suggested_cooldown_seconds,
    selectedCooldownSeconds: journey.selected_cooldown_seconds,
  };
}

function signalJourneyChange(sessionId) {
  if (!sessionId) return;
  const synchronizer = createJourneySynchronizer({ sessionId });
  synchronizer.signal();
  synchronizer.destroy();
}

function bestEffortQueueFlush(queue, timeoutMs = 750) {
  if (!queue) return Promise.resolve();
  return new Promise((resolve) => {
    let settled = false;
    let timer = null;
    const finish = () => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolve();
    };
    timer = setTimeout(finish, timeoutMs);
    Promise.resolve(queue.flush()).catch(() => {}).finally(finish);
  });
}

export function ResearchPage() {
  const [state, dispatch] = useReducer(sessionMachineReducer, undefined, createInitialSessionState);
  const planRequestInFlight = useRef(false);
  const startRequestInFlight = useRef(false);
  const cancelRequestInFlight = useRef(false);
  const finishEarlyRequestInFlight = useRef(false);
  const checkoutRequestInFlight = useRef(false);
  const overrideStartRequestInFlight = useRef(false);
  const overrideConfirmRequestInFlight = useRef(false);
  const reconciliationInFlight = useRef(null);
  const cooldownReconciliationInFlight = useRef(null);
  const lifecycleQueueRef = useRef(null);
  const planAnotherRequestInFlight = useRef(false);
  const [cooldownReconcilePending, setCooldownReconcilePending] = useState(false);
  const [overrideHidden, setOverrideHidden] = useState(false);
  const [planAnotherStatus, setPlanAnotherStatus] = useState({ pending: false, error: null });

  const bootstrap = useCallback(async () => {
    dispatch({ type: 'BOOTSTRAP_STARTED' });
    try {
      await ensureResearchParticipant({ apiUrl: import.meta.env?.VITE_API_URL ?? '' });
      const response = await intentionalBreakApi.getCurrentJourney();
      dispatch({
        type: 'BOOTSTRAP_SUCCEEDED',
        journey: response.journey ?? null,
        serverTimestamp: response.serverTimestamp,
      });
    } catch (error) {
      dispatch({ type: 'BOOTSTRAP_FAILED', error });
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    async function start() {
      try {
        await ensureResearchParticipant({ apiUrl: import.meta.env?.VITE_API_URL ?? '' });
        const response = await intentionalBreakApi.getCurrentJourney();
        if (mounted) dispatch({
          type: 'BOOTSTRAP_SUCCEEDED',
          journey: response.journey ?? null,
          serverTimestamp: response.serverTimestamp,
        });
      } catch (error) {
        if (mounted) dispatch({ type: 'BOOTSTRAP_FAILED', error });
      }
    }
    start();
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    setOverrideHidden(false);
  }, [state.journey?.session_id]);

  useEffect(() => {
    const sessionId = state.journey?.session_id;
    lifecycleQueueRef.current = null;
    if (!sessionId || !['checkout', 'cooldown', 'completed'].includes(state.stage)) {
      return undefined;
    }
    if (readIntentionalBreakQueueSnapshot(sessionId).pending.length === 0) {
      return undefined;
    }
    const queue = createIntentionalBreakEventQueue({
      sessionId,
      send: (events) => intentionalBreakApi.appendEvents(sessionId, events),
      onJourney: (journey, _event, response) => dispatch({
        type: 'SERVER_JOURNEY_RECEIVED',
        journey,
        serverTimestamp: response?.serverTimestamp,
      }),
    });
    lifecycleQueueRef.current = queue;
    const flush = () => queue.flush();
    const flushWhenVisible = () => {
      if (document.visibilityState === 'visible') flush();
    };
    window.addEventListener('online', flush);
    document.addEventListener('visibilitychange', flushWhenVisible);
    flush();
    return () => {
      window.removeEventListener('online', flush);
      document.removeEventListener('visibilitychange', flushWhenVisible);
      queue.destroy();
      if (lifecycleQueueRef.current === queue) lifecycleQueueRef.current = null;
    };
  }, [state.journey?.session_id, state.stage]);

  async function reviewPlan() {
    if (planRequestInFlight.current || state.commands.plan.pending) return;
    const idempotencyKey = state.commands.plan.idempotencyKey
      ?? intentionalBreakApi.createIdempotencyKey();
    planRequestInFlight.current = true;
    dispatch({ type: 'PLAN_SUBMIT_STARTED', idempotencyKey });
    try {
      const response = await intentionalBreakApi.createPlan({
        intention: state.draft.intention,
        plannedVideoCount: state.draft.plannedVideoCount,
        selectedCooldownSeconds: state.draft.selectedCooldownSeconds,
        idempotencyKey,
      });
      dispatch({
        type: 'PLAN_CREATED',
        journey: response.journey,
        serverTimestamp: response.serverTimestamp,
      });
    } catch (error) {
      dispatch({ type: 'PLAN_SUBMIT_FAILED', error });
    } finally {
      planRequestInFlight.current = false;
    }
  }

  async function beginSession() {
    if (startRequestInFlight.current || state.commands.start.pending) return;
    const idempotencyKey = state.commands.start.idempotencyKey
      ?? intentionalBreakApi.createIdempotencyKey();
    startRequestInFlight.current = true;
    dispatch({ type: 'SESSION_START_STARTED', idempotencyKey });
    try {
      const response = await intentionalBreakApi.startSession(
        state.journey.session_id,
        idempotencyKey,
      );
      dispatch({
        type: 'SESSION_STARTED',
        journey: response.journey,
        serverTimestamp: response.serverTimestamp,
      });
    } catch (error) {
      dispatch({ type: 'SESSION_START_FAILED', error });
    } finally {
      startRequestInFlight.current = false;
    }
  }

  async function changePlan() {
    if (cancelRequestInFlight.current || state.commands.cancel.pending) return;
    const idempotencyKey = state.commands.cancel.idempotencyKey
      ?? intentionalBreakApi.createIdempotencyKey();
    const previousDraft = draftFromJourney(state.journey);
    cancelRequestInFlight.current = true;
    dispatch({ type: 'PLAN_CANCEL_STARTED', idempotencyKey });
    try {
      const response = await intentionalBreakApi.cancelPlan(
        state.journey.session_id,
        idempotencyKey,
      );
      dispatch({
        type: 'PLAN_CANCELLED',
        journey: response.journey,
        serverTimestamp: response.serverTimestamp,
      });
      if (response.journey?.journey_state === 'cancelled') {
        dispatch({ type: 'EDIT_CANCELLED_PLAN', draft: previousDraft });
      }
    } catch (error) {
      dispatch({ type: 'PLAN_CANCEL_FAILED', error });
    } finally {
      cancelRequestInFlight.current = false;
    }
  }

  const reconcileJourney = useCallback(() => {
    if (reconciliationInFlight.current) return reconciliationInFlight.current;
    const request = intentionalBreakApi.getCurrentJourney()
      .then((response) => {
        dispatch({
          type: 'SERVER_JOURNEY_RECEIVED',
          journey: response.journey ?? null,
          serverTimestamp: response.serverTimestamp,
        });
        return response.journey ?? null;
      })
      .catch((error) => {
        dispatch({ type: 'REQUEST_FAILED', error });
        return null;
      })
      .finally(() => {
        if (reconciliationInFlight.current === request) reconciliationInFlight.current = null;
      });
    reconciliationInFlight.current = request;
    return request;
  }, []);

  const receiveServerJourney = useCallback((journey) => {
    dispatch({ type: 'SERVER_JOURNEY_RECEIVED', journey });
  }, []);

  async function finishSessionEarly(currentPosition) {
    if (finishEarlyRequestInFlight.current || state.commands.finishEarly.pending) return null;
    const idempotencyKey = state.commands.finishEarly.idempotencyKey
      ?? intentionalBreakApi.createIdempotencyKey();
    finishEarlyRequestInFlight.current = true;
    dispatch({ type: 'FINISH_EARLY_STARTED', idempotencyKey });
    try {
      const response = await intentionalBreakApi.finishEarly(state.journey.session_id, {
        currentPosition,
        idempotencyKey,
      });
      dispatch({
        type: 'FINISH_EARLY_SUCCEEDED',
        journey: response.journey,
        serverTimestamp: response.serverTimestamp,
      });
      return response.journey;
    } catch (error) {
      dispatch({ type: 'FINISH_EARLY_FAILED', error });
      return null;
    } finally {
      finishEarlyRequestInFlight.current = false;
    }
  }

  async function submitCheckout(answers) {
    if (checkoutRequestInFlight.current || state.commands.checkout.pending) return null;
    const idempotencyKey = state.commands.checkout.idempotencyKey
      ?? intentionalBreakApi.createIdempotencyKey();
    checkoutRequestInFlight.current = true;
    dispatch({ type: 'CHECKOUT_SUBMIT_STARTED', idempotencyKey });
    try {
      await bestEffortQueueFlush(lifecycleQueueRef.current);
      const response = await intentionalBreakApi.submitCheckout(state.journey.session_id, {
        ...answers,
        idempotencyKey,
      });
      dispatch({
        type: 'CHECKOUT_SUBMITTED',
        journey: response.journey,
        serverTimestamp: response.serverTimestamp,
      });
      signalJourneyChange(state.journey.session_id);
      return response.journey;
    } catch (error) {
      dispatch({ type: 'CHECKOUT_SUBMIT_FAILED', error });
      return null;
    } finally {
      checkoutRequestInFlight.current = false;
    }
  }

  const reconcileCooldown = useCallback(() => {
    const sessionId = state.journey?.session_id;
    if (!sessionId) return Promise.resolve(null);
    if (cooldownReconciliationInFlight.current) {
      return cooldownReconciliationInFlight.current;
    }
    setCooldownReconcilePending(true);
    const request = intentionalBreakApi.getCooldown(sessionId)
      .then((response) => {
        dispatch({
          type: 'SERVER_JOURNEY_RECEIVED',
          journey: response.journey,
          serverTimestamp: response.serverTimestamp,
        });
        if (response.journey?.journey_state !== 'cooldown') signalJourneyChange(sessionId);
        return response.journey;
      })
      .catch((error) => {
        dispatch({ type: 'REQUEST_FAILED', error });
        return null;
      })
      .finally(() => {
        setCooldownReconcilePending(false);
        if (cooldownReconciliationInFlight.current === request) {
          cooldownReconciliationInFlight.current = null;
        }
      });
    cooldownReconciliationInFlight.current = request;
    return request;
  }, [state.journey?.session_id]);

  async function beginOverride() {
    if (state.journey.override_started_at && state.journey.override_available_at) {
      setOverrideHidden(false);
      return state.journey;
    }
    if (overrideStartRequestInFlight.current || state.commands.overrideStart.pending) return null;
    const idempotencyKey = state.commands.overrideStart.idempotencyKey
      ?? intentionalBreakApi.createIdempotencyKey();
    overrideStartRequestInFlight.current = true;
    dispatch({ type: 'OVERRIDE_START_STARTED', idempotencyKey });
    try {
      const response = await intentionalBreakApi.startOverride(
        state.journey.session_id,
        idempotencyKey,
      );
      dispatch({
        type: 'OVERRIDE_STARTED',
        journey: response.journey,
        serverTimestamp: response.serverTimestamp,
      });
      setOverrideHidden(false);
      signalJourneyChange(state.journey.session_id);
      return response.journey;
    } catch (error) {
      dispatch({ type: 'OVERRIDE_START_FAILED', error });
      return null;
    } finally {
      overrideStartRequestInFlight.current = false;
    }
  }

  async function confirmOverride(reasonCode) {
    if (overrideConfirmRequestInFlight.current || state.commands.overrideConfirm.pending) {
      return null;
    }
    const idempotencyKey = state.commands.overrideConfirm.idempotencyKey
      ?? intentionalBreakApi.createIdempotencyKey();
    overrideConfirmRequestInFlight.current = true;
    dispatch({ type: 'OVERRIDE_CONFIRM_STARTED', idempotencyKey });
    try {
      const response = await intentionalBreakApi.confirmOverride(state.journey.session_id, {
        reasonCode,
        idempotencyKey,
      });
      dispatch({
        type: 'OVERRIDE_CONFIRMED',
        journey: response.journey,
        serverTimestamp: response.serverTimestamp,
      });
      signalJourneyChange(state.journey.session_id);
      return response.journey;
    } catch (error) {
      dispatch({ type: 'OVERRIDE_CONFIRM_FAILED', error });
      if (error?.retryable !== true && error?.errorCode !== 'override_pause_active') {
        await reconcileCooldown();
      }
      return null;
    } finally {
      overrideConfirmRequestInFlight.current = false;
    }
  }

  async function planAnother() {
    if (planAnotherRequestInFlight.current) return;
    planAnotherRequestInFlight.current = true;
    setPlanAnotherStatus({ pending: true, error: null });
    try {
      await bestEffortQueueFlush(lifecycleQueueRef.current);
      const response = await intentionalBreakApi.getCurrentJourney();
      if (response.journey && isNonterminalState(response.journey.journey_state)) {
        dispatch({
          type: 'SERVER_JOURNEY_RECEIVED',
          journey: response.journey,
          serverTimestamp: response.serverTimestamp,
        });
      } else {
        dispatch({ type: 'RETURN_TO_NOTICE' });
      }
      setPlanAnotherStatus({ pending: false, error: null });
    } catch (error) {
      setPlanAnotherStatus({ pending: false, error });
    } finally {
      planAnotherRequestInFlight.current = false;
    }
  }

  if (state.stage === 'bootstrapping') return <LoadingScreen />;
  if (state.stage === 'error') return <BootstrapError error={state.error} onRetry={bootstrap} />;
  if (state.stage === 'notice') {
    return <PilotIntroduction onContinue={() => dispatch({ type: 'NOTICE_ACKNOWLEDGED' })} />;
  }
  if (state.stage === 'planning') {
    return (
      <SessionPlanner
        draft={state.draft}
        command={state.commands.plan}
        error={state.error}
        onIntentionChange={(intention) => dispatch({ type: 'SET_INTENTION', intention })}
        onVideoCountChange={(plannedVideoCount) => dispatch({ type: 'SET_VIDEO_COUNT', plannedVideoCount })}
        onCooldownChange={(selectedCooldownSeconds) => dispatch({
          type: 'SET_SELECTED_COOLDOWN',
          selectedCooldownSeconds,
        })}
        onReview={reviewPlan}
        onClearError={() => dispatch({ type: 'CLEAR_REQUEST_ERROR' })}
      />
    );
  }
  if (state.stage === 'planned') {
    return (
      <SessionPlanConfirmation
        journey={state.journey}
        startCommand={state.commands.start}
        cancelCommand={state.commands.cancel}
        error={state.error}
        onBegin={beginSession}
        onChangePlan={changePlan}
        onClearError={() => dispatch({ type: 'CLEAR_REQUEST_ERROR' })}
      />
    );
  }
  if (state.stage === 'active') {
    return (
      <IntentionalBreakFeed
        journey={state.journey}
        finishCommand={state.commands.finishEarly}
        commandError={state.commands.finishEarly.error}
        onServerJourney={receiveServerJourney}
        onReconcileJourney={reconcileJourney}
        onFinishEarly={finishSessionEarly}
      />
    );
  }
  if (state.stage === 'checkout') {
    return (
      <CheckoutForm
        sessionId={state.journey.session_id}
        draft={state.checkoutDraft}
        command={state.commands.checkout}
        error={state.commands.checkout.error}
        onAnswer={(field, value) => dispatch({
          type: 'SET_CHECKOUT_ANSWER',
          field,
          value,
        })}
        onSubmit={submitCheckout}
        onReconcile={reconcileJourney}
      />
    );
  }
  if (state.stage === 'cooldown') {
    const overrideStarted = Boolean(
      state.journey.override_started_at && state.journey.override_available_at,
    );
    if (overrideStarted && !overrideHidden) {
      return (
        <OverrideFlow
          journey={state.journey}
          serverTimestamp={state.serverTimestamp}
          reasonCode={state.overrideDraft.reasonCode}
          command={state.commands.overrideConfirm}
          onReasonChange={(reasonCode) => dispatch({ type: 'SET_OVERRIDE_REASON', reasonCode })}
          onConfirm={confirmOverride}
          onKeepBreak={() => setOverrideHidden(true)}
          onReconcile={reconcileCooldown}
        />
      );
    }
    return (
      <CooldownScreen
        journey={state.journey}
        serverTimestamp={state.serverTimestamp}
        reconcilePending={cooldownReconcilePending}
        reconcileError={state.error}
        overrideCommand={state.commands.overrideStart}
        onReconcile={reconcileCooldown}
        onReturnEarly={beginOverride}
      />
    );
  }
  if (state.stage === 'completed') {
    return (
      <SessionComplete
        journey={state.journey}
        pending={planAnotherStatus.pending}
        error={planAnotherStatus.error}
        onPlanAnother={planAnother}
      />
    );
  }
  if (state.stage === 'cancelled') {
    return (
      <ResumeStateCard
        icon={RefreshCw}
        eyebrow="Plan cancelled"
        title="Your plan was cancelled"
        action={(
          <button
            className="study-button study-button--primary"
            type="button"
            onClick={() => dispatch({ type: 'RETURN_TO_NOTICE' })}
          >
            Return to introduction
          </button>
        )}
      >
        <p>No session was started. You can return when you are ready to make another plan.</p>
      </ResumeStateCard>
    );
  }

  return (
    <BootstrapError
      error={{ message: 'The study returned an unsupported local state.', retryable: false }}
      onRetry={bootstrap}
    />
  );
}
