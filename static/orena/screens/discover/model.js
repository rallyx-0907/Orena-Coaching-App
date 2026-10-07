/* Discover's data mapping and filtering (Design Contract rules 40, 42; frame 04-Discover.html).
   DOM-free on purpose (scripts/test_orena_screen_discover.mjs imports only this file): every
   function here takes plain data in and returns plain data out.

   An "entry" is one piece of content normalised from whichever source it came from, before any
   copy is applied. `presentCard(entry, t)` is the only place an entry becomes the props
   kit/components.js#mediaCard() needs - `t` is copy/discover.js's translate function, passed in
   rather than imported, so this stays a plain function of its two arguments.

   The six kinds a real Orena backend can hand Discover today: `article` (published Reading
   corpus), `book` (shared Reading library), `media` (curated or learner-imported Listening
   library item, as /api/listening/library already merges the two - stored_media_metadata()),
   `collection` (curated vocabulary collection), and the two device-memory kinds `text` and
   `upload` (product/memory.js's `imports`/`mediaImports`). A field the source does not measure is
   left out of the entry rather than invented (rule 40) - `presentCard` then omits that part of the
   card entirely, exactly as kit/components.js#mediaCard() already does for an absent parameter. */

import { duration } from '../../product/duration.js';
import { COVER_VISUALS } from '../../kit/cover-visuals.js';

export const TABS = Object.freeze(['all', 'read', 'listen', 'collections', 'imported']);

const TAB_OF_KIND = Object.freeze({
  article: 'read',
  book: 'read',
  media: 'listen',
  collection: 'collections',
  text: 'imported',
  upload: 'imported',
});

/* Where a learner left off, from device memory's continuation shelf (product/memory.js), as a
   whole percent. `idPrefix` matches a book's chapters ("book:<bookId>:"), which is the only kind
   whose continuation id is not the content id itself. */
export function progressFromContinuation(continuation, id, { idPrefix = '' } = {}) {
  const list = Array.isArray(continuation) ? continuation : [];
  const entry = idPrefix
    ? list.find((item) => String(item?.id || '').startsWith(idPrefix))
    : list.find((item) => String(item?.id || '') === id);
  const index = Number(entry?.place?.index) || 0;
  const total = Number(entry?.place?.total) || 0;
  if (!entry || index < 1 || total < 1) return null;
  return Math.max(1, Math.min(100, Math.round((index / total) * 100)));
}

/* GET /api/reading/articles item -> entry. No image field exists for an article today (a real
   backend gap, not an oversight) and no source/publication name, so both are left out. */
export function entryFromArticle(item, continuation) {
  const id = `article:${item.id}`;
  return {
    id,
    kind: 'article',
    title: item.title || '',
    // languages-5 / finding A: the article's own language field (reading_content_repository.py's
    // `_learner_row`), not the learner's active learning language - an article's language never
    // changes with a later switch, and this is the value the data itself declares.
    language: item.language || '',
    author: '',
    level: item.level || '',
    topic: item.topic || '',
    readingSeconds: Number.isFinite(item.reading_time_seconds) ? item.reading_time_seconds : null,
    image: '',
    started: progressFromContinuation(continuation, id) != null,
    progressPct: progressFromContinuation(continuation, id),
  };
}

/* GET /api/reading/library/books item -> entry. A chapter's own continuation id is
   "book:<bookId>:<chapterId>" (a book has no single continuation row of its own), so progress is
   read by prefix. */
export function entryFromBook(item, continuation, coverUrl) {
  const id = `book:${item.id}`;
  return {
    id,
    kind: 'book',
    title: item.title || '',
    // languages-5 / finding A: `learning_language` (writing_coach/reading_library_api.py
    // `_with_reading_time`) - the book's own field, one API field name different from an
    // article's `language`, both mapped to the same `entry.language`.
    language: item.learning_language || '',
    author: item.author || '',
    level: '',
    topic: '',
    chapterCount: Number.isFinite(item.chapter_count) ? item.chapter_count : null,
    image: item.cover_asset_key ? `url(${coverUrl})` : '',
    started: progressFromContinuation(continuation, id, { idPrefix: `${id}:` }) != null,
    progressPct: progressFromContinuation(continuation, id, { idPrefix: `${id}:` }),
  };
}

/* GET /api/listening/library item (stored_media_metadata()/_library_item() shape) -> entry. Both
   the curated catalogue and a learner's shared import arrive through this one list, already
   merged by the server - Discover draws them identically, as the source does. */
export function entryFromMedia(item, continuation) {
  const rawId = item.lesson_id || item.media_object_id || '';
  const id = `media:${rawId}`;
  const poster = typeof item.poster_url === 'string' && /^https:\/\//.test(item.poster_url) ? item.poster_url : '';
  return {
    id,
    kind: 'media',
    availableModes: Array.isArray(item.available_modes) ? item.available_modes : [],
    comprehensionCount: Number(item.comprehension_count) || 0,
    mediaType: item.media_type === 'video' ? 'video' : 'audio',
    title: item.title || '',
    // languages-5 / finding A: `language` (writing_coach/listening_api.py `stored_media_metadata` /
    // `catalog_lessons`) - the item's own field, real for both the curated catalogue and a
    // learner's shared import.
    language: item.language || '',
    author: item.source_label || '',
    level: item.level || item.estimated_level || '',
    topic: item.topic || '',
    clipMs: Number.isFinite(item.duration_ms) && item.duration_ms > 0 ? item.duration_ms : null,
    image: poster ? `url(${poster})` : '',
    started: progressFromContinuation(continuation, id) != null,
    progressPct: progressFromContinuation(continuation, id),
  };
}

/* GET /api/vocabulary/library/collections item -> entry. Progress is the collection's own
   learned/total count, not the continuation shelf (a collection is learned, not read). */
export function entryFromCollection(item) {
  const id = `collection:${item.id}`;
  const total = Number(item.item_count) || 0;
  const learned = Number(item.progress?.learned_count) || 0;
  return {
    id,
    kind: 'collection',
    title: item.title || '',
    // languages-5 / finding A: `language_code` (writing_coach/vocabulary_library.py `_summary`) -
    // the collection's own field.
    language: item.language_code || '',
    author: '',
    level: item.level_range || item.level || '',
    topic: item.topic || '',
    itemCount: total || null,
    image: '',
    started: total > 0 && learned > 0,
    progressPct: total > 0 && learned > 0 ? Math.max(1, Math.min(100, Math.round((learned / total) * 100))) : null,
    progressLearned: learned,
    progressTotal: total,
  };
}

/* product/memory.js `imports` (device-kept text) -> entry. Its own id already is "text:<uuid>",
   the exact shape Discover's content-id contract wants, so it travels unchanged. */
export function entryFromTextImport(item) {
  return {
    id: item.id,
    kind: 'text',
    title: item.title || '',
    author: '',
    level: '',
    topic: '',
    image: '',
    started: false,
    progressPct: null,
  };
}

/* product/memory.js `mediaImports` (a learner's own pasted link or uploaded file) -> entry. Its
   own id already carries a "url:"/"upload:" prefix from that module's own membership scheme
   (distinct from, and older than, this screen's content-id contract) - `upload:${item.id}` keeps
   both readable: the outer kind a Content Detail route parses, the inner id the media API needs
   verbatim. Recorded as a deliberate choice, not a silent guess (SCRATCH/reports/discover.md). */
export function entryFromMediaImport(item, continuation) {
  const id = `upload:${item.id}`;
  const poster = typeof item.thumbnail_url === 'string' && /^https:\/\// .test(item.thumbnail_url) ? item.thumbnail_url : '';
  return {
    id,
    kind: 'upload',
    title: item.title || '',
    author: item.provider || '',
    level: '',
    topic: '',
    clipMs: Number.isFinite(item.duration_ms) && item.duration_ms > 0 ? item.duration_ms : null,
    image: poster ? `url(${poster})` : '',
    started: progressFromContinuation(continuation, id) != null,
    progressPct: progressFromContinuation(continuation, id),
  };
}

/* Topics (P-06). A content tag is open metadata and holds internal and test values ("sandbox-test"), so a
   topic reaches a learner only when it names one of the topics below, written out in the learner's language
   (copy.js `topic_<key>`). Any other tag is left out of the Filter Sheet and off the cards - an explicit rule,
   not a list of bad strings. The vocabulary is Discover's own until the content model carries one
   (docs/project/UI_BACKEND_GAPS.md). A tag's key is its lower-case words joined by "_". */
export const KNOWN_TOPICS = Object.freeze([
  'daily_life', 'travel', 'conversations', 'culture', 'technology', 'food', 'work', 'health', 'education', 'science',
  'nature', 'society', 'sports', 'entertainment', 'history', 'business', 'news', 'relationships', 'environment', 'shopping',
]);

export function topicKey(topic) {
  const key = String(topic || '').trim().toLowerCase().replace(/[\s_-]+/g, '_');
  return KNOWN_TOPICS.includes(key) ? key : '';
}

export function topicLabel(topic, t) {
  const key = topicKey(topic);
  return key ? t(`topic_${key}`) : '';
}

/* The three Filter Sheet groups, derived from whatever is actually loaded (E1 "Data the backend
   must provide": a real content taxonomy, not the old fixed FILTERS constant) rather than a
   catalogue Discover does not own. Each option's `value` is what a card is matched against. */
export function filterOptions(entries) {
  const levels = new Set();
  const topics = new Set();
  const kinds = new Set();
  for (const entry of entries) {
    if (entry.level) levels.add(entry.level);
    if (topicKey(entry.topic)) topics.add(entry.topic);
    kinds.add(entry.kind === 'media' ? `media-${entry.mediaType}` : entry.kind);
  }
  const sortAlpha = (set) => [...set].sort((a, b) => a.localeCompare(b));
  return {
    level: sortAlpha(levels),
    topic: sortAlpha(topics),
    type: sortAlpha(kinds),
  };
}

function typeOf(entry) {
  return entry.kind === 'media' ? `media-${entry.mediaType}` : entry.kind;
}

const TYPE_LABEL_KEY = Object.freeze({
  article: 'typeArticle',
  book: 'typeBook',
  'media-video': 'typeVideo',
  'media-audio': 'typeAudio',
  collection: 'typeCollection',
  text: 'typeText',
  upload: 'typeUpload',
});

/* Which tile a card without a cover draws, by its content type (kit COVER_VISUALS). */
const COVER_OF_TYPE = Object.freeze({
  article: 'read', book: 'read', 'media-video': 'watch', 'media-audio': 'listen', collection: 'collection', text: 'write', upload: 'upload',
});

/* The Content-type filter group's chip label for one derived type value, and `presentCard`'s own
   type pill - one map, so the sheet's chips and the grid's pills never drift apart. */
export function typeLabel(value, t) {
  return TYPE_LABEL_KEY[value] ? t(TYPE_LABEL_KEY[value]) : value;
}

/* A card matches when every group with at least one selected option includes this card's value
   for that group (AND across groups, OR within a group - the sheet's own multi-select). */
export function matchesFilters(entry, filters) {
  const level = filters?.level;
  const topic = filters?.topic;
  const type = filters?.type;
  if (level && level.size && !level.has(entry.level)) return false;
  if (topic && topic.size && !topic.has(entry.topic)) return false;
  if (type && type.size && !type.has(typeOf(entry))) return false;
  return true;
}

export function hasAnyFilter(filters) {
  return Boolean(filters?.level?.size || filters?.topic?.size || filters?.type?.size);
}

export function filterCount(filters) {
  return (filters?.level?.size || 0) + (filters?.topic?.size || 0) + (filters?.type?.size || 0);
}

/* The tab + search query + filter sheet, all three live and all three combined (D2 "Bindings":
   `resultCount` = Discover's `filtered.length`, computed continuously from every input at once). */
export function visibleEntries(entries, { tab = 'all', query = '', filters = null } = {}) {
  const q = String(query || '').trim().toLowerCase();
  return entries
    .filter((entry) => tab === 'all' || TAB_OF_KIND[entry.kind] === tab)
    .filter((entry) => matchesFilters(entry, filters))
    .filter((entry) => !q || `${entry.title} ${entry.author}`.toLowerCase().includes(q));
}

/* entry -> kit/components.js#mediaCard() props. `t` is copy/discover.js's translate function
   (a plain function of (key, params) - this stays pure, nothing here touches the DOM). Any count
   this screen shows (minutes, chapters, words) comes from a real field on the entry; an entry with
   none of them draws no duration pill, matching mediaCard()'s own optional-parameter contract. */
export function presentCard(entry, t) {
  let durationLabel = '';
  if (entry.kind === 'article' && entry.readingSeconds != null) {
    const n = Math.max(1, Math.round(entry.readingSeconds / 60));
    durationLabel = t('durationMinRead', { n });
  } else if (entry.kind === 'book' && entry.chapterCount != null) {
    durationLabel = t.plural('durationChapters', entry.chapterCount);
  } else if (entry.kind === 'collection' && entry.itemCount != null) {
    /* The design's own live card-mapping function (orena-script.js:1163) is generic across every
       kind - `hasDur: !!it.dur, duration: it.dur` - and its own sample data gives a collection
       item a `dur` field ("24 items") alongside its `source` meta field ("24 words"): the pinned
       design draws the corner count badge on a Collection card too, the same real count shown
       twice in two units (P1, discover.review.md). */
    durationLabel = t.plural('durationItems', entry.itemCount);
  } else if (entry.clipMs != null) {
    durationLabel = duration(entry.clipMs);
  }
  let meta = entry.author || '';
  if (entry.kind === 'collection' && entry.itemCount != null) meta = t.plural('collectionWordCount', entry.itemCount);
  const tags = [];
  if (entry.level) tags.push({ label: entry.level, tone: 'accent' });
  // N-35: only a topic the vocabulary above names is shown, in the interface language (P-06).
  if (topicKey(entry.topic)) tags.push({ label: topicLabel(entry.topic, t) });
  if (entry.started) {
    const label =
      entry.kind === 'collection' && entry.progressLearned != null
        ? t('progressLearnedOf', { learned: entry.progressLearned, total: entry.progressTotal })
        : t('progressPercent', { pct: entry.progressPct });
    tags.push({ label, tone: 'good' });
  }
  return {
    image: entry.image || '',
    cover: COVER_VISUALS[COVER_OF_TYPE[typeOf(entry)]] || null,
    kind: typeLabel(typeOf(entry), t),
    duration: durationLabel,
    progress: entry.started ? entry.progressPct : null,
    title: entry.title,
    // languages-5 / finding A: the language the entry's own source declared, or '' for the two
    // device-memory kinds (a learner's own pasted text/media import), which carry no such field -
    // left unmarked rather than guessed at.
    titleLang: entry.language || '',
    meta,
    tags,
  };
}

/* Every kind opens Content Detail by its content id (`ctx.href('content', { id })`), except a
   collection, which has its own detail route keyed by the raw id alone (shell/routes.js's
   `collection/:id`) - the task's own routing note for this shared id contract. Takes `ctx.href`
   rather than building the hash itself, so screen.js stays the one place that knows a route
   path. */
export function hrefFor(entry, href) {
  return entry.kind === 'collection'
    ? href('collection', { id: entry.id.slice('collection:'.length) })
    : href('content', { id: entry.id });
}

// Capability admission comes from the shared server library, never a device import placeholder.
export function practiceCandidates(entries, intent = 'pronunciation') {
  return entries.filter(entry => entry.kind === 'media' && (intent === 'listening' ? entry.comprehensionCount > 0 : entry.availableModes?.includes(intent === 'dictation' ? 'dictation' : 'shadowing')));
}

export function practiceHref(entry, href, { source = '', segment = '', intent = 'pronunciation' } = {}) {
  if (entry.speakingId) return href('speak', {id:entry.speakingId}, {});
  const id = entry.id.slice('media:'.length);
  return href(intent === 'dictation' ? 'dictation' : intent === 'listening' ? 'listenQuestions' : 'shadow', { id }, (source === id || entry.sourceAliases?.includes(source)) && segment ? { segment } : {});
}

export function preparedMediaEntry(itemId, payload, source, language, continuation) {
  if (!source?.hasModelAudio || source.language !== language || (payload.asset?.processing_state && payload.asset.processing_state !== 'ready')) return null;
  return {
    ...entryFromMedia({
      ...payload.catalog, lesson_id:payload.catalog?.lesson_id || itemId, title:source.title, language:source.language,
      media_type:payload.playback.kind === 'audio' ? 'audio' : 'video',
      duration_ms:payload.asset.duration_ms, poster_url:payload.asset.thumbnail_url, available_modes:['shadowing','dictation'],
    }, continuation),
    sourceAliases:[itemId],
  };
}
