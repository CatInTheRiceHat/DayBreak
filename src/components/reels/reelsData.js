import { BRAND_HANDLE } from '../../brand.js';
/**
 * Built-in fallback/prompt cards for the Chrysalis Algorithm experience.
 *
 * Real YouTube videos come from one shared broad feed pool. These cards are
 * mode-specific UI fallbacks that appear only when the real pool is short:
 *   daily-dew     — short, grounding, positive daily drop (light & quick)
 *   metamorphosis — screen-time regulation: pause, breathe, notice scrolling
 *   flutter-feed  — a healthier personalized feed with more user control
 *
 * To add / edit a card: append or modify an object inside the relevant array
 * of `reelsByMode`. Each card supports:
 *   id          unique string within its mode (used as React key)
 *   title       headline shown in the bottom caption
 *   source      creator / origin line
 *   label       wellbeing tag shown as the accent chip
 *   description short supporting line
 *   image       path under /public (omit to render the branded gradient wash)
 *   reason      why this reached you — shown by the "Why this algorithm?" action
 */

export const MODES = [
  {
    key: 'daily-dew',
    label: 'Daily Dew',
    logo: '/images/daily-dew.png',
    description: 'A short, gentle reset with calm and reflective content.',
    blurb: 'A short, gentle reset with calm and reflective content.',
  },
  {
    key: 'metamorphosis',
    label: 'Metamorphosis',
    logo: '/images/metamorphosis.png',
    description: 'A slower mode for pauses, breaks, and scroll awareness.',
    blurb: 'A slower mode for pauses, breaks, and scroll awareness.',
  },
  {
    key: 'flutter-feed',
    label: "Cruisin'",
    logo: '/images/flutter-feed.png',
    description: 'A healthier personalized feed with variety, positivity, and transparency.',
    blurb: 'A healthier personalized feed with variety, positivity, and transparency.',
  },
];

export const DEFAULT_MODE = 'flutter-feed';

/** Legacy onboarding IDs from the old intention picker, kept for localStorage migration. */
export const LEGACY_INTENTION_MODES = {
  reset: 'daily-dew',
  lesstime: 'metamorphosis',
  healthier: 'flutter-feed',
};

export const reelsByMode = {
  'daily-dew': [
    {
      id: 'tiny-reset',
      title: 'A tiny reset',
      source: `@${BRAND_HANDLE} · Daily Dew`,
      label: 'Grounding',
      description: 'One slow breath in, one slow breath out. That’s the whole post.',
      image: '/images/daily-dew.png',
      reason: 'A gentle opener chosen to ease you in, not to hook you.',
    },
    {
      id: 'one-kind-thought',
      title: 'One kind thought before you scroll',
      source: `@${BRAND_HANDLE} · Daily Dew`,
      label: 'Self-love',
      description: 'You’re allowed to be a work in progress and still be worthy today.',
      image: '/images/journey-egg.png',
      reason: 'Prosocial, low-stimulation content surfaced for your morning reset.',
    },
    {
      id: 'gratitude',
      title: 'Notice one thing you’re grateful for',
      source: `@${BRAND_HANDLE} · Daily Dew`,
      label: 'Reflection',
      description: 'Small or silly counts. Warm coffee. A text back. Quiet for a minute.',
      image: '/images/hero-butterfly.png',
      reason: 'A reflective prompt to close your daily drop on a grounded note.',
    },
  ],
  'metamorphosis': [
    {
      id: 'cocoon-break',
      title: 'Take a cocoon break',
      source: `@${BRAND_HANDLE} · Metamorphosis`,
      label: 'Rest',
      description: 'You’ve been here a while. Breathe, look up, and come back when you’re ready.',
      image: '/images/journey-chrysalis.png',
      reason: 'Surfaced because your session is running long — a nudge to pause.',
    },
    {
      id: 'scrolling-a-bit',
      title: 'You’ve been scrolling for a bit',
      source: `@${BRAND_HANDLE} · Metamorphosis`,
      label: 'Awareness',
      description: 'No judgment — just a gentle marker. How are your eyes and shoulders feeling?',
      image: '/images/journey-caterpillar.png',
      reason: 'A screen-time check-in placed to help you notice the pattern.',
    },
    {
      id: 'breathe',
      title: 'Breathe before the next post',
      source: `@${BRAND_HANDLE} · Metamorphosis`,
      label: 'Pause',
      description: 'In for four, hold for four, out for four. The feed will wait for you.',
      image: '/images/metamorphosis.png',
      reason: 'A deliberate pause card that slows the pace between cards.',
    },
  ],
  'flutter-feed': [
    {
      id: 'healthier-feed',
      title: 'A healthier personalized feed',
      source: `@${BRAND_HANDLE} · Cruisin'`,
      label: 'Balance',
      description: 'Tuned to what you like — and tuned away from what quietly wears you down.',
      image: '/images/flutter-feed.png',
      reason: 'Personalized to your interests with positivity and diversity weighted in.',
    },
    {
      id: 'regenerate',
      title: 'Regenerate this algorithm view',
      source: `@${BRAND_HANDLE} · Controls`,
      label: 'Your call',
      description: 'Not feeling it? Reshuffle with a fresh blend of topics and tones in one tap.',
      image: '/images/journey-emerged.png',
      reason: 'You’re always in control — regenerate whenever the mix feels off.',
    },
    {
      id: 'balance',
      title: 'Balance positivity, diversity, and self-love',
      source: `@${BRAND_HANDLE} · For you`,
      label: 'Prosocial',
      description: 'Every recommendation weighs how it makes you feel — not just what keeps you tapping.',
      image: '/images/hero-butterfly.png',
      reason: 'Ranked by relevance, diversity, prosocial value, and a risk shield.',
    },
  ],
};
