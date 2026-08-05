function extractYouTubeVideoId(value) {
  const raw = String(value || '').trim();
  if (!raw) return null;
  if (/^[a-zA-Z0-9_-]{11}$/.test(raw)) return raw;

  try {
    const url = new URL(raw);
    const host = url.hostname.replace(/^www\./, '');
    if (host === 'youtu.be') return url.pathname.split('/').filter(Boolean)[0] || null;
    if (!host.endsWith('youtube.com') && !host.endsWith('youtube-nocookie.com')) return null;
    if (url.pathname.startsWith('/embed/')) return url.pathname.split('/')[2] || null;
    if (url.pathname.startsWith('/shorts/')) return url.pathname.split('/')[2] || null;
    return url.searchParams.get('v');
  } catch {
    return null;
  }
}

export function buildYouTubeEmbedUrl(input, {
  autoplay = true,
  muted = false,
  controls = false,
  enableJsApi = true,
  origin,
  startSeconds = 0,
} = {}) {
  if (!input) return null;
  const videoId = extractYouTubeVideoId(input);
  const baseUrl = videoId
    ? `https://www.youtube-nocookie.com/embed/${videoId}`
    : String(input);

  try {
    const url = new URL(baseUrl);
    if (autoplay) url.searchParams.set('autoplay', '1');
    url.searchParams.set('mute', muted ? '1' : '0');
    url.searchParams.set('playsinline', '1');
    url.searchParams.set('controls', controls ? '1' : '0');
    url.searchParams.set('rel', '0');
    url.searchParams.set('modestbranding', '1');
    if (enableJsApi) url.searchParams.set('enablejsapi', '1');
    if (startSeconds !== null && startSeconds !== undefined) {
      url.searchParams.set('start', String(Math.max(0, Number(startSeconds) || 0)));
    }
    if (origin) url.searchParams.set('origin', origin);
    return url.toString();
  } catch {
    return null;
  }
}
