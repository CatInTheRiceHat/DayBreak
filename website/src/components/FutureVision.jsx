import { BRAND } from '../brand.js';
import { Eye, Globe, Plug } from 'lucide-react';
import { BeveledSliderSection } from './BeveledSliderSection';

function FutureSignal({ items }) {
  return (
    <div className="beveled-signal-list">
      {items.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </div>
  );
}

const SLIDES = [
  {
    color: 'green',
    icon: Globe,
    eyebrow: 'Open Platform',
    title: 'The code, the weights, and the research should be open.',
    body: 'A healthier feed should not depend on a closed platform deciding that care is profitable enough to ship.',
    visual: <FutureSignal items={['Open source core', 'Transparent weights', 'Research citations']} />,
  },
  {
    color: 'blue',
    icon: Plug,
    eyebrow: 'Real Feeds',
    title: 'The next version should sit between people and real content.',
    body: `The goal is to reroute existing feeds through ${BRAND} so users can keep the creators they follow and change the ranking logic.`,
    visual: <FutureSignal items={['YouTube', 'TikTok', 'Instagram', 'Custom APIs']} />,
  },
  {
    color: 'pink',
    icon: Eye,
    eyebrow: 'Transparency',
    title: 'Teenagers deserve to see what their algorithm is doing.',
    body: 'The interface should reveal why posts were boosted, softened, delayed, or filtered so control becomes understandable.',
    visual: <FutureSignal items={['Why this post?', 'Boosted for balance', 'Muted for risk']} />,
  },
];

export function FutureVision() {
  return (
    <BeveledSliderSection
      id="future"
      label="What's Next"
      heading="The algorithm is just the beginning."
      intro={`${BRAND} is a prototype today. The larger vision is a feed layer that is open, transparent, and built for the people using it.`}
      slides={SLIDES}
    />
  );
}
