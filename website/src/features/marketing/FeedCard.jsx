import { motion } from 'motion/react';

const PALETTES = [
  'color-mix(in srgb, var(--db-color-morning-light) 72%, transparent)',
  'color-mix(in srgb, var(--db-color-horizon-rose) 48%, transparent)',
  'color-mix(in srgb, var(--db-color-sunrise-coral) 32%, transparent)',
  'color-mix(in srgb, var(--db-color-twilight-violet) 18%, transparent)',
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
          background: `linear-gradient(135deg, ${PALETTES[index % 4]}, color-mix(in srgb, var(--db-color-surface-elevated) 54%, transparent))`,
          border: '1px solid var(--db-color-border)',
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
              style={{ background: 'color-mix(in srgb, var(--db-color-twilight-violet) 14%, transparent)', color: 'var(--db-color-link)' }}
            >
              prosocial
            </span>
          )}
          {item.risk > 0.5 && (
            <span
              className="rounded-full px-2 py-0.5 font-body text-xs"
              style={{ background: 'color-mix(in srgb, var(--db-color-horizon-rose) 16%, transparent)', color: 'var(--db-color-highlight-text)' }}
            >
              risk
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
