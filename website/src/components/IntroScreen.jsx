import { BRAND } from '../brand.js';
import { useEffect, useRef, useState } from 'react';
import { motion as MOTION, useReducedMotion } from 'motion/react';

export function IntroScreen({ onDone }) {
  const [day, setDay] = useState(0);
  const reduceMotion = useReducedMotion();
  const maxDays = 14;
  const progress = Math.min(100, Math.round((day / maxDays) * 100));
  const statusText = progress < 62 ? 'Fluttering my wings...' : 'Emerging out of my cocoon...';
  const doneRef = useRef(false);

  useEffect(() => {
    if (reduceMotion) {
      const timeout = setTimeout(onDone, 1200);
      return () => clearTimeout(timeout);
    }

    const id = setInterval(() => {
      setDay(d => {
        const next = d + 1;
        if (next >= maxDays) {
          clearInterval(id);
          if (!doneRef.current) {
            doneRef.current = true;
            setTimeout(onDone, 1100);
          }
        }
        return next;
      });
    }, 280);
    return () => clearInterval(id);
  }, [onDone, reduceMotion]);

  return (
    <MOTION.div
      className="intro-screen"
      initial={{ opacity: 1 }}
      exit={{ opacity: 0, y: '-100%', filter: 'blur(14px)' }}
      transition={{ duration: reduceMotion ? 0.25 : 1.15, ease: [0.22, 1, 0.36, 1] }}
    >
      <MOTION.div
        className="intro-orbit"
        initial={{ scale: 0.8, opacity: 0, filter: 'blur(18px)' }}
        animate={{ scale: 1, opacity: 1, filter: 'blur(0px)' }}
        transition={{ duration: 1.45, ease: [0.22, 1, 0.36, 1] }}
        aria-hidden="true"
      >
        <span className="intro-logo" role="img" aria-label={BRAND}><img src="/images/logo.png" alt="" /></span>
      </MOTION.div>
      <MOTION.p
        className="intro-eyebrow"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.35 }}
      >
        {BRAND}
      </MOTION.p>
      <MOTION.h1
        className="intro-title"
        initial={{ opacity: 0, y: 40, filter: 'blur(12px)' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        transition={{ duration: 1.1, delay: 0.65, ease: [0.22, 1, 0.36, 1] }}
      >
        Reimagining the social media feed
        <br />
        for human wellbeing.
      </MOTION.h1>
      <MOTION.p
        className="intro-tagline"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.85, delay: 1.25 }}
      >
        What if your feed helped you feel more like yourself again?
      </MOTION.p>
      <MOTION.div
        className="intro-formula-wrapper"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.85, delay: 1.65 }}
      >
        <p className="intro-formula-text">
          {statusText}
        </p>
        <div className="intro-bar-track">
          <MOTION.div
            className="intro-bar-fill"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
          />
        </div>
      </MOTION.div>
    </MOTION.div>
  );
}
