import { useEffect, useMemo, useState } from 'react';
import { supabase, isSupabaseConfigured } from './supabaseClient';
import { AuthContext } from './authContext';

/**
 * App-wide auth state backed by Supabase Auth.
 *
 * Exposes the current session/user plus email+password auth actions. When
 * Supabase isn't configured, `configured` is false and the auth actions reject
 * with a friendly error so the UI can show a "being set up" state.
 *
 * Privacy: the user's email/phone are only ever read from this Auth session
 * (the logged-in user object) — never from the public profiles table.
 */
const notConfigured = () =>
  Promise.resolve({ data: null, error: new Error('Sign-in is not configured yet.') });

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  // Only "loading" when there's a real client to ask; otherwise we're settled.
  const [loading, setLoading] = useState(isSupabaseConfigured);

  useEffect(() => {
    if (!supabase) return undefined;
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session ?? null);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession ?? null);
    });
    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  const value = useMemo(() => ({
    configured: isSupabaseConfigured,
    loading,
    session,
    user: session?.user ?? null,
    signUp: (email, password) =>
      (supabase ? supabase.auth.signUp({ email, password }) : notConfigured()),
    signIn: (email, password) =>
      (supabase ? supabase.auth.signInWithPassword({ email, password }) : notConfigured()),
    signOut: () => (supabase ? supabase.auth.signOut() : notConfigured()),
  }), [session, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
