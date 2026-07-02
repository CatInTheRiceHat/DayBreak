import { BRAND } from '../brand.js';
import { useRef } from 'react';
import { motion, useInView } from 'motion/react';
import { Github, Linkedin, Mail, Instagram, ArrowUpRight } from 'lucide-react';

const SubstackIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M22.539 8.242H1.46V6.741h21.08v1.501zm0 2.286H1.46V12h21.08v-1.471zM1.46 15.272h21.08v-1.5H1.46v1.5zM1.46 1.5v1.501h21.08V1.5H1.46zm0 20.998L12 17.085l10.54 5.413V9.836H1.46v12.662z"/>
  </svg>
);

const LINKS = [
  {
    icon: Github,
    label: 'GitHub',
    sub: 'See the code',
    href: 'https://github.com/CatInTheRiceHat',
    color: 'var(--wing-green)',
  },
  {
    icon: Linkedin,
    label: 'LinkedIn',
    sub: "Let's connect",
    href: 'https://www.linkedin.com/in/elaine-che-03647530a/',
    color: 'var(--wing-blue)',
  },
  {
    icon: Mail,
    label: 'Email',
    sub: 'Say hello',
    href: 'mailto:elaineyouyuanche@gmail.com',
    color: 'var(--wing-pink)',
  },
  {
    icon: Instagram,
    label: 'Instagram',
    sub: 'Follow along',
    href: 'https://www.instagram.com/elaineyouyuanche/',
    color: 'var(--wing-yellow)',
  },
  {
    icon: SubstackIcon,
    label: 'Substack',
    sub: 'Read the blog',
    href: '#',
    color: '#f97316',
  },
];

function ButterflyFooterIcon() {
  return (
    <svg width="32" height="26" viewBox="0 0 32 26" fill="none" aria-hidden="true">
      <path d="M16 13 C12 9 3 6 1 10 C-1 14 5 19 11 16 C13 15 15 14 16 13Z" fill="url(#fl1)" opacity="0.7"/>
      <path d="M16 13 C20 9 29 6 31 10 C33 14 27 19 21 16 C19 15 17 14 16 13Z" fill="url(#fl2)" opacity="0.7"/>
      <path d="M16 13 C13 16 4 17 2 14 C0 11 6 8 11.5 11 C13 12 15 13 16 13Z" fill="url(#fl3)" opacity="0.55"/>
      <path d="M16 13 C19 16 28 17 30 14 C32 11 26 8 20.5 11 C19 12 17 13 16 13Z" fill="url(#fl4)" opacity="0.55"/>
      <ellipse cx="16" cy="13" rx="0.8" ry="3.5" fill="var(--wing-ink)" opacity="0.62"/>
      <defs>
        <linearGradient id="fl1" x1="1" y1="10" x2="16" y2="13" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--wing-green)"/><stop offset="1" stopColor="var(--wing-blue)"/>
        </linearGradient>
        <linearGradient id="fl2" x1="31" y1="10" x2="16" y2="13" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--wing-pink)"/><stop offset="1" stopColor="var(--wing-green)"/>
        </linearGradient>
        <linearGradient id="fl3" x1="2" y1="14" x2="16" y2="13" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--wing-yellow)"/><stop offset="1" stopColor="var(--wing-green)"/>
        </linearGradient>
        <linearGradient id="fl4" x1="30" y1="14" x2="16" y2="13" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--wing-blue)"/><stop offset="1" stopColor="var(--wing-pink)"/>
        </linearGradient>
      </defs>
    </svg>
  );
}

export function Contact() {
  const ref    = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });

  return (
    <section id="contact" className="contact-section">
      <div className="max-w-5xl mx-auto flex flex-col gap-16" ref={ref}>

        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.7 }}
          className="flex flex-col gap-5 items-center text-center"
        >
          <span className="contact-section__kicker">Contact</span>
          <h2 className="font-heading text-6xl md:text-7xl text-foreground leading-[0.88] tracking-[-3px]">
            Let's talk.
          </h2>
          <p className="font-body font-light text-base text-foreground/55 max-w-md">
            Whether you're a researcher, a recruiter, or just someone who cares
            about the same things I do — I'd love to hear from you.
          </p>
        </motion.div>

        {/* Creator card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.7, delay: 0.1 }}
          className="flex justify-center"
        >
          <div className="liquid-glass rounded-2xl p-6 flex items-center gap-5 max-w-sm w-full">
            <img
              className="rounded-full flex-shrink-0 object-cover"
              src="/images/me.png"
              alt="Portrait of Elaine"
              style={{
                width: 72,
                height: 72,
                objectPosition: 'center 42%',
                border: '1px solid rgba(147,142,151,0.28)',
              }}
            />
            <div className="flex flex-col gap-1">
              <h3 className="font-body font-semibold text-lg text-foreground leading-tight">Elaine</h3>
              <p className="font-body font-light text-sm text-foreground/50">Creator &amp; Developer, {BRAND}</p>
              <div className="flex gap-3 mt-2">
                <a href="#" aria-label="Substack" className="transition-colors" style={{ color: 'var(--wing-yellow)' }}>
                  <SubstackIcon className="w-4 h-4" />
                </a>
                <a href="https://www.linkedin.com/in/elaine-che-03647530a/" aria-label="LinkedIn" className="transition-colors" style={{ color: 'var(--wing-blue)' }}>
                  <Linkedin className="w-4 h-4" />
                </a>
                <a href="https://github.com/CatInTheRiceHat" aria-label="GitHub" className="text-foreground/50 hover:text-foreground/80 transition-colors">
                  <Github className="w-4 h-4" />
                </a>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Contact links */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.7, delay: 0.15 }}
          className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4"
        >
          {LINKS.map(({ icon: Icon, label, sub, href, color }, i) => (
            <motion.a
              key={label}
              href={href}
              target={href.startsWith('http') ? '_blank' : undefined}
              rel={href.startsWith('http') ? 'noopener noreferrer' : undefined}
              initial={{ opacity: 0, y: 16 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: 0.2 + i * 0.08 }}
              className="contact-link-card group"
            >
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center"
                style={{ background: `${color}18`, border: `1px solid ${color}35` }}
              >
                <Icon className="w-4 h-4" style={{ color }} />
              </div>
              <div className="flex flex-col gap-0.5">
                <p className="font-body font-medium text-sm text-foreground/80">{label}</p>
                <p className="font-body font-light text-xs text-foreground/45">{sub}</p>
              </div>
              <ArrowUpRight
                className="w-4 h-4 text-foreground/25 group-hover:text-foreground/60 transition-colors ml-auto mt-auto"
              />
            </motion.a>
          ))}
        </motion.div>

        {/* Footer bar */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ duration: 0.6, delay: 0.5 }}
          className="flex items-center justify-between pt-6"
          style={{ borderTop: '1px solid rgba(0,0,0,0.07)' }}
        >
          <p className="font-body font-light text-xs text-foreground/35">
            {BRAND} © 2026 — Elaine Che
          </p>
          <div className="flex items-center gap-2">
            <ButterflyFooterIcon />
          </div>
        </motion.div>

      </div>
    </section>
  );
}
