import { Check } from 'lucide-react';
import { CHALLENGES, CATEGORY_TONE } from './communityData';

/**
 * Touch Grass challenge cards. Each shows a title, short description, Dewdrop
 * reward, and a token-tinted category tag (IRL / Wellness / Friendship /
 * Perspective / Focus). "Start Challenge" flips to "Completed" on the second tap
 * and earns the Dewdrops, which bubble up to the header + leaderboard.
 *
 * Props:
 *   completed — Set of completed challenge ids (owned by CommunityPage)
 *   onComplete(challenge) — marks a challenge done and awards its Dewdrops
 */
export function TouchGrassChallenges({ completed, onComplete }) {
  return (
    <section className="cmty-section" aria-label="Touch Grass Challenges">
      <div className="cmty-section__head">
        <h2 className="cmty-section__title">Touch Grass Challenges</h2>
      </div>
      <p className="cmty-section__subtitle">
        Small real-life actions. Each one earns Dewdrops.
      </p>

      <div className="cmty-challenges">
        {CHALLENGES.map((challenge) => {
          const isDone = completed.has(challenge.id);
          return (
            <article
              key={challenge.id}
              className={`cmty-challenge${isDone ? ' is-done' : ''}`}
              data-tone={CATEGORY_TONE[challenge.category]}
            >
              <header className="cmty-challenge__head">
                <span className="cmty-challenge__emoji" aria-hidden="true">{challenge.emoji}</span>
                <span className="cmty-challenge__cat">{challenge.category}</span>
              </header>
              <h3 className="cmty-challenge__title">{challenge.title}</h3>
              <p className="cmty-challenge__copy">{challenge.description}</p>
              <footer className="cmty-challenge__foot">
                <span className={`cmty-reward${isDone ? ' is-earned' : ''}`}>
                  💧 {challenge.reward}{isDone ? ' earned' : ' Dewdrops'}
                </span>
                <button
                  type="button"
                  className={`home-btn cmty-challenge__btn${isDone ? ' is-done' : ' home-btn--primary'}`}
                  onClick={() => onComplete(challenge)}
                  disabled={isDone}
                >
                  {isDone ? (
                    <>
                      <Check size={15} aria-hidden="true" /> Completed
                    </>
                  ) : (
                    'Mark Done'
                  )}
                </button>
              </footer>
            </article>
          );
        })}
      </div>
    </section>
  );
}
