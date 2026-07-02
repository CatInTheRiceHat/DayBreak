import { useRef } from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'motion/react';

const ACCENTS = {
  green: 'var(--wing-green)',
  blue: 'var(--wing-blue)',
  pink: 'var(--wing-pink)',
  yellow: 'var(--wing-yellow)',
};

export function CardiaPanel({ children, color = 'blue', className = '' }) {
  const ref = useRef(null);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end start'],
  });

  const scale = useTransform(scrollYProgress, [0.54, 0.92], [1, 0.955]);
  const opacity = useTransform(scrollYProgress, [0.68, 0.98], [1, 0.18]);
  const blur = useTransform(scrollYProgress, [0.56, 0.92], [0, 5]);
  const y = useTransform(scrollYProgress, [0, 1], [0, -20]);
  const filter = useTransform(blur, (value) => `blur(${value}px)`);

  return (
    <div
      ref={ref}
      className={`cardia-panel-shell ${className}`}
      style={{ '--panel-accent': ACCENTS[color] ?? ACCENTS.blue }}
    >
      <motion.div
        className="cardia-panel"
        style={reduceMotion ? undefined : { scale, opacity, filter, y }}
      >
        {children}
      </motion.div>
    </div>
  );
}
