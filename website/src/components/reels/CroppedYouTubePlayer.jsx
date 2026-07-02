import { useEffect, useRef, useState } from 'react';
import { Play, Pause } from 'lucide-react';

function postCommand(iframe, func) {
  const target = iframe?.contentWindow;
  if (!target) return;
  target.postMessage(JSON.stringify({ event: 'command', func, args: [] }), '*');
}

/**
 * CroppedYouTubePlayer — wraps a YouTube IFrame embed so it fills a vertical
 * 9:16 reel frame TikTok/Reels-style instead of letterboxing.
 *
 * Crop strategy ("cover", not "contain"):
 *   The iframe is sized to *cover* the portrait frame as 16:9 content using the
 *   frame's container-query units (cqw/cqh), then scaled up by --yt-crop-scale
 *   so its edges always overshoot the frame. That overshoot hides the 1px
 *   letterbox/pillarbox gaps that sub-pixel rounding otherwise leaves at the
 *   top/bottom edges. The frame's `overflow: hidden` clips the excess. Nothing
 *   is stretched — the iframe keeps a true 16:9 ratio and is only zoomed.
 *   Tune the zoom with the `--yt-crop-scale` CSS variable on `.reel-frame`.
 *
 * Tap-to-pause/play:
 *   A transparent layer over the iframe toggles playback via the IFrame
 *   postMessage API. No control icon is shown on first render (the card
 *   autoplays on scroll). A Play icon shows while paused; a Pause icon flashes
 *   briefly when you resume, then fades.
 *
 * YouTube limitation:
 *   With controls=0 the player's own chrome is hidden, but YouTube may still
 *   flash its native buffering spinner / branding *inside* the cross-origin
 *   iframe on slow connections. That internal UI cannot be removed from outside
 *   the iframe, so we don't attempt any hacks against it.
 */
export function CroppedYouTubePlayer({
  src,
  title,
  iframeRef,
  ...iframeProps
}) {
  // Callers remount this component with key={src} when a new card becomes
  // active, so state always starts fresh: playing (autoplay) with no overlay
  // icon on first render.
  const localRef = useRef(null);
  const ref = iframeRef || localRef;
  const [playing, setPlaying] = useState(true);
  const [flash, setFlash] = useState(false);
  const flashTimer = useRef(null);

  useEffect(() => () => clearTimeout(flashTimer.current), []);

  const toggle = () => {
    const iframe = ref.current;
    clearTimeout(flashTimer.current);
    if (playing) {
      postCommand(iframe, 'pauseVideo');
      setPlaying(false);
      setFlash(false);
    } else {
      postCommand(iframe, 'playVideo');
      setPlaying(true);
      setFlash(true);
      flashTimer.current = setTimeout(() => setFlash(false), 600);
    }
  };

  // Hidden on first render; the Play icon persists while paused, the Pause icon
  // only flashes briefly after the user resumes.
  const iconVisible = !playing || flash;

  return (
    <div className="cropped-yt">
      <iframe
        key={src}
        ref={ref}
        className="cropped-yt__frame"
        src={src}
        title={title}
        {...iframeProps}
      />
      <button
        type="button"
        className="cropped-yt__tap"
        onClick={toggle}
        aria-label={playing ? 'Pause video' : 'Play video'}
      >
        <span
          className={`cropped-yt__icon${iconVisible ? ' is-visible' : ''}`}
          aria-hidden="true"
        >
          {playing
            ? <Pause size={30} fill="currentColor" />
            : <Play size={30} fill="currentColor" />}
        </span>
      </button>
    </div>
  );
}
