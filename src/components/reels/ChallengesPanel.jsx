import { useState } from 'react';
import { Award, Check, Flame, Sparkles, Trophy, UserPlus, X } from 'lucide-react';
import { CHALLENGES } from './challengesData';

/**
 * IRL challenges panel: daily challenge list with proof/reflection, points, daily
 * streak, milestone badges, a friendly leaderboard, and a friend-invite button.
 * Positive-game tone — no guilt, no shame, no toxic popularity metrics.
 */
export function ChallengesPanel({
  stats,
  completedToday,
  badges,
  leaderboard,
  onComplete,
  onClose,
  onStatus,
}) {
  const [activeChallenge, setActiveChallenge] = useState(null);
  const [reflection, setReflection] = useState('');

  const startComplete = (challenge) => {
    setActiveChallenge(challenge.id);
    setReflection('');
  };

  const confirmComplete = (challenge) => {
    onComplete?.(challenge, reflection.trim() || null);
    setActiveChallenge(null);
    setReflection('');
    onStatus?.(`Nice — +${challenge.points} points for "${challenge.label}".`);
  };

  const inviteFriend = async () => {
    const link = `${typeof window !== 'undefined' ? window.location.origin : ''}/algorithm?invite=chrysalis`;
    try {
      await navigator.clipboard?.writeText(link);
      onStatus?.('Invite link copied — share it with a friend! 🌊');
    } catch {
      onStatus?.('Invite a friend to do challenges with you! 🌊');
    }
  };

  const completedCount = Object.keys(completedToday || {}).length;

  return (
    <section className="challenges" aria-label="IRL challenges">
      <div className="challenges__head">
        <div>
          <span className="challenges__eyebrow">
            <Trophy size={13} aria-hidden="true" />
            IRL Challenges
          </span>
          <h2>Touch grass, together</h2>
        </div>
        {onClose && (
          <button type="button" className="challenges__close" onClick={onClose} aria-label="Close challenges">
            <X size={16} aria-hidden="true" />
          </button>
        )}
      </div>

      <p className="challenges__intro">
        Small real-world wins. Earn points, keep a streak, and cheer on friends — for fun, not pressure.
      </p>

      <div className="challenges__stats">
        <div className="challenges__stat">
          <Sparkles size={16} aria-hidden="true" />
          <span className="challenges__stat-value">{stats.points}</span>
          <span className="challenges__stat-label">points</span>
        </div>
        <div className="challenges__stat">
          <Flame size={16} aria-hidden="true" />
          <span className="challenges__stat-value">{stats.streak}</span>
          <span className="challenges__stat-label">day streak</span>
        </div>
        <div className="challenges__stat">
          <Award size={16} aria-hidden="true" />
          <span className="challenges__stat-value">{badges.filter((b) => b.earned).length}</span>
          <span className="challenges__stat-label">badges</span>
        </div>
      </div>

      <div className="challenges__section">
        <div className="challenges__section-title">
          <span>Today&apos;s challenges</span>
          <span className="challenges__progress">{completedCount}/{CHALLENGES.length} done</span>
        </div>
        <ul className="challenges__list">
          {CHALLENGES.map((challenge) => {
            const done = Boolean(completedToday?.[challenge.id]);
            const isActive = activeChallenge === challenge.id;
            return (
              <li key={challenge.id} className={`challenge-item${done ? ' is-done' : ''}`}>
                <span className="challenge-item__emoji" aria-hidden="true">{challenge.emoji}</span>
                <span className="challenge-item__body">
                  <span className="challenge-item__label">{challenge.label}</span>
                  <span className="challenge-item__points">+{challenge.points} pts</span>
                </span>
                {done ? (
                  <span className="challenge-item__done" aria-label="Completed">
                    <Check size={16} aria-hidden="true" />
                  </span>
                ) : (
                  <button type="button" className="challenge-item__btn" onClick={() => startComplete(challenge)}>
                    Complete
                  </button>
                )}

                {isActive && !done && (
                  <div className="challenge-item__proof">
                    <input
                      type="text"
                      value={reflection}
                      onChange={(event) => setReflection(event.target.value)}
                      placeholder="Add a quick note (optional)…"
                      maxLength={140}
                      aria-label={`Reflection for ${challenge.label}`}
                    />
                    <button type="button" className="challenge-item__confirm" onClick={() => confirmComplete(challenge)}>
                      Mark done
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="challenges__section">
        <div className="challenges__section-title"><span>Badges</span></div>
        <div className="challenges__badges">
          {badges.map((badge) => (
            <div
              key={badge.id}
              className={`challenge-badge${badge.earned ? ' is-earned' : ''}`}
              title={`${badge.label} — ${badge.blurb}`}
            >
              <span className="challenge-badge__emoji" aria-hidden="true">{badge.emoji}</span>
              <span className="challenge-badge__label">{badge.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="challenges__section">
        <div className="challenges__section-title">
          <span>Friends</span>
          <button type="button" className="challenges__invite" onClick={inviteFriend}>
            <UserPlus size={14} aria-hidden="true" />
            Invite a friend
          </button>
        </div>
        <ul className="leaderboard">
          {leaderboard.map((row) => (
            <li key={row.id} className={`leaderboard__row${row.isYou ? ' is-you' : ''}`}>
              <span className="leaderboard__rank">{row.rank}</span>
              <span className="leaderboard__avatar" aria-hidden="true">{row.emoji}</span>
              <span className="leaderboard__name">{row.name}{row.isYou ? ' (you)' : ''}</span>
              <span className="leaderboard__streak"><Flame size={12} aria-hidden="true" />{row.streak}</span>
              <span className="leaderboard__points">{row.points} pts</span>
            </li>
          ))}
        </ul>
        <p className="challenges__footnote">Friendly competition only — no follower counts, no pressure.</p>
      </div>
    </section>
  );
}
