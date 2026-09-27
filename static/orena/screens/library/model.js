/* Pure, DOM-free data mapping for My Library (frame 12: Saved content, Saved language,
   Collections, Active use, Due Review - five tabs, per the live design script's own `LIBT` array
   in `orena-script.js`, not the "4" the pinned copy's compact export hinted; see `screen.js` for
   that correction and for `activeCards`, the one tab whose content is a fixed shortcut menu rather
   than a fetched row set, so it has no model.js function of its own).

   Every function here takes already-fetched API/device-memory data and returns the shape the
   screen paints - no fetch, no DOM, no copy lookup (labels are chosen by the caller, which has the
   translated strings; this module only says which label a row needs, by a stable key). */

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

   No entry here carries a real reading/listening position: `/api/collection` never measures one
   (reading position is device memory, per-device, and keyed by an old-style id this account-level
   read cannot join to - SCRATCH/inventory/C4 §2.7), so `pct` is honestly 0 rather than a guess.
   Rule 40 (CLAUDE.md, "The UI" §0): a metric the backend does not measure renders 0, not an
   omitted bar - and this frame draws the bar unconditionally (no `sc-if` around it), so a bar is
   drawn, at 0%. */
export function contentRows(entries = []) {
  return (entries || [])
    .filter((entry) => CONTENT_DOMAINS.includes(entry?.ref?.domain))
    .map((entry) => ({
      contentId: contentRouteId(entry.ref.domain, entry.ref.id),
      domain: entry.ref.domain,
      title: entry.title || '',
      source: entry.snippet || '',
      pct: 0,
    }));
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

/* The meaning line under a saved word. `definition` is whatever free text the learner was shown
   when they saved it, in no fixed language - it is kept as-is. `translation_vi` is the one
   contract field that IS hardcoded to Vietnamese (SCRATCH/inventory/C6 §2.4, a recorded backend
   gap under the multilingual invariant); it is read only when the learner's support language is
   Vietnamese, and only as a fallback, so it can never surface as a wrong-language meaning for an
   English- or Chinese-support learner - the honest gap for them is an empty sub-line, not this
   field mis-shown, and `source_fragment` is tried first-language-agnostic since it is the exact
   text the word was met in. */
export function wordMeaning(item = {}, supportLanguage = 'en') {
  const definition = String(item.definition || '').trim();
  if (definition) return definition;
  if (supportLanguage === 'vi') {
    const vi = String(item.translation_vi || '').trim();
    if (vi) return vi;
  }
  return String(item.source_fragment || '').trim();
}

export function languageRows(items = [], supportLanguage = 'en') {
  return (items || []).map((item) => ({
    word: item.word || '',
    kind: wordKindOf(item.word),
    sub: wordMeaning(item, supportLanguage),
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

export function collectionsAndDecks(collections = [], decks = []) {
  return [...libraryCollectionRows(collections), ...deckRows(decks)];
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
   placeholder). */
export function pinnedKindKey(item = {}) {
  const map = { word: 'kindWord', reading: 'kindReading', media: 'kindMedia', writing: 'kindWriting', speaking: 'kindSpeaking', grammar: 'kindGrammar' };
  return map[item.kind] || 'kindWord';
}

export function dueListRows(queue = {}) {
  return (queue.pinned || []).map((item) => ({
    text: item.word || '',
    kindKey: pinnedKindKey(item),
  }));
}
