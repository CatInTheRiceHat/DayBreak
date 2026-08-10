import { getCurrentJourneyForStoredParticipant } from '../../lib/intentionalBreakApi.js';
import {
  getStoredResearchParticipant,
  hasResearchParticipantCredential,
} from '../../lib/researchParticipant.js';
import { isNonterminalState } from './sessionContract.js';

export const ROUTE_GUARD_OUTCOMES = Object.freeze({
  ALLOW: 'allow',
  REDIRECT: 'redirect',
  ERROR: 'error',
});

export function isRouteGuardAuthenticationFailure(error) {
  return error?.status === 401
    || error?.status === 403
    || [
      'authentication_required',
      'invalid_credential',
      'participant_inactive',
      'participant_credential_error',
    ].includes(error?.errorCode);
}

export async function resolveIntentionalBreakRouteGuard({
  getStoredParticipant = getStoredResearchParticipant,
  getCurrentJourney = getCurrentJourneyForStoredParticipant,
} = {}) {
  const participant = getStoredParticipant();
  if (!hasResearchParticipantCredential(participant)) {
    return { outcome: ROUTE_GUARD_OUTCOMES.ALLOW, reason: 'no_credential' };
  }

  try {
    const response = await getCurrentJourney(participant);
    if (isNonterminalState(response?.journey?.journey_state)) {
      return { outcome: ROUTE_GUARD_OUTCOMES.REDIRECT, reason: 'nonterminal_journey' };
    }
    return { outcome: ROUTE_GUARD_OUTCOMES.ALLOW, reason: 'no_nonterminal_journey' };
  } catch (error) {
    if (isRouteGuardAuthenticationFailure(error)) {
      return { outcome: ROUTE_GUARD_OUTCOMES.ALLOW, reason: 'unusable_credential' };
    }
    return { outcome: ROUTE_GUARD_OUTCOMES.ERROR, reason: 'authority_unavailable' };
  }
}
