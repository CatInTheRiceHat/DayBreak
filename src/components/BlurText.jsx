import { motion, useInView } from 'motion/react';
import { useRef, useEffect, useState } from 'react';

export function BlurText({
  text,
  delay = 200,
  direction = 'bottom',
  className = ''
}) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });
  const [shouldAnimate, setShouldAnimate] = useState(false);

  useEffect(() => {
    if (isInView) {
      setShouldAnimate(true);
    }
  }, [isInView]);

  const words = text.split(' ');

  return (
    <span ref={ref} className={`inline ${className}`}>
      {words.map((word, index) => (
        <motion.span
          key={index}
          initial={{
            filter: 'blur(10px)',
            opacity: 0,
            y: direction === 'bottom' ? 50 : -50
          }}
          animate={
            shouldAnimate
              ? {
                  filter: ['blur(10px)', 'blur(5px)', 'blur(0px)'],
                  opacity: [0, 0.5, 1],
                  y: direction === 'bottom' ? [50, -5, 0] : [-50, 5, 0]
                }
              : {}
          }
          transition={{
            duration: 0.35,
            delay: index * delay,
            times: [0, 0.5, 1]
          }}
          className="inline-block whitespace-nowrap"
          style={{ display: 'inline-block' }}
        >
          {word}
          {index < words.length - 1 && '\u00A0'}
        </motion.span>
      ))}
    </span>
  );
}
