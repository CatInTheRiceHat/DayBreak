import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion as MOTION } from 'motion/react';
import { useAuth } from '../../lib/authContext';
import { ReelCard } from './ReelCard';
import { FeedCompassPanel } from './FeedCompassPanel';
import { FeedDetailsDrawer } from './FeedDetailsDrawer';
import { ChrysalisTopBar } from './ChrysalisTopBar';
import { AppBottomNav } from './AppBottomNav';
import { AppSidebar } from './AppSidebar';
import { OnboardingStartScreen } from './OnboardingStartScreen';
import { getSessionId } from './preferences';
import { selectFreshCards } from './feedPagination';
import { SKIP_ALGORITHM_ONBOARDING, LOCK_HOME_FROM_ALGORITHM } from '../../brand.js';
import { MODES, reelsByMode, DEFAULT_MODE, LEGACY_INTENTION_MODES } from './reelsData';
import { getFeedDebugSnapshot } from './feedTaxonomy';
import { BreakScreen } from './BreakScreen';
import { useSessionTimer } from './useSessionTimer';
import { DEFAULT_TIME_SCALE_MS, DEMO_TIME_SCALE_MS } from './sessionBreaks';
import { useChallenges } from './useChallenges';
import { CommentsPanel } from './CommentsPanel';
import '../../reels.css';

const THEME_KEY = 'chrysalis-algorithm-theme';
const ONBOARDED_KEY = 'chrysalis-algorithm-onboarded';
const MODE_KEY = 'chrysalis-algorithm-mode';
const INTENTION_KEY = 'chrysalis-algorithm-intention';
const LEGACY_THEME_KEY = 'chrysalis-reels-theme';
const LEGACY_ONBOARDED_KEY = 'chrysalis-reels-onboarded';
const LEGACY_MODE_KEY = 'chrysalis-reels-mode';
const LEGACY_INTENTION_KEY = 'chrysalis-reels-intention';

const API_URL = import.meta.env.VITE_API_URL ?? '';
// Videos requested per infinite-scroll page.
const PAGE_SIZE = 12;

/**
 * Demo/test mode for screen-time breaks. Opt-in via `?breaks=demo` (compresses one
 * session minute into one real second, so a break arrives in ~60s and a dev
 * "Trigger break" control appears). Off by default — including in dev — so normal
 * browsing uses real minutes and breaks don't interrupt every minute.
 */
function detectBreakDemo() {
  if (typeof window !== 'undefined') {
    const param = new URLSearchParams(window.location.search).get('breaks');
    if (param === 'demo') return true;
  }
  return false;
}
const BREAK_DEMO = detectBreakDemo();
const HASHTAG_RE = /#[\w-]+/g;
const TRAILING_TITLE_SEPARATOR_RE = new RegExp(String.raw`[\s|/\\_:;,.=-]+$`);

function truncateAtWord(text, maxChars) {
  if (text.length <= maxChars) return text;
  const limit = Math.max(0, maxChars - 3);
  let shortened = text.slice(0, limit).trim();
  if (shortened.includes(' ')) shortened = shortened.replace(/\s+\S*$/, '').trim();
  return `${shortened.replace(/[.,;:|-]+$/, '').trim()}...`;
}

function compactText(value, maxChars) {
  const text = String(value || '')
    .replace(/https?:\/\/\S+|www\.\S+/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return truncateAtWord(text, maxChars);
}

function compactTitle(value) {
  const text = String(value || '')
    .replace(/https?:\/\/\S+|www\.\S+/gi, ' ')
    .replace(HASHTAG_RE, ' ')
    .replace(/\s+/g, ' ')
    .replace(TRAILING_TITLE_SEPARATOR_RE, '')
    .trim();
  return compactText(text || value, 82);
}

function compactCaption(value) {
  const text = String(value || '')
    .replace(/https?:\/\/\S+|www\.\S+/gi, ' ')
    .replace(HASHTAG_RE, ' ')
    .replace(/\b(subscribe|follow for more|follow me|links? below|link in bio|like and comment)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return truncateAtWord(text, 140);
}

function displayHashtags(item, rawTitle, rawDescription) {
  const raw = item.display_hashtags || item.displayHashtags;
  if (Array.isArray(raw)) return raw.map(String).filter(Boolean).slice(0, 3);

  const seen = new Set();
  const tags = [];
  for (const match of `${rawTitle || ''} ${rawDescription || ''}`.matchAll(HASHTAG_RE)) {
    const tag = match[0];
    const key = tag.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    tags.push(tag);
    if (tags.length >= 3) break;
  }
  return tags;
}

function isDemoPlaceholderVideoId(value) {
  return /^csl-/i.test(String(value || '').trim());
}

function isPlayableApiVideo(item, youtubeId) {
  const embedUrl = item.embed_url || item.embedUrl;
  return Boolean((youtubeId || embedUrl) && !isDemoPlaceholderVideoId(youtubeId));
}

/** Map a backend /api/feed item into the card shape ReelCard expects. */
function apiItemToCard(item) {
  const youtubeId = item.youtube_id || item.youtubeId;
  const playableVideo = isPlayableApiVideo(item, youtubeId);
  const rawTitle = item.title || '';
  const rawDescription = item.description || '';
  const rawSource = item.channel_title || item.channelTitle || item.raw_source || item.source || '';
  const displayDescription = item.display_description
    || item.displayDescription
    || item.short_description
    || item.shortDescription
    || compactCaption(rawDescription);
  const displayTitle = item.display_title || item.displayTitle || compactTitle(rawTitle);
  const displaySource = item.display_channel || item.displayChannel || compactText(rawSource, 30);

  return {
    id: youtubeId || item.embed_url || item.embedUrl,
    youtube_id: playableVideo ? youtubeId : null,
    raw_youtube_id: youtubeId,
    title: displayTitle,
    raw_title: rawTitle,
    source: displaySource,
    raw_source: rawSource,
    description: displayDescription,
    raw_description: rawDescription,
    short_description: item.short_description || item.shortDescription || displayDescription,
    display_description: item.display_description || item.displayDescription || displayDescription,
    display_hashtags: displayHashtags(item, rawTitle, rawDescription),
    thumbnail: item.thumbnail,
    embed_url: playableVideo ? item.embed_url || item.embedUrl : null,
    watch_url: playableVideo ? item.watch_url : null,
    is_playable_video: playableVideo,
    ranking_reason: item.ranking_reason || item.rankingReason,
    safety_reason: item.safety_reason || item.safetyReason,
    concern_reason: item.concern_reason || item.concernReason,
    public_signal: item.public_signal,
    source_safety_status: item.source_safety_status,
    public_signal_effect: item.public_signal_effect,
    public_signal_reason: item.public_signal_reason,
    chrysalis_scores: item.chrysalis_scores,
    mode_fit: item.mode_fit,
    source_type: item.source_type || item.sourceType || 'search',
    is_popular: Boolean(item.is_popular ?? item.isPopular),
    popularity_badge: item.popularity_badge || item.popularityBadge || null,
    content_category: item.content_category || item.contentCategory || null,
    wellness_score: item.wellness_score ?? item.wellnessScore ?? null,
    positivity_score: item.positivity_score ?? item.positivityScore ?? null,
    conflict_score: item.conflict_score ?? item.conflictScore ?? null,
    safety_risk: item.safety_risk ?? item.safetyRisk ?? null,
    perspective_topic: item.perspective_topic || item.perspectiveTopic || null,
    recommendation_lane: item.recommendation_lane || item.recommendationLane || null,
  };
}

function createFeedSeed() {
  if (typeof window !== 'undefined' && window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function storedValue(key, legacyKey) {
  if (typeof window === 'undefined') return null;
  const current = window.localStorage.getItem(key);
  return current ?? window.localStorage.getItem(legacyKey);
}

function initialTheme() {
  if (typeof window === 'undefined') return 'light';
  const saved = storedValue(THEME_KEY, LEGACY_THEME_KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

// Phones block autoplay-with-sound until the user taps once, so we start the
// feed muted on touch devices and let a single tap unlock audio for the session.
// Desktop allows sound-on autoplay, so it starts unmuted.
function initialSoundOn() {
  if (typeof window === 'undefined') return true;
  return !window.matchMedia?.('(pointer: coarse)').matches;
}

function initialMode() {
  if (typeof window === 'undefined') return DEFAULT_MODE;
  const saved = storedValue(MODE_KEY, LEGACY_MODE_KEY);
  if (saved && reelsByMode[saved]) return saved;
  const legacyIntention = storedValue(INTENTION_KEY, LEGACY_INTENTION_KEY);
  const migratedMode = LEGACY_INTENTION_MODES[legacyIntention];
  return migratedMode && reelsByMode[migratedMode] ? migratedMode : DEFAULT_MODE;
}

function initialOnboarded() {
  if (SKIP_ALGORITHM_ONBOARDING) return true;
  if (typeof window === 'undefined') return false;
  return storedValue(ONBOARDED_KEY, LEGACY_ONBOARDED_KEY) === '1';
}

function cardSessionKey(mode, index, reel) {
  return `${mode}:${reel.id ?? reel.youtube_id ?? index}`;
}

function isLiveVideoCard(card) {
  if (typeof card.is_playable_video === 'boolean') return card.is_playable_video;
  return Boolean(card.youtube_id || card.embed_url || card.embedUrl);
}

function isBreakReminder(mode, reel) {
  if (isLiveVideoCard(reel)) return false;
  return mode === 'metamorphosis' || ['Rest', 'Awareness', 'Pause'].includes(reel.label);
}

function feedStatus(cards) {
  const liveCount = cards.filter(isLiveVideoCard).length;
  if (!liveCount) return 'fallback';
  return liveCount === cards.length ? 'live' : 'mixed';
}

function scoreValue(card, key) {
  const value = Number(card.chrysalis_scores?.[key]);
  return Number.isFinite(value) ? value : 0;
}

function sourceKey(card) {
  return (card.source || card.channel_title || card.channel || 'unknown').toLowerCase();
}

function sessionTuneScore(card, selectedTunes) {
  let score = 0;
  if (selectedTunes.includes('calm')) score += scoreValue(card, 'calm') * 3;
  if (selectedTunes.includes('comparison')) score += (1 - scoreValue(card, 'comparison_risk')) * 3;
  if (selectedTunes.includes('uplifting')) {
    score += (scoreValue(card, 'prosocial') + scoreValue(card, 'self_love')) * 1.5;
  }
  return score;
}

function diversifyBySource(items) {
  const remaining = [...items];
  const output = [];
  let previousSource = null;

  while (remaining.length) {
    const nextIndex = remaining.findIndex((item) => sourceKey(item.card) !== previousSource);
    const [next] = remaining.splice(nextIndex === -1 ? 0 : nextIndex, 1);
    output.push(next);
    previousSource = sourceKey(next.card);
  }

  return output;
}

function applySessionTuning(cards, mode, selectedTunes) {
  const tunesThatReorder = selectedTunes.filter((key) => key !== 'shorter');
  if (!tunesThatReorder.length) return cards;

  let tuned = cards
    .map((card, index) => ({
      card,
      index,
      score: sessionTuneScore(card, selectedTunes),
    }))
    .sort((a, b) => (b.score - a.score) || (a.index - b.index));

  if (selectedTunes.includes('variety')) {
    tuned = diversifyBySource(tuned);
  }

  return tuned.map((item) => item.card);
}

export function ReelsPage() {
  const scrollRef = useRef(null);
  const [theme, setTheme] = useState(initialTheme);
  const [onboarded, setOnboarded] = useState(initialOnboarded);
  const [mode, setMode] = useState(initialMode);
  const [modeSelectionInitial, setModeSelectionInitial] = useState(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [soundOn, setSoundOn] = useState(initialSoundOn);
  const [viewedCards, setViewedCards] = useState(() => new Set());
  const [breakReminderCards, setBreakReminderCards] = useState(() => new Set());
  const [selectedTunes, setSelectedTunes] = useState([]);
  const [compassOpen, setCompassOpen] = useState(false);
  const [toast, setToast] = useState(null);
  // Feed for the active mode, tagged with the mode it belongs to so a stale
  // response never renders under the wrong guided mode.
  const [feed, setFeed] = useState({ mode: null, cards: null, debug: null });

  // Progressive screen-time breaks. The timer only accrues while the feed is open
  // and no break is showing; when a break is due the feed pauses behind the overlay.
  const breakScaleMs = BREAK_DEMO ? DEMO_TIME_SCALE_MS : DEFAULT_TIME_SCALE_MS;
  const {
    elapsedMin,
    dueTier,
    completeBreak,
    triggerBreakNow,
    reset: resetSessionTimer,
  } = useSessionTimer({ active: onboarded, scaleMs: breakScaleMs });
  const breakActive = onboarded && Boolean(dueTier);

  // IRL challenges (points, streaks, friend competition) — local demo state.
  const challenges = useChallenges();
  const [commentsOpen, setCommentsOpen] = useState(false);

  // Profile lives on its own route now: send signed-in users to /profile, others
  // to /login. (The old in-feed ProfilePanel/useProfile remain in the repo but
  // are no longer wired into the feed.)
  const navigate = useNavigate();
  const { user } = useAuth();
  const goToProfile = () => navigate(user ? '/profile' : '/login');
  const goToCommunity = () => navigate('/community');
  const goToSaved = () => navigate('/saved');
  const goToChallenges = () => navigate('/challenges');
  const goToSearch = () => navigate('/search');
  const goHome = () => {
    if (LOCK_HOME_FROM_ALGORITHM) {
      announceStatus('Home stays locked while you are in the feed.');
      return;
    }
    navigate('/home');
  };

  // ── Infinite-scroll feed ──────────────────────────────────────────────────
  // Load one balanced page at a time and append more as the user nears the
  // bottom. Pagination uses the backend exclude_ids contract: we send the ids
  // already shown so the next page never repeats a video. The built-in synthetic
  // sample cards are used ONLY when the backend genuinely has no real videos for
  // the mode (empty pool / network error on the first page).
  const sentinelRef = useRef(null);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const paginationRef = useRef(null);
  if (paginationRef.current === null) {
    paginationRef.current = {
      mode, seed: null, excludeIds: [], seen: new Set(),
      hasMore: true, loading: false, source: null,
    };
  }
  const [loadingMore, setLoadingMore] = useState(false);

  const loadPage = useCallback(async ({ reset }) => {
    const pg = paginationRef.current;
    if (pg.loading) return;                       // one fetch at a time
    if (!reset && !pg.hasMore) return;            // nothing left to load
    const activeMode = modeRef.current;
    const synthetic = reelsByMode[activeMode] ?? reelsByMode[DEFAULT_MODE];

    pg.loading = true;
    setLoadingMore(true);
    try {
      const seed = reset ? createFeedSeed() : (pg.seed ?? createFeedSeed());
      const excludeIds = reset ? [] : pg.excludeIds;
      const params = new URLSearchParams({ k: String(PAGE_SIZE), seed });
      const sessionId = getSessionId();
      if (sessionId) params.set('session_id', sessionId);
      if (excludeIds.length) params.set('exclude_ids', excludeIds.join(','));

      const response = await fetch(`${API_URL}/api/feed/${activeMode}?${params.toString()}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (modeRef.current !== activeMode) return; // user switched modes mid-flight

      const seen = reset ? new Set() : pg.seen;
      const mapped = (data.items ?? []).map(apiItemToCard);
      const { fresh, returnedIds } = selectFreshCards(seen, mapped);  // dedupe by video id

      if (reset && fresh.length === 0) {
        // Backend genuinely has no eligible videos → static sample fallback.
        Object.assign(pg, { seed, excludeIds: [], seen: new Set(), hasMore: false, source: 'fallback' });
        setFeed({ mode: activeMode, cards: synthetic, debug: null, hasMore: false, source: 'fallback' });
        return;
      }

      pg.seed = seed;
      pg.seen = seen;
      pg.excludeIds = reset ? returnedIds : [...pg.excludeIds, ...returnedIds];
      pg.hasMore = Boolean(data.has_more) && fresh.length > 0;
      pg.source = 'live';

      if (reset) {
        setFeed({ mode: activeMode, cards: fresh, debug: getFeedDebugSnapshot(data), hasMore: pg.hasMore, source: 'live' });
      } else {
        setFeed((prev) => (
          prev.mode === activeMode
            ? { ...prev, cards: [...(prev.cards ?? []), ...fresh], hasMore: pg.hasMore, source: 'live' }
            : prev
        ));
      }
    } catch (error) {
      if (import.meta.env.DEV) {
        console.warn('[Chrysalis algorithm] Feed page failed:', error);
      }
      if (reset) {
        const synthetic2 = reelsByMode[modeRef.current] ?? reelsByMode[DEFAULT_MODE];
        Object.assign(pg, { hasMore: false, source: 'fallback' });
        setFeed({ mode: modeRef.current, cards: synthetic2, debug: null, hasMore: false, source: 'fallback' });
      }
      // Non-reset errors keep the current feed; a later scroll can retry.
    } finally {
      pg.loading = false;
      setLoadingMore(false);
    }
  }, []);

  // (Re)load page 0 whenever the mode changes or the feed is (re)entered.
  useEffect(() => {
    if (!onboarded) return undefined;
    paginationRef.current = {
      mode, seed: null, excludeIds: [], seen: new Set(),
      hasMore: true, loading: false, source: null,
    };
    loadPage({ reset: true });
    return undefined;
  }, [mode, onboarded, loadPage]);

  // Bottom sentinel → fetch the next page as the user approaches the end.
  useEffect(() => {
    if (!onboarded) return undefined;
    const root = scrollRef.current;
    const sentinel = sentinelRef.current;
    if (!root || !sentinel || typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          loadPage({ reset: false });
        }
      },
      { root, rootMargin: '0px 0px 800px 0px', threshold: 0 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [onboarded, mode, loadPage]);

  useEffect(() => {
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (SKIP_ALGORITHM_ONBOARDING) return;
    window.localStorage.setItem(ONBOARDED_KEY, onboarded ? '1' : '0');
  }, [onboarded]);

  useEffect(() => {
    window.localStorage.setItem(MODE_KEY, mode);
  }, [mode]);

  useEffect(() => {
    if (!toast) return undefined;
    const timeout = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'));

  const startFeed = (chosenMode) => {
    const nextMode = reelsByMode[chosenMode] ? chosenMode : DEFAULT_MODE;
    setMode(nextMode);
    setModeSelectionInitial(nextMode);
    setActiveIndex(0);
    setCompassOpen(false);
    setOnboarded(true);
  };

  const cards = (feed.mode === mode && feed.cards)
    ? feed.cards
    : (reelsByMode[mode] ?? reelsByMode[DEFAULT_MODE]);
  const tunedCards = useMemo(
    () => applySessionTuning(cards, mode, selectedTunes),
    [cards, mode, selectedTunes],
  );
  const activeCard = tunedCards[Math.min(activeIndex, Math.max(tunedCards.length - 1, 0))]
    ?? tunedCards[0];
  const currentMode = MODES.find((item) => item.key === mode)
    || MODES.find((item) => item.key === DEFAULT_MODE);
  const currentFeedStatus = feedStatus(tunedCards);

  const resetIntro = () => {
    setCompassOpen(false);
    setModeSelectionInitial(mode);
    setOnboarded(false);
    resetSessionTimer();
  };

  const markCardVisible = (index, reel) => {
    setActiveIndex(index);
    const key = cardSessionKey(mode, index, reel);
    setViewedCards((previous) => {
      if (previous.has(key)) return previous;
      const next = new Set(previous);
      next.add(key);
      return next;
    });
    if (isBreakReminder(mode, reel)) {
      setBreakReminderCards((previous) => {
        if (previous.has(key)) return previous;
        const next = new Set(previous);
        next.add(key);
        return next;
      });
    }
  };

  const toggleTune = (tuneKey) => {
    setSelectedTunes((previous) => (
      previous.includes(tuneKey)
        ? previous.filter((key) => key !== tuneKey)
        : [...previous, tuneKey]
    ));
  };

  const announceStatus = (message) => {
    setToast({ id: `${Date.now()}-${message}`, message });
  };

  const handleBreakComplete = (entry) => {
    completeBreak(entry);
    announceStatus('Welcome back — enjoy your refreshed feed.');
  };

  const showNextCard = (index) => {
    if (tunedCards.length < 2) {
      announceStatus('Regenerating this session view.');
      return;
    }

    const nextIndex = (index + 1) % tunedCards.length;
    const scroller = scrollRef.current;
    setActiveIndex(nextIndex);
    scroller?.scrollTo({ top: nextIndex * scroller.clientHeight, behavior: 'smooth' });
    announceStatus('Showing a different card from this mode.');
  };

  const scrollToTop = () => {
    const scroller = scrollRef.current;
    setActiveIndex(0);
    scroller?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Unified nav handler for the shared sidebar/bottom-bar. On the feed, tapping
  // "Reels" scrolls back to the top instead of routing; everything else routes.
  const onNav = (key) => {
    switch (key) {
      case 'home': goHome(); break;
      case 'reels': scrollToTop(); break;
      case 'community': goToCommunity(); break;
      case 'challenges': goToChallenges(); break;
      case 'search': goToSearch(); break;
      case 'saved': goToSaved(); break;
      case 'profile': goToProfile(); break;
      default: break;
    }
  };

  return (
    <main
      className="reels-shell"
      data-algorithm
      data-theme={theme}
      data-onboarded={onboarded ? 'true' : 'false'}
    >
      {onboarded && (
        <AppSidebar
          active="reels"
          intentionLabel={currentMode?.label ?? "Cruisin'"}
          intentionLogo={currentMode?.logo}
          onNavigate={onNav}
          onOpenDetails={() => setCompassOpen(true)}
          detailsOpen={compassOpen}
          streak={challenges.stats.streak}
          theme={theme}
          onToggleTheme={toggleTheme}
          showBreakDemo={BREAK_DEMO}
          onTriggerBreak={triggerBreakNow}
        />
      )}

      <ChrysalisTopBar
        showActions={onboarded}
        intentionLabel={currentMode?.label ?? "Cruisin'"}
        intentionLogo={currentMode?.logo}
        theme={theme}
        onToggleTheme={toggleTheme}
        onOpenDetails={() => setCompassOpen(true)}
        detailsOpen={compassOpen}
        onOpenChallenges={goToChallenges}
        challengesOpen={false}
        streak={challenges.stats.streak}
        onOpenProfile={goToProfile}
        profileOpen={false}
        showBreakDemo={BREAK_DEMO}
        onTriggerBreak={triggerBreakNow}
      />

      <AnimatePresence mode="wait">
        {!onboarded ? (
          <OnboardingStartScreen
            key="onboard"
            initialMode={modeSelectionInitial}
            onStart={startFeed}
          />
        ) : (
          <MOTION.div
            key="feed"
            className="reels-feed"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35 }}
          >
            <div className="reels-stage">
              <div className="reels-feed-column">
                <div className="reels-scroll" data-lenis-prevent key={mode} ref={scrollRef}>
                  {tunedCards.map((reel, index) => (
                    <ReelCard
                      key={reel.id}
                      reel={reel}
                      isActive={index === activeIndex && !breakActive}
                      soundOn={soundOn}
                      onToggleSound={() => setSoundOn((on) => !on)}
                      onVisible={() => markCardVisible(index, reel)}
                      onStatus={announceStatus}
                      onRegenerate={() => showNextCard(index)}
                      onOpenComments={() => setCommentsOpen(true)}
                    />
                  ))}

                  {/* Infinite-scroll sentinel — always present so the observer
                      stays attached; loadPage no-ops when there's nothing more. */}
                  <div ref={sentinelRef} className="reels-feed-sentinel" aria-hidden="true" />

                  {loadingMore && (
                    <div className="reels-feed-status" role="status" aria-live="polite">
                      <span className="reels-feed-status__spinner" aria-hidden="true" />
                      Loading more videos…
                    </div>
                  )}

                  {feed.mode === mode && feed.source === 'live' && feed.hasMore === false && (
                    <div className="reels-feed-end" role="status">
                      <p className="reels-feed-end__title">You're all caught up</p>
                      <p className="reels-feed-end__sub">
                        You've reached the end of fresh videos for now.
                      </p>
                      <button
                        type="button"
                        className="reels-feed-end__refresh"
                        onClick={() => loadPage({ reset: true })}
                      >
                        Refresh feed
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <AppBottomNav active="reels" onNavigate={onNav} />

            <FeedDetailsDrawer
              open={compassOpen}
              onClose={() => setCompassOpen(false)}
              label="Feed details"
            >
              <FeedCompassPanel
                activeMode={mode}
                activeCard={activeCard}
                feedStatus={currentFeedStatus}
                viewedCount={viewedCards.size}
                breakReminderCount={breakReminderCards.size}
                selectedTunes={selectedTunes}
                onResetIntro={resetIntro}
                onTuneChange={toggleTune}
                onClose={() => setCompassOpen(false)}
              />
            </FeedDetailsDrawer>
          </MOTION.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {breakActive && (
          <BreakScreen
            key="break"
            tier={dueTier}
            elapsedMin={elapsedMin}
            onComplete={handleBreakComplete}
            onOpenChallenges={goToChallenges}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {commentsOpen && (
          <MOTION.div
            className="feed-compass-sheet challenges-sheet"
            role="dialog"
            aria-modal="true"
            aria-label="Comments"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div
              className="feed-compass-sheet__scrim"
              aria-hidden="true"
              onClick={() => setCommentsOpen(false)}
            />
            <MOTION.div
              className="feed-compass-sheet__panel"
              initial={{ y: 28, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 28, opacity: 0 }}
              transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            >
              <CommentsPanel
                onStatus={announceStatus}
                onClose={() => setCommentsOpen(false)}
              />
            </MOTION.div>
          </MOTION.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {toast && (
          <MOTION.div
            key={toast.id}
            className="reels-toast"
            role="status"
            aria-live="polite"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            transition={{ duration: 0.2 }}
          >
            {toast.message}
          </MOTION.div>
        )}
      </AnimatePresence>
    </main>
  );
}
