/* Word Detail's pure data mapping (D-091): turning the real backend answers - WordDetail.json
   (`POST /api/dictionary/word-detail`), the saved-vocabulary item
   (`GET /api/library/vocabulary`) and the stroke-order payload
   (`GET /api/chinese/stroke-order`) - into the shapes the frame draws (`wdWC`, `wd`, `wdClips`,
   `wdMastery`, the Stroke Practice sheet's `skChars`). No DOM, no fetch, no timers: this is what
   scripts/test_orena_screen_word.mjs exercises directly.

   Rule 40 throughout: a field the backend does not carry is left out of the result rather than
   invented, and every caller checks for that (an empty Deep Word row list means no card at all, an
   empty mastery-evidence list means the empty state, not five placeholders). */

const STAGE_COPY_KEY = {
  New: 'stageNew',
  Learning: 'stageLearning',
  Reinforcing: 'stageReinforcing',
  Available: 'stageAvailable',
};

const HAN = /[㐀-鿿]/;

/* The due-date pure function is shared with `screens/quick-sheet/model.js` (2026-09-29 fix pass:
   the two had drifted into a byte-for-byte copy with divergent callers) - see
   `product/due-schedule.js`'s own header. Re-exported here so this module's existing callers
   (`mapWordCard` below, and this gate's own `import { dueInfo } from '.../word/model.js'`) keep
   working unchanged. */
export { dueInfo } from '../../product/due-schedule.js';
import { dueInfo } from '../../product/due-schedule.js';
import { localizedMeaning } from '../../product/vocabulary-meaning.js';

/* languages-5 / finding A: the one legitimate script check in this build. A saved word carries no
   per-item language field from the backend at all - `SavedWord.language_code`
   (writing_coach/persistence/models.py) exists only to scope the `/api/library/vocabulary` query
   server-side (becoming_library.py's `_row_to_item` never returns it), and the word being viewed
   here may predate the learner's *current* active learning language (a word saved while studying
   Chinese, viewed after switching to English). The backend's own WordDetail answer resolves the
   same way (writing_coach/word_detail.py `script_of`): hanzi when the requested learning language
   is Chinese, or - the same fallback this module uses - when the headword itself contains Han
   characters, so a saved Chinese word still renders correctly even under a stale request language.
   `cardLanguage` turns that script into the actual code kit/lang.js's `langAttr`/`langSpan` take:
   this build has exactly two learning languages (product/languages.js `learningLanguage`), so
   'latin' always means 'en' here - never Vietnamese, which is an interface/support language only,
   not a learning-language option. */
export function cardLanguage(script) {
  return script === 'hanzi' ? 'zh' : 'en';
}

/* languages-4 (2) / finding B.1: the part-of-speech chip's value is mostly the shared local
   tagger's closed label set (writing_coach/linguistic_annotation.py `ALLOWED_POS`: noun/verb/
   adjective/adverb/pronoun/determiner/preposition/conjunction/numeral/particle/auxiliary/
   interjection/classifier/proper_noun/other), reachable through word_detail.py's own lookup path
   - but a saved item's own `part_of_speech` (vocabulary_source_import.py, content-authored free
   text) or an external monolingual dictionary's own wording (reading_lookup.py) is not guaranteed
   to be one of those fifteen. The closed part is mapped to real copy in en/vi/zh (word/copy.js); a
   value outside it cannot be translated - there is no dictionary of an arbitrary source's own
   wording - so it is shown exactly as the backend gave it (`known: false`), for the caller to mark
   `lang="en"` as untranslated content metadata rather than let unlabelled English sit silently
   inside a vi/zh sentence (the same honest choice this pass records for Discover's open `topic`
   field, docs/project/UI_BACKEND_GAPS.md). */
const POS_LABEL_KEY = Object.freeze({
  noun: 'posNoun', verb: 'posVerb', adjective: 'posAdjective', adverb: 'posAdverb',
  pronoun: 'posPronoun', determiner: 'posDeterminer', preposition: 'posPreposition',
  conjunction: 'posConjunction', numeral: 'posNumeral', particle: 'posParticle',
  auxiliary: 'posAuxiliary', interjection: 'posInterjection', classifier: 'posClassifier',
  proper_noun: 'posProperNoun', other: 'posOther',
});

export function posLabel(value, t) {
  const raw = text(value);
  const parts = raw.split(/\s*[\/,;|]\s*/).filter(Boolean);
  const keys = parts.map((part) => POS_LABEL_KEY[part.toLowerCase().replace(/\s+/g, '_')]);
  // A combined value ("noun/verb", V-19) is translated part by part and joined as the language joins a list;
  // a value with any part outside the closed set stays exactly as given, never half-translated.
  if (parts.length && keys.every(Boolean)) return { text: keys.map((key) => t(key)).join(t('posJoin')), known: true };
  return { text: raw, known: false };
}

function text(value) {
  return String(value ?? '').trim();
}

/* A valid `context` for POST /api/dictionary/word-detail must contain `text` (the server rejects
   it otherwise, 422 word_detail_text_not_in_context). The word's own saved source fragment is a
   real sentence when it both exists and actually contains the word; otherwise the word is its own
   (still valid) context - never an invented sentence. */
export function contextFor(word, item) {
  const w = text(word);
  const fragment = text(item?.source_fragment);
  if (fragment && fragment.toLowerCase().includes(w.toLowerCase())) return fragment;
  return w;
}

/* The reading the frame's single `ipa` slot shows: pinyin for Chinese, IPA/phonetic otherwise -
   whichever the lookup actually returned (D7 §2.6: one binding, language-dependent content). */
export function pronunciationOf(detail, item) {
  if (!detail) return text(item?.phonetic);
  if (detail.script === 'hanzi') return text(detail.pinyin) || text(item?.phonetic);
  return text(detail.ipa) || text(item?.phonetic);
}

export function savedTone(saved) {
  return saved
    ? { bg: 'var(--amber-soft)', color: 'var(--amber)' }
    : { bg: 'var(--surface2)', color: 'var(--muted)' };
}

/* 0-4 bars filled, from the real review stage (rule 40: an unsaved/unscheduled word is 0, not a
   guess). */
export function masteryFilled(item) {
  return Math.max(0, Math.min(4, Number(item?.review_stage) || 0));
}

/* The copy key for the real stage label the backend already computed (`STAGE_LABELS` in
   becoming_library.py) - not the frame's own four-item sample enum, which does not name the same
   stages. Empty when there is no saved item to report a stage for. */
export function stageCopyKey(item) {
  return STAGE_COPY_KEY[text(item?.stage_label)] || '';
}

/* The example sentence split around the headword, for the frame's tinted-highlight treatment
   (`exParts`). A word that is not actually in the sentence (or no sentence at all) renders as one
   plain part - never a fabricated match. */
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

/* The word card (`wdWC`): the header, the meaning block, the example and the mastery footer, from
   whichever of the two answers actually carries each field. `detail` may be null (the lookup
   failed); `item` may be null (the word is not in the learner's saved list yet). */
export function mapWordCard(word, { detail = null, item = null, supportLanguage = '' } = {}) {
  // `detail.available === false` (`claim: "word_detail_unavailable"`) means the lookup could
  // not resolve this word at all - but individual fields on `detail` (e.g. `partOfSpeech`, which
  // the backend can still fill from an independent heuristic) can still come back non-empty even
  // then. Treat the whole answer as unusable for the card in that case, the same way the audio
  // button and the stroke sheet already check their own APIs' `available` flags, rather than
  // rendering a fact about a word the backend just said it could not resolve (rule 40).
  const resolvedDetail = detail?.available === false ? null : detail;
  const headword = text(resolvedDetail?.headword) || text(word);
  const pos = text(resolvedDetail?.partOfSpeech) || text(item?.part_of_speech);
  const level = text(item?.level);
  const meaning = text(resolvedDetail?.contextMeaning) || text(item?.definition);
  // The sense's localization for the learner's support language (D-124), never a fixed language.
  const localized = text(localizedMeaning(item, supportLanguage)?.text);
  const support = localized && localized !== meaning ? localized : '';
  const example = text(item?.source_fragment && item.source_fragment !== meaning ? item.source_fragment : '');
  // `item` is the fresher signal once the learner has saved/unsaved in this session (the lookup's
  // own `saved` flag is only as fresh as when it was fetched); on first load, with no local
  // mutation yet, the two must agree anyway. `saved` is a direct saved-terms lookup, independent
  // of whether a meaning was resolved, so it is read off `detail` itself, not `resolvedDetail`.
  const saved = item ? true : Boolean(detail?.saved);
  const tone = savedTone(saved);
  const due = dueInfo(item);
  return {
    word: headword,
    script: resolvedDetail?.script === 'hanzi' || HAN.test(headword) ? 'hanzi' : 'latin',
    ipa: pronunciationOf(resolvedDetail, item),
    pos,
    hasLevel: Boolean(level),
    level,
    meaning,
    hasMeaning: Boolean(meaning),
    support,
    hasSupport: Boolean(support),
    hasExample: Boolean(example),
    exampleParts: highlightExample(example, headword),
    saved,
    savedBg: tone.bg,
    savedColor: tone.color,
    audioUrl: text(resolvedDetail?.audioUrl),
    filled: masteryFilled(item),
    stageKey: stageCopyKey(item),
    due,
    hasSchedule: Boolean(item),
  };
}

/* Deep Word (`wd`): only the rows that have real content. `examples` (real usage sentences the
   explanation returned) stands in for the frame's "Natural patterns" row - the closest of the
   backend's fields to what that label asks for; the other three map one to one. An entirely empty
   result means no card at all (rule 40/44: nothing drawn over nothing). */
export function mapDeepWord(detail) {
  const deeper = detail?.deeper || {};
  const rows = [];
  if (text(deeper.coreIdea)) rows.push({ key: 'deepCoreIdea', value: text(deeper.coreIdea) });
  if (text(deeper.whyHere)) rows.push({ key: 'deepWhyHere', value: text(deeper.whyHere) });
  if (text(deeper.commonMistake)) rows.push({ key: 'deepWatchOut', value: text(deeper.commonMistake) });
  const patterns = (Array.isArray(deeper.examples) ? deeper.examples : [])
    .map(text)
    .filter(Boolean)
    .slice(0, 3)
    .join(' · ');
  if (patterns) rows.push({ key: 'deepPatterns', value: patterns });
  return rows;
}

/* Context clips (`wdClips`): real moments in the listening catalogue, one to one with
   `/clips`'s answer. */
export function mapClip(clip) {
  return {
    text: text(clip?.text),
    source: [text(clip?.title), text(clip?.at)].filter(Boolean).join(' · '),
    seconds: Math.max(0, Number(clip?.seconds) || 0),
    lessonId: text(clip?.lessonId),
    url: text(clip?.url),
    kind: text(clip?.kind),
    startMs: Math.max(0, Number(clip?.startMs) || 0),
    endMs: Math.max(0, Number(clip?.endMs) || 0),
  };
}

export function mapClips(payload) {
  return (payload?.clips || []).map(mapClip).filter((clip) => clip.text);
}

/* Mastery evidence (`wdMastery`): real, dated facts about this one saved word - never a count that
   is zero because nothing happened yet. A freshly saved word has exactly one row (it was saved);
   a word graded and missed a few times has more. Order: most recent kind of fact first, matching
   how the frame reads top to bottom (what happened, then how it is going). */
export function mapMasteryEvidence(item) {
  if (!item) return [];
  const rows = [];
  if (text(item.last_reviewed_at)) {
    rows.push({ key: 'evidenceReviewed', glyph: '↻', bg: 'var(--accent)', date: item.last_reviewed_at });
  }
  if (Number(item.lapse_count) > 0) {
    rows.push({ key: 'evidenceMissed', glyph: '!', bg: 'var(--amber)', n: Number(item.lapse_count) });
  }
  if (Number(item.successful_recalls) > 0) {
    rows.push({ key: 'evidenceRecalled', glyph: '✓', bg: 'var(--green)', n: Number(item.successful_recalls) });
  }
  if (text(item.added_at)) {
    rows.push({ key: 'evidenceSaved', glyph: '+', bg: 'var(--accent)', date: item.added_at, source: text(item.source_kind) });
  }
  return rows.slice(0, 5);
}

/* ---- Stroke Practice sheet ---- */

/* Everything /api/library/vocabulary/restore needs to put a deleted word back exactly as it
   was, schedule included - not a fresh save wearing the same spelling. Undefined/absent fields
   are left out rather than sent as empty strings, so the server's own defaults decide. */
export function restorePayload(item) {
  if (!item) return null;
  const payload = { word: text(item.word) };
  // Every string field RestoreVocabularyIn accepts (writing_coach/becoming_library.py), so an undo
  // puts back the schedule's next_review_at and the catalogue identity, not only the word.
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

/* A saved word's own new-save payload (`POST /api/library/vocabulary`), from the word card as it
   stands - the definition and gloss the learner is actually looking at, so saving from Word
   Detail keeps what it shows rather than re-deriving it. */
export function savePayload(card) {
  return {
    word: text(card?.word),
    phonetic: text(card?.ipa),
    part_of_speech: text(card?.pos),
    definition: text(card?.meaning),
    source_kind: 'dictionary',
  };
}

export function hanziCharsOf(word) {
  return [...text(word)].filter((ch) => HAN.test(ch));
}

/* Which real stroke data goes with each Han character of the word, in the word's own order
   (duplicates included) - the backend's `characters`/`unavailable` split loses position, so this
   re-walks the word and looks each character up by value (a character's strokes do not depend on
   where it sits in the word). A character absent from both lists (the pack does not have it) is
   `available:false`, not a guess. */
export function mapStrokeCharacters(word, payload) {
  const byChar = new Map();
  for (const entry of payload?.characters || []) if (!byChar.has(entry.character)) byChar.set(entry.character, entry);
  return hanziCharsOf(word).map((ch) => {
    const data = byChar.get(ch) || null;
    return { ch, data, available: Boolean(data) };
  });
}
