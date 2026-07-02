import { BRAND } from '../../brand.js';
/**
 * Simple, rule-based comment safety for Chrysalis. Pure and deterministic so it is
 * unit-testable (see commentSafety.test.js). No ML, no political judgement — just a
 * small keyword/heuristic check that nudges heated comments toward kinder phrasing.
 *
 * Three levels:
 *   ok       → posts normally (with an occasional positive nudge)
 *   caution  → harsh tone: show a gentle rewrite prompt + a short cooldown before
 *              "post anyway" is allowed
 *   block    → targeted harm/threats: ask the author to rephrase; no shame, no
 *              public callout, just "let's keep it kind"
 */

export const SAFETY_OK = 'ok';
export const SAFETY_CAUTION = 'caution';
export const SAFETY_BLOCK = 'block';

// Short demo cooldown so the flow is visible in a presentation (real value could
// be longer). Applied before a caution-level comment can be posted anyway.
export const HEATED_COOLDOWN_MS = 5_000;

// Targeted harm / threats / "go away forever" language → block, ask to rephrase.
const HARMFUL_PATTERNS = [
  'kill yourself', 'kill urself', 'kys', 'go die', 'hope you die', 'end yourself',
  'nobody would miss you', 'you should disappear', "i'll find you", 'watch your back',
];

// Insults / harassment / bullying tone → caution.
const INSULT_PATTERNS = [
  'idiot', 'stupid', 'dumb', 'moron', 'loser', 'ugly', 'trash', 'garbage',
  'pathetic', 'worthless', 'shut up', 'you suck', 'disgusting', 'freak', 'clown',
  'cringe', 'hate you', 'so annoying', 'nobody likes you', 'gross', 'pig',
];

// Gentle rewrite prompts (from the product spec). Chosen deterministically.
const REWRITE_PROMPTS = [
  'This might come across as harsh. Want to rewrite it?',
  'Try making your point without attacking someone.',
  `${BRAND} keeps conversations safe and respectful.`,
];

const BLOCK_PROMPTS = [
  `Let's keep ${BRAND} kind — this could really hurt someone. Want to rephrase?`,
  'That reads as a personal attack. Try saying it without the harm.',
];

// Positive reinforcement for friendly comments.
const POSITIVE_NUDGES = [
  'Kindness looks good on you 💛',
  'Thanks for keeping it friendly.',
  'Good vibes added to the conversation 🌿',
];

function pick(list, seed) {
  if (!list.length) return null;
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  return list[hash % list.length];
}

function matches(text, pattern) {
  if (pattern.includes(' ')) return text.includes(pattern);
  // single word → word-boundary match so "trash" ≠ "trashcan"? (keep it loose but
  // boundaried so "class" doesn't trip "ass"-style false positives)
  return new RegExp(`\\b${pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`).test(text);
}

function countHits(text, patterns) {
  return patterns.reduce((n, pattern) => (matches(text, pattern) ? n + 1 : n), 0);
}

function aggressionScore(text) {
  let score = 0;
  const letters = (text.match(/[a-zA-Z]/g) || []);
  if (letters.length >= 6) {
    const caps = letters.filter((c) => c === c.toUpperCase()).length / letters.length;
    if (caps > 0.7) score += 1;
  }
  if ((text.match(/!/g) || []).length >= 3) score += 1;
  return score;
}

/**
 * Analyze a comment. Returns the level plus everything the UI needs to drive the
 * rewrite / cooldown / nudge flow.
 */
export function analyzeComment(rawText) {
  const text = String(rawText || '').trim();
  const lower = text.toLowerCase();

  if (!text) {
    return { level: SAFETY_OK, reasons: [], suggestion: null, nudge: null, cooldownMs: 0, canPostDirectly: false, allowPostAnyway: false };
  }

  if (countHits(lower, HARMFUL_PATTERNS) > 0) {
    return {
      level: SAFETY_BLOCK,
      reasons: ['targeted-harm'],
      suggestion: pick(BLOCK_PROMPTS, lower),
      nudge: null,
      cooldownMs: 0,
      canPostDirectly: false,
      allowPostAnyway: false,
    };
  }

  const insultHits = countHits(lower, INSULT_PATTERNS);
  if (insultHits > 0 || aggressionScore(text) >= 2) {
    return {
      level: SAFETY_CAUTION,
      reasons: insultHits > 0 ? ['harsh-language'] : ['aggressive-tone'],
      suggestion: pick(REWRITE_PROMPTS, lower),
      nudge: null,
      cooldownMs: HEATED_COOLDOWN_MS,
      canPostDirectly: false,
      allowPostAnyway: true,
    };
  }

  return {
    level: SAFETY_OK,
    reasons: [],
    suggestion: null,
    nudge: pick(POSITIVE_NUDGES, lower),
    cooldownMs: 0,
    canPostDirectly: true,
    allowPostAnyway: true,
  };
}

export function isAggressive(text) {
  return analyzeComment(text).level !== SAFETY_OK;
}
