import { useEffect, useState } from 'react';
import { HomeShell } from '../home/HomeShell';
import { ChallengesPanel } from '../reels/ChallengesPanel';
import { useChallenges } from '../reels/useChallenges';
import '../../saved.css';

/**
 * Challenges — the wellness / IRL challenge hub, promoted from the in-feed drawer
 * to a top-level section. Reuses <ChallengesPanel> (the same component the feed
 * used) so all the logic — daily challenges, points, streaks, badges, the friendly
 * leaderboard, and friend invites — lives in one place.
 *
 * Wholesome, lightly competitive: touch grass, walk, journal, draw, no-doomscroll
 * breaks, kindness, the daily dewdrop. Points/streaks stay gentle, never aggressive.
 */
export function ChallengesPage() {
  const { stats, completedToday, badges, leaderboard, complete } = useChallenges();
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!toast) return undefined;
    const t = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(t);
  }, [toast]);

  return (
    <HomeShell active="challenges">
      <div className="home-narrow challenges-page">
        <ChallengesPanel
          stats={stats}
          completedToday={completedToday}
          badges={badges}
          leaderboard={leaderboard}
          onComplete={complete}
          onStatus={(message) => setToast(message)}
        />
      </div>
      {toast && (
        <div className="reels-toast" role="status" aria-live="polite">{toast}</div>
      )}
    </HomeShell>
  );
}
