import { BRAND } from '../brand.js';
import { Brain, FlaskConical, TrendingUp, Zap } from 'lucide-react';
import { BeveledSliderSection } from './BeveledSliderSection';

const HARMS = [
  'Doomscrolling',
  'Body comparison',
  'Filter bubbles',
  'Emotional contagion',
  'Crisis rabbit holes',
  'Viral amplification',
];

const METRICS = [
  { label: 'Prosocial content', before: '18%', after: '31%' },
  { label: 'Diversity@10', before: '3.1', after: '6.4' },
  { label: 'Same-topic streak', before: '8+', after: '2' },
];

function OptimizationBars() {
  const rows = [
    { label: 'Watch time', pct: 95 },
    { label: 'Clicks', pct: 88 },
    { label: 'Shares', pct: 72 },
    { label: 'Wellbeing', pct: 4, quiet: true },
  ];

  return (
    <div className="beveled-mini-panel">
      <p>Traditional ranking pressure</p>
      {rows.map((row) => (
        <div key={row.label} className="beveled-meter-row">
          <span>{row.label}</span>
          <strong>{row.pct}%</strong>
          <div>
            <i style={{ width: `${row.pct}%`, opacity: row.quiet ? 0.45 : 1 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function HarmGrid() {
  return (
    <div className="beveled-chip-grid">
      {HARMS.map((harm, index) => (
        <span key={harm}>
          <b>{String(index + 1).padStart(2, '0')}</b>
          {harm}
        </span>
      ))}
    </div>
  );
}

function FormulaBlock() {
  return (
    <div className="beveled-formula">
      <span>Score</span> = engagement x w_e
      <br />
      {'      '}+ diversity x w_d
      <br />
      {'      '}+ prosocial x w_p
      <br />
      {'      '}- risk x w_r
    </div>
  );
}

function MetricsList() {
  return (
    <div className="beveled-results">
      {METRICS.map((metric) => (
        <div key={metric.label}>
          <span>{metric.label}</span>
          <p>
            <em>{metric.before}</em>
            <b>{metric.after}</b>
          </p>
        </div>
      ))}
    </div>
  );
}

const SLIDES = [
  {
    color: 'pink',
    icon: Brain,
    eyebrow: 'The Problem',
    title: 'Algorithms are designed to keep you scrolling.',
    body: "The harm is not random. Engagement-at-all-costs rewards anxiety, comparison, and empty passive streaks because those behaviors keep feeds alive.",
    visual: <OptimizationBars />,
  },
  {
    color: 'yellow',
    icon: FlaskConical,
    eyebrow: 'The Research',
    title: 'Six documented harms became six targeted fixes.',
    body: `${BRAND} maps research-backed harms into precise ranking interventions rather than treating wellbeing as a vague afterthought.`,
    visual: <HarmGrid />,
  },
  {
    color: 'blue',
    icon: Zap,
    eyebrow: 'The Solution',
    title: 'A multidimensional score that can actually care.',
    body: 'Every post is evaluated across engagement, diversity, prosocial value, risk, timing, and user controls so the feed can change direction.',
    visual: <FormulaBlock />,
  },
  {
    color: 'green',
    icon: TrendingUp,
    eyebrow: 'The Results',
    title: 'Better wellbeing signals without giving up discovery.',
    body: `Against an engagement-only baseline, ${BRAND} improves diversity and prosocial exposure while reducing repetitive same-topic loops.`,
    visual: <MetricsList />,
  },
];

export function ProjectStory() {
  return (
    <BeveledSliderSection
      id="project"
      label="The Project"
      heading="The problem. The research. The solution."
      intro={`A compact walkthrough of how ${BRAND} turns the critique of social media into an algorithm with different incentives.`}
      slides={SLIDES}
    />
  );
}
