import { BRAND } from '../brand.js';
import { useRef, useState, useEffect } from 'react';
import { motion, AnimatePresence, useMotionValue, useReducedMotion, useScroll, useSpring, useTransform } from 'motion/react';
import { ArrowUpRight } from 'lucide-react';
import ButterflyCanvas from './ButterflyCanvas';

const TAGLINES = [
  'Rewriting the Feed for Human Wellbeing',
  'A Healthier Algorithm for a Noisier Internet',
  'Recommendation Logic That Can Actually Care',
];

function CyclingHeadline() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setIndex(i => (i + 1) % TAGLINES.length);
    }, 3500);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="hero-headline-frame">
      <AnimatePresence mode="wait">
        <motion.h1
          key={index}
          initial={{ opacity: 0, y: 28, filter: 'blur(8px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -18, filter: 'blur(4px)' }}
          transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
          className="hero-heading"
        >
          {TAGLINES[index]}
        </motion.h1>
      </AnimatePresence>
    </div>
  );
}

export function Hero() {
  const heroRef = useRef(null);
  const reduceMotion = useReducedMotion();
  const pointerX = useMotionValue(0);
  const pointerY = useMotionValue(0);
  const smoothX = useSpring(pointerX, { stiffness: 90, damping: 24 });
  const smoothY = useSpring(pointerY, { stiffness: 90, damping: 24 });
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ['start start', 'end start'],
  });

  const butterflyY = useTransform(scrollYProgress, [0, 1], [0, -160]);
  const butterflyX = useTransform(smoothX, [-1, 1], [-64, 64]);
  const butterflyTilt = useTransform(smoothX, [-1, 1], [-9, 9]);
  const butterflyLift = useTransform(smoothY, [-1, 1], [-46, 46]);
  const butterflyScale = useTransform(scrollYProgress, [0, 1], [1, 0.9]);
  const networkX = useTransform(smoothX, [-1, 1], [28, -28]);
  const networkY = useTransform(smoothY, [-1, 1], [18, -18]);
  const textY = useTransform(scrollYProgress, [0, 1], [0, -90]);
  const textBlur = useTransform(scrollYProgress, [0.55, 1], [0, 6]);
  const textFilter = useTransform(textBlur, (value) => `blur(${value}px)`);

  const scrollToProject = () => {
    document.getElementById('problem')?.scrollIntoView({ behavior: 'smooth' });
  };

  const handlePointerMove = (event) => {
    if (reduceMotion) {
      return;
    }
    const rect = heroRef.current?.getBoundingClientRect();
    if (!rect) {
      return;
    }
    pointerX.set(((event.clientX - rect.left) / rect.width - 0.5) * 2);
    pointerY.set(((event.clientY - rect.top) / rect.height - 0.5) * 2);
  };

  return (
    <section
      ref={heroRef}
      id="home"
      className="hero-cardiatec"
      onPointerMove={handlePointerMove}
    >
      <motion.div
        aria-hidden="true"
        className="hero-wave-field"
        style={reduceMotion ? undefined : { x: networkX, y: networkY }}
      >
        <span />
        <span />
        <span />
      </motion.div>

      <motion.div
        style={{
          y: butterflyY,
          x: reduceMotion ? 0 : butterflyX,
          rotate: reduceMotion ? 0 : butterflyTilt,
          scale: reduceMotion ? 1 : butterflyScale,
          position: 'absolute',
          right: 0,
          top: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          zIndex: 1,
        }}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.74, filter: 'blur(16px)' }}
          animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
          transition={{ duration: 1.25, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="w-full h-full"
        >
          <motion.div
            className="hero-butterfly-stage"
            style={{ pointerEvents: 'auto', y: reduceMotion ? 0 : butterflyLift }}
          >
            <ButterflyCanvas width={1100} height={700} />
          </motion.div>
        </motion.div>
      </motion.div>

      <motion.div
        className="hero-cardiatec__content"
        style={{
          zIndex: 2,
          y: reduceMotion ? 0 : textY,
          filter: reduceMotion ? undefined : textFilter,
        }}
      >
        <motion.p
          className="hero-kicker"
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.75, delay: 0.15 }}
        >
          {BRAND} Algorithm Project
        </motion.p>
        <CyclingHeadline />
        <motion.p
          initial={{ opacity: 0, filter: 'blur(8px)', y: 50, scale: 0.97 }}
          animate={{ opacity: 1, filter: 'blur(0px)', y: 0, scale: 1 }}
          transition={{ duration: 1.2, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="hero-subhead"
        >
          {BRAND} is a research-backed recommendation algorithm that changes what a feed optimizes for:
          less passive scrolling, more diversity, safer timing, and clearer control.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 50, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 1.2, delay: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="hero-actions"
        >
          <motion.button
            onClick={scrollToProject}
            data-cursor="soft"
            whileHover={{ scale: 1.06 }}
            whileTap={{ scale: 0.96 }}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            className="hero-primary-button"
          >
            See the Research
            <ArrowUpRight className="w-4 h-4" />
          </motion.button>
          <div className="hero-pagination" aria-hidden="true">
            <span>01</span>
            <i />
            <span>06</span>
          </div>
        </motion.div>
      </motion.div>
    </section>
  );
}
