import { BRAND } from '../brand.js';
import { useRef } from 'react';
import { motion, useInView } from 'motion/react';

export function Solution() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, amount: 0.15 });

  return (
    <section id="solution" ref={ref} className="bg-white px-6 lg:px-20 py-28 lg:py-40">
      <div className="max-w-4xl">
        <motion.span
          initial={{ opacity: 0, x: -30 }}
          animate={inView ? { opacity: 1, x: 0 } : {}}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="font-body text-sm uppercase tracking-widest text-foreground/40 mb-8 block"
        >
          The Solution
        </motion.span>

        <motion.h2
          initial={{ opacity: 0, y: 80, filter: 'blur(12px)' }}
          animate={inView ? { opacity: 1, y: 0, filter: 'blur(0px)' } : {}}
          transition={{ duration: 0.9, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="font-heading text-6xl md:text-8xl text-foreground leading-[0.92] tracking-tight mb-10"
        >
          What if the algorithm<br />
          actually cared?
        </motion.h2>

        <motion.p
          initial={{ opacity: 0, y: 40, filter: 'blur(8px)' }}
          animate={inView ? { opacity: 1, y: 0, filter: 'blur(0px)' } : {}}
          transition={{ duration: 0.8, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="font-body font-light text-xl text-foreground/55 max-w-xl leading-relaxed"
        >
          {BRAND} is a recommendation algorithm built around wellbeing. It gradually
          tapers screen time, diversifies your feed, and eases you toward healthier habits —
          without quitting cold turkey.
        </motion.p>

        <motion.div
          initial={{ scaleX: 0 }}
          animate={inView ? { scaleX: 1 } : {}}
          transition={{ duration: 0.8, delay: 0.5, ease: [0.22, 1, 0.36, 1] }}
          style={{ transformOrigin: 'left' }}
          className="mt-16 flex gap-3"
        >
          <div
            className="h-px flex-1 max-w-xs opacity-70"
            style={{ background: 'linear-gradient(90deg, var(--wing-blue), var(--wing-green), var(--wing-yellow))' }}
          />
          <div
            className="h-px w-8 opacity-50"
            style={{ background: 'linear-gradient(90deg, var(--wing-pink), var(--wing-yellow))' }}
          />
        </motion.div>
      </div>
    </section>
  );
}
