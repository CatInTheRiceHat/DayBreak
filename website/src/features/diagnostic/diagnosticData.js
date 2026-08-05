// ──────────────────────────────────────────────────────────────
// Social Media Diagnostic — questions, scoring, and result mapping.
//
// A short (5-question) diagnostic shown once after first sign-in. Answers are
// turned into a set of "unlocked" features + a recommended algorithm mode, framed
// as a personalized setup ("here's what we turned on for you") rather than a
// negative label. Pure data + a pure scoring function so it's easy to test and
// analyze. No medical claims — this names behaviour patterns, not disorders.
// ──────────────────────────────────────────────────────────────

// 4-point frequency scale used by the scored questions (Q1–Q4).
export const SCALE = [
  { value: 0, label: 'Rarely' },
  { value: 1, label: 'Sometimes' },
  { value: 2, label: 'Often' },
  { value: 3, label: 'Almost always' },
];

// A scored answer of 2 (Often) or 3 (Almost always) counts as a "high" signal.
export const HIGH = 2;

// The five questions. Q1–Q4 are scored signals; Q5 captures goals (multi-select).
export const QUESTIONS = [
  {
    id: 'compulsive',
    type: 'scale',
    prompt: 'How often do you open an app without really meaning to?',
  },
  {
    id: 'latenight',
    type: 'scale',
    prompt: 'Do you end up scrolling in bed when you meant to be asleep?',
  },
  {
    id: 'comparison',
    type: 'scale',
    prompt: 'After scrolling, how often do you feel worse about yourself?',
  },
  {
    id: 'doomscroll',
    type: 'scale',
    prompt: 'Do you get pulled into a spiral of upsetting posts or news?',
  },
  {
    id: 'goals',
    type: 'multi',
    prompt: 'What would make your feed feel better?',
    hint: 'Pick as many as you like.',
    options: [
      { value: 'less-comparison', label: 'Less comparison' },
      { value: 'calmer', label: 'Calmer content' },
      { value: 'fewer-late', label: 'Fewer late-night scrolls' },
      { value: 'connection', label: 'More real connection' },
      { value: 'control', label: 'More control & transparency' },
    ],
  },
];

// Features that can be "unlocked" by the diagnostic. Each maps a behaviour pattern
// to a benefit-framed capability shown on the result screen.
export const FEATURES = {
  'night-wind-down': {
    key: 'night-wind-down',
    emoji: '🌙',
    name: 'Night Wind-Down',
    desc: 'Your feed eases off and calms down when it gets late.',
  },
  'comparison-guard': {
    key: 'comparison-guard',
    emoji: '🛡️',
    name: 'Comparison Guard',
    desc: 'Less appearance and highlight-reel content that makes you compare.',
  },
  'doomscroll-breaker': {
    key: 'doomscroll-breaker',
    emoji: '🌤️',
    name: 'Doomscroll Breaker',
    desc: 'Down-weights distressing news and negativity spirals.',
  },
  'scroll-breaks': {
    key: 'scroll-breaks',
    emoji: '⏸️',
    name: 'Scroll Breaks',
    desc: 'Gentle pause prompts when you’ve been scrolling a while.',
  },
  'prosocial-boost': {
    key: 'prosocial-boost',
    emoji: '🤝',
    name: 'Prosocial Boost',
    desc: 'Weights content by how it makes you feel — not just what keeps you tapping.',
  },
  'feed-compass': {
    key: 'feed-compass',
    emoji: '🧭',
    name: 'Feed Compass',
    desc: 'See why things are recommended — more transparency and control.',
  },
};

// One-line "why this mode" blurbs keyed by the mode keys defined in reelsData.js.
export const MODE_BLURB = {
  metamorphosis: 'Built for awareness, pauses, and gentle breaks.',
  'daily-dew': 'A short, calming daily reset.',
  'flutter-feed': 'A healthier, transparent, personalized feed.',
};

// Pick the recommended mode from the scored signals + goals.
function recommendMode(scores, goals) {
  const awareness = scores.compulsive + scores.latenight;
  const distress = scores.comparison + scores.doomscroll;
  if (awareness < 3 && distress < 3) {
    // Low distress overall — a healthy baseline. Honour a calm goal if present.
    return goals.includes('calmer') ? 'daily-dew' : 'flutter-feed';
  }
  if (awareness > distress) return 'metamorphosis';
  return 'daily-dew'; // distress >= awareness — tie breaks toward the gentler mode
}

/**
 * Score a completed diagnostic.
 *
 * @param {object} answers
 *   { compulsive, latenight, comparison, doomscroll: number(0-3), goals: string[] }
 * @returns {{ scores: object, unlockedFeatures: string[], recommendedMode: string }}
 */
export function scoreDiagnostic(answers = {}) {
  const scores = {
    compulsive: answers.compulsive ?? 0,
    latenight: answers.latenight ?? 0,
    comparison: answers.comparison ?? 0,
    doomscroll: answers.doomscroll ?? 0,
  };
  const goals = Array.isArray(answers.goals) ? answers.goals : [];

  const unlocked = [];
  const add = (key) => { if (!unlocked.includes(key)) unlocked.push(key); };

  // Scored signals flip on their mapped feature.
  if (scores.latenight >= HIGH) add('night-wind-down');
  if (scores.comparison >= HIGH) add('comparison-guard');
  if (scores.doomscroll >= HIGH) add('doomscroll-breaker');
  if (scores.compulsive >= HIGH) add('scroll-breaks');

  // Goals can unlock features and reinforce ones the scores didn't trip.
  if (goals.includes('connection')) add('prosocial-boost');
  if (goals.includes('control')) add('feed-compass');
  if (goals.includes('fewer-late')) add('night-wind-down');
  if (goals.includes('less-comparison')) add('comparison-guard');

  // Everyone leaves with at least one unlock — a healthy baseline still gets the
  // Compass so the result never feels empty or like a verdict.
  if (unlocked.length === 0) add('feed-compass');

  return {
    scores,
    unlockedFeatures: unlocked,
    recommendedMode: recommendMode(scores, goals),
  };
}
