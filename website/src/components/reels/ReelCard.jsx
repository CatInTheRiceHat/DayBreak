import { useLayoutEffect, useRef, useState } from 'react';
import { motion as MOTION } from 'motion/react';
import { Volume2, VolumeX } from 'lucide-react';
import { ReelActionRail } from './ReelActionRail';
import { ReelCaption } from './ReelCaption';
import { getRecommendationInsight } from './feedTaxonomy';
import { buildYouTubeEmbedUrl } from './youtubeEmbed';
import { CroppedYouTubePlayer } from './CroppedYouTubePlayer';
import { useSavedVideos } from './useSavedVideos';
import { useLikedVideos } from './useLikedVideos';
import { useReflections } from './useReflections';

function scoreValue(card, key) {
  const value = Number(card.chrysalis_scores?.[key]);
  return Number.isFinite(value) ? value : null;
}

function buildSignalHint(reel) {
  const insight = getRecommendationInsight(reel);
  if (insight.hasTaxonomy) return insight.summary;

  const hints = [];
  const calm = scoreValue(reel, 'calm');
  const comparisonRisk = scoreValue(reel, 'comparison_risk');
  const prosocial = scoreValue(reel, 'prosocial');
  const selfLove = scoreValue(reel, 'self_love');
  const reflection = scoreValue(reel, 'reflection_value');
  const novelty = scoreValue(reel, 'novelty');

  if (calm !== null && calm >= 0.6) hints.push('High calm');
  if (comparisonRisk !== null && comparisonRisk <= 0.2) hints.push('low comparison pressure');
  if (prosocial !== null && prosocial >= 0.5) hints.push('prosocial signal');
  if (selfLove !== null && selfLove >= 0.5) hints.push('self-love signal');
  if (reflection !== null && reflection >= 0.5) hints.push('reflective signal');
  if (novelty !== null && novelty >= 0.5) hints.push('fresh mix');

  if (hints.length) return hints.slice(0, 3).join(' · ');
  if (reel.ranking_reason) return reel.ranking_reason;
  if (reel.reason) return reel.reason;
  return 'Curated for this mode';
}

function resetYouTubeIframe(iframe) {
  const target = iframe?.contentWindow;
  if (!target) return;

  [
    { event: 'command', func: 'pauseVideo', args: [] },
    { event: 'command', func: 'seekTo', args: [0, true] },
    { event: 'command', func: 'pauseVideo', args: [] },
  ].forEach((message) => {
    target.postMessage(JSON.stringify(message), '*');
  });
}

/**
 * A single full-viewport Algorithm card. Two kinds of card:
 *  - real video (has `youtube_id`/`embed_url`): active-card YouTube autoplay embed,
 *    with a "curated by Chrysalis" badge and ranking/safety/concern reasons.
 *  - synthetic card (has `image`): the built-in wellbeing/pause cards.
 * No video files are downloaded — playback is a standard YouTube IFrame embed.
 */
export function ReelCard({
  reel,
  isActive = false,
  soundOn = true,
  onToggleSound,
  onVisible,
  onStatus,
  onRegenerate,
  onOpenComments,
}) {
  const [loaded, setLoaded] = useState(false);
  const iframeRef = useRef(null);
  const { isSaved, toggleSave } = useSavedVideos();
  const { isLiked, toggleLike } = useLikedVideos();
  const { reflectionFor, setReflection } = useReflections();

  const videoSource = reel.embed_url || reel.embedUrl || reel.youtube_id || reel.youtubeId;
  const hasVideo = Boolean(videoSource);
  const poster = reel.thumbnail || reel.image;
  const recommendationInsight = getRecommendationInsight(reel);
  const displayLabel = reel.label || recommendationInsight.label || (hasVideo ? 'Curated' : null);
  const isPopular = Boolean(reel.is_popular ?? reel.isPopular) || reel.source_type === 'most_popular';
  const popularBadgeLabel = reel.popularity_badge || reel.popularityBadge || 'Popular';
  const displayHashtags = Array.isArray(reel.display_hashtags) ? reel.display_hashtags.slice(0, 3) : [];
  const signalHint = buildSignalHint(reel);
  const embedOrigin = typeof window !== 'undefined' ? window.location.origin : undefined;
  const embedSrc = buildYouTubeEmbedUrl(videoSource, {
    autoplay: true,
    muted: !soundOn,
    controls: false,
    enableJsApi: true,
    origin: embedOrigin,
    startSeconds: 0,
  });
  const shouldRenderEmbed = hasVideo && embedSrc && isActive;

  useLayoutEffect(() => {
    if (!shouldRenderEmbed) return undefined;
    const iframe = iframeRef.current;
    return () => resetYouTubeIframe(iframe);
  }, [shouldRenderEmbed, embedSrc]);

  const requestPlayback = () => {
    onVisible?.();
  };

  const saved = isSaved(reel.id);
  const handleToggleSave = () => {
    const nowSaved = toggleSave(reel);
    onStatus?.(
      nowSaved
        ? 'Saved to your collection.'
        : 'Removed from your collection.',
    );
  };

  const liked = isLiked(reel.id);
  const handleToggleLike = () => {
    const nowLiked = toggleLike(reel);
    onStatus?.(nowLiked ? 'Added to your likes.' : 'Removed from your likes.');
  };

  const reflection = reflectionFor(reel.id);
  const handleChooseReflection = (label) => {
    setReflection(reel, label);
    onStatus?.(label ? `Reflection noted: ${label}.` : 'Reflection cleared.');
  };

  return (
    <article className="reel-card">
      <MOTION.div
        className="reel-layout"
        initial={{ opacity: 0, scale: 0.97 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ amount: 0.5 }}
        onViewportEnter={onVisible}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <ReelCaption
          title={reel.title}
          source={reel.source}
          label={displayLabel}
          description={reel.description}
          hashtags={displayHashtags}
          concernReason={reel.concern_reason}
          publicSignalEffect={reel.public_signal_effect}
          placement="desktop"
          signalHint={signalHint}
          isLiveVideo={hasVideo}
        />

        <div className="reel-media-cell">
          <div className="reel-frame">
            {/* Brand wash always sits behind the media so any image reads on-palette */}
            <div className="reel-media-wash" aria-hidden="true" />

            {hasVideo ? (
              shouldRenderEmbed ? (
                <CroppedYouTubePlayer
                  key={embedSrc}
                  src={embedSrc}
                  title={reel.title}
                  iframeRef={iframeRef}
                  loading={isActive ? 'eager' : 'lazy'}
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                  referrerPolicy="strict-origin-when-cross-origin"
                />
              ) : (
                /* Not-yet-active card: show just the tappable poster. No big
                   play badge/overlay on load — tapping activates playback. */
                <button
                  type="button"
                  className="reel-play"
                  onClick={requestPlayback}
                  aria-label={`Play video: ${reel.title}`}
                >
                  {poster && (
                    <img
                      className="reel-media"
                      src={poster}
                      alt=""
                      loading="lazy"
                      onLoad={() => setLoaded(true)}
                      style={{ opacity: loaded ? 1 : 0, transition: 'opacity 0.5s ease' }}
                    />
                  )}
                </button>
              )
            ) : (
              <div className="reel-media reel-media-loader" aria-label="Loading feed" role="img">
                <span className="reel-loader-sun" aria-hidden="true" />
              </div>
            )}

            {hasVideo && (
              <span className="reel-source-badge">YouTube embed · curated by Chrysalis</span>
            )}

            {hasVideo && isPopular && (
              <span className="reel-popular-badge" title="Currently popular on YouTube — still safety-checked by Chrysalis">
                {popularBadgeLabel}
              </span>
            )}

            {shouldRenderEmbed && onToggleSound && (
              <button
                type="button"
                className={`reel-mute${soundOn ? '' : ' reel-mute--off'}`}
                onClick={onToggleSound}
                aria-pressed={!soundOn}
                aria-label={soundOn ? 'Mute video' : 'Unmute video'}
              >
                {soundOn ? <Volume2 size={18} /> : <VolumeX size={18} />}
                {!soundOn && <span className="reel-mute__hint">Tap for sound</span>}
              </button>
            )}

            <ReelCaption
              title={reel.title}
              source={reel.source}
              label={displayLabel}
              description={reel.description}
              hashtags={displayHashtags}
              concernReason={reel.concern_reason}
              publicSignalEffect={reel.public_signal_effect}
              placement="mobile"
            />
          </div>
        </div>

        <ReelActionRail
          title={reel.title}
          source={reel.source}
          rankingReason={reel.ranking_reason}
          recommendationSummary={recommendationInsight.summary}
          categoryLabel={recommendationInsight.label}
          categoryTone={recommendationInsight.tone}
          fallbackReason={reel.reason}
          concernReason={reel.concern_reason}
          safetyReason={reel.safety_reason}
          publicSignalReason={reel.public_signal_reason}
          publicSignalEffect={reel.public_signal_effect}
          sourceSafetyStatus={reel.source_safety_status}
          saved={saved}
          onToggleSave={handleToggleSave}
          liked={liked}
          onToggleLike={handleToggleLike}
          reflection={reflection}
          onChooseReflection={handleChooseReflection}
          onStatus={onStatus}
          onRegenerate={onRegenerate}
          onComment={onOpenComments}
        />
      </MOTION.div>
    </article>
  );
}
