/** `stamp()`: media positions read as M:SS, never as raw milliseconds. */
export function stamp(ms: number): string {
  const value = Number.isFinite(ms) ? Math.max(0, ms) : 0;
  return `${Math.floor(value / 60000)}:${String(Math.floor(value / 1000) % 60).padStart(2, '0')}`;
}

/** The rights-reviewed Commons origins, matching media-player.js. */
const COMMONS_MEDIA_HOSTS = ['commons.wikimedia.org', 'upload.wikimedia.org'];
/**
 * Posters come from whichever provider publishes the media, so this list is
 * wider than the playback one: a YouTube lesson's thumbnail is on YouTube's
 * image CDN. listening_catalog.py checks poster host against the source's own
 * provider; this is defence in depth against an arbitrary origin.
 */
const POSTER_HOSTS = [...COMMONS_MEDIA_HOSTS, 'thumb.wikimedia.org', 'i.ytimg.com', 'img.youtube.com'];

/**
 * One reviewed-media URL policy, stated the same way on all three sides:
 * https, an exact allowlisted host, no credentials, no port. A regex over the
 * whole URL happened to reject credentials, but only by accident of shape;
 * saying the rule outright keeps the server, the web player and this adapter
 * from drifting into three slightly different answers.
 */
export function reviewedMediaUrl(
  value: string | undefined | null,
  hosts: readonly string[] = COMMONS_MEDIA_HOSTS,
): string | null {
  const raw = String(value || '');
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:' || url.username || url.password || url.port) return null;
    return hosts.includes(url.hostname) ? url.href : null;
  } catch {
    return null;
  }
}

/**
 * `playbackAvailable()`: Active and Shadowing are reconstruction and speaking
 * exercises against real audio, so they are only offered when the provider
 * actually gives us something playable. Follow works from the transcript alone.
 *
 * Curated `video` is a direct Commons file exactly as `audio` is, so it is
 * playable on the same terms. The web gained it first; native must agree, or
 * the same lesson is a real video on the web and "unavailable" on a phone.
 */
export function playbackAvailable(playback: {kind?: string; provider?: string; url?: string} | undefined): boolean {
  if (!playback) return false;
  return (playback.kind === 'embed' && playback.provider === 'youtube' && /^https:\/\/www\.youtube-nocookie\.com\/embed\/[A-Za-z0-9_-]{11}(?:[?].*)?$/.test(playback.url || ''))
    || (directMediaKind(playback) !== null);
}

/**
 * Which HTMLMediaElement-equivalent adapter a direct Commons file needs, or
 * null when this is not one. Both platforms decide with this single rule, so a
 * provider added to one cannot silently be missing from the other.
 */
export function directMediaKind(
  playback: {kind?: string; provider?: string; url?: string} | undefined,
): 'audio' | 'video' | null {
  if (!playback || playback.provider !== 'wikimedia-commons') return null;
  if (playback.kind !== 'audio' && playback.kind !== 'video') return null;
  return reviewedMediaUrl(playback.url) ? playback.kind : null;
}

/**
 * A poster decorates a player and must never become a way to load an image
 * from an arbitrary host, so it is held to the same origins as the media.
 * `posterUrl()` in media-player.js applies the identical rule.
 */
export function posterSource(poster: string | undefined | null): string | null {
  return reviewedMediaUrl(poster, POSTER_HOSTS);
}


/** listening.js's unit split: characters for zh, words elsewhere. */
export function listeningUnits(text: string, language: string): string[] {
  const value = String(text || '').normalize('NFKC').replace(/[\u2018\u2019\u02bc]/g, "'").replace(/[\u2010-\u2015\u2212]/g, '-').replace(/\s+/gu, ' ').trim();
  if (!value) return [];
  if (language === 'zh') return (value.match(/\p{Script=Han}|[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*/gu) || []).map((unit) => /^\p{Script=Han}$/u.test(unit) ? unit : unit.toLocaleLowerCase('en'));
  return value.toLocaleLowerCase('en').match(/[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*/gu) || [];
}

export const MAX_LISTENING_EVALUATION_UNITS = 500;
export const MAX_LISTENING_RECONSTRUCTION_CHARS = 2000;

export type TextMatch = {accuracy_percent: number; exact: boolean};

/**
 * The reconstruction comparison. It is a text match against this transcript --
 * listening.js says so on screen -- not a proficiency score, so it stays a
 * plain ordered-overlap ratio rather than anything that could read as an
 * assessment.
 */
export function textMatch(answer: string, expected: string, language: string): TextMatch {
  const left = listeningUnits(answer, language);
  const right = listeningUnits(expected, language);
  if (!right.length) return {accuracy_percent: 0, exact: false};
  let previous = Array.from({length: left.length + 1}, (_, index) => index);
  for (let row = 1; row <= right.length; row += 1) {
    const current = [row];
    for (let column = 1; column <= left.length; column += 1) {
      current[column] = Math.min(previous[column]! + 1, current[column - 1]! + 1, previous[column - 1]! + (right[row - 1] === left[column - 1] ? 0 : 1));
    }
    previous = current;
  }
  const distance = previous[left.length]!;
  const denominator = Math.max(right.length, left.length);
  return {accuracy_percent: Math.round(Math.max(0, Math.min(1, 1 - distance / denominator)) * 100), exact: distance === 0};
}

export type ReconstructionDiff = {status: 'correct' | 'missing' | 'wrong' | 'extra'; expected: string; actual: string};

export function reconstructionDiff(answer: string, expected: string, language: string): ReconstructionDiff[] {
  const actual = listeningUnits(answer, language);
  const canonical = listeningUnits(expected, language);
  const common = Array.from({length: canonical.length + 1}, () => Array(actual.length + 1).fill(0));
  for (let row = canonical.length - 1; row >= 0; row -= 1) for (let column = actual.length - 1; column >= 0; column -= 1) {
    common[row]![column] = canonical[row] === actual[column] ? common[row + 1]![column + 1]! + 1 : Math.max(common[row + 1]![column]!, common[row]![column + 1]!);
  }
  const raw: ReconstructionDiff[] = [];
  let row = 0, column = 0;
  while (row < canonical.length || column < actual.length) {
    if (row < canonical.length && column < actual.length && canonical[row] === actual[column]) { raw.push({status: 'correct', expected: canonical[row]!, actual: actual[column]!}); row += 1; column += 1; continue; }
    if (row < canonical.length && (column >= actual.length || common[row + 1]![column]! >= common[row]![column + 1]!)) { raw.push({status: 'missing', expected: canonical[row]!, actual: ''}); row += 1; continue; }
    raw.push({status: 'extra', expected: '', actual: actual[column]!}); column += 1;
  }
  const aligned: ReconstructionDiff[] = [];
  for (let index = 0; index < raw.length; index += 1) {
    const current = raw[index]!, next = raw[index + 1];
    if (next && current.status !== next.status && (current.status === 'missing' || current.status === 'extra') && (next.status === 'missing' || next.status === 'extra')) {
      const missing = current.status === 'missing' ? current : next;
      const extra = current.status === 'extra' ? current : next;
      aligned.push({status: 'wrong', expected: missing.expected, actual: extra.actual}); index += 1;
    } else aligned.push(current);
  }
  return aligned;
}

/** The segment that owns a media position, for follow-along selection. */
export function segmentAt(segments: readonly {segment_id: string; start_ms: number; end_ms: number}[], positionMs: number): string | null {
  const hit = segments.find((segment) => positionMs >= segment.start_ms && positionMs < segment.end_ms);
  return hit?.segment_id ?? null;
}
