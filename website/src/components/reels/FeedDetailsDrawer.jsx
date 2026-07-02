import { useEffect, useState } from 'react';
import { AnimatePresence, motion as MOTION } from 'motion/react';

/**
 * Container that reveals the Feed details / Algorithm Compass content on demand.
 *
 * Closed by default. On desktop (>=768px) it slides in as a right-side drawer;
 * on mobile it rises as a bottom sheet. Closes on the panel's own X (rendered by
 * the child), on Escape, and on a tap of the scrim / outside the panel.
 *
 * Props:
 *   open      — whether the drawer is visible
 *   onClose   — called to request closing (Escape, scrim, outside tap)
 *   label     — accessible dialog label
 *   children  — panel content (e.g. FeedCompassPanel with its own close button)
 */
function readIsDesktop() {
  if (typeof window === 'undefined') return true;
  return window.matchMedia('(min-width: 768px)').matches;
}

export function FeedDetailsDrawer({ open, onClose, label = 'Feed details', children }) {
  const [isDesktop, setIsDesktop] = useState(readIsDesktop);

  // Keep the slide direction in sync with the viewport while the drawer is open.
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const query = window.matchMedia('(min-width: 768px)');
    const update = () => setIsDesktop(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  // Escape closes the drawer.
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  const enterFrom = isDesktop ? { x: 48, opacity: 0 } : { y: 40, opacity: 0 };
  const settled = isDesktop ? { x: 0, opacity: 1 } : { y: 0, opacity: 1 };

  return (
    <AnimatePresence>
      {open && (
        <MOTION.div
          className={`feed-details-drawer${isDesktop ? ' feed-details-drawer--side' : ' feed-details-drawer--sheet'}`}
          role="dialog"
          aria-modal="true"
          aria-label={label}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <button
            type="button"
            className="feed-details-drawer__scrim"
            aria-label="Close feed details"
            onClick={onClose}
          />
          <MOTION.div
            className="feed-details-drawer__panel"
            initial={enterFrom}
            animate={settled}
            exit={enterFrom}
            transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
          >
            {children}
          </MOTION.div>
        </MOTION.div>
      )}
    </AnimatePresence>
  );
}
