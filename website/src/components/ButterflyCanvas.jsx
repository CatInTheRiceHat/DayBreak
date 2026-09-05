import { useState } from 'react';
import { motion } from 'motion/react';

const ANNOTATIONS = [
  { label: ['Wellbeing-First', 'Scoring'], x: 16,  y: 22,  dx: -90, dy: -18 },
  { label: ['Session Cap'],               x: 30,  y: 10,  dx: -15, dy: -55 },
  { label: ['Content Diversity'],         x: 40,  y: 27,  dx:  45, dy: -40 },
  { label: ['Emotional Balance'],         x: 40,  y: 54,  dx:  45, dy:  18 },
  { label: ['Sleep-Safe Hours'],          x: 27,  y: 72,  dx: -15, dy:  55 },
  { label: ['Crisis Detection'],          x: 14,  y: 60,  dx: -90, dy:  18 },
];

// ── Tune these to frame the shot ─────────────────────────────
const ROTATION    = 15;   // degrees clockwise
const SCALE       = 2;  // zoom
const TRANSLATE_X = 15;   // % left/right
const TRANSLATE_Y = 5;   // % up/down
// ─────────────────────────────────────────────────────────────

export default function ButterflyCanvas({ width = 900, height = 700 }) {
  const imgW = width;
  const imgH = Math.round(width * (1482 / 2048));
  const [hoveredId, setHoveredId] = useState(null);

  return (
    // No overflow:hidden here — the parent hero section clips at its edge.
    // pointer-events enabled so SVG hover targets work.
    <div
      style={{ width: imgW, height: imgH, position: 'relative' }}
      className="butterfly-float"
      aria-hidden="true"
    >
      <div
        style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
          transform: `rotate(${ROTATION}deg) scale(${SCALE}) translate(${TRANSLATE_X}%, ${TRANSLATE_Y}%)`,
          transformOrigin: 'center center',
        }}
      >
        {/* Left wing */}
        <div
          className="wing-left"
          style={{ position: 'absolute', top: 0, left: 0, width: '50%', height: '100%', overflow: 'hidden' }}
        >
          <img
            src="/images/butterfly.png"
            alt=""
            style={{ width: imgW, height: imgH, display: 'block', maxWidth: 'none' }}
            draggable={false}
          />
        </div>

        {/* Right wing */}
        <div
          className="wing-right"
          style={{ position: 'absolute', top: 0, right: 0, width: '50%', height: '100%', overflow: 'hidden' }}
        >
          <img
            src="/images/butterfly.png"
            alt=""
            style={{
              width: imgW, height: imgH, display: 'block', maxWidth: 'none',
              position: 'relative', left: `-${imgW / 2}px`,
            }}
            draggable={false}
          />
        </div>

        {/* Iridescent shimmer */}
        <div className="butterfly-iridescent" />

        {/* SVG annotations — hover to reveal */}
        <svg
          style={{
            position: 'absolute', top: 0, left: 0,
            width: imgW, height: imgH,
            overflow: 'visible',
            pointerEvents: 'none',
          }}
        >
          {ANNOTATIONS.map((ann, i) => {
            const sx = (ann.x / 100) * imgW;
            const sy = (ann.y / 100) * imgH;
            const ex = sx + ann.dx;
            const ey = sy + ann.dy;
            const alignEnd = ann.dx < 0;
            return (
              <g key={i}>
                {/* Invisible hover target — larger radius for easy targeting */}
                <circle
                  cx={sx}
                  cy={sy}
                  r={14}
                  fillOpacity={0}
                  style={{ cursor: 'crosshair', pointerEvents: 'all' }}
                  onMouseEnter={() => setHoveredId(i)}
                  onMouseLeave={() => setHoveredId(null)}
                />
                {/* Visible dot — always shown at low opacity, brightens on hover */}
                <circle
                  cx={sx}
                  cy={sy}
                  r="3"
                  fill={hoveredId === i ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.35)'}
                  style={{ pointerEvents: 'none', transition: 'fill 0.2s' }}
                />
                {/* Annotation line + label — fades in on hover */}
                <motion.g
                  animate={{
                    opacity: hoveredId === i ? 1 : 0,
                    scale: hoveredId === i ? 1 : 0.88,
                  }}
                  transition={{ duration: 0.2, ease: 'easeOut' }}
                  style={{ pointerEvents: 'none', transformOrigin: `${sx}px ${sy}px` }}
                >
                  <line
                    x1={sx} y1={sy} x2={ex} y2={ey}
                    stroke="rgba(255,255,255,0.6)"
                    strokeWidth="0.8"
                  />
                  <g transform={`translate(${ex},${ey}) rotate(${-ROTATION})`}>
                    {ann.label.map((line, li) => (
                      <text
                        key={li}
                        x={alignEnd ? -6 : 6}
                        y={li * 13 - (ann.label.length - 1) * 6}
                        textAnchor={alignEnd ? 'end' : 'start'}
                        dominantBaseline="middle"
                        fill="rgba(255,255,255,0.95)"
                        fontSize="9"
                        fontFamily="system-ui, -apple-system, sans-serif"
                        letterSpacing="1.8"
                      >
                        {line.toUpperCase()}
                      </text>
                    ))}
                  </g>
                </motion.g>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
