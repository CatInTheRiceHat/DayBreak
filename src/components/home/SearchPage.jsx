import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search } from 'lucide-react';
import { HomeShell } from './HomeShell';
import {
  SEARCH_ACTIVITIES,
  SEARCH_PEOPLE,
  SUGGESTED_SEARCHES,
} from './homeData';

/**
 * Search — people, activities, and (eventually) saved resets.
 *
 * Backend search does not exist yet, so this searches the local demo cast and the
 * activity vocabulary, and is honest about it ("Searching Chrysalis demo content").
 * No fake backend claims, no popularity ranking.
 */
// Healthy-feed vibe filters — Chrysalis's content tones, so Search reads as a calm
// discovery surface rather than a generic explore grid. Tapping one searches it.
const FILTER_TAGS = ['calm', 'funny', 'wellness', 'perspective', 'creative', 'study', 'social'];

function matches(text, query) {
  return text.toLowerCase().includes(query.trim().toLowerCase());
}

export function SearchPage() {
  const [query, setQuery] = useState('');
  const active = query.trim().length > 0;

  const people = useMemo(
    () => (active
      ? SEARCH_PEOPLE.filter((p) => matches(p.displayName, query) || matches(p.username, query) || matches(p.reason, query))
      : []),
    [query, active],
  );
  const activities = useMemo(
    () => (active ? SEARCH_ACTIVITIES.filter((a) => matches(a.label, query)) : []),
    [query, active],
  );
  const nothing = active && people.length === 0 && activities.length === 0;

  return (
    <HomeShell active="search">
      <div className="home-narrow">
        <h1 className="page-title">Search</h1>

        <label className="search-field">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search people, activities, or saved resets"
            aria-label="Search people, activities, or saved resets"
            autoFocus
          />
        </label>

        <section className="search-filters" aria-label="Filter by vibe">
          <div className="chips-wrap">
            {FILTER_TAGS.map((tag) => (
              <button
                key={tag}
                type="button"
                className={`home-btn home-btn--chip${query.trim().toLowerCase() === tag ? ' is-active' : ''}`}
                onClick={() => setQuery(tag)}
              >
                {tag}
              </button>
            ))}
          </div>
        </section>

        {!active && (
          <section className="search-suggested" aria-label="Suggested searches">
            <h2 className="section-title">Suggested searches</h2>
            <div className="chips-wrap">
              {SUGGESTED_SEARCHES.map((term) => (
                <button key={term} type="button" className="home-btn home-btn--chip" onClick={() => setQuery(term)}>
                  {term}
                </button>
              ))}
            </div>
          </section>
        )}

        {people.length > 0 && (
          <section className="search-results" aria-label="People">
            <h2 className="section-title">People</h2>
            <ul className="result-list">
              {people.map((p) => (
                <li key={p.id}>
                  <Link to={`/u/${p.username}`} className="result-row">
                    <span className="cx-avatar cx-avatar--sm" aria-hidden="true">
                      <span className="wing__emoji">{p.emoji}</span>
                    </span>
                    <span className="result-meta">
                      <span className="result-name">{p.displayName}</span>
                      <span className="result-sub">{p.reason}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        {activities.length > 0 && (
          <section className="search-results" aria-label="Activities">
            <h2 className="section-title">Activities</h2>
            <div className="chips-wrap">
              {activities.map((a) => (
                <span key={a.id} className="home-btn home-btn--chip is-static">
                  <span aria-hidden="true">{a.emoji}</span> {a.label}
                </span>
              ))}
            </div>
          </section>
        )}

        {active && (
          <section className="search-results" aria-label="Your collection">
            <h2 className="section-title">Your collection</h2>
            <p className="empty-note">
              Looking for something you kept? Check <Link to="/saved">Liked &amp; Saved</Link>.
            </p>
          </section>
        )}

        {nothing && (
          <p className="empty-note">No demo matches for “{query.trim()}”. Try a suggested search.</p>
        )}

        <p className="demo-note">Searching Chrysalis demo content — full search is on the way.</p>
      </div>
    </HomeShell>
  );
}
