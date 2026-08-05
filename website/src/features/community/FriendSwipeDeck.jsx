import { AnimatePresence, motion as MOTION } from 'motion/react';
import { Heart, Clock, X } from 'lucide-react';
import { FRIEND_CANDIDATES } from './communityData';

/**
 * Swipe-style friend discovery deck.
 *
 * One avatar-first card at a time, advanced by three buttons (Connect / Maybe
 * Later / Not My Circle) rather than touch-drag physics — reads as "swipe" but
 * stays reliable in a demo on desktop. Connect adds the person to Your Circle and
 * surfaces a small success state. The card emphasises goals, interests, and
 * shared values — never appearance or popularity (profiles are avatars only).
 *
 * Props:
 *   index — current card position (owned by CommunityPage)
 *   lastConnected — name just added to the circle, for the success toast
 *   onDecision(candidate, decision) — "connect" | "later" | "decline"
 */
export function FriendSwipeDeck({ index, lastConnected, onDecision }) {
  const candidate = FRIEND_CANDIDATES[index];
  const remaining = FRIEND_CANDIDATES.length - index;

  return (
    <section className="cmty-section cmty-deck" aria-label="Find friends">
      <div className="cmty-section__head">
        <h2 className="cmty-section__title">Find friends</h2>
        <span className="cmty-section__count">
          {candidate ? `${remaining} to meet` : 'all caught up'}
        </span>
      </div>
      <p className="cmty-note cmty-note--inline">
        Matches are based on goals, interests, and healthy habits — not popularity.
      </p>

      {lastConnected && (
        <p className="cmty-success" role="status" aria-live="polite">
          You sent a circle request to {lastConnected}. 💜
        </p>
      )}

      <div className="cmty-deck__stage">
        <AnimatePresence mode="wait">
          {candidate ? (
            <MOTION.article
              key={candidate.id}
              className="cmty-card"
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: -40, scale: 0.96 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
            >
              <header className="cmty-card__head">
                <span className="cx-avatar cmty-avatar" aria-hidden="true">
                  <span className="cx-avatar__fallback">{candidate.emoji}</span>
                </span>
                <div className="cmty-card__id">
                  <span className="cmty-card__name">{candidate.name}</span>
                  <span className="cmty-card__age">Age {candidate.age}</span>
                </div>
              </header>

              <dl className="cmty-card__facts">
                <div className="cmty-card__fact">
                  <dt>Current goal</dt>
                  <dd>{candidate.goal}</dd>
                </div>
                <div className="cmty-card__fact">
                  <dt>Interests</dt>
                  <dd className="cmty-tags">
                    {candidate.interests.map((interest) => (
                      <span key={interest} className="cmty-tag">{interest}</span>
                    ))}
                  </dd>
                </div>
                <div className="cmty-card__fact">
                  <dt>Looking for</dt>
                  <dd>{candidate.lookingFor}</dd>
                </div>
                <div className="cmty-card__fact">
                  <dt>Shared interests</dt>
                  <dd className="cmty-tags">
                    {candidate.shared.map((item) => (
                      <span key={item} className="cmty-tag cmty-tag--shared">{item}</span>
                    ))}
                  </dd>
                </div>
              </dl>

              <p className="cmty-card__why">
                <span className="cmty-card__why-label">Why suggested</span>
                “{candidate.why}”
              </p>

              <div className="cmty-card__actions">
                <button
                  type="button"
                  className="home-btn cmty-action cmty-action--decline"
                  onClick={() => onDecision(candidate, 'decline')}
                >
                  <X size={16} aria-hidden="true" /> Not My Circle
                </button>
                <button
                  type="button"
                  className="home-btn cmty-action cmty-action--later"
                  onClick={() => onDecision(candidate, 'later')}
                >
                  <Clock size={16} aria-hidden="true" /> Maybe Later
                </button>
                <button
                  type="button"
                  className="home-btn home-btn--primary cmty-action cmty-action--connect"
                  onClick={() => onDecision(candidate, 'connect')}
                >
                  <Heart size={16} aria-hidden="true" /> Connect
                </button>
              </div>
            </MOTION.article>
          ) : (
            <MOTION.div
              key="empty"
              className="cmty-card cmty-card--empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <span className="cmty-card__empty-emoji" aria-hidden="true">🌱</span>
              <p className="cmty-card__empty-title">You’ve seen everyone for now</p>
              <p className="cmty-card__empty-copy">
                New people show up slowly here, on purpose. Check back later.
              </p>
            </MOTION.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
