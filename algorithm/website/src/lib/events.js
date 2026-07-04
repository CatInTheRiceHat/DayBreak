import { supabase } from './supabaseClient';

/**
 * Fire-and-forget per-user behavioral logging for the pilot. Writes one row to the
 * `usage_events` table (see migrations/013_usage_events.sql). Never throws and
 * never blocks the feed — logging failures are swallowed on purpose.
 */
export async function logEvent(userId, eventType, payload = {}) {
  if (!supabase || !userId) return;
  try {
    await supabase.from('usage_events').insert({ user_id: userId, event_type: eventType, payload });
  } catch (e) { /* never let logging break the feed */ }
}
