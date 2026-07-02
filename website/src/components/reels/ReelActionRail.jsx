import { BRAND } from '../../brand.js';
import { useState } from 'react';
import { Heart, Bookmark, MessageCircle, Sparkles, RefreshCw, HelpCircle, Share2, X } from 'lucide-react';
import { FEED_BALANCE_COPY } from './feedTaxonomy';

const REFLECTION_OPTIONS = ['Calmer', 'Curious', 'Not for me'];

/**
 * Side action rail for one Algorithm card. All actions are local/demo-safe: no API
 * writes, no permanent personalization, and no internal ranking metadata leaks.
 */
export function ReelActionRail({
  title,
  source,
  rankingReason,
  recommendationSummary,
  categoryLabel,
  categoryTone = 'neutral',
  fallbackReason,
  concernReason,
  safetyReason,
  publicSignalReason,
  publicSignalEffect,
  sourceSafetyStatus,
  saved = false,
  onToggleSave,
  liked = false,
  onToggleLike,
  reflection = null,
  onChooseReflection,
  onStatus,
  onRegenerate,
  onComment,
}) {
  const [showReflect, setShowReflect] = useState(false);
  const [showWhy, setShowWhy] = useState(false);
  const showPublicSignal = Boolean(publicSignalReason && publicSignalEffect !== 'none');

  const announce = (message) => onStatus?.(message);

  // Like / Save / Reflect persistence + status copy are owned by ReelCard (via the
  // useLikedVideos / useSavedVideos / useReflections hooks); the rail reflects the
  // props and forwards taps so the choices survive in the Liked/Saved section.
  const toggleLiked = () => {
    onToggleLike?.();
  };

  const toggleSaved = () => {
    onToggleSave?.();
  };

  const toggleReflect = () => {
    const nextOpen = !showReflect;
    setShowReflect(nextOpen);
    if (nextOpen) setShowWhy(false);
    announce(
      nextOpen
        ? 'What feeling did this card leave you with?'
        : 'Reflection prompt closed.',
    );
  };

  const chooseReflection = (option) => {
    // Tapping the current reflection again clears it.
    onChooseReflection?.(option === reflection ? null : option);
    setShowReflect(false);
  };

  const toggleWhy = () => {
    const nextOpen = !showWhy;
    setShowWhy(nextOpen);
    if (nextOpen) setShowReflect(false);
  };

  const handleRegenerate = () => {
    setShowReflect(false);
    setShowWhy(false);
    if (onRegenerate) {
      onRegenerate();
      return;
    }
    announce('Regenerating this session view.');
  };

  const handleShare = async () => {
    const pageUrl = typeof window !== 'undefined' ? window.location.href : '';
    const shareTitle = title ? `${title} | ${BRAND}` : `${BRAND} algorithm card`;
    const shareText = source
      ? `A ${BRAND} algorithm card from ${source}.`
      : `A ${BRAND} algorithm card for a calmer session.`;

    try {
      if (navigator.share) {
        announce('Opening share options.');
        await navigator.share({ title: shareTitle, text: shareText, url: pageUrl });
        return;
      }

      if (navigator.clipboard?.writeText && pageUrl) {
        await navigator.clipboard.writeText(pageUrl);
      }
      announce('Share link copied.');
    } catch (error) {
      if (error?.name === 'AbortError') return;
      announce('Share link copied.');
    }
  };

  return (
    <div className="reel-rail" role="group" aria-label="Algorithm card actions">
      <Action
        label="Like"
        pressed={liked}
        ariaLabel={liked ? 'Unlike' : 'Like'}
        onClick={toggleLiked}
      >
        <Heart size={20} fill={liked ? 'currentColor' : 'none'} aria-hidden="true" />
      </Action>

      <Action
        label="Save"
        pressed={saved}
        ariaLabel={saved ? 'Remove from saved' : 'Save'}
        onClick={toggleSaved}
      >
        <Bookmark size={20} fill={saved ? 'currentColor' : 'none'} aria-hidden="true" />
      </Action>

      {onComment && (
        <Action label="Comments" ariaLabel="Open comments" onClick={onComment}>
          <MessageCircle size={20} aria-hidden="true" />
        </Action>
      )}

      <Action
        label="Reflect"
        pressed={showReflect || Boolean(reflection)}
        expanded={showReflect}
        ariaLabel={showReflect ? 'Close reflection prompt' : 'Reflect on this card'}
        onClick={toggleReflect}
      >
        <Sparkles size={20} aria-hidden="true" />
      </Action>

      <Action
        label="Regenerate"
        ariaLabel="Show a different card from this mode"
        onClick={handleRegenerate}
      >
        <RefreshCw size={20} aria-hidden="true" />
      </Action>

      <Action
        label="Why?"
        pressed={showWhy}
        expanded={showWhy}
        ariaLabel="Why this video?"
        onClick={toggleWhy}
      >
        <HelpCircle size={20} aria-hidden="true" />
      </Action>

      <Action label="Share" ariaLabel="Share this card" onClick={handleShare}>
        <Share2 size={20} aria-hidden="true" />
      </Action>

      {showReflect && (
        <div className="reel-reflect" role="dialog" aria-label="Reflection prompt">
          <button
            type="button"
            className="reel-why__close"
            onClick={() => setShowReflect(false)}
            aria-label="Close reflection prompt"
          >
            <X size={15} aria-hidden="true" />
          </button>
          <p className="reel-reflect__title">What feeling did this card leave you with?</p>
          <div className="reel-reflect__chips" aria-label="Reflection options">
            {REFLECTION_OPTIONS.map((option) => (
              <button
                key={option}
                type="button"
                className={reflection === option ? 'is-selected' : ''}
                aria-pressed={reflection === option}
                onClick={() => chooseReflection(option)}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
      )}

      {showWhy && (
        <div className="reel-why" role="dialog" aria-label="Why this video?">
          <button
            type="button"
            className="reel-why__close"
            onClick={() => setShowWhy(false)}
            aria-label="Close explanation"
          >
            <X size={15} aria-hidden="true" />
          </button>
          <p className="reel-why__title">Why this video?</p>
          {categoryLabel && (
            <span className={`reel-why__badge reel-why__badge--${categoryTone}`}>
              {categoryLabel}
            </span>
          )}
          <p className="reel-why__summary">
            {recommendationSummary || 'A balanced pick chosen to keep your feed varied.'}
          </p>
          {(rankingReason || fallbackReason) && (
            <p className="reel-why__body">{rankingReason || fallbackReason}</p>
          )}
          <p className="reel-why__balance">{FEED_BALANCE_COPY}</p>
          {showPublicSignal && (
            <div className="reel-why__public">
              <p className="reel-why__public-title">Reputation context</p>
              <p className="reel-why__public-body">{publicSignalReason}</p>
              {sourceSafetyStatus === 'caution' && (
                <p className="reel-why__public-meta">Requires review</p>
              )}
            </div>
          )}
          {concernReason && <p className="reel-why__concern">{concernReason}</p>}
          {safetyReason && <p className="reel-why__safety">{safetyReason}</p>}
        </div>
      )}
    </div>
  );
}

function Action({
  children,
  label,
  ariaLabel,
  pressed,
  expanded,
  onClick,
}) {
  const isPressed = typeof pressed === 'boolean' ? pressed : false;

  return (
    <button
      type="button"
      className="reel-action"
      onClick={onClick}
      aria-label={ariaLabel}
      aria-pressed={typeof pressed === 'boolean' ? pressed : undefined}
      aria-expanded={typeof expanded === 'boolean' ? expanded : undefined}
    >
      <span className={`reel-action__btn${isPressed ? ' is-on' : ''}`}>{children}</span>
      <span className="reel-action__label">{label}</span>
    </button>
  );
}
