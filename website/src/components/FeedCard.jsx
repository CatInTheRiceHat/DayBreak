import { motion } from 'motion/react';

const PALETTES = [
  'rgba(207,203,211,0.72)',
  'rgba(173,158,184,0.48)',
  'rgba(147,142,151,0.32)',
  'rgba(124,109,140,0.18)',
];

export function FeedCard({ item, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
      className="liquid-glass rounded-xl p-4 flex-shrink-0 w-48 flex flex-col gap-3"
    >
      <div
        className="w-full h-24 rounded-lg flex items-center justify-center text-2xl"
        style={{
          background: `linear-gradient(135deg, ${PALETTES[index % 4]}, rgba(250,249,246,0.54))`,
          border: '1px solid rgba(147,142,151,0.26)',
        }}
      />

      <div className="flex flex-col gap-1">
        <span className="font-body text-xs font-medium text-foreground/70 capitalize">
          {item.topic || 'Content'}
        </span>
        <div className="flex items-center gap-1.5 flex-wrap">
          {item.prosocial === 1 && (
            <span
              className="rounded-full px-2 py-0.5 font-body text-xs"
              style={{ background: 'rgba(124,109,140,0.14)', color: '#7C6D8C' }}
            >
              prosocial
            </span>
          )}
          {item.risk > 0.5 && (
            <span
              className="rounded-full px-2 py-0.5 font-body text-xs"
              style={{ background: 'rgba(207,203,211,0.45)', color: '#938E97' }}
            >
              risk
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
