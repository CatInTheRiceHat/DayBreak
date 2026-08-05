/**
 * Pure helpers for curated profiles: default-merging, chip toggling, and
 * connection state. No React/storage here so it's unit-testable (profiles.test.js).
 *
 * "Connected" means a friend (from the challenge friend graph) OR someone you've
 * connected with locally. Connection is about meaningful links — never popularity.
 */

import { DEFAULT_PROFILE, COMMUNITY_PROFILES } from './profileData.js';
import { friendIds } from './messaging.js';

/** Fill any missing fields on a stored profile with defaults. */
export function mergeProfile(stored) {
  const base = { ...DEFAULT_PROFILE };
  if (!stored || typeof stored !== 'object') return base;
  return {
    ...base,
    ...stored,
    goals: Array.isArray(stored.goals) ? stored.goals : base.goals,
    interests: Array.isArray(stored.interests) ? stored.interests : base.interests,
    activities: Array.isArray(stored.activities) ? stored.activities : base.activities,
  };
}

/** Toggle an id in an array (immutable). */
export function toggleInArray(list, id) {
  const arr = Array.isArray(list) ? list : [];
  return arr.includes(id) ? arr.filter((item) => item !== id) : [...arr, id];
}

/** Is this person a connection? Friends are always connected. */
export function isConnected(userId, connections = [], friends) {
  if (friendIds(friends).has(userId)) return true;
  return (connections || []).includes(userId);
}

/** A friend can't be "un-connected"; otherwise toggle the local connection. */
export function toggleConnection(userId, connections = [], friends) {
  if (friendIds(friends).has(userId)) return connections; // already a friend
  return toggleInArray(connections, userId);
}

/** Annotate community profiles with connection state for rendering. */
export function buildCommunity(connections = [], friends, profiles = COMMUNITY_PROFILES) {
  const friendSet = friendIds(friends);
  return profiles.map((profile) => ({
    ...profile,
    isFriend: friendSet.has(profile.id),
    isConnected: friendSet.has(profile.id) || (connections || []).includes(profile.id),
  }));
}
