import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Hand, UserPlus } from 'lucide-react';
import { SUGGESTED_PROFILES } from './homeData';

/**
 * "Suggested for you" — Chrysalis-branded discovery for the desktop right column.
 *
 * Each suggestion leads with an intention-based *reason* ("Same intention today",
 * "Into creativity + calm") — never a follower count or popularity metric. The
 * action is a gentle "Connect" or "Wave"; pressing it is a local, ephemeral demo
 * acknowledgement (no real connection graph yet).
 */
export function SuggestedProfilesPanel() {
  const [acted, setActed] = useState(() => new Set());

  const act = (id) => {
    setActed((prev) => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  };

  return (
    <section className="suggested" aria-label="Suggested for you">
      <div className="suggested__head">
        <h2 className="suggested__title">Suggested for you</h2>
        <span className="suggested__hint">demo</span>
      </div>
      <ul className="suggested__list">
        {SUGGESTED_PROFILES.map((person) => {
          const done = acted.has(person.id);
          const isWave = person.action === 'wave';
          return (
            <li key={person.id} className="suggested__item">
              <Link to={`/u/${person.username}`} className="suggested__who">
                <span className="cx-avatar cx-avatar--sm" aria-hidden="true">
                  <span className="wing__emoji">{person.emoji}</span>
                </span>
                <span className="suggested__meta">
                  <span className="suggested__name">{person.displayName}</span>
                  <span className="suggested__reason">{person.reason}</span>
                </span>
              </Link>
              <button
                type="button"
                className={`home-btn home-btn--chip${done ? ' is-done' : ''}`}
                onClick={() => act(person.id)}
                disabled={done}
              >
                {done
                  ? (isWave ? 'Waved' : 'Sent')
                  : (
                    <>
                      {isWave
                        ? <Hand size={14} aria-hidden="true" />
                        : <UserPlus size={14} aria-hidden="true" />}
                      {isWave ? 'Wave' : 'Connect'}
                    </>
                  )}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
