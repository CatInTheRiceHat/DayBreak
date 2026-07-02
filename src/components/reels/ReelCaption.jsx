import { useEffect, useId, useRef, useState } from 'react';
import { Leaf, ShieldAlert } from 'lucide-react';

/**
 * Algorithm card text block. On desktop this becomes the left-side editorial info panel;
 * on mobile it stays as the compact bottom overlay with a local more/less
 * description toggle.
 */
export function ReelCaption({
  title,
  source,
  label,
  description,
  hashtags = [],
  concernReason,
  publicSignalEffect,
  placement = 'mobile',
  signalHint,
  isLiveVideo = false,
}) {
  const descriptionId = useId();
  const descriptionRef = useRef(null);
  const [expanded, setExpanded] = useState(false);
  const [hasOverflow, setHasOverflow] = useState(false);
  const showReviewSignal = Boolean(publicSignalEffect && publicSignalEffect !== 'none');
  const visibleHashtags = hashtags.slice(0, 3);
  const canExpand = placement === 'mobile'
    && Boolean(description)
    && (hasOverflow || description.length > 96);

  useEffect(() => {
    if (placement !== 'mobile' || !description || !descriptionRef.current) return undefined;

    let frame = 0;
    const measure = () => {
      const node = descriptionRef.current;
      if (!node) return;
      setHasOverflow(node.scrollHeight > node.clientHeight + 1);
    };
    const scheduleMeasure = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(measure);
    };

    scheduleMeasure();
    window.addEventListener('resize', scheduleMeasure);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', scheduleMeasure);
    };
  }, [description, placement]);

  return (
    <div className={`reel-caption reel-caption--${placement}${expanded ? ' is-expanded' : ''}`}>
      <div className="reel-caption__chips">
        {label && (
          <span className="reel-caption__chip reel-meta-clamp">
            <Leaf size={12} aria-hidden="true" />
            {label}
          </span>
        )}
        {concernReason && (
          <span className="reel-caption__chip reel-caption__chip--concern reel-meta-clamp">
            <ShieldAlert size={12} aria-hidden="true" />
            Heads up
          </span>
        )}
        {showReviewSignal && (
          <span className="reel-caption__chip reel-caption__chip--review reel-meta-clamp">
            <ShieldAlert size={12} aria-hidden="true" />
            Review signal
          </span>
        )}
      </div>
      <h2 className="reel-caption__title reel-title-clamp">{title}</h2>
      {source && <span className="reel-caption__source reel-channel-clamp">{source}</span>}
      {visibleHashtags.length > 0 && (
        <div className="reel-caption__hashtags reel-hashtag-row" aria-label="Video hashtags">
          {visibleHashtags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      )}
      {description && (
        <p className="reel-caption__desc reel-caption-clamp" id={descriptionId} ref={descriptionRef}>
          {description}
        </p>
      )}
      {canExpand && (
        <button
          type="button"
          className="reel-caption__more"
          aria-expanded={expanded}
          aria-controls={descriptionId}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? 'less' : '...more'}
        </button>
      )}
      {placement === 'desktop' && signalHint && (
        <p className="reel-caption__signal reel-meta-clamp">{signalHint}</p>
      )}
      {placement === 'desktop' && isLiveVideo && (
        <p className="reel-caption__embed-note reel-meta-clamp">YouTube embed · curated by Chrysalis</p>
      )}
    </div>
  );
}
