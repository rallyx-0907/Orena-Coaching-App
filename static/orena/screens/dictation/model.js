/* Pure data mapping for Dictation (frame 07, D4): one Listening segment at a time, Play → Type →
   Hint (optional) → Check → Compare → Retry/Next. No DOM, no fetch, no timers - what
   scripts/test_orena_screen_dictation.mjs exercises directly.

   The comparison and evidence math are NOT reimplemented here: they are the same pure,
   already-tested modules the old Dictation panel used (`capabilities/dictation-result.js`,
   `capabilities/dictation-hints.js`, `product/evidence.js`) - this module only shapes their output
   into what the new, standalone frame draws.

   The hint ladder is the design's (state script `giveHint`, three taps, then "Hint 3/3 used"):
   level 1 word shapes, level 2 first letters, level 3 some words revealed, each drawn on the
   frame's own "Live check" strip (`dLiveOn`: on while a hint is in use and the line is unchecked).
   The strip is built on `wordProgress` (reach-limited: a word the learner has not reached is never
   confirmed, and a word they typed wrong is never handed back whole - the same principle
   `dictation-hints.js` states, and the design brief's "a wrong word is not fully exposed merely
   because the learner asks for a hint"). The design's own prototype reveals every word at level 3;
   the note beside the button says "some words revealed", so this build reveals some: every third
   word not yet earned and not attempted wrong. */
import { dictationResult, verdictOf } from '../../capabilities/dictation-result.js';
import { listeningUnits } from '../../capabilities/dictation-evaluator.js';
import { hintTokens, wordProgress } from '../../capabilities/dictation-hints.js';

/* The design's shared speed ladder (`cycleSpeed`: 1 -> 0.75 -> 0.5 -> 1.25 -> 1); every value is one
   `media-player.js#setPlaybackRate` accepts. */
export const DICTATION_RATES = Object.freeze([1, 0.75, 0.5, 1.25]);
/* Three taps, then "Hint 3/3 used" (`giveHint`: Math.min(3, level + 1)). The evidence API accepts
   0-3 (`last_hint_level`, writing_coach/listening_api.py). */
export const MAX_HINT_LEVEL = 3;
export const WAVE_BARS = 32;
const MASK = '·';

function text(value) {
  return String(value ?? '').trim();
}

/* `M:SS`, tabular - the clip's own elapsed/segment-length labels. */
export function clock(ms) {
  const seconds = Math.max(0, Math.round(Number(ms) || 0) / 1000);
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

/* GET /api/listening/library/{id} (scripts/fixtures/api/listening_library_lesson.*.json) into what
   this screen needs: a title, the real playback, and the segments to dictate - the same
   `spoken_text || original_text` target `product/evidence.js#dictationEvidence` already compares
   against, so a segment's saved evidence and this screen's own check agree on what was dictated. */
export function mapLesson(payload) {
  const asset = payload?.asset || {};
  const catalog = payload?.catalog || {};
  const spoken = catalog.spoken_text_by_segment || {};
  const support = new Map();
  for (const row of payload?.translations || []) {
    const id = text(row?.segment_id);
    if (id) support.set(id, text(row?.translated_meaning));
  }
  const segments = (payload?.transcript?.segments || [])
    .slice()
    .sort((a, b) => Number(a.order ?? 0) - Number(b.order ?? 0))
    .map((segment) => ({
      id: text(segment.segment_id),
      startMs: Number(segment.start_ms) || 0,
      endMs: Number(segment.end_ms) || 0,
      text: text(spoken[segment.segment_id]) || text(segment.original_text),
      support: support.get(text(segment.segment_id)) || '',
    }))
    .filter((segment) => segment.id && segment.text);
  return {
    id: text(catalog.lesson_id) || text(asset.asset_id),
    assetId: text(asset.asset_id),
    title: text(catalog.title) || text(asset.title),
    language: text(catalog.language) || text(asset.source_language) || 'en',
    playback: payload?.playback || null,
    segments,
  };
}

/* The segment to start on: a caller's own `seg` query param when it names a real segment of this
   lesson (the Listening Workspace's "Dictation" hand-off to a specific line), else the first. */
export function startIndex(segments, requestedId) {
  if (!requestedId) return 0;
  const at = (segments || []).findIndex((segment) => segment.id === requestedId);
  return at >= 0 ? at : 0;
}

export function rateLabel(rate) {
  const value = Number(rate) || 1;
  return `${value}×`;
}

export function nextRate(rate) {
  const at = DICTATION_RATES.indexOf(Number(rate));
  return DICTATION_RATES[(at + 1 + DICTATION_RATES.length) % DICTATION_RATES.length] ?? DICTATION_RATES[0];
}

/* The bars under the player are decoration, exactly as the frame draws them (`waveBars`: a fixed,
   segment-seeded sine of heights and delays) - not a level meter and never presented as one. */
export function waveBars(seed = 0) {
  return Array.from({ length: WAVE_BARS }, (_, at) => ({
    height: Math.round(30 + Math.abs(Math.sin(at * 1.7 + (Number(seed) || 0))) * 70),
    delay: (at * 37) % 600,
  }));
}

/* `ListeningProgressIn` (writing_coach/listening_api.py) keyed by segment, one row per segment
   already checked in an earlier session - the map the dots and the evidence controller read from. */
export function progressBySegment(records) {
  const map = new Map();
  for (const item of records || []) {
    const id = text(item?.segment_id);
    if (id) map.set(id, item);
  }
  return map;
}

/* How far a segment has got: `exact` (its check matched every word), `partial` (checked, not
   exact) or `none` - from this session's own latest check when there is one, else the saved record
   (`best_exact`/`checked_attempt_count`). Never a guess from navigation position (rule 40). */
export function segmentState(record, local) {
  if (local) return local.exact ? 'exact' : 'partial';
  if (!record || !(Number(record.checked_attempt_count) > 0)) return 'none';
  return record.best_exact ? 'exact' : 'partial';
}

/* The frame's dots (`dDots`): the current segment is the accent, a checked one green (exact) or
   amber (partial), the rest the plain track. */
export function dotStates(segments, byId, localById, index) {
  return (segments || []).map((segment, at) => {
    if (at === index) return 'current';
    return segmentState(byId?.get(segment.id), localById?.get(segment.id));
  });
}

export function doneCount(segments, byId, localById) {
  return (segments || []).filter((segment) => segmentState(byId?.get(segment.id), localById?.get(segment.id)) !== 'none').length;
}

/* The evidence a checked segment carries into `dictationEvidence({..., previous})` - exactly the
   `ListeningProgressIn` fields, nothing this screen invents. */
export function previousEvidence(record) {
  if (!record) return {};
  return {
    revealed: Boolean(record.revealed),
    checked_attempt_count: Number(record.checked_attempt_count) || 0,
    best_accuracy_percent: record.best_accuracy_percent ?? null,
    best_exact: Boolean(record.best_exact),
    last_answer: text(record.last_answer),
    last_used_hint: Boolean(record.last_used_hint),
    last_hint_level: Number(record.last_hint_level) || 0,
  };
}

/* The words of a line as the learner and the transcript actually spell them (case, apostrophes
   kept): the evaluator compares normalised units, but a chip shows what was written. Used only when
   it lines up one-to-one with the units; otherwise the units themselves are shown. */
function surfaceWords(line, language) {
  return hintTokens(line, language)
    .filter((token) => token.word)
    .map((token) => token.text);
}

/* One check: the real comparison (`dictationResult`), never reimplemented here. The evaluator
   itself refuses an empty answer (there is nothing to align) - an honest "everything is missing"
   result, real for a blank submission, not a fabricated one. */
export function checkAnswer({ expected, answer, language }) {
  const trimmed = text(answer);
  if (!trimmed) {
    const units = listeningUnits(expected, language);
    return {
      lineIndex: 0,
      lineTotal: 1,
      original: expected,
      originalPinyin: '',
      attempt: '',
      score: 0,
      exact: false,
      correctCount: 0,
      totalCount: units.length,
      hint: { level: 0, revealed: [], charTotal: 0, charRevealed: 0 },
      marks: units.map((word) => ({ kind: 'missing', from: null, to: word })),
      diffs: units.map((word) => ({ kind: 'missing', from: null, to: word, note: '' })),
    };
  }
  return dictationResult({ lineIndex: 0, lineTotal: 1, expected, spoken: expected, answer: trimmed, language });
}

/* The frame's score (`dScore`: "matched/total") and its three-tier note (`dScoreNote`): every word,
   close (0.7 or better), or replay. `correct` counts the units the comparison matched. */
export function scoreOf(result) {
  const total = Number(result.totalCount) || 0;
  const correct = result.marks.filter((mark) => mark.kind === 'correct').length;
  const tier = result.exact ? 'exact' : total > 0 && correct / total >= 0.7 ? 'close' : 'again';
  return { correct, total, tier };
}

const SCORE_NOTE_KEY = Object.freeze({ exact: 'scoreNoteExact', close: 'scoreNoteClose', again: 'scoreNoteAgain' });

export function scoreNoteKey(tier) {
  return SCORE_NOTE_KEY[tier] || SCORE_NOTE_KEY.again;
}

/* "You wrote" / "Transcript" chips from the same marks: a mark with no `from` (missing) never
   appears on the "you wrote" side, and one with no `to` (extra) never appears on the transcript
   side - each side shows only the tokens it actually has. Kinds follow the design's `tok()`: a
   matched token is plain, an unmatched one on the learner's side is `bad`, on the transcript's
   side `fix`. */
export function chipsFor(result, { expected = '', answer = '', language = 'en' } = {}) {
  const mineMarks = result.marks.filter((mark) => mark.from != null);
  const srcMarks = result.marks.filter((mark) => mark.to != null);
  const written = surfaceWords(answer, language);
  const spelled = surfaceWords(expected, language);
  const mineWords = written.length === mineMarks.length ? written : null;
  const srcWords = spelled.length === srcMarks.length ? spelled : null;
  const mine = mineMarks.map((mark, at) => ({ text: mineWords ? mineWords[at] : mark.from, kind: mark.kind === 'correct' ? 'correct' : 'bad' }));
  const src = srcMarks.map((mark, at) => ({ text: srcWords ? srcWords[at] : mark.to, kind: mark.kind === 'correct' ? 'correct' : 'fix' }));
  return { mine, src, mineEmpty: mine.length === 0 };
}

export { verdictOf };

/* The label beside the Hint button: a fixed category for the current level, never the answer's own
   text (design: `hintNote`, always present, even before a hint is asked for). */
export function hintNoteKey(level, language = 'en') {
  // A Chinese lesson's second rung reveals each word's first character, not first letters (L-05).
  const han = language === 'zh';
  if (level <= 0) return han ? 'hintNoteStartHan' : 'hintNoteStart';
  if (level === 1) return 'hintNoteShapes';
  if (level === 2) return han ? 'hintNoteLettersHan' : 'hintNoteLetters';
  return 'hintNoteWords';
}

/* Which label the Hint button carries: "Hint", "More hint (2/3)", "More hint (3/3)", "Hint 3/3 used". */
export function hintButton(level) {
  const at = Math.max(0, Math.min(MAX_HINT_LEVEL, Math.round(Number(level) || 0)));
  if (at <= 0) return { key: 'hintGive', values: {}, disabled: false };
  if (at >= MAX_HINT_LEVEL) return { key: 'hintMaxed', values: { n: MAX_HINT_LEVEL, total: MAX_HINT_LEVEL }, disabled: true };
  return { key: 'hintMore', values: { n: at + 1, total: MAX_HINT_LEVEL }, disabled: false };
}

/* Which expected words belong together on the strip: a word each in a spaced language; in Chinese,
   where the evaluator's unit is one character, the language's own word boundaries (`Intl.Segmenter`)
   so a hint is "the first character of a word", never a single character given away whole. Falls
   back to one character each when the runtime has no segmenter or it does not line up. */
function wordGroups(line, language, count) {
  const single = Array.from({ length: count }, (_, at) => [at]);
  if (language !== 'zh' || typeof Intl === 'undefined' || typeof Intl.Segmenter !== 'function') return single;
  const groups = [];
  let at = 0;
  for (const part of new Intl.Segmenter('zh', { granularity: 'word' }).segment(String(line ?? ''))) {
    if (!part.isWordLike) continue;
    const size = hintTokens(part.segment, 'zh').filter((token) => token.word).length;
    if (!size) continue;
    groups.push(Array.from({ length: size }, (_, offset) => at + offset));
    at += size;
  }
  return at === count ? groups : single;
}

function commonPrefix(a, b) {
  const left = [...String(a ?? '')].map((c) => c.toLowerCase());
  const right = [...String(b ?? '')].map((c) => c.toLowerCase());
  let at = 0;
  while (at < left.length && at < right.length && left[at] === right[at]) at += 1;
  return at;
}

/* What the learner has actually reached on each expected word (`wordProgress`, reach-limited),
   grouped into the strip's slots: `found` (typed it all correctly), `earned` (leading characters
   typed correctly), `wrong` (they typed something for it that is not it). */
export function liveSlots({ expected, answer, language }) {
  const progress = wordProgress({ expected, answer, source_language: language });
  const spelled = surfaceWords(expected, language);
  const words = spelled.length === progress.length ? spelled : progress.map((entry) => entry.word);
  return wordGroups(expected, language, words.length).map((indices) => {
    const parts = indices.map((at) => progress[at]);
    const surface = indices.map((at) => words[at]).join('');
    const found = parts.every((part) => part.found);
    if (indices.length === 1) {
      const attempt = parts[0].attempt || '';
      const earned = found ? [...surface].length : commonPrefix(attempt, surface);
      return { text: surface, found, earned, wrong: !found && [...attempt].length > earned };
    }
    let earned = 0;
    while (earned < parts.length && parts[earned].found) earned += 1;
    return { text: surface, found, earned, wrong: !found && Boolean(parts[earned]?.attempt) };
  });
}

/* The strip at a hint level: a found word shows whole (`ok`); an unfound one shows its shape with
   what the learner has earned and what the level offers - level 2 the first character (never when
   that would be the whole word), level 3 also every third word whole, unless the learner already
   typed something wrong for it. `kind` drives the chip colour (design `dLive`). */
export function liveView({ expected, answer, language, level }) {
  const at = Math.max(0, Math.min(MAX_HINT_LEVEL, Math.round(Number(level) || 0)));
  const slots = liveSlots({ expected, answer, language });
  const chips = slots.map((slot, position) => {
    if (slot.found) return { text: slot.text, kind: 'ok' };
    const characters = [...slot.text];
    let shown = slot.earned;
    if (at >= 3 && position % 3 === 1 && !slot.wrong) shown = characters.length;
    else if (at >= 2 && characters.length > 1) shown = Math.max(shown, 1);
    shown = Math.min(shown, characters.length);
    return {
      text: characters.slice(0, shown).join('') + MASK.repeat(characters.length - shown),
      kind: slot.wrong ? 'wrong' : slot.earned > 0 ? 'partial' : 'blank',
    };
  });
  return { chips, found: chips.filter((chip) => chip.kind === 'ok').length, total: chips.length };
}
