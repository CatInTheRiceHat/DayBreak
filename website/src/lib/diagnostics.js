import { supabase } from './supabaseClient';

/**
 * Persistence for the social-media diagnostic.
 *
 * Rows are append-only (one per attempt) in the RLS-protected `diagnostics`
 * table, so a user's retakes form a history that can be analyzed later. The full
 * raw answers are retained alongside the computed scores + result.
 */

// Insert one completed diagnostic for the given user.
export async function saveDiagnostic({ userId, answers, scores, unlockedFeatures, recommendedMode, interests = [] }) {
  if (!supabase) return { data: null, error: new Error('Supabase not configured') };
  return supabase
    .from('diagnostics')
    .insert({
      user_id: userId,
      answers,
      scores,
      unlocked_features: unlockedFeatures,
      recommended_mode: recommendedMode,
      interests,
    })
    .select()
    .single();
}

// Fetch the user's most recent diagnostic, or null if they've never taken one.
// Used to gate the one-time first-run flow.
export async function getLatestDiagnostic(userId) {
  if (!supabase) return { data: null, error: null };
  return supabase
    .from('diagnostics')
    .select('*')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
    .limit(1)
    .maybeSingle();
}
