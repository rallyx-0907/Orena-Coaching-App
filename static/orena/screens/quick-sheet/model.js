/* Pure data mapping for the Word Quick Sheet (frame 53) and Sentence Quick Sheet (frame 57), D-066.
   No DOM, no fetch, no timers - what scripts/test_orena_screen_quick-sheet.mjs exercises directly.

   Rule 40 throughout: a field neither `POST /api/dictionary/word-detail` nor
   `POST /api/dictionary/sentence-sheet` returned is left out rather than invented - an unavailable
   answer (`available:false`, the documented fallback when this build has no AI provider key)
   renders the frame's own "not prepared" branch, never a guessed meaning. */

const STAGE_COPY_KEY = {
  New: 'stageNew',
  Learning: 'stageLearning',
  Reinforcing: 'stageReinforcing',
  Available: 'stageAvailable',
};

const POS_LABEL_KEY = Object.freeze({
  noun: 'posNoun', verb: 'posVerb', adjective: 'posAdjective', adverb: 'posAdverb',
  pronoun: 'posPronoun', determiner: 'posDeterminer', preposition: 'posPreposition',
  conjunction: 'posConjunction', numeral: 'posNumeral', particle: 'posParticle',
  auxiliary: 'posAuxiliary', interjection: 'posInterjection', classifier: 'posClassifier',
  proper_noun: 'posProperNoun', other: 'posOther',
});

/* AGENT_CONTRACT.md §6.1: the surface id names *where the learner is*, not what they selected.
   `source.kind` (the caller's own vocabulary - 'reading'|'listening'|'dictation'|'speaking'|
   'writing'|'vocabulary'|'grammar'|…) maps to the §6.1 id for that workspace; an unrecognised or
   absent kind falls back to the one surface §6.1 names specifically for a word
   (`vocabulary.word{text,lang}`) or, for a sentence (no sentence-specific id exists), the most
   general vocabulary surface - never a guessed or invented id. */
const SURFACE_BY_KIND = Object.freeze({
  reading: 'reading.workspace',
  listening: 'listening.workspace',
  dictation: 'listening.dictation',
  speaking: 'speaking.workspace',
  writing: 'writing.workspace',
  vocabulary: 'vocabulary.my_language',
  grammar: 'grammar.catalog',
});

function text(value) {
  return String(value ?? '').trim();
}

const HAN = /[㐀-鿿]/;

/* The due-date pure function is shared with `screens/word/model.js` (2026-09-29 fix pass: this
   module had grown a byte-for-byte copy of `word/model.js#dueInfo`, and the two callers had
   already drifted - see `product/due-schedule.js`'s own header). Re-exported here so this
   module's existing callers (`mapWordCard` below, and this gate's own
   `import { dueInfo } from '.../quick-sheet/model.js'`) keep working unchanged. */
export { dueInfo } from '../../product/due-schedule.js';
import { dueInfo } from '../../product/due-schedule.js';

/* The content id a dictionary request carries, so the server can tell shared published content from the learner's
   own text (D-228). Only the id of what the learner is reading or listening to is sent; a personal import (`text:`)
   or anything without an id carries none, and the server then treats the sentence as private. The server, not this
   function, decides what is shared. */
export function lookupContentId(source) {
  const id = text(source?.content_id);
  if (!id || id.startsWith('text:')) return undefined;
  return id;
}

/* The body of `POST /api/dictionary/word-detail` for the word sheet: one place for both of its asks. */
export function wordDetailRequest({ contextual, target, context, lang, support, source }) {
  const contentId = lookupContentId(source);
  return {
    depth: 'sheet',
    contextual: Boolean(contextual),
    text: target,
    context,
    source_language: lang,
    target_language: support,
    ...(contentId ? { content_id: contentId } : {}),
  };
}

export function surfaceFor(source, fallback) {
  return SURFACE_BY_KIND[text(source?.kind)] || fallback;
}

/* A valid `context` for either dictionary route must contain `text` (the server rejects it
   otherwise, 422). The caller's own sentence is used when it actually contains the selection;
   otherwise the selection is its own (still valid) context - never an invented sentence. */
export function contextFor(selection, sentence) {
  const w = text(selection);
  const s = text(sentence);
  if (s && s.toLowerCase().includes(w.toLowerCase())) return s;
  return w;
}

/* ---- Word Quick Sheet ------------------------------------------------- */

export function posLabel(value, t) {
  const raw = text(value);
  const parts = raw.split(/\s*[\/,;|]\s*/).filter(Boolean);
  const keys = parts.map((part) => POS_LABEL_KEY[part.toLowerCase().replace(/\s+/g, '_')]);
  // A combined value ("noun/verb", V-19) is translated part by part and joined as the language joins a list;
  // a value with any part outside the closed set stays exactly as given, never half-translated.
  if (parts.length && keys.every(Boolean)) return { text: keys.map((key) => t(key)).join(t('posJoin')), known: true };
  return { text: raw, known: false };
}

export function savedTone(saved) {
  return saved
    ? { bg: 'var(--amber-soft)', color: 'var(--amber)' }
    : { bg: 'var(--surface2)', color: 'var(--muted)' };
}

/* 0-4 bars filled, from the real review stage (an unsaved word is 0, not a guess). */
export function masteryFilled(item) {
  return Math.max(0, Math.min(4, Number(item?.review_stage) || 0));
}

export function stageCopyKey(item) {
  return STAGE_COPY_KEY[text(item?.stage_label)] || '';
}

/* The example sentence split around the headword, for the frame's tinted-highlight treatment. A
   word not actually present in the sentence renders as one plain part - never a fabricated match. */
export function highlightExample(example, word) {
  const value = text(example);
  if (!value) return [];
  const w = text(word);
  const at = w ? value.toLowerCase().indexOf(w.toLowerCase()) : -1;
  if (at < 0) return [{ value, hit: false }];
  const parts = [];
  if (at > 0) parts.push({ value: value.slice(0, at), hit: false });
  parts.push({ value: value.slice(at, at + w.length), hit: true });
  if (at + w.length < value.length) parts.push({ value: value.slice(at + w.length), hit: false });
  return parts;
}

/* The word card (`qsHasWC`/`qsNoWC`, E5 §3.2), from WordDetail (`detail`, may be null on a failed
   lookup) and the learner's own saved record (`item`, only fetched - and only present - when
   `detail.saved` is true; see sheet.js). `hasContent` decides the branch: real content
   (`meaningSource !== 'none'`) draws the word/meaning/example card, otherwise the "no prepared
   gloss" fallback - the real-data equivalent of the mock's GLOSS-hit split (E5 §3.5's own note:
   the mock's `known`/`unknown` pair was unreachable by construction, not a state to reproduce). */
export function mapWordCard(word, { detail = null, item = null, support = '' } = {}) {
  const headword = text(detail?.headword) || text(word);
  const script = detail?.script === 'hanzi' || HAN.test(headword) ? 'hanzi' : 'latin';
  const reading = script === 'hanzi' ? text(detail?.pinyin) : text(detail?.ipa);
  // Independent of whether a contextual meaning was found (a dictionary POS heuristic runs either
  // way) - real when the backend has it, the frame's own "word" placeholder (sheet.js/copy.js
  // `posUnknown`) only when it truly does not, never the mock's always-placeholder value.
  const pos = text(detail?.partOfSpeech);
  const meaning = text(detail?.contextMeaning);
  const hasContent = Boolean(meaning) && detail?.meaningSource !== 'none';
  const saved = Boolean(detail?.saved);
  const tone = savedTone(saved);
  // The language the main line is written in (D18): the server tags a dictionary line ("en" while the support-language
  // localization is not ready); a contextual meaning is written in the support language. Empty = the support language.
  const supportCode = text(support).toLowerCase();
  const writtenIn = text(detail?.meaningLanguage).toLowerCase();
  const meaningLanguage = hasContent && writtenIn && writtenIn !== supportCode ? writtenIn : '';
  return {
    word: headword,
    meaningLanguage,
    supportLanguage: supportCode,
    script,
    reading,
    hasContent,
    pos,
    meaning,
    // What the word commonly means, beside what it means here (LEX-018): shown only under a contextual meaning.
    generalMeaning: detail?.meaningSource === 'context' || detail?.meaningSource === 'contextual' ? text(detail?.generalMeaning) : '',
    // The language that common meaning is written in when it is not the support language (an English definition no
    // layer localized, kept beside the contextual meaning rather than hidden by it); empty = the support language.
    generalMeaningLanguage: (() => {
      const written = text(detail?.generalMeaningLanguage).toLowerCase();
      return written && written !== supportCode ? written : '';
    })(),
    example: text(detail?.deeper?.examples?.[0]),
    exampleParts: highlightExample(detail?.deeper?.examples?.[0], headword),
    audioUrl: text(detail?.audioUrl),
    whyHere: text(detail?.deeper?.whyHere),
    // "Meaning here" (frame 53) only when the meaning is this sentence's own, not a dictionary sense.
    meaningIsContextual: detail?.meaningSource === 'context' || detail?.meaningSource === 'contextual',
    contextSentence: text(detail?.contextSentence),
    // The dictionary's own definition behind a localized meaning: secondary data, never the main line.
    originalDefinition: detail?.originalDefinition?.text ? { text: text(detail.originalDefinition.text), language: text(detail.originalDefinition.language) || 'en' } : null,
    saved,
    savedBg: tone.bg,
    savedColor: tone.color,
    level: text(item?.level),
    filled: masteryFilled(item),
    stageKey: stageCopyKey(item),
    due: dueInfo(item),
    hasSchedule: Boolean(item),
  };
}

/* A saved word's own new-save payload (`POST /api/library/vocabulary`) - the meaning the learner is
   actually looking at, and where they met it (`source.kind`), rather than a generic 'manual'. */
function vietnameseMeaning(card) {
  const written = text(card?.meaningLanguage) || text(card?.supportLanguage);
  return written.toLowerCase() === 'vi' ? text(card?.meaning) : '';
}

/* The video a save from Listening comes from (D-248 §4): saving from a video to review is one of the paid tools around
   it, and the server needs the video to apply an editor's override. Nothing for any other source. */
export function sourceMediaOf(source) {
  if (text(source?.kind) !== 'listening') return {};
  const id = text(source?.content_id).replace(/^media:/, '').slice(0, 255);
  return id ? { source_media_id: id } : {};
}

export function wordSavePayload(card, sentence, source) {
  return {
    word: text(card?.word),
    phonetic: text(card?.reading),
    part_of_speech: text(card?.pos),
    definition: text(card?.meaning),
    // The Vietnamese localization goes in its own field, and only when the line shown is Vietnamese (D18): an English
    // fallback is never stored as the Vietnamese meaning, so a later localization can still fill it.
    ...(vietnameseMeaning(card) ? { translation_vi: vietnameseMeaning(card) } : {}),
    source_fragment: text(sentence),
    source_kind: ['reading', 'listening', 'writing', 'speaking', 'feed', 'collection', 'feedback', 'strength', 'dictionary'].includes(text(source?.kind))
      ? text(source.kind)
      : 'dictionary',
    ...sourceMediaOf(source),
  };
}

/* The source kinds `/api/library/vocabulary` accepts. An empty stored kind cannot be sent back as it is (the
   API would default it to "manual" and overwrite it), so such a word is not re-saved. */
const SAVE_SOURCE_KINDS = ['manual', 'dictionary', 'feedback', 'strength', 'reading', 'listening', 'writing', 'speaking', 'feed', 'collection'];

/* A word kept from the sheet before "Why here?" answered holds the basic meaning; when the contextual one
   arrives the kept word takes it. Only the definition changes: the stored source kind and fragment are sent
   back as they are. `guard` is the sheet's live state - `readOnly`, `kept()` (the learner's own last
   save/unsave, never what an answer says), `busy()` / `setBusy()` (the same lock Save and unsave use, so an
   unsave cannot land between the check and the write) - and `stored()` reads the kept item. Returns the
   saved item, or null when nothing was written. */
export async function resaveContextualMeaning({ api, card, guard, stored }) {
  if (guard.readOnly || guard.busy() || !guard.kept() || !card?.meaningIsContextual || !card.meaning) return null;
  const row = await stored();
  if (!row || !guard.kept() || guard.busy() || !SAVE_SOURCE_KINDS.includes(text(row.source_kind))) return null;
  guard.setBusy(true);
  try {
    const saved = await api.saveLibraryVocabulary({
      word: text(card.word),
      definition: text(card.meaning),
      source_kind: text(row.source_kind),
      source_fragment: text(row.source_fragment),
    });
    return saved?.item || null;
  } catch {
    return null;
  } finally {
    guard.setBusy(false);
  }
}

/* Everything `/api/library/vocabulary/restore` needs to put a deleted word back exactly as it was,
   schedule included - not a fresh save wearing the same spelling. */
export function wordRestorePayload(item) {
  if (!item) return null;
  const payload = { word: text(item.word) };
  const strings = [
    'phonetic', 'part_of_speech', 'definition', 'translation_vi', 'added_at', 'source_fragment',
    'source_kind', 'focus_note', 'last_reviewed_at', 'next_review_at',
    'entry_identity_key', 'entry_id', 'reading_key',
  ];
  for (const key of strings) if (item[key] != null) payload[key] = text(item[key]);
  const numbers = ['source_essay_id', 'review_stage', 'successful_recalls', 'lapse_count'];
  for (const key of numbers) if (item[key] != null) payload[key] = Number(item[key]);
  return payload;
}

/* ---- Sentence Quick Sheet ---------------------------------------------- */

/* SentenceSheet.json → the four tabs' data. `available:false` (no AI provider, or the explanation
   capability had nothing) means none of translation/structure/vocabulary exist - each tab's own
   "not prepared" fallback (E5 §4's tab panels, reusing the word sheet's dashed-notice pattern) -
   never an empty string standing in for a real sentence. */
export function mapSentenceSheet(response, savedVocabTerms = new Set()) {
  const available = Boolean(response?.available);
  const translation = available ? text(response.translation) : '';
  const structure = available ? (response.structure || []).map((s) => ({ chunk: text(s.chunk), role: text(s.role) })).filter((s) => s.chunk) : [];
  const vocabulary = available
    ? (response.vocabulary || [])
        .map((v) => ({ term: text(v.term), meaning: text(v.meaning), saved: Boolean(v.saved) || savedVocabTerms.has(text(v.term).toLowerCase()) }))
        .filter((v) => v.term)
    : [];
  return { available, translation, structure, vocabulary };
}

export function vocabSavePayload(term, meaning, sentence, source, supportLanguage = '') {
  return {
    word: text(term),
    definition: text(meaning),
    // The sentence sheet's vocabulary meanings are written in the support language.
    ...(text(supportLanguage).toLowerCase() === 'vi' && text(meaning) ? { translation_vi: text(meaning) } : {}),
    source_fragment: text(sentence),
    source_kind: ['reading', 'listening', 'writing', 'speaking'].includes(text(source?.kind)) ? text(source.kind) : 'dictionary',
    ...sourceMediaOf(source),
  };
}

/* ---- Notes (device memory, Architecture holds §7: learner-owned, no server schema yet) -------- */

const NOTE_TYPES = ['factual', 'reflection', 'question'];

export function noteTypeColorKey(kind) {
  if (kind === 'question') return 'var(--amber)';
  if (kind === 'reflection') return 'var(--accent-text)';
  return 'var(--muted)';
}

/* A stable per-sentence key: the content this sentence belongs to (when known) plus the sentence's
   own text, never a random id - so the same sentence reopened later finds the same notes. */
export function noteKeyFor(sentence, source) {
  const kind = text(source?.kind) || 'unknown';
  const contentId = text(source?.content_id);
  const segment = source?.segment != null ? String(source.segment) : '';
  return `${kind}:${contentId}:${segment}:${text(sentence).slice(0, 200).toLowerCase()}`;
}

/* Every key a sentence's notes may be under: its own, then the ones the sentence had before D-201 changed
   how a paragraph is cut into sentences (`source.legacy`: [{ segment, sentence }], reader/legacy-sentences.js).
   Reading looks under all of them; writing uses the first only. */
export function noteKeysFor(sentence, source) {
  const own = noteKeyFor(sentence, source);
  const keys = [own];
  for (const old of Array.isArray(source?.legacy) ? source.legacy : []) {
    const key = noteKeyFor(old.sentence, { ...source, segment: old.segment });
    if (!keys.includes(key)) keys.push(key);
  }
  return keys;
}

/* The notes under any of these keys, each note once (by id). */
export function loadNotesAcross(storage, owner, keys) {
  const seen = new Set();
  const out = [];
  for (const key of keys) {
    for (const note of loadNotes(storage, owner, key)) {
      if (seen.has(note?.id)) continue;
      seen.add(note?.id);
      out.push(note);
    }
  }
  return out;
}

/* The key (among these) that holds the note, so an edit or a delete lands where the note is stored. */
export function noteKeyHolding(storage, owner, keys, id) {
  return keys.find((key) => loadNotes(storage, owner, key).some((note) => note.id === id)) || keys[0];
}

function storageKey(owner) {
  return `orena.quicksheet.notes.v1:${encodeURIComponent(text(owner) || 'local')}`;
}

function readStore(storage, owner) {
  try {
    const raw = storage.getItem(storageKey(owner));
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(storage, owner, store) {
  try {
    storage.setItem(storageKey(owner), JSON.stringify(store));
  } catch {
    /* A device out of storage keeps the note only for this visit. */
  }
}

export function loadNotes(storage, owner, key) {
  const store = readStore(storage, owner);
  const list = store[key];
  return Array.isArray(list) ? list : [];
}

/* The account keeps at most 120 notes of 600 characters per text (D4 I10). */
export const MAX_NOTES_PER_TEXT = 120;

/* Every note made in one text, flat, each with the sentence key it belongs to - the shape the account
   keeps. A note made before this field existed has no text and stays on the device only. */
export function notesForContent(storage, owner, contentId) {
  if (!contentId) return [];
  const store = readStore(storage, owner);
  return Object.entries(store).flatMap(([key, list]) => (Array.isArray(list) ? list : [])
    .filter((note) => note?.content === contentId)
    .map((note) => ({ id: String(note.id), key, type: note.type, text: note.text, at: note.at || '' })));
}

/* The text's notes replaced by exactly this set: every note made in this text is dropped first, then the set is
   written back under its sentence keys. A note the account no longer holds leaves this device too. */
export function setNotesForContent(storage, owner, contentId, incoming) {
  if (!contentId) return;
  const store = readStore(storage, owner);
  for (const key of Object.keys(store)) {
    if (Array.isArray(store[key])) store[key] = store[key].filter((note) => note?.content !== contentId);
  }
  for (const note of Array.isArray(incoming) ? incoming : []) {
    if (!note?.id || !note.key || !NOTE_TYPES.includes(note.type)) continue;
    const list = Array.isArray(store[note.key]) ? store[note.key] : [];
    store[note.key] = [...list, { id: note.id, type: note.type, text: text(note.text).slice(0, 600), at: note.at || '', content: contentId }];
  }
  for (const key of Object.keys(store)) if (Array.isArray(store[key]) && !store[key].length) delete store[key];
  writeStore(storage, owner, store);
}

/* The account's notes for a text merged into this device's (a union by id). Returns how many arrived. */
export function mergeNotes(storage, owner, contentId, incoming) {
  const store = readStore(storage, owner);
  const known = new Set(Object.values(store).flat().filter(Boolean).map((note) => note.id));
  let arrived = 0;
  for (const note of Array.isArray(incoming) ? incoming : []) {
    if (!note?.id || !note.key || known.has(note.id) || !NOTE_TYPES.includes(note.type)) continue;
    const list = Array.isArray(store[note.key]) ? store[note.key] : [];
    store[note.key] = [...list, { id: note.id, type: note.type, text: text(note.text).slice(0, 600), at: note.at || '', content: contentId }];
    arrived += 1;
  }
  if (arrived) writeStore(storage, owner, store);
  return arrived;
}

export function addNote(storage, owner, key, { type, text: body, content = '' }) {
  const kind = NOTE_TYPES.includes(type) ? type : 'factual';
  const value = text(body).slice(0, 600);
  if (!value) return null;
  const store = readStore(storage, owner);
  const list = Array.isArray(store[key]) ? store[key] : [];
  if (content && notesForContent(storage, owner, content).length >= MAX_NOTES_PER_TEXT) return null;
  const note = { id: `${Date.now()}:${Math.random().toString(36).slice(2, 8)}`, type: kind, text: value, at: new Date().toISOString(), ...(content ? { content } : {}) };
  store[key] = [...list, note];
  writeStore(storage, owner, store);
  return note;
}

/* An existing note rewritten in place (LEX-023): same id and time, new text and type, so the account keeps one
   note rather than a copy. Returns the note, or null when it is gone or the text is empty. */
export function updateNote(storage, owner, key, id, { type, text: body }) {
  const value = text(body).slice(0, 600);
  if (!value) return null;
  const store = readStore(storage, owner);
  const list = Array.isArray(store[key]) ? store[key] : [];
  const at = list.findIndex((note) => note.id === id);
  if (at < 0) return null;
  const note = { ...list[at], type: NOTE_TYPES.includes(type) ? type : list[at].type, text: value };
  store[key] = [...list.slice(0, at), note, ...list.slice(at + 1)];
  writeStore(storage, owner, store);
  return note;
}

export function deleteNote(storage, owner, key, id) {
  const store = readStore(storage, owner);
  const list = Array.isArray(store[key]) ? store[key] : [];
  store[key] = list.filter((note) => note.id !== id);
  writeStore(storage, owner, store);
}
