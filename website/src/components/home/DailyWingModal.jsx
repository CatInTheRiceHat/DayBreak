import { useEffect, useState } from 'react';
import { AnimatePresence, motion as MOTION } from 'motion/react';
import { X } from 'lucide-react';
import { WING_REACTIONS } from './homeData';

/**
 * Story-style sheet for a single Daily Wing.
 *
 * Shows the person, their activity/status, an optional note and image placeholder,
 * and supportive-only reactions ("proud of you", "same here", "inspired",
 * "join reset"). There are no like counts and no comments — just a small,
 * encouraging tap-back. Reaction state is local/ephemeral demo only.
 *
 * Closes on scrim click or Escape. Renders nothing when `wing` is null.
 */
export function DailyWingModal({ wing, onClose, onReact }) {
  // Keyed by wing id so each wing remembers its own sent reaction without an
  // effect resetting state when `wing` changes.
  const [sentByWing, setSentByWing] = useState({});
  const reacted = wing ? sentByWing[wing.id] : null;

  useEffect(() => {
    if (!wing) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [wing, onClose]);

  const react = (reaction) => {
    setSentByWing((prev) => ({ ...prev, [wing.id]: reaction.id }));
    onReact?.(wing, reaction);
  };

  return (
    <AnimatePresence>
      {wing && (
        <MOTION.div
          className="wing-sheet"
          role="dialog"
          aria-modal="true"
          aria-label={`${wing.firstName}'s wing`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <div className="wing-sheet__scrim" aria-hidden="true" onClick={onClose} />
          <MOTION.div
            className="wing-sheet__panel"
            initial={{ y: 28, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 28, opacity: 0 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          >
            <button type="button" className="wing-sheet__close" onClick={onClose} aria-label="Close">
              <X size={18} aria-hidden="true" />
            </button>

            <div className="wing-sheet__person">
              <span className="cx-avatar cx-avatar--lg wing-sheet__avatar" aria-hidden="true">
                <span className="wing__emoji">{wing.emoji}</span>
              </span>
              <div className="wing-sheet__id">
                <span className="wing-sheet__name">{wing.firstName}</span>
                <span className="wing-sheet__status">{wing.activity}</span>
              </div>
            </div>

            {wing.hasImage && (
              <div className="wing-sheet__image" role="img" aria-label="Shared moment">
                <span aria-hidden="true">{wing.emoji}</span>
              </div>
            )}

            {wing.note && <p className="wing-sheet__note">{wing.note}</p>}

            {wing.isSelf ? (
              <p className="wing-sheet__self">
                Sharing wings is coming soon — your small wins will live here.
              </p>
            ) : (
              <div className="wing-sheet__reactions" role="group" aria-label="Send support">
                {WING_REACTIONS.map((reaction) => (
                  <button
                    key={reaction.id}
                    type="button"
                    className={`wing-react${reacted === reaction.id ? ' is-sent' : ''}`}
                    onClick={() => react(reaction)}
                    disabled={reacted === reaction.id}
                  >
                    <span aria-hidden="true">{reaction.emoji}</span> {reaction.label}
                  </button>
                ))}
              </div>
            )}
          </MOTION.div>
        </MOTION.div>
      )}
    </AnimatePresence>
  );
}
