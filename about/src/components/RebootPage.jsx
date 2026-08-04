import {
  ArrowRight,
  BookOpen,
  CirclePause,
  Compass,
  HeartHandshake,
  Layers3,
  MessageCircleMore,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import './public-pages.css';

const socialMediaBenefits = [
  ['Connect', 'Keep up with friends, communities, and people who understand your interests.'],
  ['Inspire', 'Discover creative work, new perspectives, and ideas worth trying.'],
  ['Educate', 'Learn from explainers, lived experiences, and thoughtful conversations.'],
  ['Entertain', 'Enjoy humor, stories, and moments that make a difficult day feel lighter.'],
];

const socialMediaTensions = [
  ['Comparison', 'Feeds can narrow attention toward unrealistic or repetitive reference points.'],
  ['Repetition', 'Familiar signals can crowd out variety and make every scroll feel the same.'],
  ['Passive scrolling', 'It is easy to keep going without choosing whether the next post is useful.'],
  ['Reduced agency', 'People rarely get a clear say in what the recommendation system optimizes.'],
];

const principles = [
  {
    icon: <Compass size={22} aria-hidden="true" />,
    title: 'More user agency',
    body: 'Make preferences understandable and give people meaningful ways to shape their feed.',
  },
  {
    icon: <Layers3 size={22} aria-hidden="true" />,
    title: 'Broader content variety',
    body: 'Look beyond the strongest engagement signal so one topic does not take over the experience.',
  },
  {
    icon: <CirclePause size={22} aria-hidden="true" />,
    title: 'Intentional pauses',
    body: 'Create room to notice how a session feels and decide what should happen next.',
  },
  {
    icon: <ShieldCheck size={22} aria-hidden="true" />,
    title: 'Transparent choices',
    body: 'Explain recommendations in plain language without pretending a complex system is simple.',
  },
];

function SectionHeading({ eyebrow, title, children, align = 'left' }) {
  return (
    <header className={`db-section-heading db-section-heading--${align}`}>
      <p className="db-eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      {children && <p className="db-section-heading__body">{children}</p>}
    </header>
  );
}

function HorizonArtwork() {
  return (
    <div className="db-horizon" aria-hidden="true">
      <span className="db-horizon__line db-horizon__line--back" />
      <span className="db-horizon__line db-horizon__line--middle" />
      <span className="db-horizon__line db-horizon__line--front" />
      <span className="db-horizon__note">pause · notice · choose</span>
    </div>
  );
}

function HeroSection() {
  return (
    <section id="home" className="db-hero" aria-labelledby="db-hero-title">
      <div className="db-hero__copy">
        <p className="db-eyebrow">A teen-centered digital well-being project</p>
        <h1 id="db-hero-title">A brighter way to scroll.</h1>
        <p className="db-hero__lede">
          DayBreak explores how recommendation algorithms can support healthier, more intentional
          social media experiences—without treating social media as simply good or bad.
        </p>
        <div className="db-actions">
          <a
            className="db-button db-button--primary"
            href="https://thechrysalisproject.vercel.app/"
          >
            Try the prototype <ArrowRight size={18} aria-hidden="true" />
          </a>
          <a className="db-button db-button--secondary" href="#solution">
            Explore the approach
          </a>
        </div>
        <p className="db-hero__annotation">
          An exploratory project by Elaine Che · designed with teen perspectives in mind
        </p>
      </div>
      <HorizonArtwork />
    </section>
  );
}

function ProblemSection() {
  return (
    <section id="problem" className="db-section db-section--light" aria-labelledby="db-problem-title">
      <SectionHeading eyebrow="The context" title="Social media holds more than one truth." align="center">
        It can help people connect, learn, create, and laugh. It can also encourage comparison,
        repetitive content, and scrolling that no longer feels chosen.
      </SectionHeading>

      <div className="db-tension-grid">
        <article className="db-tension-card db-tension-card--positive">
          <div className="db-tension-card__heading">
            <HeartHandshake size={22} aria-hidden="true" />
            <h3>What it can offer</h3>
          </div>
          <ul>
            {socialMediaBenefits.map(([title, body]) => (
              <li key={title}><strong>{title}</strong><span>{body}</span></li>
            ))}
          </ul>
        </article>
        <article className="db-tension-card db-tension-card--reflective">
          <div className="db-tension-card__heading">
            <RefreshCw size={22} aria-hidden="true" />
            <h3>Where design can help</h3>
          </div>
          <ul>
            {socialMediaTensions.map(([title, body]) => (
              <li key={title}><strong>{title}</strong><span>{body}</span></li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  );
}

function JourneySection() {
  return (
    <section id="journey" className="db-section db-origin" aria-labelledby="db-journey-title">
      <div className="db-origin__story">
        <SectionHeading eyebrow="How the idea evolved" title="From a research question to DayBreak">
          The project began as MorphoMedia, a Synopsys science fair exploration of whether
          recommendation systems could be designed around more than engagement alone.
        </SectionHeading>
        <p>
          DayBreak carries that question into an interactive prototype. The name marks a shift
          toward reflection and renewal: a chance to interrupt an automatic pattern, notice what
          the feed is doing, and choose a more intentional direction.
        </p>
      </div>
      <ol className="db-origin__steps" aria-label="Project evolution">
        <li><span>01</span><div><strong>Observe</strong><p>Start with the real complexity of teen online life.</p></div></li>
        <li><span>02</span><div><strong>Question</strong><p>Ask what recommendation systems reward and what they overlook.</p></div></li>
        <li><span>03</span><div><strong>Prototype</strong><p>Turn well-being principles into choices people can see and try.</p></div></li>
        <li><span>04</span><div><strong>Learn</strong><p>Use feedback to refine the experience without overclaiming the result.</p></div></li>
      </ol>
    </section>
  );
}

function SolutionSection() {
  return (
    <section id="solution" className="db-section db-section--warm" aria-labelledby="db-solution-title">
      <SectionHeading eyebrow="The DayBreak approach" title="Designing for a healthier digital rhythm" align="center">
        DayBreak explores recommendation experiences that make room for intention, variety,
        explanation, and rest while keeping the useful parts of social media in view.
      </SectionHeading>
      <div className="db-principle-grid">
        {principles.map(({ icon, title, body }) => (
          <article className="db-principle-card" key={title}>
            <span className="db-principle-card__icon">{icon}</span>
            <h3>{title}</h3>
            <p>{body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function PrototypeSection() {
  return (
    <section className="db-section db-prototype" aria-labelledby="db-prototype-title">
      <div className="db-prototype__copy">
        <SectionHeading eyebrow="Prototype preview" title="See why a post reached you">
          A recommendation should not feel like a mysterious verdict. The prototype pairs familiar
          feed interactions with direct explanations and controls for changing direction.
        </SectionHeading>
        <ul className="db-check-list">
          <li><Sparkles size={18} aria-hidden="true" /> Plain-language recommendation context</li>
          <li><MessageCircleMore size={18} aria-hidden="true" /> Familiar social interactions</li>
          <li><CirclePause size={18} aria-hidden="true" /> Supportive break and reflection prompts</li>
        </ul>
        <a className="db-text-link" href="https://thechrysalisproject.vercel.app/">
          Open the interactive prototype <ArrowRight size={17} aria-hidden="true" />
        </a>
      </div>

      <figure className="db-feed-preview">
        <figcaption>Example recommendation</figcaption>
        <div className="db-feed-preview__media">
          <span>Make something small today</span>
        </div>
        <div className="db-feed-preview__meta">
          <span className="db-avatar" aria-hidden="true">A</span>
          <div><strong>@after.school.studio</strong><span>Creative practice · 2 min</span></div>
        </div>
        <div className="db-why-card">
          <span>Why this is here</span>
          <p>You asked for creative ideas and more topic variety.</p>
          <button type="button">Adjust my feed</button>
        </div>
      </figure>
    </section>
  );
}

function ResearchSection() {
  return (
    <section id="future" className="db-section db-research" aria-labelledby="db-research-title">
      <div>
        <SectionHeading eyebrow="Research framing" title="A prototype for learning, not a finished answer">
          DayBreak is an exploratory digital well-being project. It does not claim that one feed can
          solve the broader challenges of social media or that every person needs the same experience.
        </SectionHeading>
      </div>
      <div className="db-research__notes">
        <article>
          <BookOpen size={22} aria-hidden="true" />
          <h3>Research-informed</h3>
          <p>Questions and design choices should be documented, testable, and open to revision.</p>
        </article>
        <article>
          <HeartHandshake size={22} aria-hidden="true" />
          <h3>Human-centered</h3>
          <p>Teen feedback and lived experience belong in the design process, not at the margins.</p>
        </article>
      </div>
    </section>
  );
}

function AboutSection() {
  return (
    <section id="about" className="db-section db-about" aria-labelledby="db-about-title">
      <p className="db-eyebrow">Built by Elaine</p>
      <div className="db-about__grid">
        <h2 id="db-about-title">Technology should leave room for people to choose.</h2>
        <div>
          <p>
            DayBreak brings together interests in journalism, coding, media, and ethical technology.
            The goal is to build with curiosity about how people actually use social platforms—not
            to shame them for being there.
          </p>
          <p>
            The work is still growing through prototyping, feedback, and careful research.
          </p>
        </div>
      </div>
    </section>
  );
}

function ContactSection() {
  return (
    <section id="contact" className="db-contact" aria-labelledby="db-contact-title">
      <p className="db-eyebrow">Help shape what comes next</p>
      <h2 id="db-contact-title">Ready for a brighter feed?</h2>
      <p>Try the prototype, share your perspective, or start a conversation about the project.</p>
      <div className="db-actions db-actions--center">
        <a className="db-button db-button--light" href="https://thechrysalisproject.vercel.app/">
          Try DayBreak <ArrowRight size={18} aria-hidden="true" />
        </a>
        <a className="db-button db-button--outline-light" href="mailto:elaineyouyuanche@gmail.com">
          Contact Elaine
        </a>
      </div>
    </section>
  );
}

export function RebootPage() {
  return (
    <main className="db-public-page">
      <HeroSection />
      <ProblemSection />
      <JourneySection />
      <SolutionSection />
      <PrototypeSection />
      <ResearchSection />
      <AboutSection />
      <ContactSection />
    </main>
  );
}
