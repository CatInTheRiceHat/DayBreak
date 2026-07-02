import { BRAND } from '../brand.js';
import { useEffect, useState, useRef } from 'react';
import { motion as MOTION, useInView, AnimatePresence, useReducedMotion } from 'motion/react';
import { FlutterFeed } from './FlutterFeed';
import { Metamorphosis } from './Metamorphosis';
import { DailyDew } from './DailyDew';

const ALGORITHM_UNDER_CONSTRUCTION = true;

const PHASE_ICONS = [
  {
    src: '/images/journey-egg.png',
    alt: 'Egg phase',
  },
  {
    src: '/images/journey-caterpillar.png',
    alt: 'Caterpillar phase',
  },
  {
    src: '/images/journey-chrysalis.png',
    alt: `${BRAND} phase`,
  },
  {
    src: '/images/journey-emerged.png',
    alt: 'Emerged phase',
  },
];

const TABS = [
  {
    id: 'algorithm',
    label: 'Flutter Feed',
    title: 'Try the algorithm.',
    subtitle: `Configure and run the ${BRAND} recommendation engine against a live dataset.`,
  },
  {
    id: 'cocoon',
    label: 'Metamorphosis',
    title: 'Start your taper.',
    subtitle: 'Enroll to gradually reduce daily screen time using exponential decay — 20% less each week.',
  },
  {
    id: 'migration',
    label: 'Daily Dew',
    title: "Today's drops.",
    subtitle: 'Non-personalized daily drops curated for diversity and wellbeing. Same content for everyone.',
  },
];

function PhaseIconCarousel({ reduceMotion }) {
  const [activePhase, setActivePhase] = useState(0);
  const phase = PHASE_ICONS[activePhase];

  useEffect(() => {
    if (reduceMotion) {
      return undefined;
    }

    const id = window.setInterval(() => {
      setActivePhase((current) => (current + 1) % PHASE_ICONS.length);
    }, 1350);

    return () => window.clearInterval(id);
  }, [reduceMotion]);

  return (
    <div
      className="relative h-28 w-32 sm:h-32 sm:w-36 flex items-center justify-center"
      role="img"
      aria-label={`${phase.alt} icon`}
    >
      <AnimatePresence mode="wait">
        <MOTION.img
          key={phase.src}
          src={phase.src}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 m-auto h-full w-full object-contain drop-shadow-[0_24px_52px_rgba(124,109,140,0.22)]"
          initial={{
            opacity: 0,
            x: reduceMotion ? 0 : 20,
            scale: reduceMotion ? 1 : 0.9,
            rotate: reduceMotion ? 0 : -5,
            filter: reduceMotion ? 'none' : 'blur(8px)',
          }}
          animate={{ opacity: 1, x: 0, scale: 1, rotate: 0, filter: 'blur(0px)' }}
          exit={{
            opacity: 0,
            x: reduceMotion ? 0 : -20,
            scale: reduceMotion ? 1 : 0.9,
            rotate: reduceMotion ? 0 : 5,
            filter: reduceMotion ? 'none' : 'blur(8px)',
          }}
          transition={{ duration: reduceMotion ? 0.01 : 0.48, ease: [0.22, 1, 0.36, 1] }}
        />
      </AnimatePresence>
    </div>
  );
}

function AlgorithmUnderConstruction({ reduceMotion }) {
  return (
    <section
      id="algorithm"
      className="min-h-screen px-8 py-32 lg:px-16 gradient-mesh overflow-hidden flex items-center justify-center"
    >
      <MOTION.div
        className="w-full max-w-3xl mx-auto flex flex-col items-center text-center gap-7"
        initial={{ opacity: 0, y: reduceMotion ? 0 : 24, filter: reduceMotion ? 'none' : 'blur(10px)' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        transition={{ duration: reduceMotion ? 0.2 : 0.7, ease: [0.22, 1, 0.36, 1] }}
      >
        <PhaseIconCarousel reduceMotion={reduceMotion} />
        <span className="section-badge liquid-glass">Algorithm</span>
        <div className="flex flex-col gap-4 items-center">
          <h1 className="font-title text-5xl sm:text-6xl md:text-7xl text-foreground leading-[0.95] tracking-normal">
            Algorithm under construction.
          </h1>
          <p className="font-body font-light text-base sm:text-lg text-foreground/60 max-w-xl leading-relaxed">
            This part of {BRAND} is still being polished, so please do not test the algorithm yet.
          </p>
        </div>
      </MOTION.div>
    </section>
  );
}

export function AlgorithmPage() {
  const reduceMotion = useReducedMotion();
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });
  const [active, setActive] = useState('algorithm');

  if (ALGORITHM_UNDER_CONSTRUCTION) {
    return <AlgorithmUnderConstruction reduceMotion={reduceMotion} />;
  }

  const meta = TABS.find((t) => t.id === active);

  return (
    <section id="algorithm" className="py-32 px-8 lg:px-16 gradient-mesh overflow-hidden">
      <div className="max-w-7xl mx-auto flex flex-col gap-12" ref={ref}>

        <MOTION.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="flex flex-col gap-5 items-center text-center"
        >
          <span className="section-badge liquid-glass">Algorithm</span>

          <div
            className="algorithm-tab-list flex items-center gap-1 p-1.5 rounded-full"
            style={{
              background: 'rgba(250,249,246,0.76)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid rgba(147,142,151,0.34)',
              boxShadow: '0 4px 20px rgba(43,38,49,0.08)',
            }}
          >
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActive(tab.id)}
                className={`algorithm-tab rounded-full px-4 py-2 font-body text-sm font-medium transition-all duration-200 ${
                  active === tab.id
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-foreground/50 hover:text-foreground hover:bg-secondary/45'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            <MOTION.div
              key={active}
              initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              exit={{ opacity: 0, y: -8, filter: 'blur(4px)' }}
              transition={{ duration: 0.25 }}
              className="flex flex-col gap-2 items-center"
            >
              <h2 className="algorithm-title font-title text-4xl md:text-6xl text-foreground leading-[1] tracking-normal">
                {meta.title}
              </h2>
              <p className="font-body font-light text-base text-foreground/55 max-w-lg">
                {meta.subtitle}
              </p>
            </MOTION.div>
          </AnimatePresence>
        </MOTION.div>

        <MOTION.div
          initial={{ opacity: 0, y: 24 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.7, delay: 0.15 }}
        >
          <AnimatePresence mode="wait">
            <MOTION.div
              key={active}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.3 }}
            >
              {active === 'algorithm' && <FlutterFeed />}
              {active === 'cocoon' && <Metamorphosis />}
              {active === 'migration' && <DailyDew />}
            </MOTION.div>
          </AnimatePresence>
        </MOTION.div>

      </div>
    </section>
  );
}
