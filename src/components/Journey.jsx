import { BRAND } from '../brand.js';
import { Code2, Database, Rocket, ScrollText } from 'lucide-react';
import { BeveledSliderSection } from './BeveledSliderSection';

function MilestoneList({ items }) {
  return (
    <div className="beveled-timeline-list">
      {items.map((item, index) => (
        <div key={item}>
          <span>{String(index + 1).padStart(2, '0')}</span>
          <p>{item}</p>
        </div>
      ))}
    </div>
  );
}

function SnapshotFrame({ title, body }) {
  return (
    <div className="beveled-snapshot">
      <div>
        <span />
        <span />
        <span />
      </div>
      <h4>{title}</h4>
      <p>{body}</p>
    </div>
  );
}

const SLIDES = [
  {
    color: 'blue',
    icon: Database,
    eyebrow: 'Dataset',
    title: 'First, the feed needed a real baseline.',
    body: `The build started by loading and validating social media data, then comparing ${BRAND} against a simple engagement-only ranker.`,
    visual: <MilestoneList items={['VK-LSVD dataset loaded', 'Baseline algorithm built', 'Metric comparison scaffolded']} />,
  },
  {
    color: 'yellow',
    icon: ScrollText,
    eyebrow: 'Research',
    title: 'The research became the product requirements.',
    body: 'Papers on teen mental health, passive consumption, and crisis rabbit holes became concrete ranking constraints.',
    visual: <SnapshotFrame title="Research notes" body="Harm mechanisms mapped into scoring levers and user-facing protections." />,
  },
  {
    color: 'pink',
    icon: Code2,
    eyebrow: 'Build',
    title: 'The algorithm grew into a working system.',
    body: 'Diversity scoring, nighttime protection, user controls, crisis routing, and test coverage were layered into the prototype.',
    visual: <MilestoneList items={['Gini diversity scoring', 'Night mode + UCRS', '78 tests passing']} />,
  },
  {
    color: 'green',
    icon: Rocket,
    eyebrow: 'Algorithm',
    title: 'Then it became something people could try.',
    body: 'The FastAPI backend and React algorithm interface make the healthier ranking visible.',
    visual: <SnapshotFrame title="Live algorithm" body="FastAPI, React, and feed cards working end-to-end." />,
  },
];

export function Journey() {
  return (
    <BeveledSliderSection
      id="journey"
      label="The Journey"
      heading="From idea to algorithm."
      intro={`The build path, compressed into the moments that changed ${BRAND} from a research question into a working prototype.`}
      slides={SLIDES}
    />
  );
}
