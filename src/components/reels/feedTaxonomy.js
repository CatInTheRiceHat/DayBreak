import { BRAND } from '../../brand.js';
export const FEED_BALANCE_COPY = `${BRAND} mixes positive, wellness, perspective, and regular videos so your feed stays fun without becoming draining.`;

const CATEGORY_BADGES = {
  healthy: { label: 'Healthy', tone: 'healthy' },
  positive: { label: 'Positive', tone: 'positive' },
  regular: { label: 'Fun', tone: 'fun' },
  perspective: { label: 'Perspective', tone: 'perspective' },
  reduced: { label: 'Reset', tone: 'reset' },
};

const TEXT_BADGES = [
  {
    label: 'Creative',
    tone: 'creative',
    pattern: /\b(diy|craft|creative|create|draw|paint|art|build|make|recipe|cook|decorate|design)\b/i,
  },
  {
    label: 'Social',
    tone: 'social',
    pattern: /\b(friend|friends|friendship|social|kindness|community|classmate|teammate|team|together)\b/i,
  },
  {
    label: 'Reset',
    tone: 'reset',
    pattern: /\b(journal|journaling|walk|walking|outside|drink water|water|stretch|breathe|calm|reset|touch grass|gratitude)\b/i,
  },
];

function asText(value) {
  if (Array.isArray(value)) return value.join(' ');
  return String(value || '');
}

function normalizeKey(value) {
  return String(value || '').trim().toLowerCase();
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function cardText(card = {}) {
  return [
    card.title,
    card.raw_title,
    card.description,
    card.raw_description,
    card.short_description,
    card.display_description,
    asText(card.display_hashtags),
    asText(card.tags),
  ].filter(Boolean).join(' ');
}

function textBadge(card) {
  const text = cardText(card);
  return TEXT_BADGES.find((badge) => badge.pattern.test(text)) || null;
}

export function getContentBadge(card = {}) {
  const category = normalizeKey(card.content_category || card.contentCategory);
  const lane = normalizeKey(card.recommendation_lane || card.recommendationLane);

  if (category === 'perspective' || lane === 'perspective_mix') {
    return CATEGORY_BADGES.perspective;
  }

  const contextualBadge = textBadge(card);
  if (contextualBadge && ['healthy', 'positive', 'regular'].includes(category)) {
    return contextualBadge;
  }

  if (category && CATEGORY_BADGES[category]) return CATEGORY_BADGES[category];
  if (lane === 'healthy_mix') return CATEGORY_BADGES.healthy;
  if (lane === 'regular_mix') return CATEGORY_BADGES.regular;

  return null;
}

export function getRecommendationInsight(card = {}) {
  const category = normalizeKey(card.content_category || card.contentCategory);
  const lane = normalizeKey(card.recommendation_lane || card.recommendationLane);
  const wellness = numberOrNull(card.wellness_score ?? card.wellnessScore);
  const positivity = numberOrNull(card.positivity_score ?? card.positivityScore);
  const badge = getContentBadge(card);
  const detail = card.ranking_reason || card.rankingReason || card.reason || '';

  let summary = 'A balanced pick chosen to keep your feed varied.';
  if (category === 'perspective' || lane === 'perspective_mix') {
    summary = 'A low-conflict perspective video to keep your feed diverse.';
  } else if (category === 'positive') {
    summary = badge?.label === 'Social'
      ? 'A positive social clip chosen for a healthier vibe.'
      : 'A positive clip chosen for a healthier vibe.';
  } else if (lane === 'healthy_mix' || category === 'healthy') {
    if (badge?.label === 'Creative') {
      summary = 'A calm creative pick to keep your feed feeling lighter.';
    } else if (badge?.label === 'Social') {
      summary = 'A positive social clip chosen for a healthier vibe.';
    } else if ((wellness ?? 0) >= 0.45 || badge?.label === 'Reset') {
      summary = 'A calming wellness pick to reset your scroll.';
    } else if ((positivity ?? 0) >= 0.45) {
      summary = 'A positive pick chosen for a healthier vibe.';
    }
  } else if (lane === 'regular_mix' || category === 'regular') {
    if (badge?.label === 'Creative') {
      summary = 'A creative regular video to keep your feed balanced.';
    } else if (badge?.label === 'Social') {
      summary = 'A social regular clip to keep your feed feeling normal.';
    } else {
      summary = 'A fun regular video to keep your feed balanced.';
    }
  } else if (category === 'reduced' || lane === 'reduced_filler') {
    summary = 'A lower-priority fallback after higher-conflict picks were reduced.';
  }

  return {
    label: badge?.label || null,
    tone: badge?.tone || 'neutral',
    summary,
    detail,
    category,
    lane,
    hasTaxonomy: Boolean(category || lane),
  };
}

export function getFeedDebugSnapshot(payload = {}) {
  const debug = payload?.debug && typeof payload.debug === 'object'
    ? payload.debug
    : payload;
  if (!debug || typeof debug !== 'object') return null;

  const snapshot = {
    healthyRatio: numberOrNull(debug.healthy_content_ratio ?? debug.healthyContentRatio),
    healthyTarget: debug.healthy_content_target || debug.healthyContentTarget || null,
    contentCategoryCounts: debug.content_category_counts || debug.contentCategoryCounts || null,
    candidateCategoryCounts: debug.candidate_content_category_counts || debug.candidateContentCategoryCounts || null,
    laneCounts: debug.recommendation_lane_counts || debug.recommendationLaneCounts || null,
    filteredCount: numberOrNull(debug.reduced_or_blocked_filtered_count ?? debug.reducedOrBlockedFilteredCount),
  };

  if (
    snapshot.healthyRatio === null
    && !snapshot.contentCategoryCounts
    && !snapshot.candidateCategoryCounts
    && !snapshot.laneCounts
    && snapshot.filteredCount === null
  ) {
    return null;
  }

  return snapshot;
}

export function formatPercent(value) {
  const number = numberOrNull(value);
  if (number === null) return null;
  const percent = number <= 1 ? number * 100 : number;
  return `${Math.round(percent)}%`;
}

export function formatCountMap(map, limit = 4) {
  if (!map || typeof map !== 'object') return null;
  const entries = Object.entries(map)
    .map(([key, value]) => [key, Number(value)])
    .filter(([, value]) => Number.isFinite(value) && value > 0)
    .sort((a, b) => b[1] - a[1]);
  if (!entries.length) return null;

  const visible = entries.slice(0, limit).map(([key, value]) => `${prettyKey(key)} ${value}`);
  const hidden = entries.length - visible.length;
  return hidden > 0 ? `${visible.join(' / ')} / +${hidden}` : visible.join(' / ');
}

export function prettyKey(key) {
  return String(key || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
