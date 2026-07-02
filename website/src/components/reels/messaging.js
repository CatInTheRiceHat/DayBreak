import { BRAND } from '../../brand.js';
/**
 * Friends-only messaging rule for Chrysalis. Pure + testable (messaging.test.js).
 *
 * Direct messages are only allowed between friends — strangers cannot DM you. This
 * is the core anti-harassment guarantee; the UI surfaces it as a friendly note, not
 * a punishment.
 */

import { DEMO_FRIENDS } from './challengesData.js';

export const FRIENDS_ONLY_MESSAGE =
  `Messaging on ${BRAND} is friends-only. Add each other as friends to start a chat.`;

/** Friend ids for the signed-in demo user (the leaderboard friends). */
export function friendIds(friends = DEMO_FRIENDS) {
  return new Set(friends.map((friend) => friend.id));
}

export function isFriend(userId, friends = DEMO_FRIENDS) {
  return friendIds(friends).has(userId);
}

/** Whether the current user may directly message `userId`. */
export function canMessage(userId, friends = DEMO_FRIENDS) {
  return isFriend(userId, friends);
}

/** Outcome object for the UI: { allowed, reason }. */
export function messageOutcome(userId, friends = DEMO_FRIENDS) {
  return canMessage(userId, friends)
    ? { allowed: true, reason: null }
    : { allowed: false, reason: FRIENDS_ONLY_MESSAGE };
}
