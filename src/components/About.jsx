import { BRAND } from '../brand.js';
import { useRef } from 'react';
import { motion, useInView } from 'motion/react';
import { AnimatedSection, AnimatedItem } from './AnimatedSection';

const PILLS = ['Student', 'Researcher', 'Builder'];

function GlassOrb({ size, style }) {
  return (
    <div
      className="orb absolute pointer-events-none"
      style={{ width: size, height: size, ...style }}
    />
  );
}

export function About() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <section id="about" className="relative py-32 px-8 lg:px-16 overflow-hidden gradient-mesh">
      {/* Decorative orbs */}
      <GlassOrb size={220} style={{ top: '10%', right: '-4%', opacity: 0.35, animationDelay: '1s' }} />
      <GlassOrb size={140} style={{ bottom: '15%', left: '-2%', opacity: 0.25, animationDelay: '3s' }} />

      <div className="max-w-7xl mx-auto" ref={ref}>
        <div className="grid lg:grid-cols-2 gap-16 lg:gap-24 items-center">

          {/* ── Text column ── */}
          <div className="flex flex-col gap-8">
            <motion.span
              initial={{ opacity: 0, y: 12 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5 }}
              className="section-badge liquid-glass self-start"
            >
              About
            </motion.span>

            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="font-heading text-4xl md:text-5xl text-foreground leading-[0.92] tracking-[-1px]"
            >
              Built by someone who got tired of watching people scroll.
            </motion.h2>

            <div className="flex flex-col gap-5">
              {[
                {
                  delay: 0.2,
                  text: "I grew up watching the people around me — including myself — get pulled deeper into feeds that seemed designed to leave you feeling worse than when you started. The anxiety, the comparison, the doomscrolling at 2am. I kept wondering: does it have to be this way?",
                },
                {
                  delay: 0.3,
                  text: "So I started researching. I read the papers on passive consumption, upward social comparison, emotional contagion, crisis rabbit holes. What I found was that the harms weren't random — they were built into the algorithm. Engagement-at-all-costs was the design. I decided to build a different one.",
                },
                {
                  delay: 0.4,
                  text: `${BRAND} is what came out of that: a recommendation algorithm grounded in psychology and data science, tested on real data, and built specifically for teenagers. I'm Elaine Che — a student and builder who thinks technology can be designed to actually care about the people using it.`,
                },
              ].map(({ delay, text }) => (
                <motion.p
                  key={delay}
                  initial={{ opacity: 0, y: 14 }}
                  animate={inView ? { opacity: 1, y: 0 } : {}}
                  transition={{ duration: 0.6, delay }}
                  className="font-body font-light text-base text-foreground/65 leading-relaxed"
                >
                  {text}
                </motion.p>
              ))}
            </div>

            {/* Role pills */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: 0.55 }}
              className="flex items-center gap-3 flex-wrap pt-2"
            >
              {PILLS.map((label) => (
                <span
                  key={label}
                  className="liquid-glass rounded-full px-4 py-1.5 font-body text-sm font-medium text-foreground/70"
                >
                  {label}
                </span>
              ))}
            </motion.div>
          </div>

          {/* ── Decorative right column ── */}
          <motion.div
            initial={{ opacity: 0, scale: 0.92 }}
            animate={inView ? { opacity: 1, scale: 1 } : {}}
            transition={{ duration: 0.9, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="relative flex justify-center items-center"
          >
            {/* Main glass card */}
            <div className="glass-card rounded-3xl p-8 max-w-sm w-full flex flex-col gap-6">
              <div className="flex items-center gap-3">
                <img
                  className="w-12 h-12 rounded-full object-cover"
                  src="/images/me.png"
                  alt="Portrait of Elaine Che"
                  style={{ objectPosition: 'center 42%', border: '1px solid rgba(167,139,250,0.3)' }}
                />
                <div>
                  <p className="font-body font-semibold text-sm text-foreground">Elaine Che</p>
                  <p className="font-body font-light text-xs text-foreground/50">Creator of {BRAND}</p>
                </div>
              </div>

              <AnimatedSection stagger className="flex flex-col gap-4">
                {[
                  { label: 'Focus', val: 'Youth mental health & tech ethics' },
                  { label: 'Stack', val: 'Python · React · Three.js · FastAPI' },
                  { label: 'Approach', val: 'Research-first, data-backed' },
                  { label: 'Goal', val: 'Algorithms that heal, not harm' },
                ].map(({ label, val }) => (
                  <AnimatedItem key={label}>
                    <div className="flex flex-col gap-0.5">
                      <span className="font-body text-xs font-medium text-foreground/40 uppercase tracking-wider">{label}</span>
                      <span className="font-body text-sm text-foreground/80">{val}</span>
                    </div>
                  </AnimatedItem>
                ))}
              </AnimatedSection>

              {/* Iridescent accent line */}
              <div className="h-px w-full" style={{ background: 'linear-gradient(90deg, #a78bfa, #67e8f9, #f0abfc)', opacity: 0.4 }} />

              <p className="font-body font-light text-xs text-foreground/40 italic">
                "The algorithm is the argument."
              </p>
            </div>

            {/* Floating accent orbs */}
            <div className="orb absolute w-20 h-20 opacity-50" style={{ top: '-8%', right: '2%', animationDelay: '0.5s' }} />
            <div className="orb absolute w-12 h-12 opacity-35" style={{ bottom: '5%', left: '0%', animationDelay: '2.5s' }} />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
