/* Review Session's pure data mapping (frame 13, D-091; D7 §1). A spaced-repetition drill over the
   learner's real due vocabulary (`GET /api/library/vocabulary?status=due&order=due`, the same
   `_row_to_item` shape `screens/word/model.js#mapWordCard` already turns into a Word Card - this
   screen reuses that function directly rather than re-deriving the card).

   The frame draws four grades (Again/Hard/Good/Easy) with four invented interval labels
   ("1 min"/"1 day"/"3 days"/"8 days"). The real scheduler
   (`writing_coach/becoming_library.py#review_schedule`, carried on every item as `item.schedule`)
   accepts exactly three (`again`/`unsure`/`got_it` - `POST /api/library/vocabulary/{word}/review`'s
   own `VocabularyReviewIn.result` pattern) and reports real per-grade intervals for THIS card's
   stage, not a fixed table. Rule 40 ("map honestly... never fake intervals"): this screen draws
   three grade buttons, not four, each labelled with the real number `item.schedule` carries for
   this exact card - never the frame's four fixed strings. Recorded as a deviation in the surface
   report, not resolved silently. */

import { mapWordCard, cardLanguage, highlightExample } from '../word/model.js';
import { worthKeeping } from '../../product/review-queue.js';

function text(value) {
  return String(value ?? '').trim();
}

function normWord(value) {
  return text(value).toLowerCase();
}

function pickLang(list, lang) {
  const arr = Array.isArray(list) ? list : [];
  const exact = arr.find((entry) => entry && entry.language === lang && text(entry.text));
  if (exact) return text(exact.text);
  const any = arr.find((entry) => entry && text(entry.text));
  return any ? text(any.text) : '';
}

/* `mapWordCard` (word/model.js) reads only a saved item's own, learner-authored `definition`/
   `translation_vi`/`source_fragment`. A due-queue row can also carry the catalogue fields
   `becoming_library.py#_row_to_item` merges in for a word that has real catalogue data but no
   definition of its own yet (`support_translations`, `short_meanings`, `detailed_definitions`,
   `examples`) - confirmed live in this sandbox ("health": source_kind dictionary, definition and
   translation_vi both empty, support_translations.vi and examples both real). This backfills the
   card from those real fields when `mapWordCard`'s own fields came back empty - it never invents a
   meaning, it only looks in the one other real place the backend already put one. */
export function reviewCard(word, item, supportLang = '') {
  const row = item || {};
  const card = mapWordCard(word, { item });
  if (!card.hasMeaning) {
    const meaning =
      pickLang(row?.short_meanings, supportLang) ||
      pickLang(row?.detailed_definitions, supportLang) ||
      text(row?.support_translations?.[supportLang]) ||
      text(row?.translation_vi);
    if (meaning) {
      card.meaning = meaning;
      card.hasMeaning = true;
    }
  }
  if (!card.hasExample) {
    const example = pickLang(row?.examples, cardLanguage(card.script));
    if (example && example !== card.meaning) {
      card.hasExample = true;
      card.exampleParts = highlightExample(example, card.word);
    }
  }
  return card;
}

/* #/review's three entry shapes (D-091 routing note): a plain due-queue session, one word forced
   into a one-card session (Word Detail's own "Review" action, once it exists), or a session scoped
   to a curated collection's saved words (Collection Detail's "Start review"). The router hands a
   room its address's query as a `URLSearchParams` (shell/routes.js#match), so it is read with
   `.get()`; a plain object is accepted too, for a caller that has one. */
function param(query, key) {
  return text(typeof query?.get === 'function' ? query.get(key) : query?.[key]);
}

export function queueScope(query = {}) {
  const word = param(query, 'word');
  if (word) return { mode: 'word', word };
  const collection = param(query, 'collection');
  if (collection) return { mode: 'collection', collection };
  return { mode: 'due' };
}

/* Real rows only - a row with no word is not a card (defends the queue against a malformed
   response rather than crashing the session). */
export function buildQueue(rows = []) {
  return (Array.isArray(rows) ? rows : []).filter((row) => row && text(row.word));
}

/* Collection-scoped review reviews what the learner actually kept from that collection - the
   catalogue card's own `saved` flag (a per-request cross-reference, `app.py`'s vocabulary-library
   collection route), never every entry in the collection whether kept or not. */
export function collectionWordSet(collectionPayload) {
  const items = Array.isArray(collectionPayload?.items) ? collectionPayload.items : [];
  return new Set(items.filter((item) => item && item.saved).map((item) => normWord(item.word || item.headword)));
}

export function filterByWordSet(rows, wordSet) {
  return (Array.isArray(rows) ? rows : []).filter((row) => wordSet.has(normWord(row?.word)));
}

/* The frame's "{n} of {total}" counter (`rvProgressLabel`): the card being asked, and once the
   session is over the last one, never "total + 1 of total". Numbers only - the screen puts them
   through its own `progress` copy so vi/zh word the "of" their own way. */
export function progressCounts(index, total) {
  if (!total) return null;
  return { n: Math.min(index + 1, total), total };
}

export function progressPercent(index, total) {
  if (!total) return 0;
  return Math.max(0, Math.min(100, Math.round((Math.min(index, total) / total) * 100)));
}

const GRADE_UNIT_KEY = { minutes: 'scheduleMinutes', days: 'scheduleDays' };

/* The real interval this exact card would get for this exact grade, read off the scheduler's own
   answer (`item.schedule[grade]`) - never a table this screen invents. Empty when the item carries
   no schedule (should not happen for a due-queue row, but a defensive empty rather than a guess for
   any other caller). */
export function scheduleLabel(schedule, grade, t) {
  const value = schedule?.[grade];
  if (!value || typeof value !== 'object') return '';
  for (const [unit, key] of Object.entries(GRADE_UNIT_KEY)) {
    const n = Number(value[unit]);
    if (Number.isFinite(n) && n > 0) return t.plural(key, n);
  }
  return '';
}

export const GRADES = Object.freeze(['again', 'unsure', 'got_it']);

export function initialStats() {
  return { again: 0, unsure: 0, got_it: 0 };
}

export function tally(stats, grade) {
  if (!GRADES.includes(grade)) return stats;
  return { ...stats, [grade]: (stats[grade] || 0) + 1 };
}

/* ---- How a card asks its question (frame 13's `rvMode`, D7 §1.5) ---------------------------------
   The frame draws two ways in: "Target -> meaning" (the word, recall what it means) and
   "Source-aware cue" (the sentence the learner met the word in, the word taken out, recall the
   word). The second needs a sentence the learner really met the word in - the saved item's own
   `source_fragment` (POST /api/library/vocabulary's field, written by Reading, Writing feedback,
   the Daily Feed...) - so a card asks it only when that fragment really contains the word, exactly
   as the old product's `recall.js` decided ("anything met inside a sentence comes back inside that
   sentence"). A word with no such sentence is asked the first way; nothing is made up for it
   (rule 40), and the choice is the card's, not chance's, so the same card is asked the same way
   twice. */
export const MODES = Object.freeze(['target', 'cloze']);

const HAN = /[㐀-鿿]/;
const BLANK = '＿';
const BLANK_MIN = 3;
const BLANK_MAX = 14;

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/* The sentence with every occurrence of the word taken out (one left in would turn recall into
   reading). An English word may carry a short inflection ("figured" for "figure": at most three
   letters and then the word ends, so "cat" never blanks the front of "category"), and the blank
   covers what was matched, in the frame's own width rule (its length, at least three). Chinese has no
   word boundaries, so the word is matched where it stands. Returns null when the fragment does not
   contain the word. */
export function clozeFor(row) {
  const word = text(row?.word);
  const fragment = text(row?.source_fragment);
  if (!word || !fragment) return null;
  const pattern = new RegExp(
    HAN.test(word) ? escapeRegExp(word) : `(?<![\\p{L}\\p{N}_])${escapeRegExp(word)}\\p{L}{0,3}(?![\\p{L}\\p{N}_])`,
    'giu',
  );
  const parts = [];
  let out = '';
  let last = 0;
  let hits = 0;
  let match = pattern.exec(fragment);
  while (match) {
    const before = fragment.slice(last, match.index);
    const blank = BLANK.repeat(Math.min(BLANK_MAX, Math.max(BLANK_MIN, match[0].length)));
    if (before) parts.push({ blank: false, value: before });
    parts.push({ blank: true, value: blank });
    out += before + blank;
    last = match.index + match[0].length;
    hits += 1;
    match = pattern.exec(fragment);
  }
  if (!hits) return null;
  const rest = fragment.slice(last);
  if (rest) parts.push({ blank: false, value: rest });
  /* `parts` lets a screen keep each blank whole on one line; `text` is the same sentence as a string. */
  return { text: out + rest, parts, hits };
}

export function cardMode(row) {
  return clozeFor(row) ? 'cloze' : 'target';
}

/* The frame's `rvHint` for a source-aware card: how the answer starts and how long it is, word by
   word ("h_____"), with nothing else given away. */
export function hintMask(word) {
  return text(word)
    .split(/\s+/)
    .filter(Boolean)
    .map((piece) => {
      const letters = Array.from(piece);
      return letters[0] + '_'.repeat(letters.length - 1);
    })
    .join(' ');
}

/* The kinds the backend actually stores (`LibraryVocabularyIn.source_kind`) that name where a
   sentence came from; anything else carries no source label (rule 40 - no title or time exists on
   a saved item to draw the frame's "A Morning in the City - 0:24"). */
const SOURCE_LABEL_KEY = { reading: 'sourceReading', feedback: 'sourceFeedback', strength: 'sourceFeedback' };
export function sourceLabelKey(kind) {
  return SOURCE_LABEL_KEY[text(kind)] || '';
}

/* What the hidden card offers as a hint. Target -> meaning: the learner's own-language gloss (the
   frame's `rvG.vi`), and nothing when the card has none. Source-aware: the answer's mask. */
export function hintFor(mode, card) {
  if (mode === 'cloze') return hintMask(card?.word);
  return text(card?.support);
}

/* ---- A grade's fate ----------------------------------------------------------------------------
   `saved`: the server rescheduled the card. `kept`: it could not be reached - the answer waits in
   the device's review queue (`product/review-queue.js`, the same one the old Review used) and goes
   up when there is a connection. `failed`: the server refused it, and it will refuse it again, so
   nothing waits. `missing`: the card was unsaved mid-grade and there is nothing left to
   reschedule (`becoming_library.py#review_library_vocabulary` answers `{found:false}`). `aborted`:
   the learner left while it was in flight (infrastructure/navigation.js cancels a room's requests) -
   whether it arrived is unknown and there is no room left to tell. Only the first two are an answer
   the learner really gave that counts toward the session summary. */
export function gradeOutcome({ result = null, error = null } = {}) {
  if (error?.name === 'AbortError') return 'aborted';
  if (error) return worthKeeping(error) ? 'kept' : 'failed';
  if (result && result.found === false) return 'missing';
  return 'saved';
}

export function countsForSession(outcome) {
  return outcome === 'saved' || outcome === 'kept';
}
