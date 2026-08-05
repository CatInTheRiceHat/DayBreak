// ──────────────────────────────────────────────────────────────
// Interest-based feed boosting.
//
// The backend already ranks the feed for wellbeing/diversity. On top of that we
// gently boost cards that match the topics a user chose in onboarding — a stable
// re-order, never a hard filter, so the algorithm's careful balance is preserved
// and no card is dropped just for not matching an interest.
// ──────────────────────────────────────────────────────────────

// Keywords per interest id, matched against a card's category / hashtags / text.
// Ids line up with INTERESTS in profileData.js so picks map straight through.
export const INTEREST_KEYWORDS = {
  art: ['art', 'draw', 'paint', 'sketch', 'design', 'craft', 'illustration', 'doodle'],
  music: ['music', 'song', 'guitar', 'piano', 'singing', 'beat', 'band', 'album', 'lofi'],
  journaling: ['journal', 'journaling', 'diary', 'reflect', 'gratitude', 'notebook'],
  walking: ['walk', 'walking', 'hike', 'hiking', 'stroll', 'steps', 'outdoors'],
  cooking: ['cook', 'cooking', 'recipe', 'baking', 'food', 'kitchen', 'meal'],
  reading: ['read', 'reading', 'book', 'books', 'novel', 'author', 'literature'],
  photography: ['photo', 'photography', 'camera', 'lens', 'portrait', 'shot'],
  gaming: ['game', 'gaming', 'gamer', 'gameplay', 'console', 'esports'],
  sports: ['sport', 'sports', 'soccer', 'basketball', 'workout', 'fitness', 'run', 'gym'],
  nature: ['nature', 'forest', 'garden', 'plant', 'ocean', 'mountain', 'wildlife', 'outdoor'],
  volunteering: ['volunteer', 'volunteering', 'charity', 'community', 'giving', 'kindness'],
  learning: ['learn', 'learning', 'study', 'education', 'science', 'facts', 'explained', 'tutorial'],
};

// Build one lowercased haystack of a card's matchable text.
function cardText(card) {
  const parts = [
    card.content_category,
    card.perspective_topic,
    card.title,
    card.raw_title,
    card.description,
    card.raw_description,
    ...(Array.isArray(card.display_hashtags) ? card.display_hashtags : []),
  ];
  return parts.filter(Boolean).join(' ').toLowerCase();
}

/**
 * How many of the user's chosen interests a card matches (0..n).
 * Exported for testing and for surfacing a "matches your interests" reason.
 */
export function interestMatchScore(card, interests = []) {
  if (!interests.length) return 0;
  const text = cardText(card);
  let score = 0;
  for (const id of interests) {
    const keywords = INTEREST_KEYWORDS[id];
    if (keywords && keywords.some((kw) => text.includes(kw))) score += 1;
  }
  return score;
}

/**
 * Stable-sort cards so higher interest-match scores rise, preserving the
 * backend's original order among cards with equal scores. Returns a new array;
 * with no interests it returns the input order unchanged.
 */
export function rankByInterests(cards = [], interests = []) {
  if (!interests.length || cards.length < 2) return cards;
  return cards
    .map((card, index) => ({ card, index, score: interestMatchScore(card, interests) }))
    .sort((a, b) => (b.score - a.score) || (a.index - b.index))
    .map((entry) => entry.card);
}
