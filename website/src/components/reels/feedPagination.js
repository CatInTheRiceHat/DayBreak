/**
 * Pure helpers for the infinite-scroll feed pagination.
 *
 * Kept framework-free so the dedupe contract can be unit-tested without a DOM:
 *   npm run test:unit
 */

/** Stable video id used for cross-page dedupe + the backend exclude_ids set. */
export function cardVideoId(card) {
  return (card && (card.raw_youtube_id || card.id)) || null;
}

/**
 * Split a freshly-fetched page of mapped cards into the ones the user hasn't
 * seen yet versus the full list of ids the backend returned.
 *
 * `seen` is a Set of already-shown video ids; it is mutated to include the new
 * fresh ids so the caller can reuse it across pages. Returns:
 *   - `fresh`: cards not already in `seen` (deduped by stable video id)
 *   - `returnedIds`: every id the backend returned this page (for exclude_ids)
 */
export function selectFreshCards(seen, cards) {
  const fresh = [];
  const returnedIds = [];
  for (const card of cards || []) {
    const vid = cardVideoId(card);
    if (vid) returnedIds.push(vid);
    if (!vid || seen.has(vid)) continue;
    seen.add(vid);
    fresh.push(card);
  }
  return { fresh, returnedIds };
}
