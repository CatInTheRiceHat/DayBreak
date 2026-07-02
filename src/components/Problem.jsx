import { useRef, useEffect } from 'react';
import { motion, useInView, useMotionValue, useTransform, animate } from 'motion/react';

function StatCounter({ value, suffix, label, delay = 0 }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-80px' });
  const count = useMotionValue(0);
  const displayed = useTransform(count, (v) => {
    const fixed = suffix === ' hrs/day' ? v.toFixed(1) : Math.round(v);
    return `${fixed}${suffix}`;
  });

  useEffect(() => {
    if (isInView) {
      const controls = animate(count, value, {
        duration: 1.8,
        delay,
        ease: [0.22, 1, 0.36, 1],
      });
      return controls.stop;
    }
  }, [isInView, count, value, delay]);

  return (
    <div ref={ref} className="flex flex-col gap-2">
      <motion.span className="font-heading text-5xl lg:text-6xl tracking-tight text-foreground">
        {displayed}
      </motion.span>
      <span className="font-body font-light text-sm text-foreground/45 leading-snug max-w-[160px]">
        {label}
      </span>
    </div>
  );
}

export function Problem() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, amount: 0.15 });

  return (
    <section id="problem" ref={ref} className="px-6 lg:px-20 py-28 lg:py-40">
      <div className="max-w-4xl">
        <motion.span
          initial={{ opacity: 0, x: -30 }}
          animate={inView ? { opacity: 1, x: 0 } : {}}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="font-body text-sm uppercase tracking-widest text-foreground/40 mb-8 block"
        >
          The Problem
        </motion.span>

        <motion.h2
          initial={{ opacity: 0, y: 80, filter: 'blur(12px)' }}
          animate={inView ? { opacity: 1, y: 0, filter: 'blur(0px)' } : {}}
          transition={{ duration: 0.9, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="font-heading text-6xl md:text-8xl text-foreground leading-[0.92] tracking-tight mb-10"
        >
          The feed is working exactly<br />
          as designed.
        </motion.h2>

        <motion.p
          initial={{ opacity: 0, y: 40, filter: 'blur(8px)' }}
          animate={inView ? { opacity: 1, y: 0, filter: 'blur(0px)' } : {}}
          transition={{ duration: 0.8, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="font-body font-light text-xl text-foreground/55 max-w-xl leading-relaxed"
        >
          Today's algorithms optimize for one metric: time on screen. The result is content
          engineered to spike dopamine, disrupt sleep, and leave you scrolling past empty.
        </motion.p>

        <motion.div
          initial={{ scaleX: 0 }}
          animate={inView ? { scaleX: 1 } : {}}
          transition={{ duration: 0.8, delay: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mt-16 h-px w-32 opacity-70"
          style={{
            transformOrigin: 'left',
            background: 'linear-gradient(90deg, var(--wing-green), var(--wing-blue), var(--wing-pink))',
          }}
        />

        {/* Stat counters */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, delay: 0.65, ease: [0.22, 1, 0.36, 1] }}
          className="grid grid-cols-1 sm:grid-cols-3 gap-10 mt-14 pt-10 border-t border-black/8"
        >
          {[
            { value: 2.5, suffix: ' hrs/day', label: 'avg. daily teen social media use' },
            { value: 43, suffix: '%', label: 'of teens say it worsens their mental health' },
            { value: 17, suffix: 'M', label: 'US teens actively on social platforms' },
          ].map((stat, i) => (
            <StatCounter key={i} {...stat} delay={0.7 + i * 0.15} />
          ))}
        </motion.div>
      </div>
    </section>
  );
}
