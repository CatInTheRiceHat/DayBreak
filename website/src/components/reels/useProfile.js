import { useEffect, useMemo, useState } from 'react';
import { buildCommunity, mergeProfile, toggleConnection, toggleInArray } from './profiles';

const PROFILE_KEY = 'chrysalis-profile';
const CONNECTIONS_KEY = 'chrysalis-connections';

function load(key, fallback) {
  if (typeof window === 'undefined') return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

/** Signed-in (demo) user's curated profile + their connections, persisted locally. */
export function useProfile() {
  const [profile, setProfile] = useState(() => mergeProfile(load(PROFILE_KEY, null)));
  const [connections, setConnections] = useState(() => load(CONNECTIONS_KEY, []));

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try { window.localStorage.setItem(PROFILE_KEY, JSON.stringify(profile)); } catch { /* best-effort */ }
  }, [profile]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try { window.localStorage.setItem(CONNECTIONS_KEY, JSON.stringify(connections)); } catch { /* best-effort */ }
  }, [connections]);

  const community = useMemo(() => buildCommunity(connections), [connections]);

  function setField(field, value) {
    setProfile((previous) => ({ ...previous, [field]: value }));
  }

  function toggleField(field, id) {
    setProfile((previous) => ({ ...previous, [field]: toggleInArray(previous[field], id) }));
  }

  function toggleConnect(userId) {
    setConnections((previous) => toggleConnection(userId, previous));
  }

  return { profile, setField, toggleField, community, toggleConnect };
}
