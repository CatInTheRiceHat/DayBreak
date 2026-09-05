import { Sparkles, HeartHandshake } from 'lucide-react';

/**
 * "Your Circle" — people already matched. Each card shows the avatar, shared
 * goal, and a suggested activity, plus two *guided* actions: Invite to Challenge
 * and Send Encouragement. There are no open DMs in this first pass; tapping an
 * action surfaces a small confirmation rather than opening a chat.
 *
 * Props:
 *   members — circle entries (starter set + anyone the user just connected with)
 *   onGuidedAction(member, kind) — "invite" | "encourage"
 *   note — transient confirmation message for the most recent guided action
 */
export function YourCircle({ members, onGuidedAction, note }) {
  return (
    <section className="cmty-section" aria-label="Your Circle">
      <div className="cmty-section__head">
        <h2 className="cmty-section__title">Your Circle</h2>
        <span className="cmty-section__count">{members.length} buddies</span>
      </div>

      {note && (
        <p className="cmty-success" role="status" aria-live="polite">{note}</p>
      )}

      <div className="cmty-circle">
        {members.map((member) => (
          <article key={member.id} className="cmty-buddy">
            <header className="cmty-buddy__head">
              <span className="cx-avatar cx-avatar--sm cmty-buddy__avatar" aria-hidden="true">
                <span className="cx-avatar__fallback cmty-board__emoji">{member.emoji}</span>
              </span>
              <div className="cmty-buddy__id">
                <span className="cmty-buddy__name">{member.name}</span>
                <span className="cmty-buddy__goal">{member.circleGoal}</span>
              </div>
            </header>
            <p className="cmty-buddy__activity">{member.activity}</p>
            <div className="cmty-buddy__actions">
              <button
                type="button"
                className="home-btn home-btn--chip"
                onClick={() => onGuidedAction(member, 'invite')}
              >
                <Sparkles size={14} aria-hidden="true" /> Invite to Challenge
              </button>
              <button
                type="button"
                className="home-btn home-btn--chip"
                onClick={() => onGuidedAction(member, 'encourage')}
              >
                <HeartHandshake size={14} aria-hidden="true" /> Send Encouragement
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
