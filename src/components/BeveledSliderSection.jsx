import { useEffect, useRef, useState } from 'react';
import { motion, useInView, useMotionValueEvent, useReducedMotion, useScroll, useTransform } from 'motion/react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Pagination } from 'swiper/modules';
import 'swiper/css';
import 'swiper/css/pagination';

const COLOR_MAP = {
  green: 'var(--wing-green)',
  blue: 'var(--wing-blue)',
  pink: 'var(--wing-pink)',
  yellow: 'var(--wing-yellow)',
};

function useDesktopCards() {
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    const query = window.matchMedia('(min-width: 1025px)');
    const update = () => setIsDesktop(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  return isDesktop;
}

export function BeveledCard({ slide, active = true, index = 0 }) {
  const accent = COLOR_MAP[slide.color] ?? slide.color ?? COLOR_MAP.blue;
  const Icon = slide.icon;

  return (
    <motion.article
      className="beveled-card"
      data-cursor="soft"
      data-color={slide.color}
      style={{ '--card-accent': accent }}
      initial={{ opacity: 0, y: 36, rotateX: 10 }}
      animate={{
        opacity: active ? 1 : 0.32,
        y: active ? 0 : 20,
        scale: active ? 1 : 0.94,
        rotateX: active ? 0 : 8,
        filter: active ? 'blur(0px)' : 'blur(4px)',
      }}
      transition={{ duration: 0.55, delay: active ? index * 0.02 : 0, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="beveled-card__shine" aria-hidden="true" />
      <div className="beveled-card__header">
        <span className="beveled-card__number">{String(index + 1).padStart(2, '0')}</span>
        <span className="beveled-card__eyebrow">{slide.eyebrow}</span>
        {Icon && (
          <span className="beveled-card__icon" aria-hidden="true">
            <Icon className="w-4 h-4" />
          </span>
        )}
      </div>

      <div className="beveled-card__body">
        <h3>{slide.title}</h3>
        <p>{slide.body}</p>
      </div>

      {slide.visual && (
        <div className="beveled-card__visual">
          {slide.visual}
        </div>
      )}
    </motion.article>
  );
}

export function BeveledSliderSection({ id, label, heading, intro, slides }) {
  const ref = useRef(null);
  const headerRef = useRef(null);
  const inView = useInView(headerRef, { once: true, margin: '-80px' });
  const isDesktop = useDesktopCards();
  const reduceMotion = useReducedMotion();
  const [activeIndex, setActiveIndex] = useState(0);
  const activeSlide = slides[activeIndex] ?? slides[0];
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end end'],
  });
  const stageScale = useTransform(scrollYProgress, [0.78, 1], [1, 0.96]);
  const stageOpacity = useTransform(scrollYProgress, [0.84, 1], [1, 0.42]);
  const stageBlur = useTransform(scrollYProgress, [0.78, 1], [0, 5]);
  const stageFilter = useTransform(stageBlur, (value) => `blur(${value}px)`);

  useMotionValueEvent(scrollYProgress, 'change', (latest) => {
    if (!isDesktop || reduceMotion) {
      return;
    }
    const nextIndex = Math.min(slides.length - 1, Math.max(0, Math.round(latest * (slides.length - 1))));
    setActiveIndex(nextIndex);
  });

  const goTo = (direction) => {
    setActiveIndex((current) => {
      const next = current + direction;
      return Math.min(slides.length - 1, Math.max(0, next));
    });
  };

  return (
    <section
      id={id}
      ref={ref}
      className="beveled-slider-section"
      style={{ '--slide-count': slides.length, '--section-accent': COLOR_MAP[activeSlide.color] ?? COLOR_MAP.blue }}
    >
      <motion.div
        className="beveled-slider__stage"
        style={reduceMotion ? undefined : { scale: stageScale, opacity: stageOpacity, filter: stageFilter }}
      >
        <motion.div
          ref={headerRef}
          className="beveled-slider__copy"
          initial={{ opacity: 0, y: 28, filter: 'blur(10px)' }}
          animate={inView ? { opacity: 1, y: 0, filter: 'blur(0px)' } : {}}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        >
          <span className="section-badge liquid-glass">{label}</span>
          <h2>{heading}</h2>
          <p>{intro}</p>
          <div className="beveled-slider__progress">
            {slides.map((slide, index) => (
              <button
                key={slide.eyebrow}
                type="button"
                className={index === activeIndex ? 'is-active' : ''}
                onClick={() => setActiveIndex(index)}
                style={{ '--dot-color': COLOR_MAP[slide.color] ?? COLOR_MAP.blue }}
                aria-label={`Show ${slide.eyebrow}`}
              />
            ))}
          </div>
          <div className="beveled-slider__counter" aria-live="polite">
            <span>{String(activeIndex + 1).padStart(2, '0')}</span>
            <i />
            <span>{String(slides.length).padStart(2, '0')}</span>
          </div>
          <div className="beveled-slider__controls">
            <button type="button" data-cursor="soft" onClick={() => goTo(-1)} disabled={activeIndex === 0} aria-label="Previous card">
              <ArrowLeft className="w-4 h-4" />
            </button>
            <button type="button" data-cursor="soft" onClick={() => goTo(1)} disabled={activeIndex === slides.length - 1} aria-label="Next card">
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </motion.div>

        <div className="beveled-slider__desktop" aria-live="polite">
          <div className="beveled-slider__deck">
            {slides.map((slide, index) => {
              const offset = index - activeIndex;
              return (
                <motion.div
                  key={slide.eyebrow}
                  className="beveled-slider__deck-card"
                  style={{
                    zIndex: slides.length - Math.abs(offset),
                    pointerEvents: index === activeIndex ? 'auto' : 'none',
                  }}
                  animate={{
                    x: offset * 30,
                    y: Math.abs(offset) * 22,
                    rotate: offset * 2.2,
                    scale: index === activeIndex ? 1 : 0.96 - Math.min(Math.abs(offset), 3) * 0.025,
                  }}
                  transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
                >
                  <BeveledCard slide={slide} active={index === activeIndex} index={index} />
                </motion.div>
              );
            })}
          </div>
        </div>

        <div className="beveled-slider__mobile">
          <Swiper
            modules={[Pagination]}
            pagination={{ clickable: true }}
            spaceBetween={18}
            slidesPerView={1}
            onSlideChange={(swiper) => setActiveIndex(swiper.activeIndex)}
          >
            {slides.map((slide, index) => (
              <SwiperSlide key={slide.eyebrow}>
                <BeveledCard slide={slide} active index={index} />
              </SwiperSlide>
            ))}
          </Swiper>
        </div>
      </motion.div>
    </section>
  );
}
