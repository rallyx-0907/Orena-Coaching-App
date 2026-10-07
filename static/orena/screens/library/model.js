/* Pure, DOM-free data mapping for My Library (frame 12: Saved content, Saved language,
   Collections, Active use, Due Review - five tabs, per the live design script's own `LIBT` array
   in `orena-script.js`, not the "4" the pinned copy's compact export hinted; see `screen.js` for
   that correction and for `activeCards`, the one tab whose content is a fixed shortcut menu rather
   than a fetched row set, so it has no model.js function of its own).

   Every function here takes already-fetched API/device-memory data and returns the shape the
   screen paints - no fetch, no DOM, no copy lookup (labels are chosen by the caller, which has the
   translated strings; this module only says which label a row needs, by a stable key). */

import { placeFor } from '../content/model.js';
import { vocabularyMeaning } from '../../product/vocabulary-meaning.js';
import { buildQueue, cardMode, sourceLabelKey } from '../review/model.js';

/* ---- Content tab: reading + media entries from GET /api/collection?domains=reading,media ---- */

/* Which two domains this tab draws (the "Saved Content" section, ML1 §A) - not writing/speaking/
   grammar, which have no place in this frame's five states once "Active Use" is dropped (above). */
export const CONTENT_DOMAINS = ['reading', 'media'];

/* screens/content/model.js's own `parseContentId` recognises a content *kind* ('article', 'book',
   'media', 'upload', 'text'), never a `/api/collection` *domain* ('reading', 'media', 'writing',
   'grammar') - two different vocabularies for the same idea, and they are not the same string for
   every domain: a reading-domain entry is content-kind 'article'. Built locally (not imported from
   another surface's own `screens/content/`, out of this screen's ownership) so the Content tab's
   route id is always one `#/content/:id` actually parses, for both domains this tab ever shows
   (`CONTENT_DOMAINS` above - 'media' already matches its own kind name 1:1). */
const CONTENT_KIND_FOR_DOMAIN = { reading: 'article', media: 'media' };

export function contentRouteId(domain, id) {
  return `${CONTENT_KIND_FOR_DOMAIN[domain] || domain}:${id}`;
}

/* One collection entry -> one Content-tab row.

   `pct` is the learner's own place in it - the continuation record Content Detail reads (placeFor),
   keyed by the same content id - so My Library and the content's own page show the same progress
   (LEX-024). A content never opened has no place and shows 0%: this frame draws the bar
   unconditionally (rule 40: a metric not measured renders 0, never a guess). */
export function contentRows(entries = [], continuation = []) {
  return (entries || [])
    .filter((entry) => CONTENT_DOMAINS.includes(entry?.ref?.domain))
    .map((entry) => {
      const contentId = contentRouteId(entry.ref.domain, entry.ref.id);
      return {
        contentId,
        domain: entry.ref.domain,
        title: entry.title || '',
        source: entry.snippet || '',
        unavailable: entry.availability === 'unavailable',
        pct: placeFor(continuation, contentId).percent,
      };
    });
}

/* ---- Saved-Language tab: GET /api/library/vocabulary (paged) ---- */

/* A saved entry with a space in it was kept as a phrase/sentence, not a single word - a real,
   observable property of the string itself, not a guess. The backend has no third "highlight"
   kind (SCRATCH/inventory/C6 §2.1: this app's saved vocabulary is one table, `saved_words`), so
   the frame's three-way Words/Phrases/Highlights chip collapses to this one honest distinction. */
export function wordKindOf(word = '') {
  return /\s/.test(String(word).trim()) ? 'phrase' : 'word';
}

/* Never reviewed yet (`last_reviewed_at` empty) is what "NEW" means here - the same signal the
   review scheduler itself uses to tell a fresh card from one that has been graded at least once. */
export function isNewWord(item = {}) {
  return !String(item.last_reviewed_at || '').trim();
}

/* The mastery-bar meter's filled count. `review_stage` is the scheduler's own stage number; there
   is no ceiling documented beyond what the ladder needs, so it is clamped to the meter's own size
   rather than let a high stage overflow the four bars the frame draws. */
export function masteryFilled(item = {}, total = 4) {
  const stage = Number(item.review_stage) || 0;
  return Math.max(0, Math.min(total, Math.trunc(stage)));
}

/* The meaning line under a saved word: the word's sense in the learner's support language, then
   the learner's own note, then the sense in another language (product/vocabulary-meaning.js,
   D-124), and only then the sentence the word was met in. No language is named here. */
export function wordMeaning(item = {}, supportLanguage = 'en') {
  const meaning = vocabularyMeaning(item, supportLanguage)?.text;
  if (meaning) return meaning;
  // A phrase's source sentence is often the phrase itself: a line that only repeats the row says nothing (V-15).
  const fragment = String(item.source_fragment || '').trim();
  return fragment.toLowerCase() === String(item.word || '').trim().toLowerCase() ? '' : fragment;
}

/* The language of that meaning when it is the sense's meaning in another language (D-124). */
export function wordMeaningLanguage(item = {}, supportLanguage = 'en') {
  const meaning = vocabularyMeaning(item, supportLanguage);
  return meaning?.language && meaning.language !== String(supportLanguage || '').toLowerCase() ? meaning.language : '';
}

export function languageRows(items = [], supportLanguage = 'en') {
  return (items || []).map((item) => ({
    word: item.word || '',
    kind: wordKindOf(item.word),
    reading: String(item.phonetic || '').trim(),
    sub: wordMeaning(item, supportLanguage),
    subLanguage: wordMeaningLanguage(item, supportLanguage),
    isNew: isNewWord(item),
    filled: masteryFilled(item),
  }));
}

/* ---- Collections tab: GET /api/library/collections + GET /api/vocabulary/decks ----

   Two backend concepts share this one tab (SCRATCH/inventory/C6 §2.1's "three collection
   concepts", concepts B and C - decks and generic My Library collections; concept A, the curated
   catalogue, has its own Discover-reached screen and does not belong to a learner's own library).
   Neither carries a cover image, a level or a source string - only a title and a size - so the
   card renders with no artwork and a real item count where the frame's sample draws a level/
   source line (rule 40: show what is measured, in the drawn slot, rather than invent the fields
   the sample data happens to have). */
export function libraryCollectionRows(collections = []) {
  return (collections || []).map((row) => ({
    collectionId: `library:${row.id}`,
    title: row.title || '',
    size: Number(row.size) || 0,
  }));
}

export function deckRows(decks = []) {
  return (decks || []).map((deck) => ({
    collectionId: `deck:${deck.id}`,
    title: deck.title || '',
    size: Number(deck.size) || 0,
  }));
}

/* Published curated collections for the content language (GET /api/vocabulary/library/collections, the same list
   Discover draws; HV-5 A, V-13). They open the collection's own screen. */
export function curatedRows(items = []) {
  return (items || []).filter((item) => item && item.id).map((item) => ({
    collectionId: `curated:${item.id}`,
    title: item.title || '',
    size: Number(item.item_count) || 0,
  }));
}

export function collectionsAndDecks(collections = [], decks = [], curated = []) {
  return [...curatedRows(curated), ...libraryCollectionRows(collections), ...deckRows(decks)];
}

/* ---- Due-Review tab: GET /api/library/review-queue ----

   The route answers `{pinned, pinned_count, due_count, first_due_word, total}` - marked items of
   any kind, and a count (never the words themselves) of what the SRS schedule says is due. There
   is no persisted distinction between a saved word and a saved phrase (both are one `saved_words`
   row - see `wordKindOf` above) and no persisted duration estimate for a session, so `duePhrases`
   and `dueMin` are the rule-40 zero the backend has no measure for; `dueSource` is the pinned
   count, the closest real number to "marked from a source, ready to revisit". `dueMin` is kept
   here as the documented gap, but screen.js's "Start review" CTA no longer states a minute figure
   built from it - showing "~0 min" would state a measurement nobody made, worse than the honest
   zero this field otherwise stands for. */
export function dueStats(queue = {}) {
  const dueWords = Number(queue.due_count) || 0;
  const dueSource = Number(queue.pinned_count) || 0;
  return {
    dueCount: Number(queue.total) || dueWords + dueSource,
    dueWords,
    duePhrases: 0,
    dueSource,
    dueMin: 0,
  };
}

/* A fallback label key for a pinned row with no title of its own (only a word-kind pinned item
   carries readable text; the rest are shown by their kind, a real fact about the row, not a
   placeholder).

   `item.kind` here is a `LibraryItem.kind` (`writing_coach/persistence/models.py`'s
   `LIBRARY_KINDS = ('word', 'grammar', 'reading', 'listening', 'note', 'writing', 'speaking',
   'book')`), never a `/api/collection` *domain* - that is a different, sibling vocabulary
   `contentRows()` above reads instead (`entry.ref.domain`, which does use `'media'`). The map key
   is `listening`, the real value the backend writes for a listening pin (confirmed live via
   `POST /api/library/items {kind:'listening', ...}` -> `GET /api/library/review-queue`'s
   `pinned[].kind`, `scripts/fixtures/api/library_review_queue_pinned_listening.json`, and matched
   at both write sites that produce it: `screens/content/model.js`'s `libraryKindFor` and
   `ui/collection.js`'s `ITEM_KIND`). `'media'` is never a `LibraryItem.kind` value, so it could
   never match here - the row silently fell back to `'kindWord'` for every pinned listening item. */
export function pinnedKindKey(item = {}) {
  const map = { word: 'kindWord', reading: 'kindReading', listening: 'kindMedia', writing: 'kindWriting', speaking: 'kindSpeaking', grammar: 'kindGrammar' };
  return map[item.kind] || 'kindWord';
}

export function dueListRows(queue = {}) {
  return (queue.pinned || []).map((item) => ({
    text: item.word || '',
    kindKey: pinnedKindKey(item),
  }));
}

/* "In this session" (V-12, HV-4 A): the due words Review will ask, from the same queue it builds
   (`GET /api/library/vocabulary?status=due&order=due`, review/model.js#buildQueue), each with where its sentence
   came from when that is known. `sourceKey` is review copy's own key (sourceReading / sourceFeedback). */
export function sessionRows(items = []) {
  return buildQueue(items).map((row) => ({
    text: String(row.word || '').trim(),
    sourceKey: sourceLabelKey(row.source_kind),
    cloze: cardMode(row) === 'cloze',
  }));
}

/* The "source-aware" count of the session: the cards that ask the sentence the word was met in. */
export function sessionSourceCount(rows = []) {
  return rows.filter((row) => row.cloze).length;
}
