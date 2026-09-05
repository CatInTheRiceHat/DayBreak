import { useEffect, useMemo, useState } from 'react';
import { HomeShell } from '../home/HomeShell';
import { CommunityHeader } from './CommunityHeader';
import { FriendSwipeDeck } from './FriendSwipeDeck';
import { GoodThingsLeaderboard } from './GoodThingsLeaderboard';
import { YourCircle } from './YourCircle';
import { SafetyNote } from './SafetyNote';
import { LEADERBOARD, STARTER_CIRCLE } from './communityData';
import '../../community.css';

/**
 * Chrysalis Community — make friends through healthy actions, not clout. Friend
 * discovery (the swipe deck), your small circle, and a leaderboard that rewards
 * kind, real-world action with Dewdrops instead of follower counts.
 *
 * Wellness challenges live in their own top-level Challenges section now; Community
 * stays focused on people. Dewdrops here are earned through *social* good — adding
 * someone to your circle or sending encouragement — which bumps the header stat and
 * re-ranks the leaderboard live. All frontend-only (no backend).
 */
const BASE_WEEK_DEWDROPS = 128; // header "earned this week" starting figure
const SELF_BASE_SCORE = 310; // the "You" leaderboard row's starting Dewdrops
const CONNECT_DEWDROPS = 8; // adding a friend to your circle
const ENCOURAGE_DEWDROPS = 5; // inviting / cheering someone on

export function CommunityPage() {
  const [deckIndex, setDeckIndex] = useState(0);
  const [lastConnected, setLastConnected] = useState(null);
  const [circle, setCircle] = useState(STARTER_CIRCLE);
  const [earnedDewdrops, setEarnedDewdrops] = useState(0);
  const [circleNote, setCircleNote] = useState(null);

  // Auto-clear the transient confirmations so they read as gentle, not sticky.
  useEffect(() => {
    if (!lastConnected) return undefined;
    const t = window.setTimeout(() => setLastConnected(null), 3200);
    return () => window.clearTimeout(t);
  }, [lastConnected]);

  useEffect(() => {
    if (!circleNote) return undefined;
    const t = window.setTimeout(() => setCircleNote(null), 3200);
    return () => window.clearTimeout(t);
  }, [circleNote]);

  const handleDecision = (candidate, decision) => {
    if (decision === 'connect') {
      setLastConnected(candidate.name);
      setCircle((prev) => {
        if (prev.some((m) => m.id === candidate.id)) return prev;
        setEarnedDewdrops((d) => d + CONNECT_DEWDROPS);
        return [
          ...prev,
          {
            id: candidate.id,
            name: candidate.name,
            emoji: candidate.emoji,
            circleGoal: candidate.circleGoal,
            activity: candidate.activity,
          },
        ];
      });
    }
    setDeckIndex((i) => i + 1);
  };

  const handleGuidedAction = (member, kind) => {
    setEarnedDewdrops((d) => d + ENCOURAGE_DEWDROPS);
    setCircleNote(
      kind === 'invite'
        ? `You invited ${member.name} to a challenge. 🌿 +${ENCOURAGE_DEWDROPS} Dewdrops`
        : `You sent ${member.name} some encouragement. 💜 +${ENCOURAGE_DEWDROPS} Dewdrops`,
    );
  };

  // The "You" row grows with earned Dewdrops; re-sort so rank reflects action.
  const leaderboardRows = useMemo(() => {
    return LEADERBOARD.map((row) =>
      row.isSelf ? { ...row, dewdrops: SELF_BASE_SCORE + earnedDewdrops } : row,
    ).sort((a, b) => b.dewdrops - a.dewdrops);
  }, [earnedDewdrops]);

  return (
    <HomeShell active="community">
      <div className="cmty-page">
        <CommunityHeader dewdropsThisWeek={BASE_WEEK_DEWDROPS + earnedDewdrops} />

        <div className="cmty-grid">
          <div className="cmty-col cmty-col--main">
            <FriendSwipeDeck
              index={deckIndex}
              lastConnected={lastConnected}
              onDecision={handleDecision}
            />
          </div>

          <div className="cmty-col cmty-col--side">
            <GoodThingsLeaderboard rows={leaderboardRows} />
            <YourCircle
              members={circle}
              onGuidedAction={handleGuidedAction}
              note={circleNote}
            />
          </div>
        </div>

        <SafetyNote />
      </div>
    </HomeShell>
  );
}
