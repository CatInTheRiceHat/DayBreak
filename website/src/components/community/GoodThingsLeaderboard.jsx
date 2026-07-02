import { POSITIVE_ACTIONS } from './communityData';

/**
 * "Good Things" leaderboard — competitive, but ranked by Dewdrops earned through
 * healthy actions, never followers / likes / matches / comments / watch time.
 *
 * Rows are passed in already sorted by CommunityPage so the user's own row moves
 * as they complete challenges. The "You" row is highlighted; a small "how to
 * earn" footer reinforces that the scoring rewards behaviour, not attention.
 *
 * Props:
 *   rows — leaderboard entries, pre-sorted desc by dewdrops, with live rank
 */
export function GoodThingsLeaderboard({ rows }) {
  return (
    <section className="cmty-section" aria-label="Good Things Leaderboard">
      <div className="cmty-section__head">
        <h2 className="cmty-section__title">Good Things Leaderboard</h2>
      </div>
      <p className="cmty-section__subtitle">
        Compete by doing things that help you and your community feel better.
      </p>

      <ol className="cmty-board">
        {rows.map((row, i) => (
          <li
            key={row.id}
            className={`cmty-board__row${row.isSelf ? ' is-self' : ''}`}
          >
            <span className="cmty-board__rank" aria-label={`Rank ${i + 1}`}>
              {i + 1}
            </span>
            <span className="cx-avatar cx-avatar--sm cmty-board__avatar" aria-hidden="true">
              <span className="cx-avatar__fallback cmty-board__emoji">{row.emoji}</span>
            </span>
            <span className="cmty-board__id">
              <span className="cmty-board__name">{row.name}</span>
              <span className="cmty-board__action">{row.topAction}</span>
            </span>
            <span className="cmty-board__score">
              <strong>{row.dewdrops}</strong>
              <span className="cmty-board__unit">Dewdrops</span>
            </span>
          </li>
        ))}
      </ol>

      <div className="cmty-earn">
        <p className="cmty-earn__lead">Dewdrops are earned by:</p>
        <ul className="cmty-tags cmty-earn__tags">
          {POSITIVE_ACTIONS.map((action) => (
            <li key={action} className="cmty-tag">{action}</li>
          ))}
        </ul>
        <p className="cmty-note">Chrysalis rewards healthier behavior, not attention-seeking.</p>
      </div>
    </section>
  );
}
