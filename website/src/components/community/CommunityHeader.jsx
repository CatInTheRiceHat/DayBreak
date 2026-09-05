import { COMMUNITY_HEADER } from './communityData';

/**
 * Community page header: title, supportive subtitle, and a row of small stat
 * cards (Dewdrops earned, challenges completed, circle matches, offline resets).
 *
 * The Dewdrops stat is driven by live state from CommunityPage so it ticks up as
 * the user completes challenges; the rest are static demo figures.
 */
export function CommunityHeader({ dewdropsThisWeek }) {
  const stats = COMMUNITY_HEADER.stats.map((stat) =>
    stat.id === 'dewdrops' ? { ...stat, value: dewdropsThisWeek } : stat,
  );

  return (
    <header className="cmty-header">
      <div className="cmty-header__intro">
        <h1 className="cmty-header__title">{COMMUNITY_HEADER.title}</h1>
        <p className="cmty-header__subtitle">{COMMUNITY_HEADER.subtitle}</p>
      </div>
      <ul className="cmty-stats" aria-label="Your community at a glance">
        {stats.map((stat) => (
          <li key={stat.id} className="cmty-stat">
            <span className="cmty-stat__emoji" aria-hidden="true">{stat.emoji}</span>
            <span className="cmty-stat__value">{stat.value}</span>
            <span className="cmty-stat__label">{stat.label}</span>
          </li>
        ))}
      </ul>
    </header>
  );
}
