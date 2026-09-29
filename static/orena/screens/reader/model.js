/* Reader (design route `reader`, frame 14): pure data mapping, DOM-free so
   scripts/test_orena_screen_reader.mjs can test it without a browser.

   Content id parsing (`parseContentId`/`contentIdFor`) and the device-memory continuation reader
   (`placeFor`) are Content Detail's own contract (screens/content/model.js's own header: "shared by
   Discover, Today, Content Detail, My Library and Search") - a Reader route id ("article:x",
   "book:b:c", "text:x") is that same id, so this module reads them from there rather than parsing
   a second, possibly-drifting copy. blocksFrom/chapterNeighbours/sentenceSpans/selectionKind/
   sentenceAround/the endpoint limits are product/reader-text.js's contract (moved out of the old
   ui/reading-room.js, see that module's own header). Notes are the Quick Sheet's own device-memory
   contract (screens/quick-sheet/model.js) - the same notes a learner adds from the Sentence Quick
   Sheet's Note tab are what this screen's "Notes & highlights" panel lists, so this module reads
   its loadNotes/noteKeyFor rather than a second notes store. */
import { parseContentId, contentIdFor, placeFor, libraryKindFor, metaLine } from '../content/model.js';
import {
  blocksFrom,
  chapterNeighbours,
  sentenceSpans,
  selectionKind,
  sentenceAround,
  LOOKUP_LIMITS,
  EXPLAIN_LIMITS,
  TRANSLATE_LIMITS,
} from '../../product/reader-text.js';

export {
  parseContentId,
  contentIdFor,
  placeFor,
  libraryKindFor,
  metaLine,
  chapterNeighbours,
  selectionKind,
  sentenceAround,
  LOOKUP_LIMITS,
  EXPLAIN_LIMITS,
  TRANSLATE_LIMITS,
};

/* ------------------------------------------------------------------------------- Shaping ------ */

/* An article's body / a learner's own imported text is one string; the reader reads it as
   paragraphs split on a blank line (a real line, not an invented one - a text with no blank line
   at all is one paragraph, never split mid-sentence). */
export function paragraphsFromText(raw) {
  const parts = String(raw ?? '')
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length) return parts;
  const whole = String(raw ?? '').trim();
  return whole ? [whole] : [];
}

/* The blocks Reader renders, for whichever of the three sources it opened: a book chapter already
   carries structured blocks/paragraphs (GET .../chapters/{id}); an article's `body` and a learner's
   own imported text are both one string, split into paragraphs above. */
export function blocksForSource(kind, raw) {
  if (kind === 'book') return blocksFrom({ blocks: raw?.blocks, paragraphs: raw?.paragraphs });
  if (kind === 'article') return blocksFrom({ paragraphs: paragraphsFromText(raw?.body) });
  return blocksFrom({ paragraphs: paragraphsFromText(raw?.text) });
}

const flat = (value) => String(value ?? '').replace(/\s+/g, ' ').trim().toLowerCase();

/* What the page draws from a source's blocks: a chapter that opens by repeating its own title
   (a heading, or a plain first line) does not print it twice - the toolbar already names it - and
   a break/heading stays what it is. `pi` is a paragraph's index among the PARAGRAPHS only: the
   stable half of a sentence's segment id ("p{pi}s{si}") that a note is keyed by, so a heading
   before or after it never renumbers a saved note. */
export function pageBlocks(blocks, title) {
  const list = Array.isArray(blocks) ? blocks : [];
  const first = list[0];
  const dropFirst = Boolean(first) && first.type !== 'break' && flat(first.text) === flat(title);
  let pi = 0;
  const out = [];
  list.forEach((block, index) => {
    if (index === 0 && dropFirst) {
      if (block.type === 'paragraph') pi += 1;
      return;
    }
    if (block.type === 'paragraph') {
      out.push({ ...block, pi });
      pi += 1;
    } else out.push(block);
  });
  return out;
}

/* A paragraph's text, split into the sentences the frame renders one `<span>` per (D3 §1.1
   `pg.sentences`). Empty spans (pure whitespace between two sentence-end matches) are dropped. */
export function sentencesOf(text) {
  return sentenceSpans(text)
    .map(({ start, end }) => text.slice(start, end))
    .map((value) => value.trim())
    .filter(Boolean);
}

export const segmentId = (pi, si) => `p${pi}s${si}`;

/* Every paragraph of a document, in reading order, as { pi, text }: the shape the note and
   highlight counters walk. */
export function paragraphsOf(blocks) {
  return (Array.isArray(blocks) ? blocks : []).filter((b) => b.type === 'paragraph');
}

/* ----------------------------------------------------------------------- Word roles (POS lens) -- */

/* The design's six word roles (frame 14's POS legend: noun, verb, modifier, connector, pronoun,
   number) and the app's own `--skill-*` hues that the design's legend colours ARE (noun #4867EC =
   --skill-grammar, verb #1FB8B8 = --skill-listen, modifier #FF7A3D = --skill-read, connector
   #7B4FD8 = --skill-write, pronoun #EE4F6C = --skill-speak, number #F2B705 = --skill-vocab).
   The colour itself lives in reader.css against `data-role`; this module owns the mapping from the
   backend's label set (writing_coach/linguistic_annotation.py ALLOWED_POS, whose own note says "a
   caller with a narrower vocabulary is responsible for its own mapping") onto the design's six.
   A word with no role (a determiner, a preposition, an interjection, "other") is left untinted -
   the design's own roleOf() leaves such words unmarked too. */
export const ROLES = Object.freeze(['noun', 'verb', 'modifier', 'connector', 'pronoun', 'number']);

const ROLE_OF_POS = Object.freeze({
  noun: 'noun',
  proper_noun: 'noun',
  classifier: 'noun',
  verb: 'verb',
  auxiliary: 'verb',
  adjective: 'modifier',
  adverb: 'modifier',
  conjunction: 'connector',
  pronoun: 'pronoun',
  numeral: 'number',
});

export function roleOf(pos) {
  return ROLE_OF_POS[String(pos || '')] || '';
}

/* How many reading aids are on right now - the "Aids · N" chip. The frame counts three
   (translation, vocabulary lens, word roles); pinyin is the learner's own pinyin preference, not
   an aid the chip counts. */
export function aidsCount({ translation, vocabLens, posLens }) {
  return [translation, vocabLens, posLens].filter(Boolean).length;
}

/* -------------------------------------------------------------------- Sentence -> word pieces -- */

const WORD_RE = /[\p{L}\p{M}\p{N}]+(?:['’-][\p{L}\p{M}\p{N}]+)*/gu;
const HAN = /[\p{Script=Han}]/u;

/* A sentence's text as an ordered list of pieces: `{ text }` for plain runs and
   `{ text, word: true, role, pos, pinyin: [{ h, p }] , saved }` for a word. `tokens` are the
   tagger's own (`POST /api/media-learning/annotate`, offsets relative to the sentence) when the
   caller has them; without tokens an alphabetic text is still split into words by a plain rule (so
   a word can be tapped and hovered), and a script written without spaces stays one run until the
   tagger has segmented it - guessing a Chinese word boundary would hand a lookup something the
   learner did not point at. `saved` is a lower-cased set of words the learner kept from this
   sentence (see reader/source.js#savedFromSentences). */
export function segmentSentence(text, tokens, { saved = new Set() } = {}) {
  const value = String(text ?? '');
  const isSaved = (word) => saved.has(word.toLowerCase());
  const pieces = [];
  const pushPlain = (run) => {
    if (run) pieces.push({ text: run });
  };
  if (Array.isArray(tokens) && tokens.length) {
    let cursor = 0;
    for (const token of tokens) {
      if (!(token.start >= cursor) || !(token.end > token.start) || token.end > value.length) continue;
      pushPlain(value.slice(cursor, token.start));
      const fragment = value.slice(token.start, token.end);
      pieces.push({
        text: fragment,
        word: true,
        pos: token.pos || '',
        role: roleOf(token.pos),
        pinyin: pinyinStack(fragment, token.pronunciation),
        saved: isSaved(fragment),
      });
      cursor = token.end;
    }
    pushPlain(value.slice(cursor));
    return pieces;
  }
  if (HAN.test(value)) return value ? [{ text: value }] : [];
  let cursor = 0;
  for (const match of value.matchAll(WORD_RE)) {
    pushPlain(value.slice(cursor, match.index));
    pieces.push({ text: match[0], word: true, pos: '', role: '', pinyin: [], saved: isSaved(match[0]) });
    cursor = match.index + match[0].length;
  }
  pushPlain(value.slice(cursor));
  return pieces;
}

/* Pinyin above each Hanzi (frame 14's `hc.p`/`hc.h` stack): one syllable per character when the
   tagger's reading has as many syllables as the word has characters; otherwise the whole reading
   sits above the word's first character rather than being split by a guess. Nothing for a word
   the tagger gave no reading (English). */
export function pinyinStack(fragment, pronunciation) {
  const reading = String(pronunciation || '').trim();
  if (!reading || !HAN.test(fragment)) return [];
  const chars = Array.from(fragment);
  const syllables = reading.split(/\s+/).filter(Boolean);
  if (syllables.length === chars.length) return chars.map((h, i) => ({ h, p: syllables[i] }));
  return chars.map((h, i) => ({ h, p: i === 0 ? reading : '' }));
}

/* The frame's word-role toast: "word · role - what the role does" (frame 14's own script: "famished ·
   modifier - describes or qualifies"). The help is the role's short meaning in the support language;
   without one the toast is "word · role". */
export function roleToast(word, roleLabel, roleHelp = '') {
  const head = `${String(word || '').trim()} · ${roleLabel}`;
  return roleHelp ? `${head} — ${roleHelp}` : head;
}

/* ------------------------------------------------------------------------ Reader preferences -- */

/* The article's reading font-size (frame 14: `font-size:{{ rdSize }}`; the Aa menu shows the current
   value as a literal pixel size, 18px by default, A-/A+ stepping 1px between 15 and 24). The one
   preference this control writes, `readerSettings.size`, is shared device state
   (product/reader-settings.js, `orena.reader`) whose own unit is a 0.85-1.4 multiplier - the same
   contract Settings' "Reader text size" S/M/L choice already commits to - so this frame expresses
   that stored multiplier in the unit its own control shows: READER_BASE_PX is the frame's measured
   default (rdSize:18 at the stored default size 1), clamped to the control's own 15..24. */
export const READER_BASE_PX = 18;
export const READER_PX = Object.freeze({ min: 15, max: 24 });

const clampPx = (px) => Math.min(READER_PX.max, Math.max(READER_PX.min, px));

export function readerSizePx(size) {
  return clampPx(Math.round(READER_BASE_PX * (Number.isFinite(size) ? size : 1)));
}

/* The stored multiplier after one A- (-1) or A+ (+1) step: a whole pixel step of the control,
   written back as the multiplier the rest of the app reads. */
export function steppedSize(size, direction) {
  const next = clampPx(readerSizePx(size) + (direction < 0 ? -1 : 1));
  return Math.round((next / READER_BASE_PX) * 100) / 100;
}

/* ---------------------------------------------------------------------------------- Toolbar ---- */

/* The second line of the toolbar (frame 14: `{{ rdDocMeta }} · {{ rdPageLabel }}`): what the text
   is (its author or source, its level) and where the learner is in it. A book shows the chapter and
   its real position in the book; an article/imported text has no page to invent, so it shows the
   same real reading percent the progress bar measures. Parts the backend did not give are absent,
   never a placeholder. */
export function toolbarMeta({ isBook, chapterTitle = '', author = '', level = '', chapterIndex, chapterTotal, percent }) {
  const position = isBook && Number.isInteger(chapterIndex) && Number.isInteger(chapterTotal) ? `${chapterIndex + 1}/${chapterTotal}` : `${percent}%`;
  return metaLine([isBook ? chapterTitle : author, isBook ? '' : level, position]);
}

/* ------------------------------------------------------------------------------- End of text --- */

/* The end-of-content block: which primary action shows, whether "Mark as finished" also shows as a
   secondary ghost action, whether a Next-chapter button shows, and which end-note key applies. Real
   state only: `hasQuiz` comes from whether GET .../practice/articles/{id} actually answers (Content
   Detail's own `loadHasPractice` establishes this same check), never invented for every article. */
export function endOfContent({ isBook, hasQuiz, hasNextChapter, chapterNumber }) {
  const primaryIsCheck = Boolean(hasQuiz);
  let endNoteKey = 'endNoteText';
  if (isBook) endNoteKey = 'endNoteChapter';
  else if (hasQuiz) endNoteKey = 'endNoteArticle';
  return {
    primaryIsCheck,
    secondaryHas: !isBook && primaryIsCheck,
    hasNextChapter: Boolean(isBook && hasNextChapter),
    endNoteKey,
    endNoteParams: isBook ? { n: chapterNumber } : {},
  };
}

/* ------------------------------------------------------------------------------ Position ------ */

/* Reading position as a whole percentage of the scrollable content, clamped. A region shorter than
   its own viewport (nothing to scroll) reads as fully read - true, not a guess: there is no more of
   it to reveal by scrolling. */
export function percentFromScroll(scrollTop, scrollHeight, clientHeight) {
  const max = scrollHeight - clientHeight;
  if (!(max > 0)) return 100;
  return Math.max(0, Math.min(100, Math.round((scrollTop / max) * 100)));
}

/* The scroll offset for a stored percent (the inverse of percentFromScroll). */
export function scrollTopFor(percent, scrollHeight, clientHeight) {
  const max = Math.max(0, scrollHeight - clientHeight);
  return Math.round((Math.min(100, Math.max(0, percent)) / 100) * max);
}

/* `product/memory.js#enter`'s `place` needs a real index/total pair (readPlace rejects anything
   else) - a book chapter's real position in its real chapter count IS that pair; a flat
   article/imported text has no chapters to count, so it is honestly "1 of 1", with `within` (the
   percent above) carrying the real progress. `within` is only written once the learner has really
   read into the text: a place with none is "opened, not yet moved through" (memory.js). */
export function placeFor2(kind, { chapterIndex = 0, chapterTotal = 1, percent = null }) {
  const place = {
    index: kind === 'book' ? chapterIndex + 1 : 1,
    total: kind === 'book' ? Math.max(1, chapterTotal) : 1,
  };
  if (Number.isFinite(percent)) place.within = percent;
  return place;
}

/* The furthest point reached: reading back up a page never lowers where the learner has been (the
   old Reader's own "furthest forward only" rule, kept). */
export function furthest(stored, current) {
  const a = Number.isFinite(stored) ? stored : 0;
  const b = Number.isFinite(current) ? current : 0;
  return Math.max(a, b);
}

/* A short, real excerpt for the continuation record (product/memory.js#enter's `excerpt`) - the
   opening of whichever paragraph the learner is nearest, never invented summary text. */
export function excerptFrom(paragraphs, percent) {
  if (!paragraphs.length) return '';
  const index = Math.min(paragraphs.length - 1, Math.floor((percent / 100) * paragraphs.length));
  const text = String(paragraphs[index] || '').trim();
  return text.length > 160 ? `${text.slice(0, 160).trim()}…` : text;
}

/* -------------------------------------------------------------------------- Translation layer -- */

/* The paragraphs of a document as translate requests, in turns: `POST /api/reading/translate`
   takes at most 48 segments of at most 6000 characters, and its own comment says a reader asking for
   a whole chapter "sends it in turns, so the first meanings arrive while the rest are still on their
   way". A paragraph over the per-text limit is cut to it, as the old Reader did. Segment ids are the
   paragraph's own index ("p3"). */
export function translationTurns(paragraphs, { perTurn = 12, chars = TRANSLATE_LIMITS.text } = {}) {
  const turns = [];
  let current = [];
  let used = 0;
  paragraphs.forEach((text, index) => {
    const value = String(text || '').slice(0, chars);
    if (!value) return;
    if (current.length && (current.length >= perTurn || used + value.length > chars)) {
      turns.push(current);
      current = [];
      used = 0;
    }
    current.push({ segment_id: `p${index}`, text: value });
    used += value.length;
  });
  if (current.length) turns.push(current);
  return turns;
}

/* A translate answer as { paragraphIndex -> meaning }; only a `ready` answer carries meanings. */
export function translationsFrom(response) {
  const out = new Map();
  if (response?.status !== 'ready') return out;
  for (const item of response.translations || []) {
    const index = Number(String(item?.segment_id || '').slice(1));
    const meaning = String(item?.translated_meaning || '').trim();
    if (Number.isInteger(index) && meaning) out.set(index, meaning);
  }
  return out;
}

/* ----------------------------------------------------------------------- Words kept from here -- */

const squash = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();

/* The learner's saved words that were kept from a sentence of THIS text: an item the Quick Sheet
   saved from reading carries `source_fragment` = the sentence it was met in (screens/quick-sheet/
   model.js#wordSavePayload). The library keeps no link from a saved word to the document itself, so
   the sentence is the only provenance there is - an exact match on a sentence of this document, not
   a guess from the word appearing somewhere in it. Returns { bySentence: Map<squashed sentence,
   Set<lower-cased word>>, count } - `count` is distinct words. */
export function savedFromSentences(items, sentences) {
  const wanted = new Set(sentences.map(squash));
  const bySentence = new Map();
  const words = new Set();
  for (const item of Array.isArray(items) ? items : []) {
    const fragment = squash(item?.source_fragment);
    const word = String(item?.word || '').trim().toLowerCase();
    if (!fragment || !word || !wanted.has(fragment)) continue;
    if (!bySentence.has(fragment)) bySentence.set(fragment, new Set());
    bySentence.get(fragment).add(word);
    words.add(word);
  }
  return { bySentence, count: words.size };
}

export { squash };
