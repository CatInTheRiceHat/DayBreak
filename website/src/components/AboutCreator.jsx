import { BRAND } from '../brand.js';
import { createElement, useRef } from 'react';
import { motion, useInView } from 'motion/react';
import { Github, Linkedin, Mail, ArrowUpRight } from 'lucide-react';

const LINKS = [
  { label: 'GitHub', href: 'https://github.com/CatInTheRiceHat', icon: Github },
  { label: 'LinkedIn', href: 'https://www.linkedin.com/in/elaine-che-03647530a/', icon: Linkedin },
  { label: 'Email', href: 'mailto:elaineyouyuanche@gmail.com', icon: Mail },
];

export function AboutCreator() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, amount: 0.18 });
  const MotionDiv = motion.div;
  const MotionAside = motion.aside;

  return (
    <section id="creator" ref={ref} className="creator-section">
      <div className="creator-section__grid">
        <MotionDiv
          className="creator-section__copy"
          initial={{ opacity: 0, y: 70, filter: 'blur(12px)' }}
          animate={inView ? { opacity: 1, y: 0, filter: 'blur(0px)' } : {}}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        >
          <span className="creator-section__kicker">About the Creator</span>
          <h2>Built from the feeling that the feed should not get the final word.</h2>
          <p>
            {BRAND} began as a personal refusal to accept that the most intimate technology in
            our day should be tuned only for retention. I wanted to build something that could
            name the harms, translate research into ranking logic, and make a different kind of
            feed feel possible.
          </p>
          <p>
            I am Elaine, the creator and developer behind {BRAND}. This project is part critique,
            part prototype, and part proof that algorithms can be designed around care when care is
            made measurable.
          </p>
        </MotionDiv>

        <MotionAside
          className="creator-card"
          initial={{ opacity: 0, x: 70, rotateY: -8, filter: 'blur(10px)' }}
          animate={inView ? { opacity: 1, x: 0, rotateY: 0, filter: 'blur(0px)' } : {}}
          transition={{ duration: 0.9, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
          data-cursor="soft"
        >
          <div className="creator-card__portrait" aria-hidden="true">
            <img src="/images/me.png" alt="" />
          </div>
          <div>
            <span>Creator & Developer</span>
            <h3>Elaine Che</h3>
          </div>
          <div className="creator-card__rule" />
          <div className="creator-card__links">
            {LINKS.map(({ label, href, icon: Icon }) => (
              <a
                key={label}
                href={href}
                target={href.startsWith('http') ? '_blank' : undefined}
                rel={href.startsWith('http') ? 'noopener noreferrer' : undefined}
              >
                {createElement(Icon, { className: 'w-4 h-4' })}
                {label}
                <ArrowUpRight className="w-3.5 h-3.5" />
              </a>
            ))}
          </div>
        </MotionAside>
      </div>
    </section>
  );
}
