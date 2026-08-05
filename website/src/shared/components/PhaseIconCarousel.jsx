import { BRAND } from '../../brand.js';
import { useEffect, useState } from 'react';
import { motion as MOTION, AnimatePresence, useReducedMotion } from 'motion/react';

// Butterfly life-cycle phases, in metamorphosis order.
export const PHASE_ICONS = [
  { src: '/images/journey-egg.png', alt: 'Egg phase' },
  { src: '/images/journey-caterpillar.png', alt: 'Caterpillar phase' },
  { src: '/images/journey-chrysalis.png', alt: `${BRAND} phase` },
  { src: '/images/journey-emerged.png', alt: 'Emerged phase' },
];

/**
 * Cycles the four metamorphosis phase icons, morphing between them with a
 * blur + slide + scale + rotate transition (shared by the "Algorithm under
 * construction" screen and the reel feed loader).
 *
 * @param {string} className  sizing/positioning classes for the root box
 * @param {number} interval   ms between phase changes (default 1350)
 */
export function PhaseIconCarousel({ className = '', interval = 1350 }) {
  const reduceMotion = useReducedMotion();
  const [activePhase, setActivePhase] = useState(0);
  const phase = PHASE_ICONS[activePhase];

  useEffect(() => {
    if (reduceMotion) {
      return undefined;
    }
    const id = window.setInterval(() => {
      setActivePhase((current) => (current + 1) % PHASE_ICONS.length);
    }, interval);
    return () => window.clearInterval(id);
  }, [reduceMotion, interval]);

  return (
    <div
      className={`relative flex items-center justify-center ${className}`.trim()}
      role="img"
      aria-label={`${phase.alt} icon`}
    >
      <AnimatePresence mode="wait">
        <MOTION.img
          key={phase.src}
          src={phase.src}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 m-auto h-full w-full object-contain"
          style={{ filter: 'drop-shadow(0 24px 52px color-mix(in srgb, var(--db-color-twilight-violet) 22%, transparent))' }}
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
