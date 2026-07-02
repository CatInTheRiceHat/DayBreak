import { createClient } from '@supabase/supabase-js';

/**
 * Single shared Supabase browser client for Chrysalis.
 *
 * Reads the public project URL + anon (publishable) key from Vite env. The anon
 * key is safe to ship to the browser — data is protected by Row Level Security,
 * not by hiding this key.
 *
 * If either value is missing we export `null` instead of throwing, so the app
 * keeps running without auth configured and the sign-in UI can show a calm
 * "being set up" state rather than a crash.
 */
const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

function createSupabaseClient() {
  if (!url || !anonKey) return null;
  try {
    return createClient(url, anonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  } catch (err) {
    // A malformed VITE_SUPABASE_URL (e.g. missing the https:// scheme) must not
    // white-screen the whole app. Fall back to the "auth not configured" state.
    console.error('[supabase] client init failed; running without auth:', err);
    return null;
  }
}

export const supabase = createSupabaseClient();

export const isSupabaseConfigured = Boolean(supabase);
