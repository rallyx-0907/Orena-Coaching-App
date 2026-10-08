/* Pure data mapping for Shadowing (frame 28, E2 §1): Model → Countdown → Speak with the model →
   Result, line by line inside a Listening lesson. No DOM, no fetch, no timers — what
   scripts/test_orena_screen_shadowing.mjs exercises directly.

   The assessment itself is the same provider-neutral, never-invents-a-measurement contract every
   other Speaking surface already uses (`capabilities/pronunciation-result.js#pronunciationView`),
   which already carries each word's own offset/duration (`offsetMs`/`durationMs`/`offsetKnown`,
   read straight off `view.words[i]` the way `screens/compare/model.js` does — no patching here).
   This module only adds what that contract does not carry itself: "Start lag" (`lagMs`, the first
   assessed word's own offset) and the line's own total-time comparison against the model
   (`matchPercent`) — and never a synthetic score (unlike the old prototype's retry-count formula,
   C5 §1, which this build does not reproduce). */
import { isNumber } from '../../capabilities/pronunciation-result.js';

/* The design's own shared speed ladder (`cycleSpeed`: 1 -> 0.75 -> 0.5 -> 1.25 -> 1); every value is
   one `media-player.js#setPlaybackRate` accepts (0.85, the old room's own step, is not one). */
export const SHADOW_RATES = Object.freeze([1, 0.75, 0.5, 1.25]);
export const WAVE_BARS = 40;
export const COUNTDOWN = Object.freeze([3, 2, 1]);

function text(value) {
  return String(value ?? '').trim();
}

export function clock(ms) {
  const seconds = Math.max(0, Math.round(Number(ms) || 0) / 1000);
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

/* GET /api/listening/library/{id} into what this screen needs: a title, the real playback, and
   the lines to shadow. No support/meaning line — the source frame draws none for Shadowing. */
export function mapLesson(payload) {
  const asset = payload?.asset || {};
  const catalog = payload?.catalog || {};
  const spoken = catalog.spoken_text_by_segment || {};
  const segments = (payload?.transcript?.segments || [])
    .slice()
    .sort((a, b) => Number(a.order ?? 0) - Number(b.order ?? 0))
    .map((segment) => ({
      id: text(segment.segment_id),
      startMs: Number(segment.start_ms) || 0,
      endMs: Number(segment.end_ms) || 0,
      text: text(spoken[segment.segment_id]) || text(segment.original_text),
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
  const at = SHADOW_RATES.indexOf(Number(rate));
  return SHADOW_RATES[(at + 1 + SHADOW_RATES.length) % SHADOW_RATES.length] ?? SHADOW_RATES[0];
}

/* Start lag: the first assessed word's own offset into the take — real only when the provider
   timed at least one word. */
export function lagMs(view) {
  const known = view.words.filter((word) => isNumber(word.offsetMs));
  return known.length ? Math.min(...known.map((word) => word.offsetMs)) : null;
}

/* How closely the total time spent speaking matched the model line's own span - straight from
   `view.timing` (already real-or-null, never invented). */
export function matchPercent(timing) {
  if (!timing || !(timing.modelMs > 0)) return null;
  return Math.max(0, Math.min(100, Math.round(100 - (Math.abs(timing.deltaMs) / timing.modelMs) * 100)));
}

/* Stat-tile values: an em dash for "not measured" (rule 40), never a guessed number. The lag is
   shown as the frame draws it, a signed number of seconds ("+0.48"); the unit is the caller's copy. */
export function lagSeconds(ms) {
  return ms == null ? null : `+${(Math.max(0, ms) / 1000).toFixed(2)}`;
}

/* Seconds elapsed while recording, one decimal ("2.3"), as the frame's recording line draws it. */
export function elapsedSeconds(ms) {
  return (Math.max(0, Number(ms) || 0) / 1000).toFixed(1);
}

export function percentLabel(pct) {
  return pct == null ? '—' : `${pct}%`;
}

const ERROR_KEY = Object.freeze({
  mispronunciation: 'errorMispronunciation',
  omission: 'errorOmission',
  unexpectedbreak: 'errorUnexpectedBreak',
  missingbreak: 'errorMissingBreak',
  monotone: 'errorMonotone',
});

export function errorLabelKey(errorType) {
  return ERROR_KEY[text(errorType).toLowerCase()] || 'errorOther';
}

/* "One thing to fix": the single lowest-scored flagged word, real from the same assessment the
   result ring already shows — never a second, invented judgement. */
export function issueWord(view) {
  const flagged = (view?.words || []).filter((word) => word.flagged);
  if (!flagged.length) return null;
  return flagged.reduce((low, word) => (word.score < low.score ? word : low));
}

const PHASE_LABEL_KEY = Object.freeze({
  idle: 'phaseIdle',
  model: 'phaseModel',
  count: 'phaseCount',
  speak: 'phaseSpeak',
  processing: 'phaseProcessing',
  result: 'phaseResult',
});
/* The phase label's ink, from the design's five-state map (`shPhase`): idle muted, the model
   accent, the countdown amber, speaking red, the result green (processing, which the frame does not
   name, is the quiet one). The class each becomes lives in the stylesheet, on tokens. */
const PHASE_TONE = Object.freeze({
  idle: 'muted',
  model: 'accent',
  count: 'amber',
  speak: 'red',
  processing: 'muted',
  result: 'green',
});

export function phaseLabelKey(phase) {
  return PHASE_LABEL_KEY[phase] || PHASE_LABEL_KEY.idle;
}

export function phaseTone(phase) {
  return PHASE_TONE[phase] || PHASE_TONE.idle;
}

/* The bars are lit while the model plays or the learner speaks, dim otherwise (`shWaveOp`), and red
   only while speaking (`shWaveColor`). */
export function waveState(phase) {
  return { active: phase === 'model' || phase === 'speak', speaking: phase === 'speak' };
}

/* The frame's decoration (`spWave` with no recording seconds): a fixed sine of heights and delays -
   not a level meter and never presented as one. */
export function waveBars() {
  return Array.from({ length: WAVE_BARS }, (_, at) => ({
    height: Math.round(25 + Math.abs(Math.sin(at * 1.3)) * 75),
    delay: (at * 41) % 700,
  }));
}

/* The bars while the learner speaks: the microphone's own level per bar (0-1), floored at 6% so a
   silent room is a flat row, not a gap. Real levels only - nothing here invents a shape. */
export function levelHeights(levels) {
  return Array.from({ length: WAVE_BARS }, (_, at) => Math.max(6, Math.round(Math.min(1, Math.max(0, Number(levels?.[at]) || 0)) * 100)));
}

/* `GET /api/listening/shadowing-progress` (scripts/fixtures/api/listening_shadowing_progress.json):
   one row per shadowed segment, `completed_rounds` the count Progress already reads. The map a new
   round adds one to (`POST` carries the running total, clamped to what the API accepts). */
export const MAX_ROUNDS = 1000;

export function roundsBySegment(rows) {
  const map = new Map();
  for (const row of rows || []) {
    const id = text(row?.segment_id);
    if (id) map.set(id, Math.max(0, Math.min(MAX_ROUNDS, Number(row.completed_rounds) || 0)));
  }
  return map;
}

export function nextRounds(map, segmentId) {
  return Math.min(MAX_ROUNDS, (map?.get(segmentId) || 0) + 1);
}
