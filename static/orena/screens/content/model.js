/* Content Detail (design route `detail`, frame 05): pure data mapping, DOM-free so
   scripts/test_orena_screen_content.mjs can test it without a browser.

   A content item's route id is shared by Discover, Today, Content Detail, My Library and
   Search: "<kind>:<id>", kind in article (published Reading corpus article), book (shared
   Reading library book; a chapter is "book:<bookId>:<chapterId>"), media (curated or imported
   Listening lesson / media object id, as the Listening API names it), upload (learner's own
   uploaded media id), text (learner-imported text kept in device memory). A vocabulary
   collection is a different route ("#/collection/:id") and never reaches this screen. */

export const KINDS = Object.freeze(['article', 'book', 'media', 'upload', 'text']);

/* "article:abc" -> {kind:'article', id:'abc'}; "book:b1:c2" -> {kind:'book', id:'b1',
   chapterId:'c2'}; an id this screen does not recognise comes back with kind:'' so the caller
   can fail honestly (the router's own load-error path) rather than guess. */
export function parseContentId(raw) {
  const value = String(raw || '');
  const first = value.indexOf(':');
  if (first === -1) return { kind: '', id: '' };
  const kind = value.slice(0, first);
  const rest = value.slice(first + 1);
  if (!KINDS.includes(kind) || !rest) return { kind: '', id: '' };
  if (kind === 'book') {
    const second = rest.indexOf(':');
    if (second === -1) return { kind, id: rest, chapterId: '' };
    return { kind, id: rest.slice(0, second), chapterId: rest.slice(second + 1) };
  }
  return { kind, id: rest };
}

/* The inverse: the route id for a kind+id pair, e.g. for a related item or a Reader target. */
export function contentIdFor(kind, id) {
  return `${kind}:${id}`;
}

/* Rule 40: a duration the backend did not measure is absent, never a fabricated number. Real
   zero (an actual 0-length record) is still a real number and is kept. `unitSeconds` divides a
   millisecond duration down to seconds first. */
export function minutesFrom(value, { unitMs = false } = {}) {
  if (value == null) return null;
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  const total = unitMs ? seconds / 1000 : seconds;
  if (total === 0) return 0;
  return Math.max(1, Math.round(total / 60));
}

/* A transcript timestamp, "0:44" - null when the value is not a real number (rule 40: no
   fabricated "0:00"). */
export function mmss(ms) {
  if (ms == null) return null;
  const value = Number(ms);
  if (!Number.isFinite(value) || value < 0) return null;
  const totalSeconds = Math.floor(value / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

/* Join the non-empty parts of a meta line ("source · level · duration") without stray
   separators when a part is missing - never invent a placeholder for a missing part. */
export function metaLine(parts, sep = ' · ') {
  return parts.filter((part) => part != null && part !== '').join(sep);
}

/* The server-side "kind" `/api/library/items` understands for this content kind, or null when
   the content is device-memory-only (a learner's own imported text has no server kind to keep
   it under - it is kept via product/memory.js's own kept[] instead). */
export function libraryKindFor(kind) {
  if (kind === 'article') return 'reading';
  if (kind === 'book') return 'book';
  if (kind === 'media' || kind === 'upload') return 'listening';
  return null;
}

/* Whether this kind opens into the Reader (an id-carrying text source) or the Listening
   workspace (a bare media id) - the harness's own routing rule, not the prototype script's
   demo-content branching (which is not behaviour to copy). */
export function primaryDestination(kind) {
  if (kind === 'article' || kind === 'book' || kind === 'text') return 'reader';
  if (kind === 'media' || kind === 'upload') return 'listening';
  return '';
}

/* The learner's own device-memory continuation entry for this content id, reduced to what the
   hero's progress row needs. `started` is true only when a real percent exists - an entry with
   a position but no measured percent (rule 40) shows no progress row rather than an invented
   bar. */
export function placeFor(continuation, id) {
  const entry = Array.isArray(continuation) ? continuation.find((item) => item?.id === id) : null;
  const within = entry?.place?.within;
  if (!entry || !Number.isFinite(within)) return { started: false, percent: 0 };
  return { started: true, percent: Math.max(0, Math.min(100, Math.round(within))) };
}

/* Start time (ms) of each transcript line, by the segment id a media place carries (X-11). */
export function segmentStarts(payload) {
  const out = {};
  for (const segment of payload?.transcript?.segments || []) {
    const start = Number(segment?.start_ms);
    if (segment?.segment_id && segment.start_ms != null && Number.isFinite(start) && start >= 0) out[segment.segment_id] = start;
  }
  return out;
}

/* A media item's saved place. Media places carry the line the learner was on (`segment`), not a
   percent, so a place with a line that is in this transcript resumes at that line's start - the
   same entry Today calls "Continue". `started` is true for any saved place (the room reopens
   it); `atMs` / `at` only when the line is found; `percent` only when the duration is known
   (rule 40: nothing is invented). */
export function mediaPlaceFor(continuation, id, starts, durationMs) {
  const entry = Array.isArray(continuation) ? continuation.find((item) => item?.id === id) : null;
  if (!entry) return { started: false, atMs: null, at: '', percent: null };
  const atMs = starts && Object.hasOwn(starts, entry.segment) ? starts[entry.segment] : null;
  const duration = Number(durationMs);
  const percent = atMs != null && Number.isFinite(duration) && duration > 0
    ? Math.max(0, Math.min(100, Math.round((atMs / duration) * 100)))
    : null;
  return { started: true, atMs, at: atMs == null ? '' : mmss(atMs), percent };
}

/* An article's list/detail JSON -> this screen's own fields. `desc` is the article's own
   description metadata when an administrator gave one (D-130): the block is hidden without it, and
   the first lines of the body are never shown as a description. */
export function normalizeArticle(article) {
  return {
    title: String(article?.title || ''),
    // languages-5 / finding A: the article's own field (reading_content_repository.py's
    // `_article` projection), not the learner's current active learning language.
    language: String(article?.language || ''),
    source: String(article?.attribution?.author || ''),
    level: String(article?.level || ''),
    minutes: minutesFrom(article?.reading_time_seconds),
    topic: String(article?.topic || ''),
    desc: String(article?.description || article?.summary || '').trim(),
    image: '',
  };
}

export function normalizeBook(book) {
  return {
    title: String(book?.title || ''),
    // languages-5 / finding A: `learning_language` (writing_coach/reading_library_api.py
    // `_with_reading_time`) - a book's own field, named differently from an article's `language`.
    language: String(book?.learning_language || ''),
    source: String(book?.author || ''),
    level: '',
    minutes: null,
    desc: String(book?.description || ''),
    image: book?.cover_asset_key ? `url("/api/reading/library/books/${encodeURIComponent(book.id)}/cover")` : '',
  };
}

/* One shape for both a curated/admin-imported Listening lesson (`GET
   /api/listening/library/{id}`, which carries `catalog`) and a learner's own upload/import
   (`GET /api/media/my/{id}`, which does not) - the acquisition envelope (`asset`, `transcript`,
   `playback`) is the same either way; `catalog` only adds what a curated lesson knows and an
   upload genuinely does not (level, topic, a written description). */
export function normalizeMedia(payload) {
  const catalog = payload?.catalog || null;
  const asset = payload?.asset || {};
  const segments = payload?.transcript?.segments || [];
  return {
    title: String(catalog?.title || asset.title || ''),
    // languages-5 / finding A: `catalog.language` (writing_coach/listening_api.py
    // `stored_media_metadata`) for a curated/shared lesson, else the asset's own
    // `source_language` (`_stored_asset`) for a learner's own upload - the same field name
    // difference `normalizeArticle`/`normalizeBook` already carry.
    language: String(catalog?.language || asset.source_language || ''),
    source: String(catalog?.source?.creator || asset.source_provider || ''),
    level: String(catalog?.level || ''),
    minutes: minutesFrom(catalog?.duration_ms ?? asset.duration_ms, { unitMs: true }),
    topic: String(catalog?.topic || ''),
    desc: String(catalog?.description || ''),
    image: asset.thumbnail_url ? `url("${asset.thumbnail_url}")` : catalog?.poster_url ? `url("${catalog.poster_url}")` : '',
    playbackKind: String(payload?.playback?.kind || ''),
    transcriptOrigin: String(payload?.transcript_origin || 'none'),
    segments: segments.map((segment) => ({ time: mmss(segment.start_ms), text: String(segment.original_text || '') })).filter((segment) => segment.time && segment.text),
  };
}

/* A learner's own imported text (product/memory.js's `imports[]`) - device memory only, no
   level/duration/source the app can honestly measure. */
export function normalizeText(record) {
  const text = String(record?.text || '');
  return {
    title: String(record?.title || ''),
    source: '',
    level: '',
    minutes: null,
    desc: text.length > 320 ? `${text.slice(0, 320).trim()}…` : text,
    image: '',
  };
}

/* Up to `limit` items from a raw listing, mapped by `map`, with the current item excluded (by
   the raw item's own id/lesson_id, before `map` renames it to a content route id) and any item
   `map` could not honestly build (no title) dropped rather than shown blank. */
export function pickRelated(items, { excludeId, map, limit = 3, score = null }) {
  const list = Array.isArray(items) ? items : [];
  const out = [];
  for (const [order, raw] of list.entries()) {
    const rawId = String(raw?.id ?? raw?.lesson_id ?? '');
    if (!rawId || rawId === excludeId) continue;
    // Related means related (LEX-075): with a `score`, an item that shares nothing with the open one is not
    // offered, and the closest come first; without one the caller has no relatedness signal and gets the list.
    const points = score ? Number(score(raw)) || 0 : 1;
    if (score && points <= 0) continue;
    const mapped = map(raw);
    if (mapped && mapped.title) out.push({ mapped, points, order });
  }
  out.sort((a, b) => b.points - a.points || a.order - b.order);
  return out.slice(0, limit).map((entry) => entry.mapped);
}

/* How close a catalogue item is to the open one by the fields the catalogue really has: the same topic counts
   most, the same level next. A field the open item does not have cannot relate anything. */
export function relatednessScore(current, candidate) {
  const norm = (value) => String(value || '').trim().toLowerCase();
  let points = 0;
  if (norm(current?.topic) && norm(current.topic) === norm(candidate?.topic)) points += 2;
  if (norm(current?.level) && norm(current.level) === norm(candidate?.level)) points += 1;
  if (norm(current?.source) && norm(current.source) === norm(candidate?.author || candidate?.source?.creator)) points += 2;
  return points;
}

/* The stored media id inside a content route's `upload` id. Discover and Search open a device
   media import as "upload:" + its memory id, and an uploaded file's memory id is itself
   "upload:<media id>" - the media API wants the bare id. */
export function uploadMediaId(id) {
  const value = String(id || '');
  return value.startsWith('upload:') ? value.slice(7) : value;
}
