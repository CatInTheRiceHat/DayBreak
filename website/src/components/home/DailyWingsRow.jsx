import { Plus } from 'lucide-react';
import { DAILY_WINGS, DAILY_WINGS_TITLE } from './homeData';

/**
 * The "Daily Wings" row — Chrysalis's calm take on a stories strip.
 *
 * These are NOT popularity stories. Each bubble is a small wellbeing action (a
 * screen break, a walk, journaling) with an avatar, first name, and a soft status.
 * Tapping one opens a supportive story-style sheet (DailyWingModal).
 *
 * The first bubble is the signed-in user's "Share a wing" entry point.
 */
export function DailyWingsRow({ onOpen }) {
  return (
    <section className="wings" aria-label={DAILY_WINGS_TITLE}>
      <div className="wings__head">
        <h2 className="wings__title">{DAILY_WINGS_TITLE}</h2>
        <span className="wings__hint">small wins, not flexes</span>
      </div>
      <ul className="wings__row">
        {DAILY_WINGS.map((wing) => (
          <li key={wing.id}>
            <button
              type="button"
              className={`wing${wing.isSelf ? ' wing--self' : ''}`}
              onClick={() => onOpen?.(wing)}
              aria-label={wing.isSelf ? 'Share a wing' : `${wing.firstName}: ${wing.activity}`}
            >
              <span className={`wing__ring${wing.isSelf ? ' wing__ring--self' : ''}`}>
                <span className="cx-avatar wing__avatar" aria-hidden="true">
                  <span className="wing__emoji">{wing.emoji}</span>
                </span>
                {wing.isSelf && (
                  <span className="wing__add" aria-hidden="true">
                    <Plus size={12} />
                  </span>
                )}
              </span>
              <span className="wing__name">{wing.firstName}</span>
              <span className="wing__status">{wing.activity}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
