import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, LoaderCircle, Volume2, VolumeX, X } from 'lucide-react';
import { DayBreakLogo } from '../../shared/components/DayBreakLogo';
import { CroppedYouTubePlayer } from '../reels/CroppedYouTubePlayer';
import { buildYouTubeEmbedUrl } from '../reels/youtubeEmbed.js';
import * as intentionalBreakApi from '../../lib/intentionalBreakApi.js';
import {
  activeResumePosition,
  createJourneySynchronizer,
  INTENTIONAL_BREAK_PAGE_SIZE,
  shouldLoadNextPage,
  validateReservedItemsPage,
} from './intentionalBreakFeedState.js';
import { readIntentionalBreakQueueSnapshot } from './intentionalBreakEventQueue.js';
import {
  useIntentionalBreakEvents,
  useIntentionalBreakItemVisibility,
} from './useIntentionalBreakEvents.js';
import '../../styles/reels.css';

function postPlayerCommand(iframe, func) {
  iframe?.contentWindow?.postMessage(JSON.stringify({ event: 'command', func, args: [] }), '*');
}

function IntentionalBreakCard({
  item,
  plannedTotal,
  isActive,
  eventsReady,
  enqueue,
  onCurrent,
  onFinalImpression,
}) {
  const iframeRef = useRef(null);
  const [soundOn, setSoundOn] = useState(false);
  const cardRef = useIntentionalBreakItemVisibility({
    enabled: eventsReady,
    item,
    enqueue,
    onCurrent,
    onMeaningfulImpression: onFinalImpression,
  });
  const embedOrigin = typeof window !== 'undefined' ? window.location.origin : undefined;
  const embedSrc = buildYouTubeEmbedUrl(item.post_id, {
    autoplay: true,
    muted: true,
    controls: false,
    enableJsApi: true,
    origin: embedOrigin,
    startSeconds: 0,
  });

  useEffect(() => () => postPlayerCommand(iframeRef.current, 'pauseVideo'), []);

  function toggleSound() {
    const next = !soundOn;
    postPlayerCommand(iframeRef.current, next ? 'unMute' : 'mute');
    setSoundOn(next);
  }

  return (
    <article
      className="intentional-feed-card"
      ref={cardRef}
      data-session-position={item.session_position}
      aria-label={`Video ${item.session_position} of ${plannedTotal}`}
    >
      <div className="intentional-feed-card__frame">
        {isActive && embedSrc ? (
          <CroppedYouTubePlayer
            key={`${item.post_id}:${item.session_position}`}
            src={embedSrc}
            title={`DayBreak video ${item.session_position}`}
            iframeRef={iframeRef}
            loading="eager"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
          />
        ) : (
          <button
            className="intentional-feed-card__poster"
            type="button"
            onClick={() => onCurrent(item.session_position)}
            aria-label={`Play video ${item.session_position}`}
          >
            <img
              src={`https://i.ytimg.com/vi/${encodeURIComponent(item.post_id)}/hqdefault.jpg`}
              alt=""
              loading="lazy"
            />
          </button>
        )}
        <div className="intentional-feed-card__shade" aria-hidden="true" />
        <span className="intentional-feed-card__context">Your chosen session</span>
        {isActive && (
          <button
            className="intentional-feed-card__sound"
            type="button"
            onClick={toggleSound}
            aria-pressed={soundOn}
            aria-label={soundOn ? 'Mute video' : 'Turn on sound'}
          >
            {soundOn ? <Volume2 aria-hidden="true" /> : <VolumeX aria-hidden="true" />}
          </button>
        )}
      </div>
    </article>
  );
}

function FeedLoadError({ initial, error, onRetry }) {
  return (
    <section className={`intentional-feed-error${initial ? ' intentional-feed-error--initial' : ''}`} role="alert">
      <AlertTriangle aria-hidden="true" />
      <div>
        <strong>
          {initial
            ? error?.retryable
              ? "We couldn't load your DayBreak yet."
              : "We couldn't restore this session safely."
            : "We couldn't load the rest of your session."}
        </strong>
        <p>{initial ? 'Your session is still saved.' : 'The videos already loaded are still available.'}</p>
        {error?.retryable && (
          <button type="button" onClick={onRetry}>Try again</button>
        )}
      </div>
    </section>
  );
}

export function IntentionalBreakFeed({
  journey,
  finishCommand,
  commandError,
  onServerJourney,
  onReconcileJourney,
  onFinishEarly,
}) {
  const sessionId = journey.session_id;
  const plannedTotal = journey.planned_video_count;
  const queueSnapshot = useRef(readIntentionalBreakQueueSnapshot(sessionId));
  const resumePosition = useRef(activeResumePosition(journey, queueSnapshot.current.pending));
  const [items, setItems] = useState([]);
  const itemsRef = useRef(items);
  const [currentPosition, setCurrentPosition] = useState(resumePosition.current);
  const [nextPosition, setNextPosition] = useState(resumePosition.current);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [boundaryPending, setBoundaryPending] = useState(false);
  const [finishDialogOpen, setFinishDialogOpen] = useState(false);
  const requestedStarts = useRef(new Set());
  const synchronizerRef = useRef(null);
  itemsRef.current = items;

  const handleEventJourney = useCallback((authoritativeJourney) => {
    if (authoritativeJourney?.journey_state !== 'active') synchronizerRef.current?.signal();
    onServerJourney(authoritativeJourney);
  }, [onServerJourney]);
  const { enqueue, queueStatus } = useIntentionalBreakEvents({
    sessionId,
    onJourney: handleEventJourney,
  });

  const loadPage = useCallback(async (startPosition) => {
    if (!Number.isInteger(startPosition)
      || startPosition > plannedTotal
      || requestedStarts.current.has(startPosition)
      || boundaryPending) return;
    requestedStarts.current.add(startPosition);
    setLoading(true);
    setLoadError(null);
    try {
      const response = await intentionalBreakApi.getItems(sessionId, {
        startPosition,
        limit: INTENTIONAL_BREAK_PAGE_SIZE,
      });
      const validated = validateReservedItemsPage(response, {
        plannedTotal,
        requestedStart: startPosition,
        existingItems: itemsRef.current,
      });
      setItems(validated.items);
      setNextPosition(validated.nextPosition);
      setHasMore(validated.hasMore);
    } catch (error) {
      requestedStarts.current.delete(startPosition);
      if (error?.errorCode === 'invalid_transition') onReconcileJourney();
      setLoadError(error);
    } finally {
      setLoading(false);
    }
  }, [boundaryPending, onReconcileJourney, plannedTotal, sessionId]);

  useEffect(() => {
    if (queueStatus.ready && !queueStatus.reconciling && itemsRef.current.length === 0) {
      loadPage(resumePosition.current);
    }
  }, [loadPage, queueStatus.ready, queueStatus.reconciling]);

  useEffect(() => {
    const sync = createJourneySynchronizer({
      sessionId,
      onChange: onReconcileJourney,
    });
    synchronizerRef.current = sync;
    const reconcileVisible = () => {
      if (document.visibilityState === 'visible') onReconcileJourney();
    };
    window.addEventListener('focus', onReconcileJourney);
    document.addEventListener('visibilitychange', reconcileVisible);
    return () => {
      sync.destroy();
      synchronizerRef.current = null;
      window.removeEventListener('focus', onReconcileJourney);
      document.removeEventListener('visibilitychange', reconcileVisible);
    };
  }, [onReconcileJourney, sessionId]);

  useEffect(() => {
    if (shouldLoadNextPage({
      currentPosition,
      loadedItems: items,
      hasMore,
      loading,
      boundaryPending,
      plannedTotal,
    })) loadPage(nextPosition);
  }, [boundaryPending, currentPosition, hasMore, items, loadPage, loading, nextPosition, plannedTotal]);

  const handleMeaningfulImpression = useCallback((item, result) => {
    if (item.session_position !== plannedTotal) return;
    if (result?.status === 'terminal') return;
    setBoundaryPending(true);
    if (result?.status === 'accepted') onReconcileJourney();
  }, [onReconcileJourney, plannedTotal]);

  async function confirmFinishEarly() {
    const authoritativeJourney = await onFinishEarly(currentPosition);
    if (authoritativeJourney?.journey_state !== 'active') synchronizerRef.current?.signal();
  }

  const finalTerminal = queueStatus.terminal.find(
    (event) => event.event_type === 'post_impression' && event.session_position === plannedTotal,
  );
  const finishing = boundaryPending || Boolean(finalTerminal);
  const initialLoading = items.length === 0 && (loading || queueStatus.reconciling || !queueStatus.ready);

  if (items.length === 0 && loadError) {
    return (
      <main className="intentional-feed-shell" data-algorithm data-research="true">
        <FeedLoadError initial error={loadError} onRetry={() => loadPage(resumePosition.current)} />
      </main>
    );
  }

  return (
    <main className="intentional-feed-shell" data-algorithm data-research="true">
      <header className="intentional-feed-chrome">
        <div className="intentional-feed-brand">
          <DayBreakLogo className="intentional-feed-brand__logo" />
          <span>Your chosen session</span>
        </div>
        <p className="intentional-feed-progress" aria-live="polite">
          <strong>{currentPosition}</strong> of {plannedTotal}
        </p>
        <button
          className="intentional-feed-finish"
          type="button"
          onClick={() => setFinishDialogOpen(true)}
          disabled={finishing || finishCommand.pending}
        >
          Finish early
        </button>
      </header>

      {initialLoading ? (
        <section className="intentional-feed-loading" aria-busy="true">
          <LoaderCircle className="study-spinner" aria-hidden="true" />
          <p role="status">{queueStatus.reconciling ? 'Restoring your session…' : 'Loading your DayBreak…'}</p>
        </section>
      ) : (
        <div className="intentional-feed-scroll">
          {items.map((item) => (
            <IntentionalBreakCard
              key={`${item.post_id}:${item.session_position}`}
              item={item}
              plannedTotal={plannedTotal}
              isActive={currentPosition === item.session_position && !finishing}
              eventsReady={queueStatus.ready && !queueStatus.reconciling}
              enqueue={enqueue}
              onCurrent={setCurrentPosition}
              onFinalImpression={handleMeaningfulImpression}
            />
          ))}
          {loading && items.length > 0 && (
            <div className="intentional-feed-page-status" role="status">
              <LoaderCircle className="study-spinner" aria-hidden="true" />
              Loading the next part of your session…
            </div>
          )}
          {loadError && items.length > 0 && (
            <FeedLoadError error={loadError} onRetry={() => loadPage(nextPosition)} />
          )}
        </div>
      )}

      {finishing && (
        <div className="intentional-feed-finishing" role="status" aria-live="assertive">
          {finalTerminal ? (
            <>
              <AlertTriangle aria-hidden="true" />
              <strong>We couldn&apos;t finish your DayBreak safely.</strong>
              <p>We couldn&apos;t record the final boundary safely. Your active session has not been completed.</p>
              <button type="button" onClick={onReconcileJourney}>Check session</button>
            </>
          ) : (
            <>
              <LoaderCircle className="study-spinner" aria-hidden="true" />
              <strong>Finishing your DayBreak…</strong>
            </>
          )}
        </div>
      )}

      {queueStatus.terminal.length > 0 && !finalTerminal && (
        <div className="intentional-feed-warning" role="alert">
          Some study activity could not be recorded. Your session remains active.
        </div>
      )}

      {finishDialogOpen && (
        <div className="intentional-feed-dialog-backdrop" role="presentation">
          <section
            className="intentional-feed-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="finish-early-title"
          >
            <button
              className="intentional-feed-dialog__close"
              type="button"
              onClick={() => setFinishDialogOpen(false)}
              disabled={finishCommand.pending}
              aria-label="Keep scrolling"
            >
              <X aria-hidden="true" />
            </button>
            <h2 id="finish-early-title">Finish your session here?</h2>
            <p>You planned for {plannedTotal} videos. It&apos;s okay to stop before that.</p>
            {commandError && (
              <div className="intentional-feed-dialog__error" role="alert">
                <strong>{commandError.retryable ? "We couldn't reach the study service." : 'Your session is still active.'}</strong>
                <span>{commandError.message}</span>
              </div>
            )}
            <div className="intentional-feed-dialog__actions">
              <button
                className="study-button study-button--primary"
                type="button"
                onClick={confirmFinishEarly}
                disabled={finishCommand.pending}
              >
                {finishCommand.pending ? 'Finishing…' : commandError?.retryable ? 'Try finish again' : 'Finish here'}
              </button>
              <button
                className="study-button study-button--secondary"
                type="button"
                onClick={() => setFinishDialogOpen(false)}
                disabled={finishCommand.pending}
              >
                Keep scrolling
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
