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

/* When this word next comes due, from the real schedule - `null` when there is none to report
   (a word that was never saved, or a payload with no next_review_at) so the caller can leave the
   whole due line out rather than showing an invented date. */
export function dueInfo(item, now = Date.now()) {
  if (!item) return null;
  const raw = text(item.next_review_at);
  if (!raw) return null;
  const at = Date.parse(raw);
  if (!Number.isFinite(at)) return null;
  const days = Math.ceil((at - now) / 86400000);
  if (item.due || days <= 0) return { key: 'dueToday' };
  return { key: 'dueInDays', n: Math.max(1, days) };
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
export function mapWordCard(word, { detail = null, item = null } = {}) {
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
  const support = text(item?.translation_vi);
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
  const strings = ['phonetic', 'part_of_speech', 'definition', 'translation_vi', 'added_at', 'source_fragment', 'source_kind', 'focus_note', 'last_reviewed_at'];
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
    translation_vi: text(card?.support),
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
