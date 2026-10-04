/* Scripted Pronunciation (frame 15, `#/speak/:id`) - pure data shaping. No DOM, no copy text:
   `screen.js` turns this into markup, `copy.js` supplies the words. */
import { lineUnits, placeWords } from '../../product/speaking-line.js';

/* The three colour rules frame 15 draws, each with its own thresholds (read from the source's own
   bindings, not unified: `scoreColor` for a word's underline and a metric's fill, the ring's own
   3-band tone, and the verdict's two cut-offs). Tokens only - a colour never leaves here as a
   literal. */

/* A word's underline and a metric's fill (`scoreColor`): green >= 85, amber >= 65, else red. */
export function scoreBand(score) {
  if (score >= 85) return 'good';
  if (score >= 65) return 'ok';
  return 'weak';
}
const SCORE_INK = { good: 'var(--green)', ok: 'var(--amber)', weak: 'var(--red)' };
export const scoreInk = (score) => SCORE_INK[scoreBand(score)];
export const bandInk = (band) => SCORE_INK[band] || SCORE_INK.weak;

/* The result ring and the Attempt History score tile (`spRing`, `ahRows.tileBg`): green >= 85,
   accent >= 70, else amber. */
export function ringBand(score) {
  if (score >= 85) return 'good';
  if (score >= 70) return 'ok';
  return 'weak';
}
export function ringTone(score) {
  const band = ringBand(score);
  if (band === 'good') return { bg: 'var(--green-soft)', ink: 'var(--green)' };
  if (band === 'ok') return { bg: 'var(--accent-soft)', ink: 'var(--accent)' };
  return { bg: 'var(--amber-soft)', ink: 'var(--amber)' };
}

/* The verdict under "Attempt N" (`spAtt.verdict`): three fixed labels on the same 85 / 70 cut-offs
   as the ring. Says something about the score only - never a written judgement of the audio. */
export function verdictKey(score) {
  if (score >= 85) return 'verdictClear';
  if (score >= 70) return 'verdictUnderstandable';
  return 'verdictNeedsWork';
}

/* The token strip: `lineUnits` gives the tappable pieces, `placeWords` lays the last result's
   per-word scores over them. Before any result, or for the punctuation-only pieces, a token
   carries no score treatment at all - never a guessed one. */
export function tokenStrip(text, language, view) {
  const units = lineUnits(text, language);
  if (!view?.measured) return units.map((unit) => ({ ...unit, wordIndex: null, flagged: false, band: null }));
  const placed = placeWords(text, view.words, language);
  return units.map((unit) => {
    if (!unit.unit) return { ...unit, wordIndex: null, flagged: false, band: null };
    const at = placed.findIndex((range) => range && unit.start >= range.start && unit.end <= range.end);
    if (at < 0) return { ...unit, wordIndex: null, flagged: false, band: null };
    const word = view.words[at];
    // A word reopened from an older attempt has no score, only the provider's flag: it is marked
    // by that flag alone (amber = not passed, green = passed), never by a number it does not have.
    const band = word.scoreKnown === false ? (word.flagged ? 'ok' : 'good') : scoreBand(word.score);
    return { ...unit, wordIndex: at, flagged: word.flagged, band };
  });
}

/* The tip panel: the single worst-scoring flagged word, with its weakest measured unit - the real
   equivalent of the source's `spTip` (D5 §2: "Word+IPA ... then '· {{spTip.text}}'"). `null` when
   nothing is flagged (or nothing has been attempted yet), never a guessed coaching line. */
export function tipFor(view) {
  if (!view?.measured) return null;
  const flagged = view.words.filter((word) => word.flagged);
  if (!flagged.length) return null;
  const worst = flagged.reduce((a, b) => ((b.score ?? 100) < (a.score ?? 100) ? b : a));
  return { index: worst.index, word: worst.text, pinyin: worst.pinyin, errorType: worst.errorType, weakest: worst.weakest };
}

/* The inline token-detail panel for a tapped word. */
export function detailFor(view, index) {
  const word = view?.words?.[index];
  if (!word) return null;
  return {
    index,
    word: word.text,
    pinyin: word.pinyin,
    score: word.score,
    scoreKnown: word.scoreKnown !== false,
    flagged: word.flagged,
    errorType: word.errorType,
    weakest: word.weakest,
    ink: word.scoreKnown === false ? (word.flagged ? 'var(--amber)' : 'var(--green)') : scoreInk(word.score),
  };
}

/* The three fixed metric cells the frame always draws (D5 §2: "hint-placeholder-count='3'") -
   Accuracy / Fluency / Completeness (frame 15's `spMetrics`), each the real measured value or null
   when the provider did not return it (shown as unavailable), never omitted (the grid's own shape is fixed at
   3). A reopened attempt (`view.reduced`) knows only its overall score: it draws no metric cells
   rather than three zeros that were measured and simply not kept. */
export function metricsFor(view) {
  if (!view?.measured || view.reduced) return [];
  const cells = [
    { key: 'accuracy', value: view.accuracy },
    { key: 'fluency', value: view.fluencyMeasured ? view.fluency : null },
    { key: 'completeness', value: view.completeness },
  ];
  return cells.map((cell) => ({ ...cell, ink: cell.value == null ? 'var(--muted)' : scoreInk(cell.value) }));
}

/* The state pill above the mic (`spStateBg/Color/Label`): idle and a finished take both read
   "Ready" (frame 15 has no separate "assessed" state), recording is red, scoring is accent. */
export function recorderState(phase) {
  if (phase === 'recording') return { key: 'recording', bg: 'var(--red-soft)', ink: 'var(--red)' };
  if (phase === 'processing') return { key: 'scoring', bg: 'var(--accent-soft)', ink: 'var(--accent)' };
  return { key: 'ready', bg: 'var(--surface2)', ink: 'var(--muted)' };
}

/* The caption under the mic (`spRecLabel`) says what tapping it does next: record, record again
   once there is a result, and nothing while a take is being scored (the pill already says so). */
export function recCaptionKey(phase, hasResult) {
  if (phase === 'recording') return 'captionRecording';
  if (phase === 'processing') return '';
  return hasResult ? 'captionAgain' : 'captionIdle';
}

/* A take failure, mapped to one of `screens/mic/sheet.js`'s post-recording states - never a raw
   error string. `service`/`unavailable`/`too_long`/`line_invalid`/`audio_unsupported` all read as
   "the service", the mic sheet's `provider` state; anything about the network is `offline`; a
   learner outcome (no speech / too short) is `notheard`. `microphone` is handled before a take is
   even attempted (`micGate`), so it is not mapped here. */
export function micStateFor(failureKind) {
  if (failureKind === 'no_speech' || failureKind === 'too_short') return 'notheard';
  if (failureKind === 'offline') return 'offline';
  return 'provider';
}

/* Attempt count and "Attempt N" number for the result header, from this line's own take list
   (newest first, `product/take-store.js#listTakes`). */
export function attemptOrdinal(list, take_ref) {
  const index = list.findIndex((item) => item.id === take_ref);
  return index < 0 ? list.length : list.length - index;
}

/* `mm:ss`, the pill's own clock while recording. */
export function clockLabel(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

/* The 40 waveform bars: while nothing is being said they rest in the frame's own pattern (its
   `25 + |sin(i * 1.3)| * 75` percent, opacity .2 - a still drawing, not a measurement); while
   recording they are the microphone's real level, newest on the right. */
export const WAVE_BARS = 40;
export function restingWave() {
  return Array.from({ length: WAVE_BARS }, (_, i) => Math.round(25 + Math.abs(Math.sin(i * 1.3)) * 75));
}
export function liveWave(levels) {
  return Array.from({ length: WAVE_BARS }, (_, i) => Math.max(6, Math.round(Math.min(1, Math.max(0, Number(levels[i]) || 0)) * 100)));
}

/* "Today 08:05": the day (relative, in the interface language) and the time. The day word is
   dropped for an attempt of an older day, which then shows its date instead. */
export function whenLabel(at, locale, now = Date.now()) {
  const date = new Date(at);
  const time = date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
  const same = new Date(now).toDateString() === date.toDateString();
  if (same) {
    let day = '';
    try {
      day = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' }).format(0, 'day');
    } catch {
      day = '';
    }
    return day ? `${day.charAt(0).toLocaleUpperCase(locale)}${day.slice(1)} ${time}` : time;
  }
  return `${date.toLocaleDateString(locale, { month: 'short', day: 'numeric' })} ${time}`;
}
