import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AnimatePresence,
  motion as MOTION,
  useInView,
  useMotionValueEvent,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  useVelocity,
} from 'motion/react';
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Award,
  Brain,
  ClipboardList,
  Code2,
  Droplets,
  Github,
  Linkedin,
  Mail,
  MessageCircle,
  Newspaper,
  Route,
  SlidersHorizontal,
  Sparkles,
  X,
} from 'lucide-react';

const originCards = [
  ['Award recognition', 'MorphoMedia was recognized by SPV Market Research at the 2026 Synopsys Championship Science Fair.'],
  ['Interactive prototype', 'Chrysalis later became an interactive full-stack prototype with personalized algorithm controls and three modes: Flutter Feed, Metamorphosis, and Daily Dew.'],
];

const problemRows = [
  ['46%', 'The U.S. Surgeon General advisory notes that 46% of adolescents ages 13-17 said social media makes them feel worse about their body image.'],
  ['2x risk', 'The U.S. Surgeon General advisory notes that adolescents who spend more than 3 hours a day on social media faced double the risk of poor mental health outcomes, including symptoms of depression and anxiety.'],
  ['64%', 'The U.S. Surgeon General advisory reports that 64% of adolescents are often or sometimes exposed to hate-based content through social media.'],
];

const journeySteps = [
  {
    title: 'Ova Phase',
    body: 'Observation: Through journalism, I started paying attention to how technology, AI, school pressure, and internet culture shape student life.',
    symbolImage: '/images/journey-egg.png',
    mosaic: 'ova',
    artifacts: [
      {
        src: '/images/poster.png',
        alt: 'The Social Dilemma poster',
        label: 'The Social Dilemma poster',
        variant: 'ova-poster',
        depth: 22,
        lateral: -3,
        driftDepth: 30,
        driftLateral: -6,
        driftRotate: -0.55,
        lag: 1.12,
        response: 2.15,
        driftResponse: 2.35,
        sway: 1.06,
      },
      {
        src: '/images/newspaper.png',
        alt: 'Article screenshot by Elaine Che',
        label: 'Elaine Che article screenshot',
        variant: 'ova-article',
        depth: 52,
        lateral: 9,
        driftDepth: 64,
        driftLateral: 14,
        driftRotate: 1.25,
        lag: 1.72,
        response: 1.08,
        driftResponse: 1.2,
        sway: 1.52,
      },
    ],
    icon: Newspaper,
  },
  {
    title: 'Larva Phase',
    body: 'MorphoMedia: I turned those questions into MorphoMedia, my Synopsys science fair project. The project explored whether recommendation systems could be redesigned around teen wellbeing instead of pure engagement.',
    symbolImage: '/images/journey-caterpillar.png',
    mosaic: 'larva',
    artifacts: [
      {
        src: '/images/synopsys-poster.jpeg',
        alt: 'MorphoMedia science fair poster',
        label: 'MorphoMedia science fair poster',
        variant: 'larva-poster',
        depth: 24,
        lateral: -5,
        driftDepth: 32,
        driftLateral: -7,
        driftRotate: -0.7,
        lag: 1.18,
        response: 2.25,
        driftResponse: 2.45,
        sway: 1.08,
      },
      {
        src: '/images/award.png',
        alt: 'SPV Market Research award certificate',
        label: 'SPV Market Research award certificate',
        variant: 'larva-certificate',
        depth: 56,
        lateral: 10,
        driftDepth: 68,
        driftLateral: 16,
        driftRotate: 1.35,
        lag: 1.84,
        response: 1,
        driftResponse: 1.12,
        sway: 1.56,
      },
    ],
    icon: Award,
  },
  {
    title: 'Chrysalis Phase',
    body: 'Rebuilding: After showcasing MorphoMedia at science fair, I rebuilt the idea as Chrysalis: a more interactive full-stack passion project with three modes - Flutter Feed, Metamorphosis, and Daily Dew.',
    symbolImage: '/images/journey-chrysalis.png',
    mosaic: 'chrysalis',
    artifacts: [
      {
        src: '/images/app-icon.png',
        alt: 'Chrysalis app icon',
        label: 'Chrysalis app icon',
        variant: 'chrysalis-app',
        depth: 28,
        lateral: -7,
        driftDepth: 35,
        driftLateral: -11,
        driftRotate: -0.75,
        lag: 1.22,
        response: 2.05,
        driftResponse: 2.25,
        sway: 1.12,
      },
      {
        src: '/images/code.png',
        alt: 'Chrysalis code screenshot',
        label: 'Chrysalis code screenshot',
        variant: 'chrysalis-code',
        depth: 58,
        lateral: 11,
        driftDepth: 72,
        driftLateral: 17,
        driftRotate: 1.45,
        lag: 1.88,
        response: 1.02,
        driftResponse: 1.16,
        sway: 1.62,
      },
    ],
    icon: Code2,
  },
  {
    title: 'Imago Phase',
    body: 'Vision: My long-term goal is not to shame people for using social media. I want Chrysalis to help people use digital spaces with more agency, more self-awareness, and more respect for themselves than when they entered.',
    symbolImage: '/images/journey-emerged.png',
    mosaic: 'imago',
    artifacts: [
      {
        src: '/images/future.png',
        alt: 'Future social media network illustration',
        label: 'Future social media network illustration',
        variant: 'imago-placeholder',
        depth: 42,
        lateral: 5,
        driftDepth: 54,
        driftLateral: 8,
        driftRotate: -0.5,
        lag: 1.5,
        response: 1.3,
        driftResponse: 1.5,
        sway: 1.34,
      },
    ],
    icon: Sparkles,
  },
];

const solutionModes = [
  {
    title: 'Flutter Feed',
    body: 'The classic infinite feed, but re-ranked. Flutter Feed keeps the familiar scrolling experience but changes what the algorithm rewards. Instead of only prioritizing engagement, users can describe what they want to see, and the algorithm re-ranks content based on relevance, variety, positivity, and risk.',
    icon: SlidersHorizontal,
    image: '/images/flutter-feed.png',
  },
  {
    title: 'Metamorphosis',
    body: 'A recovery mode for people who feel stuck in endless scrolling. Metamorphosis helps users gradually reduce screen time instead of forcing an abrupt cutoff. The goal is not punishment. It is support.',
    icon: Sparkles,
    image: '/images/metamorphosis.png',
  },
  {
    title: 'Daily Dew',
    body: 'A limited daily drop of content. Inspired by the intentional design of daily games like The New York Times puzzles, Daily Dew replaces endless personalization with a small set of daily videos. The content is designed to feel more thoughtful, creative, and perspective-building instead of infinite and addictive.',
    icon: Droplets,
    image: '/images/daily-dew.png',
  },
];

const SURVEY_URL = 'https://forms.gle/tyhkHUfPJgs4FjSJ6';

function getJourneyStepPercent(index) {
  return journeySteps.length > 1
    ? 12 + (index / (journeySteps.length - 1)) * 76
    : 50;
}

function getPhaseTitleParts(title) {
  const parts = title.trim().split(/\s+/);
  const suffix = parts[parts.length - 1] === 'Phase' ? parts.pop() : '';

  return {
    name: parts.join(' '),
    suffix,
  };
}

function PhaseTitle({ step, showImage = true }) {
  const { name, suffix } = getPhaseTitleParts(step.title);

  return (
    <span className="ct-phase-title">
      <span className="ct-phase-title__text">
        <span>{name}</span>
        {suffix && <span>{suffix}</span>}
      </span>
      {showImage && (
        <img className="ct-phase-title__image" src={step.symbolImage} alt="" aria-hidden="true" />
      )}
    </span>
  );
}

function useDesktopFiling() {
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    const query = window.matchMedia('(min-width: 1025px)');
    const update = () => setIsDesktop(query.matches);

    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  return isDesktop;
}

function Reveal({ children, className = '', delay = 0 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <MOTION.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 42, filter: 'blur(12px)' }}
      animate={inView ? { opacity: 1, y: 0, filter: 'blur(0px)' } : {}}
      transition={{ duration: 0.72, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </MOTION.div>
  );
}

const droopyElements = {
  a: MOTION.a,
  article: MOTION.article,
  div: MOTION.div,
  h2: MOTION.h2,
  p: MOTION.p,
  span: MOTION.span,
};

function useDroopyMotion({
  depth = 14,
  lateral = 0,
  rotate = 0,
  lag,
  response,
  sway,
}) {
  const ref = useRef(null);
  const reduceMotion = useReducedMotion();
  const { scrollY } = useScroll();
  const scrollVelocity = useVelocity(scrollY);
  const driftWeight = lag ?? 1 + Math.min(Math.abs(depth) / 56, 0.55);
  const responseWeight = response ?? driftWeight;
  const variation = 1 + Math.min((Math.abs(lateral) * 0.035) + (Math.abs(rotate) * 0.16) + ((sway ?? 1) - 1) * 0.16, 0.32);
  const maxTravel = Math.min(Math.abs(depth) * 0.82, 34);
  const velocityY = useTransform(scrollVelocity, (latest) => {
    const bounded = Math.max(-1250, Math.min(1250, latest));
    const direction = Math.sign(bounded);
    const normalized = Math.abs(bounded) / 1250;
    const curved = normalized ** (0.92 + Math.min(Math.max(responseWeight - 1, -0.28), 0.58) * 0.16);
    return direction * curved * maxTravel * driftWeight * variation;
  });

  const y = useSpring(velocityY, {
    stiffness: 56 / Math.max(responseWeight, 0.72),
    damping: 16.8 + Math.min(responseWeight, 2.8) * 2.6,
    mass: 0.92 + Math.min(responseWeight, 2.8) * 0.2 + Math.max((sway ?? 1) - 1, 0) * 0.26,
  });
  const travelRange = Math.max(maxTravel * driftWeight * variation, 1);
  const x = useTransform(y, (value) => (value / travelRange) * lateral * 2.35);
  const rotateZ = useTransform(y, (value) => (value / travelRange) * rotate);

  return {
    ref,
    x,
    y,
    rotateZ,
    reduceMotion,
  };
}

function DroopyElement({
  as = 'div',
  children,
  className = '',
  depth = 14,
  lateral = 0,
  rotate = 0,
  lag,
  response,
  sway,
  style,
  ...props
}) {
  const Component = droopyElements[as] || MOTION.div;
  const { ref, y, reduceMotion } = useDroopyMotion({ depth, lateral, rotate, lag, response, sway });
  const motionStyle = reduceMotion ? style : { ...style, y };

  return (
    <Component ref={ref} className={className} style={motionStyle} {...props}>
      {children}
    </Component>
  );
}

function JourneyArtifact({ artifact, onPreview, stepTitle, interactive = true }) {
  const {
    ref,
    x,
    y,
    rotateZ,
    reduceMotion,
  } = useDroopyMotion({
    depth: artifact.driftDepth ?? artifact.depth ?? 32,
    lateral: artifact.driftLateral ?? artifact.lateral ?? 0,
    rotate: artifact.driftRotate ?? 0,
    lag: (artifact.lag ?? 1.4) + 0.18,
    response: artifact.driftResponse ?? artifact.response,
    sway: artifact.sway,
  });
  const droopY = useTransform(y, (value) => `${value}px`);
  const droopX = useTransform(x, (value) => `${value}px`);
  const droopRotate = useTransform(rotateZ, (value) => `${value}deg`);
  const motionStyle = reduceMotion
    ? undefined
    : {
      '--droop-x': droopX,
      '--droop-y': droopY,
      '--droop-rotate': droopRotate,
    };

  return (
    <MOTION.button
      type="button"
      ref={ref}
      className={`ct-journey-artifact ct-journey-artifact--${artifact.variant}`}
      style={motionStyle}
      onClick={() => onPreview({
        title: artifact.alt,
        label: artifact.label || artifact.alt,
        src: artifact.src,
        previewSrc: artifact.previewSrc || artifact.src,
      })}
      aria-label={`Preview ${artifact.alt}`}
      disabled={!interactive}
      tabIndex={interactive ? 0 : -1}
      data-cursor="soft"
    >
      <span className="ct-journey-artifact__drift">
        <img src={artifact.src} alt={artifact.alt} />
      </span>
    </MOTION.button>
  );
}

function JourneyMosaic({ step, className = '', onPreview = () => {}, interactive = true }) {
  return (
    <div className={`ct-journey-mosaic ct-journey-mosaic--${step.mosaic} ${className}`.trim()}>
      {step.artifacts.map((artifact) => (
        <JourneyArtifact
          artifact={artifact}
          key={`${step.title}-${artifact.variant}`}
          onPreview={onPreview}
          stepTitle={step.title}
          interactive={interactive}
        />
      ))}
    </div>
  );
}

function TextTrail({
  children,
  as = 'div',
  className = '',
  depth = 14,
  lag = 1,
}) {
  return (
    <DroopyElement as={as} className={className} depth={depth} lag={lag}>
      {children}
    </DroopyElement>
  );
}

function SectionFrame({ id, tone = 'paper', label, children }) {
  const ref = useRef(null);
  const reduceMotion = useReducedMotion();
  const isDesktop = useDesktopFiling();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end start'],
  });

  const scale = useTransform(scrollYProgress, [0.48, 0.92], [1, 0.925]);
  const y = useTransform(scrollYProgress, [0.48, 1], [0, -42]);
  const rotateX = useTransform(scrollYProgress, [0.52, 0.96], [0, -3.5]);
  const blur = useTransform(scrollYProgress, [0.58, 0.96], [0, 7]);
  const opacity = useTransform(scrollYProgress, [0.72, 1], [1, 0.24]);
  const filter = useTransform(blur, (value) => `blur(${value}px)`);
  const depthShadow = useTransform(
    scrollYProgress,
    [0, 0.55, 1],
    [
      '0 0 0 rgba(43, 38, 49, 0)',
      '0 -18px 42px rgba(43, 38, 49, 0.08)',
      '0 -34px 86px rgba(43, 38, 49, 0.18)',
    ],
  );
  const useFilingMotion = tone === 'paper';
  const filingStyle = reduceMotion || !isDesktop || !useFilingMotion
    ? undefined
    : { scale, y, rotateX, filter, opacity, boxShadow: depthShadow };

  return (
    <section id={id} ref={ref} className={`ct-section-shell ct-section-shell--${tone}`}>
      <MOTION.div
        className="ct-section"
        style={filingStyle}
      >
        <div className="ct-section__tab ct-reveal-color" aria-hidden="true">{label}</div>
        {children}
      </MOTION.div>
    </section>
  );
}

function MetricRows() {
  return (
    <div className="ct-metric-table">
      {problemRows.map(([value, label], index) => (
        <DroopyElement
          className="ct-metric-row"
          depth={16 + index * 5}
          lag={1.18 + index * 0.22}
          key={value}
        >
          <strong>{value}</strong>
          <span>{label}</span>
        </DroopyElement>
      ))}
    </div>
  );
}

const modeCardVariants = {
  enter: (dir) => ({ opacity: 0, x: dir >= 0 ? 36 : -36, filter: 'blur(8px)' }),
  center: { opacity: 1, x: 0, filter: 'blur(0px)' },
  exit: (dir) => ({ opacity: 0, x: dir >= 0 ? -36 : 36, filter: 'blur(8px)' }),
};

function ModeCarousel({ modes }) {
  const [active, setActive] = useState(0);
  const [direction, setDirection] = useState(0);
  const mode = modes[active];

  const go = (delta) => {
    setActive((current) => {
      const next = Math.min(modes.length - 1, Math.max(0, current + delta));
      if (next !== current) {
        setDirection(delta);
      }
      return next;
    });
  };

  const jump = (index) => {
    setActive((current) => {
      if (index !== current) {
        setDirection(index > current ? 1 : -1);
      }
      return index;
    });
  };

  return (
    <div className="ct-mode-carousel">
      <div className="ct-mode-carousel__stage" aria-live="polite">
        <AnimatePresence mode="wait" custom={direction}>
          <MOTION.article
            key={active}
            className="ct-mode-card"
            custom={direction}
            variants={modeCardVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="ct-mode-card__badge">
              <span className="ct-mode-card__rule" aria-hidden="true" />
              <span className="ct-mode-card__ring">
                <img src={mode.image} alt="" aria-hidden="true" />
              </span>
              <span className="ct-mode-card__rule" aria-hidden="true" />
            </div>
            <span className="ct-mode-card__index">{String(active + 1).padStart(2, '0')}</span>
            <h3>{mode.title}</h3>
            <p>{mode.body}</p>
          </MOTION.article>
        </AnimatePresence>
      </div>

      <div className="ct-mode-carousel__controls">
        <button
          type="button"
          className="ct-mode-carousel__arrow"
          onClick={() => go(-1)}
          disabled={active === 0}
          aria-label="Previous mode"
        >
          <ArrowLeft size={18} aria-hidden="true" />
        </button>
        <div className="ct-mode-carousel__dots" role="tablist" aria-label="Modes">
          {modes.map((item, index) => (
            <button
              key={item.title}
              type="button"
              role="tab"
              aria-selected={index === active}
              aria-label={item.title}
              className={`ct-mode-carousel__dot ${index === active ? 'is-active' : ''}`}
              onClick={() => jump(index)}
            />
          ))}
        </div>
        <button
          type="button"
          className="ct-mode-carousel__arrow"
          onClick={() => go(1)}
          disabled={active === modes.length - 1}
          aria-label="Next mode"
        >
          <ArrowRight size={18} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

function ArtifactPreview({ artifact, onClose }) {
  useEffect(() => {
    if (!artifact) {
      return undefined;
    }

    const previousOverflow = document.body.style.overflow;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [artifact, onClose]);

  return (
    <AnimatePresence>
      {artifact && (
        <MOTION.div
          className="ct-artifact-preview"
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.22 }}
          onMouseDown={onClose}
        >
          <MOTION.div
            className="ct-artifact-preview__panel"
            role="dialog"
            aria-modal="true"
            aria-label={`${artifact.title} preview`}
            initial={{ opacity: 0, y: 24, scale: 0.96, filter: 'blur(10px)' }}
            animate={{ opacity: 1, y: 0, scale: 1, filter: 'blur(0px)' }}
            exit={{ opacity: 0, y: 18, scale: 0.97, filter: 'blur(8px)' }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="ct-artifact-preview__close"
              aria-label="Close preview"
              onClick={onClose}
            >
              <X size={20} />
            </button>
            <img src={artifact.previewSrc || artifact.src} alt={artifact.title} />
            <span>{artifact.label}</span>
          </MOTION.div>
        </MOTION.div>
      )}
    </AnimatePresence>
  );
}

function clampUnit(value) {
  return Math.min(1, Math.max(-1, value));
}

const artifactMotionStates = new WeakMap();
const artifactFollowEase = 0.055;
const artifactSettleThreshold = 0.01;

function writeArtifactMotion(element, values) {
  element.style.setProperty('--tilt-x', `${values.tiltX.toFixed(2)}deg`);
  element.style.setProperty('--tilt-y', `${values.tiltY.toFixed(2)}deg`);
  element.style.setProperty('--shift-x', `${values.shiftX.toFixed(2)}px`);
  element.style.setProperty('--shift-y', `${values.shiftY.toFixed(2)}px`);
}

function getArtifactMotionState(element) {
  if (!artifactMotionStates.has(element)) {
    artifactMotionStates.set(element, {
      current: { tiltX: 0, tiltY: 0, shiftX: 0, shiftY: 0 },
      target: { tiltX: 0, tiltY: 0, shiftX: 0, shiftY: 0 },
      frame: null,
    });
  }

  return artifactMotionStates.get(element);
}

function animateArtifactMotion(element) {
  const state = getArtifactMotionState(element);
  let maxDelta = 0;

  Object.keys(state.current).forEach((key) => {
    const delta = state.target[key] - state.current[key];
    state.current[key] += delta * artifactFollowEase;
    maxDelta = Math.max(maxDelta, Math.abs(delta));
  });

  writeArtifactMotion(element, state.current);

  if (maxDelta > artifactSettleThreshold) {
    state.frame = requestAnimationFrame(() => animateArtifactMotion(element));
    return;
  }

  state.current = { ...state.target };
  writeArtifactMotion(element, state.current);
  state.frame = null;
}

function setArtifactMotionTarget(element, target) {
  const state = getArtifactMotionState(element);
  state.target = target;

  if (!state.frame) {
    state.frame = requestAnimationFrame(() => animateArtifactMotion(element));
  }
}

function orbitArtifact(element, clientX, clientY, sectionRect) {
  const rect = element.getBoundingClientRect();
  const nx = clampUnit((clientX - (rect.left + rect.width / 2)) / (sectionRect.width / 2));
  const ny = clampUnit((clientY - (rect.top + rect.height / 2)) / (sectionRect.height / 2));

  setArtifactMotionTarget(element, {
    tiltX: -ny * 8,
    tiltY: nx * 10,
    shiftX: nx * 10,
    shiftY: ny * 8,
  });
}

function resetArtifactTilt(element) {
  setArtifactMotionTarget(element, {
    tiltX: 0,
    tiltY: 0,
    shiftX: 0,
    shiftY: 0,
  });
}

const heroVerbs = ['Rebalancing', 'Rewriting', 'Rethinking'];

function RotatingTitle() {
  const reduceMotion = useReducedMotion();
  const [verbIndex, setVerbIndex] = useState(0);

  useEffect(() => {
    if (reduceMotion) {
      return undefined;
    }

    const id = window.setInterval(() => {
      setVerbIndex((index) => (index + 1) % heroVerbs.length);
    }, 3600);
    return () => window.clearInterval(id);
  }, [reduceMotion]);

  const currentVerb = heroVerbs[verbIndex];

  return (
    <h1 aria-label="Rebalancing, rewriting, and rethinking the feed.">
      <span className="ct-hero-title__verb" aria-hidden="true">
        <span className="ct-hero-title__measure">{currentVerb}</span>
        <span
          className={`ct-hero-title__typed ${reduceMotion ? 'is-static' : ''}`}
          key={currentVerb}
          style={{ '--typewriter-steps': currentVerb.length }}
        >
          {currentVerb}
        </span>
      </span>
      <span className="ct-hero-title__rest" aria-hidden="true">the feed.</span>
    </h1>
  );
}

function HeroVisual() {
  const { ref, y, reduceMotion } = useDroopyMotion({
    depth: 46,
    lateral: 4,
    lag: 1.9,
    sway: 1.45,
  });
  const recoilY = useTransform(y, (value) => `${value}px`);

  return (
    <div className="ct-hero-visual">
      <div className="ct-hero-canvas ct-reveal-color" aria-hidden="true">
        <MOTION.div
          ref={ref}
          className="ct-hero-butterfly"
          style={reduceMotion ? undefined : { '--hero-recoil-y': recoilY }}
        >
          <img className="ct-hero-wing ct-hero-wing--left" src="/images/hero-butterfly.png" alt="" />
          <img className="ct-hero-wing ct-hero-wing--right" src="/images/hero-butterfly.png" alt="" />
          <img className="ct-hero-body" src="/images/hero-butterfly.png" alt="" />
        </MOTION.div>
      </div>
    </div>
  );
}

function HeroSection() {
  return (
    <section id="home" className="ct-hero">
      <HeroVisual />
      <div className="ct-hero__grid">
        <Reveal className="ct-hero__copy">
          <TextTrail className="ct-title-trail" depth={24} lag={1.2}>
            <RotatingTitle />
          </TextTrail>
          <TextTrail as="p" depth={18} lag={1.05}>
            Chrysalis is a digital wellbeing prototype exploring how social media algorithms
            can support self-awareness, variety, and healthier digital habits.
          </TextTrail>
          <TextTrail as="p" className="ct-origin-line" depth={15} lag={1.16}>
            It began after MorphoMedia, my Synopsys science fair project, and grew into a
            more personal question about the gray areas of technology ethics: how can something
            be entertaining, useful, harmful, and meaningful all at once?
          </TextTrail>
          <DroopyElement className="ct-hero__actions" depth={12} lag={0.95}>
            <a href="#journey" className="ct-button" data-cursor="soft">
              Learn my story
              <ArrowUpRight size={17} />
            </a>
            <a
              href={SURVEY_URL}
              className="ct-button ct-button--survey"
              data-cursor="soft"
              target="_blank"
              rel="noreferrer"
            >
              Take the survey
              <ArrowUpRight size={17} />
            </a>
            <Link to="/algorithm" className="ct-button ct-button--ghost" data-cursor="soft">
              Try the algorithm
              <ArrowUpRight size={17} />
            </Link>
          </DroopyElement>
          <div className="ct-origin-grid" aria-label="Project origin highlights">
            {originCards.map(([title, body], index) => (
              <DroopyElement
                className={`ct-origin-card ct-origin-card--${index + 1} ct-reveal-color`}
                depth={10 + index * 4}
                lag={1 + index * 0.18}
                key={title}
              >
                <span>{title}</span>
                <strong>{body}</strong>
              </DroopyElement>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function ProblemSection() {
  return (
    <SectionFrame id="problem" tone="aqua" label="The Problem">
      <div className="ct-split">
        <Reveal className="ct-copy-block">
          <TextTrail as="span" className="ct-kicker ct-kicker--light" depth={8} lag={0.8}>
            The Problem
          </TextTrail>
          <TextTrail as="h2" depth={24} lag={1.12}>
            "If you aren't paying for the product, you are the product."
          </TextTrail>
          <TextTrail as="span" className="ct-quote-credit" depth={10} lag={0.86}>
            Tristan Harris, The Social Dilemma, 2020
          </TextTrail>
        </Reveal>
        <Reveal className="ct-copy-block ct-copy-block--narrow" delay={0.08}>
          <TextTrail as="p" depth={18} lag={1.05}>
            After watching The Social Dilemma, one of my favorite documentaries,
            I started thinking more deeply about how social media affects people, especially teenagers.
            People often scroll when they are bored, stressed, tired, lonely, or procrastinating. 
            But I also know that social media is not all bad. Most of us cannot simply delete every app and disappear
            from the internet. That is why I made Chrysalis.
          </TextTrail>
          <MetricRows />
        </Reveal>
      </div>
    </SectionFrame>
  );
}

function JourneySection() {
  const ref = useRef(null);
  const reduceMotion = useReducedMotion();
  const isDesktop = useDesktopFiling();
  const [activeStep, setActiveStep] = useState(0);
  const [lockState, setLockState] = useState('before');
  const [previewArtifact, setPreviewArtifact] = useState(null);
  const closePreview = () => setPreviewArtifact(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end end'],
  });
  const progressScale = useTransform(scrollYProgress, [0.08, 0.92], [0, 1]);
  const shouldPin = isDesktop && !reduceMotion;
  const activeJourneyStep = journeySteps[activeStep];

  const scrollToStep = (index) => {
    const shell = ref.current;
    if (!shell) {
      return;
    }

    // When the section isn't pinned (mobile / reduced motion), the steps are a
    // simple vertical list — just bring the matching card into view.
    if (!shouldPin) {
      const mobileSteps = shell.querySelectorAll('.ct-journey-mobile-step');
      mobileSteps[index]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    // While pinned, activeStep = floor(scrollProgress × N). Aim for the middle
    // of the target step's band so it lands cleanly on that step.
    const sectionTop = shell.getBoundingClientRect().top + window.scrollY;
    const scrollable = shell.offsetHeight - window.innerHeight;
    const targetProgress = (index + 0.5) / journeySteps.length;
    window.scrollTo({
      top: sectionTop + targetProgress * scrollable,
      behavior: 'smooth',
    });
  };

  useMotionValueEvent(scrollYProgress, 'change', (latest) => {
    if (!shouldPin) {
      return;
    }

    const nextStep = Math.min(
      journeySteps.length - 1,
      Math.max(0, Math.floor(latest * journeySteps.length)),
    );
    const nextLockState = latest >= 0.995 ? 'after' : latest > 0.002 ? 'active' : 'before';

    setActiveStep((current) => (current === nextStep ? current : nextStep));
    setLockState((current) => (current === nextLockState ? current : nextLockState));
  });

  useEffect(() => {
    const shell = ref.current;
    if (!shell) {
      return undefined;
    }

    const reduceQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const activeArtifacts = () => Array.from(
      shell.querySelectorAll('.ct-journey-image.is-active .ct-journey-artifact'),
    );
    const allArtifacts = () => Array.from(shell.querySelectorAll('.ct-journey-artifact'));

    const onPointerMove = (event) => {
      if (event.pointerType === 'touch' || reduceQuery.matches) {
        return;
      }

      const stageRect = shell.querySelector('.ct-journey-stage-art')?.getBoundingClientRect()
        ?? shell.getBoundingClientRect();

      activeArtifacts().forEach((element) => {
        orbitArtifact(element, event.clientX, event.clientY, stageRect);
      });
    };
    const onPointerLeave = () => {
      allArtifacts().forEach(resetArtifactTilt);
    };

    shell.addEventListener('pointermove', onPointerMove);
    shell.addEventListener('pointerleave', onPointerLeave);

    return () => {
      shell.removeEventListener('pointermove', onPointerMove);
      shell.removeEventListener('pointerleave', onPointerLeave);
    };
  }, []);

  useEffect(() => {
    const shell = ref.current;
    if (!shell) {
      return;
    }

    Array.from(shell.querySelectorAll('.ct-journey-artifact')).forEach(resetArtifactTilt);
  }, [activeStep]);

  return (
    <section
      id="journey"
      ref={ref}
      className={`ct-journey-shell ct-journey-shell--${lockState} ct-section-shell ct-section-shell--paper`}
    >
      <div className="ct-journey-sticky ct-section">
        <div className="ct-section__tab ct-reveal-color" aria-hidden="true">The Journey</div>
        <div className="ct-journey-layout">
          <Reveal className="ct-copy-block ct-journey-copy">
            <TextTrail as="span" className="ct-kicker" depth={8} lag={0.8}>
              The Journey
            </TextTrail>
            <TextTrail as="h2" depth={26} lag={1.14}>
              A lifecycle of ethical technology.
            </TextTrail>
            <TextTrail as="p" depth={18} lag={1.04}>
              By combining the lifecycle of a butterfly with the engineering process, Chrysalis
              follows the way ethical technology is made: observation, experimentation,
              rebuilding, and growth. Chrysalis grew from the intersection of my deepest
              interests: journalism, media, and coding.
            </TextTrail>
          </Reveal>

          <div className="ct-journey-lock" aria-label="Chrysalis journey timeline">
            <div className="ct-journey-stage-art" aria-hidden="true">
              {journeySteps.map((step, index) => {
                const isActive = activeStep === index;

                return (
                  <MOTION.figure
                    className={`ct-journey-image ${isActive ? 'is-active' : ''}`}
                    key={step.title}
                    animate={{
                      opacity: isActive ? 1 : 0,
                      scale: isActive ? 1 : 0.88,
                      y: isActive ? 0 : 24,
                      filter: isActive ? 'blur(0px)' : 'blur(12px)',
                    }}
                    transition={{ duration: 0.58, ease: [0.22, 1, 0.36, 1] }}
                  >
                    <JourneyMosaic step={step} onPreview={setPreviewArtifact} interactive={isActive} />
                  </MOTION.figure>
                );
              })}
            </div>

            <DroopyElement
              className="ct-journey-caption"
              depth={20}
              lag={1.28}
              sway={1.12}
              aria-live="polite"
            >
              <span>{String(activeStep + 1).padStart(2, '0')} / {activeJourneyStep.title}</span>
              <MOTION.h3
                key={`${activeJourneyStep.title}-heading`}
                initial={shouldPin ? { opacity: 0, y: 18, filter: 'blur(8px)' } : false}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
              >
                <PhaseTitle step={activeJourneyStep} />
              </MOTION.h3>
              <MOTION.p
                key={`${activeJourneyStep.title}-body`}
                initial={shouldPin ? { opacity: 0, y: 16 } : false}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.42, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
              >
                {activeJourneyStep.body}
              </MOTION.p>
            </DroopyElement>

            <div className="ct-journey-timeline">
              <div className="ct-journey-progress" aria-hidden="true">
                <MOTION.div
                  className="ct-journey-progress__fill"
                  style={{ scaleY: shouldPin ? progressScale : 1 }}
                />
              </div>

              <div className="ct-journey-nodes">
                {journeySteps.map((step, index) => {
                  const ICON = step.icon;
                  const isActive = activeStep === index;
                  const isPast = activeStep > index;
                  const stepPercent = getJourneyStepPercent(index);

                  return (
                    <MOTION.button
                      type="button"
                      className={`ct-journey-node ${isActive ? 'is-active' : ''} ${isPast ? 'is-past' : ''}`}
                      key={step.title}
                      style={{ '--step-y': `${stepPercent}%` }}
                      onClick={() => scrollToStep(index)}
                      aria-label={`Jump to ${step.title}`}
                      aria-current={isActive ? 'step' : undefined}
                      animate={{
                        opacity: 1,
                        scale: isActive ? 1 : 0.92,
                      }}
                      transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
                    >
                      <span className="ct-journey-node__icon">
                        <ICON size={20} />
                      </span>
                      <span className="ct-journey-node__label">
                        <PhaseTitle step={step} showImage={false} />
                      </span>
                    </MOTION.button>
                  );
                })}
              </div>
            </div>

            <div className="ct-journey-mobile-list">
              {journeySteps.map((step, index) => {
                const ICON = step.icon;

                return (
                  <article className="ct-journey-mobile-step" key={step.title}>
                    <div className="ct-journey-mobile-step__mark">
                      <ICON size={19} aria-hidden="true" />
                      <span>{String(index + 1).padStart(2, '0')}</span>
                    </div>
                    <JourneyMosaic
                      step={step}
                      className="ct-journey-mobile-step__mosaic"
                      onPreview={setPreviewArtifact}
                    />
                    <div>
                      <h3><PhaseTitle step={step} /></h3>
                      <p>{step.body}</p>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </div>
      </div>
      <ArtifactPreview artifact={previewArtifact} onClose={closePreview} />
    </section>
  );
}

function SolutionSection() {
  return (
    <SectionFrame id="solution" tone="ink" label="The Solution">
      <div className="ct-solution-layout">
        <Reveal className="ct-copy-block ct-solution-copy">
          <TextTrail as="span" className="ct-kicker" depth={8} lag={0.8}>
            The Solution
          </TextTrail>
          <TextTrail as="h2" depth={26} lag={1.16}>
            Three algorithms for three goals.
          </TextTrail>
          <TextTrail as="p" depth={18} lag={1.06}>
            While designing Chrysalis, I thought about different ways people struggle with
            social media. Some people want a healthier feed. Some want help reducing screen
            time. Others want a small daily reset instead of an endless personalized scroll.
            Chrysalis turns those needs into three modes.
          </TextTrail>
        </Reveal>
        <Reveal className="ct-mode-showcase">
          <ModeCarousel modes={solutionModes} />
        </Reveal>
      </div>
    </SectionFrame>
  );
}

function FutureSection() {
  return (
    <SectionFrame id="future" tone="paper" label="The Future">
      <div className="ct-future-layout">
        <Reveal className="ct-copy-block ct-copy-block--center">
          <TextTrail as="span" className="ct-kicker" depth={8} lag={0.8}>
            The Future
          </TextTrail>
          <TextTrail as="h2" depth={26} lag={1.16}>
            A changing prototype for a changing internet.
          </TextTrail>
          <TextTrail as="p" depth={18} lag={1.06}>
            Chrysalis is a prototype. It is not a finished product, and it should not pretend
            to be one. The beauty and difficulty of ethical technology is that there is always
            a gray area. Social media can connect and harm, inspire and distract, help and
            overwhelm. Understanding those gray areas will take time. The next step is making
            Chrysalis more grounded in real student experiences and more transparent about how
            its recommendations work.
          </TextTrail>
          <DroopyElement className="ct-future__actions" depth={12} lag={0.95}>
            <a
              href={SURVEY_URL}
              className="ct-button"
              data-cursor="soft"
              target="_blank"
              rel="noreferrer"
            >
              Take the Survey
              <ArrowUpRight size={17} />
            </a>
          </DroopyElement>
        </Reveal>
      </div>
    </SectionFrame>
  );
}

function CreatorSection() {
  return (
    <SectionFrame id="about" tone="aqua" label="About">
      <div className="ct-creator-layout">
        <Reveal className="ct-copy-block">
          <TextTrail as="span" className="ct-kicker ct-kicker--light" depth={8} lag={0.8}>
            About
          </TextTrail>
          <TextTrail as="h2" depth={24} lag={1.12}>
            The Creator
          </TextTrail>
          <TextTrail as="p" depth={18} lag={1.05}>
            My name is Elaine Che, and I am a student at Saratoga High School. As a journalist,
            coder, and researcher, I am interested in how technology shapes the way people think,
            feel, and live. Chrysalis is where I combine those interests into one project.
          </TextTrail>
          <TextTrail as="p" depth={20} lag={1.14}>
            It began as MorphoMedia, my Synopsys science fair project, and grew into a prototype
            about healthier recommendation systems. I hope to build technology that does not
            just capture people's attention but helps them understand themselves better.
          </TextTrail>
        </Reveal>
        <DroopyElement className="ct-profile-card-shell" depth={30} lag={1.5} sway={1.25}>
          <Reveal className="ct-profile-card ct-reveal-color" delay={0.12}>
            <div className="ct-profile-card__mark ct-reveal-color">
              <img src="/images/me.png" alt="Portrait of Elaine Che" />
            </div>
            <div className="ct-profile-card__meta">
              <span>Student journalist, coder, researcher</span>
            </div>
            <div className="ct-profile-card__name">
              <h3>Elaine Che</h3>
            </div>
            <div className="ct-profile-card__links-layer">
              <div className="ct-profile-card__links">
                <a href="https://github.com/CatInTheRiceHat" target="_blank" rel="noopener noreferrer">
                  <Github size={17} />
                  GitHub
                </a>
                <a href="https://www.linkedin.com/in/elaine-che-03647530a/" target="_blank" rel="noopener noreferrer">
                  <Linkedin size={17} />
                  LinkedIn
                </a>
                <a href="mailto:elaineyouyuanche@gmail.com">
                  <Mail size={17} />
                  Email
                </a>
              </div>
            </div>
          </Reveal>
        </DroopyElement>
      </div>
    </SectionFrame>
  );
}

function ContactSection() {
  return (
    <footer id="contact" className="ct-footer">
      <div className="ct-footer__heading">
        <TextTrail as="span" className="ct-kicker ct-kicker--light" depth={8} lag={0.8}>
          Contact
        </TextTrail>
        <TextTrail as="h2" depth={26} lag={1.16}>
          Let's learn together.
        </TextTrail>
        <TextTrail as="p" className="ct-footer__lede" depth={18} lag={1.04}>
          Chrysalis is still growing. I am looking for feedback from students, educators,
          researchers, and anyone interested in healthier technology.
        </TextTrail>
      </div>
      <div className="ct-footer__grid">
        {[
          ['Try the algorithm', '/algorithm', <Route size={22} aria-hidden="true" />],
          ['Email Elaine', 'mailto:elaineyouyuanche@gmail.com', <Mail size={22} aria-hidden="true" />],
        ].map(([label, href, icon], index) => (
          <DroopyElement
            as="a"
            depth={16 + index * 7}
            href={href}
            key={label}
            lag={1 + index * 0.18}
            className="ct-footer-card ct-reveal-color"
          >
            <div className="ct-footer-card__icon">
              {icon}
            </div>
            <div className="ct-footer-card__label-layer">
              <span>{label}</span>
            </div>
            <div className="ct-footer-card__arrow">
              <ArrowUpRight size={18} />
            </div>
          </DroopyElement>
        ))}
      </div>
      <div className="ct-footer__bottom">
        <span>Chrysalis © 2026</span>
        <span>Teen-built recommendation systems prototype</span>
      </div>
    </footer>
  );
}

function SystemRail() {
  return (
    <aside className="ct-system-rail" aria-label="System summary">
      <div>
        <Newspaper size={18} className="ct-reveal-color" />
        <span>journalism</span>
      </div>
      <div>
        <Award size={18} className="ct-reveal-color" />
        <span>science fair</span>
      </div>
      <div>
        <Code2 size={18} className="ct-reveal-color" />
        <span>prototype</span>
      </div>
      <div>
        <ClipboardList size={18} className="ct-reveal-color" />
        <span>student input</span>
      </div>
      <div>
        <MessageCircle size={18} className="ct-reveal-color" />
        <span>agency</span>
      </div>
      <div>
        <Brain size={18} className="ct-reveal-color" />
        <span>wellbeing aware</span>
      </div>
    </aside>
  );
}

export function RebootPage() {
  return (
    <main className="ct-page">
      <SystemRail />
      <HeroSection />
      <ProblemSection />
      <JourneySection />
      <SolutionSection />
      <FutureSection />
      <CreatorSection />
      <ContactSection />
    </main>
  );
}
