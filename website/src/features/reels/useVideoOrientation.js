import { useState, useEffect } from 'react';

// Cache orientation per video id so each thumbnail is probed at most once.
const orientationCache = new Map();

/**
 * Best-effort video-orientation probe. Loads the video's maxres thumbnail
 * (1280×720 for true landscape videos) off-screen and compares its natural
 * dimensions. Returns 'landscape' | 'portrait' | null (while still unknown).
 *
 * Portrait is the safe default: if the thumbnail is missing or tall we keep the
 * current cover-fill behaviour, so vertical Shorts never regress — only clearly
 * landscape videos switch to the contained + blurred-backdrop layout.
 */
export function useVideoOrientation(youtubeId) {
  const [orientation, setOrientation] = useState(
    () => (youtubeId && orientationCache.get(youtubeId)) || null,
  );

  useEffect(() => {
    if (!youtubeId) {
      setOrientation(null);
      return undefined;
    }
    if (orientationCache.has(youtubeId)) {
      setOrientation(orientationCache.get(youtubeId));
      return undefined;
    }

    let cancelled = false;
    const settle = (value) => {
      if (cancelled) return;
      orientationCache.set(youtubeId, value);
      setOrientation(value);
    };

    const img = new Image();
    img.onload = () =>
      settle(img.naturalWidth > img.naturalHeight ? 'landscape' : 'portrait');
    img.onerror = () => settle('portrait'); // no maxres thumb → assume portrait
    img.src = `https://i.ytimg.com/vi/${youtubeId}/maxresdefault.jpg`;

    return () => {
      cancelled = true;
    };
  }, [youtubeId]);

  return orientation;
}
