function timestampMs(value) {
  if (typeof value !== 'string' || !value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function nonNegativeSeconds(value) {
  return Number.isFinite(value) && value >= 0 ? value : null;
}

export function calculateServerClockOffsetMs(serverTimestamp, clientNowMs = Date.now()) {
  const serverMs = timestampMs(serverTimestamp);
  if (serverMs === null || !Number.isFinite(clientNowMs)) return null;
  return serverMs - clientNowMs;
}

export function createServerTimeReference({
  serverTimestamp,
  endsAt,
  remainingSeconds,
  clientNowMs = Date.now(),
} = {}) {
  const offsetMs = calculateServerClockOffsetMs(serverTimestamp, clientNowMs);
  const endMs = timestampMs(endsAt);
  const anchoredRemainingSeconds = nonNegativeSeconds(remainingSeconds);

  if (offsetMs === null && endMs === null && anchoredRemainingSeconds === null) return null;

  return Object.freeze({
    offsetMs,
    endMs,
    anchoredRemainingSeconds,
    anchoredAtClientMs: Number.isFinite(clientNowMs) ? clientNowMs : Date.now(),
  });
}

export function remainingSecondsAt(reference, clientNowMs = Date.now()) {
  if (!reference || !Number.isFinite(clientNowMs)) return null;

  if (Number.isFinite(reference.endMs) && Number.isFinite(reference.offsetMs)) {
    const approximateServerNow = clientNowMs + reference.offsetMs;
    return Math.max(0, Math.ceil((reference.endMs - approximateServerNow) / 1_000));
  }

  if (Number.isFinite(reference.anchoredRemainingSeconds)
    && Number.isFinite(reference.anchoredAtClientMs)) {
    const elapsedSeconds = Math.max(0, (clientNowMs - reference.anchoredAtClientMs) / 1_000);
    return Math.max(0, Math.ceil(reference.anchoredRemainingSeconds - elapsedSeconds));
  }

  return null;
}

export function formatCountdown(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '--:--';
  const wholeSeconds = Math.ceil(seconds);
  const hours = Math.floor(wholeSeconds / 3_600);
  const minutes = Math.floor((wholeSeconds % 3_600) / 60);
  const remainder = wholeSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
  }
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

export function durationMinutes(seconds) {
  return Number.isFinite(seconds) && seconds >= 0 ? Math.ceil(seconds / 60) : null;
}
