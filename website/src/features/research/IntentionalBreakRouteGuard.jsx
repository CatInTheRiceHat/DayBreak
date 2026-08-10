import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { getCurrentJourneyForStoredParticipant } from '../../lib/intentionalBreakApi.js';
import {
  getStoredResearchParticipant,
  hasResearchParticipantCredential,
} from '../../lib/researchParticipant.js';
import { createJourneySynchronizer } from './intentionalBreakFeedState.js';
import {
  resolveIntentionalBreakRouteGuard,
  ROUTE_GUARD_OUTCOMES,
} from './intentionalBreakRouteGuard.js';

const CHECKING = 'checking';

function routeIdentity(location) {
  return `${location.key}:${location.pathname}${location.search}${location.hash}`;
}

function initialGuardState(locationId) {
  const participant = getStoredResearchParticipant();
  return {
    locationId,
    outcome: hasResearchParticipantCredential(participant)
      ? CHECKING
      : ROUTE_GUARD_OUTCOMES.ALLOW,
    reason: hasResearchParticipantCredential(participant) ? 'checking' : 'no_credential',
  };
}

function GuardLoading() {
  return (
    <main className="study-flow">
      <section className="study-panel study-state-card" aria-busy="true">
        <p className="study-eyebrow">DayBreak pilot</p>
        <h1>Checking your DayBreak…</h1>
      </section>
    </main>
  );
}

function GuardError({ onRetry }) {
  return (
    <main className="study-flow">
      <section className="study-panel study-state-card">
        <p className="study-eyebrow">DayBreak pilot</p>
        <h1>We couldn&apos;t check your DayBreak session.</h1>
        <p role="alert">Try again, or return to your study session.</p>
        <div className="study-state-card__actions">
          <button className="study-button study-button--primary" type="button" onClick={onRetry}>
            Try again
          </button>
          <Link className="study-button study-button--secondary" to="/study" replace>
            Return to /study
          </Link>
        </div>
      </section>
    </main>
  );
}

export function IntentionalBreakRouteGuard() {
  const location = useLocation();
  const locationId = routeIdentity(location);
  const requestSequence = useRef(0);
  const [guardState, setGuardState] = useState(() => initialGuardState(locationId));

  const checkAuthority = useCallback(async () => {
    const participant = getStoredResearchParticipant();
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    if (!hasResearchParticipantCredential(participant)) {
      setGuardState({
        locationId,
        outcome: ROUTE_GUARD_OUTCOMES.ALLOW,
        reason: 'no_credential',
      });
      return;
    }

    setGuardState({ locationId, outcome: CHECKING, reason: 'checking' });
    const decision = await resolveIntentionalBreakRouteGuard({
      getStoredParticipant: () => participant,
      getCurrentJourney: (storedParticipant) => getCurrentJourneyForStoredParticipant(
        storedParticipant,
        { apiUrl: import.meta.env?.VITE_API_URL ?? '' },
      ),
    });
    if (requestSequence.current !== requestId) return;
    setGuardState({ locationId, ...decision });
  }, [locationId]);

  useEffect(() => {
    let cancelled = false;
    Promise.resolve().then(() => {
      if (!cancelled) checkAuthority();
    });
    return () => {
      cancelled = true;
      requestSequence.current += 1;
    };
  }, [checkAuthority]);

  useEffect(() => {
    const synchronizer = createJourneySynchronizer({ onChange: checkAuthority });
    const checkWhenVisible = () => {
      if (document.visibilityState === 'visible') checkAuthority();
    };
    window.addEventListener('focus', checkAuthority);
    document.addEventListener('visibilitychange', checkWhenVisible);
    return () => {
      synchronizer.destroy();
      window.removeEventListener('focus', checkAuthority);
      document.removeEventListener('visibilitychange', checkWhenVisible);
    };
  }, [checkAuthority]);

  const credentialPresent = hasResearchParticipantCredential(getStoredResearchParticipant());
  const state = guardState.locationId === locationId
    || !credentialPresent
    || guardState.reason === 'unusable_credential'
    ? guardState
    : { locationId, outcome: CHECKING, reason: 'checking' };

  if (state.outcome === ROUTE_GUARD_OUTCOMES.REDIRECT) {
    return <Navigate to="/study" replace />;
  }
  if (state.outcome === ROUTE_GUARD_OUTCOMES.ERROR) {
    return <GuardError onRetry={checkAuthority} />;
  }
  if (state.outcome === CHECKING) return <GuardLoading />;
  return <Outlet />;
}
