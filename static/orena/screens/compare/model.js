/* Compare With Model (frame 16 + the embedded `Compare With Model.dc.html`, `#/speak/:id/compare`)
   - pure data shaping. The embedded component's own script is a client-only ASR/pitch prototype
   (SCRATCH/inventory/C5-listening-dictation-speaking.md §5: a from-scratch autocorrelation pitch
   guess, a synthesized "model" contour, five canned demo sentences) - none of that is reproduced
   here. Every number below comes from a take this room already holds: the real assessment
   (`capabilities/pronunciation-result.js#pronunciationView`) and the real decoded-audio pitch
   contour (`capabilities/audio-analysis.js`), never a synthesized stand-in. Nothing here writes a
   verdict about the audio (D-076): a word's status is the assessment's own score and miscue flag,
   and a pitch line is only ever drawn, never described. */
import { contourPolylines } from '../../capabilities/audio-analysis.js';

/* ---- The component's own colour rules (read from its script, not unified with frame 15's) ---- */

/* The ring's colour (`col`): green >= 80, amber >= 60, else red. */
export function ringColor(score) {
  if (score >= 80) return 'var(--green)';
  if (score >= 60) return 'var(--amber)';
  return 'var(--red)';
}

/* The label under the ring (`scoreLabel`): four cut-offs of its own, 90 / 80 / 65. */
export function scoreLabelKey(score) {
  if (score >= 90) return 'labelExcellent';
  if (score >= 80) return 'labelVeryGood';
  if (score >= 65) return 'labelGood';
  return 'labelKeepGoing';
}

/* The line beside the ring (`headline`) - same cut-offs, a sentence about the score only. */
export function headlineKey(score) {
  if (score >= 90) return 'headlineNatural';
  if (score >= 80) return 'headlineClear';
  if (score >= 65) return 'headlineUnderstandable';
  return 'headlineKeepPractising';
}

/* ---- One word, as the tiles and the word detail say it ---- */

/* 'ok' | 'weak' | 'wrong' | 'unclear' - the tile's colour and the detail's pill. From the
   assessment's own facts only: an omitted word is 'unclear' (the provider heard nothing there);
   otherwise the score band frame 15 uses for a word (85 / 65), and a word the provider flagged is
   never better than 'weak'. A word reopened from an older attempt has no score (D-076), only the
   provider's flag. */
export function wordStatus(word) {
  if (!word) return 'ok';
  if (String(word.errorType || '').toLowerCase() === 'omission') return 'unclear';
  if (word.scoreKnown === false) return word.flagged ? 'weak' : 'ok';
  const score = word.score ?? 0;
  if (score >= 85) return word.flagged ? 'weak' : 'ok';
  if (score >= 65) return 'weak';
  return 'wrong';
}

const STATUS = {
  ok: { bg: 'var(--surface2)', ink: 'var(--text)', sub: 'var(--muted)', stroke: 'var(--green)', pillBg: 'var(--green-soft)', pillInk: 'var(--green)', pillKey: 'statusGood' },
  weak: { bg: 'var(--amber-soft)', ink: 'var(--amber)', sub: 'var(--amber)', stroke: 'var(--amber)', pillBg: 'var(--amber-soft)', pillInk: 'var(--amber)', pillKey: 'statusClose' },
  wrong: { bg: 'var(--red-soft)', ink: 'var(--red)', sub: 'var(--red)', stroke: 'var(--red)', pillBg: 'var(--red-soft)', pillInk: 'var(--red)', pillKey: 'statusNeedsWork' },
  unclear: { bg: 'var(--amber-soft)', ink: 'var(--amber)', sub: 'var(--amber)', stroke: 'var(--amber)', pillBg: 'var(--amber-soft)', pillInk: 'var(--amber)', pillKey: 'statusUnclear' },
};
export const statusTone = (status) => STATUS[status] || STATUS.ok;

/* A tile's minimum width (the component's own `minW`): wider for Han characters, and never
   narrower than 116. */
export function tileMinWidth(text, language) {
  const zh = language === 'zh';
  return Math.max(116, Math.max(zh ? 58 : 54, (zh ? [...text].length * 24 : [...text].length * 9) + 26));
}

/* The word detail's panels and Details rows, from one word. Everything here is what the
   assessment measured for it: the score, the miscue flag and type, the weakest sound and each
   sound's score, where the word sits in the take. `pinyin` and `toneTarget` come from the lesson's
   own reading (never the provider's syllables). */
export function wordDetailFor(view, index) {
  const word = view?.words?.[index];
  if (!word) return null;
  const status = wordStatus(word);
  const sounds = (word.phonemes?.length ? word.phonemes : word.syllables || []).map((unit) => ({ label: unit.label, score: unit.score }));
  return {
    index,
    text: word.text,
      pinyin: word.pinyin,
      reading: word.reading || word.pinyin || '',
    score: word.score,
    scoreKnown: word.scoreKnown !== false,
    flagged: word.flagged,
    errorType: word.errorType,
    weakest: word.weakest,
    status,
    tone: statusTone(status),
    toneTarget: word.toneTarget?.length ? word.toneTarget[0] : null,
    sounds,
    offsetMs: word.offsetMs,
    durationMs: word.durationMs,
    offsetKnown: Boolean(word.offsetKnown),
  };
}

/* The first word that is not fine is opened by default (there is something to look at); with
   nothing wrong, the first word (the component's own `defSel`). */
export function defaultWordIndex(view) {
  if (!view?.measured || !view.words?.length) return null;
  const at = view.words.findIndex((word) => wordStatus(word) !== 'ok');
  return at < 0 ? 0 : at;
}

/* ---- The summary's chips and its measured line ---- */

/* Each chip is one thing this line's assessment measured: how many words the provider did not
   pass, the pace against the model line (only when the provider timed the words and the model line
   has a span), prosody (only when the provider returned it - a false 0 as a chip would read as a
   fact). `kind` picks the frame's status glyph: ok / bad / clock / info. */
export function chipsFor(view) {
  const chips = [];
  if (!view?.measured) return chips;
  if (view.totalCount) {
    const failed = view.totalCount - view.passedCount;
    chips.push({ kind: failed ? 'bad' : 'ok', key: failed ? 'chipUnclear' : 'chipClear', params: { n: failed } });
  }
  if (view.timing) {
    const seconds = Math.abs(view.timing.deltaMs / 1000).toFixed(1);
    if (view.timing.deltaMs === 0) chips.push({ kind: 'ok', key: 'chipPaceSame', params: {} });
    else chips.push({ kind: Math.abs(view.timing.deltaMs) <= 500 ? 'ok' : 'clock', key: view.timing.deltaMs > 0 ? 'chipPaceSlower' : 'chipPaceFaster', params: { s: seconds } });
  }
  if (view.prosody != null) chips.push({ kind: view.prosody >= 70 ? 'ok' : 'bad', key: 'chipProsody', params: { n: view.prosody } });
  return chips;
}

/* The line under the chips (`metricLine`): the assessment's own three numbers, each only when it
   is known, plus the seconds of speech when the provider timed the words. */
export function metricLineFor(view) {
  if (!view?.measured) return { parts: [], speechS: null };
  const parts = [];
  if (view.accuracy != null) parts.push({ key: 'metricAccuracy', value: view.accuracy });
  if (view.fluencyMeasured) parts.push({ key: 'metricFluency', value: view.fluency });
  if (view.completeness != null) parts.push({ key: 'metricCompleteness', value: view.completeness });
  return { parts, speechS: view.timing ? Number((view.timing.learnerMs / 1000).toFixed(1)) : null };
}

/* "Model 2.4 s · You 2.7 s" (`axisRight`), only when both are measured. */
export function axisFor(view) {
  if (!view?.timing) return null;
  return { modelS: (view.timing.modelMs / 1000).toFixed(1), youS: (view.timing.learnerMs / 1000).toFixed(1) };
}

/* ---- The chart ---- */

/* The chart's plot area inside its 320x130 viewBox (the component's own gridlines: 20 / 65 / 110,
   labels at x 0, lines from x 40 to 312). */
export const CHART = Object.freeze({ width: 272, height: 90, x: 40, y: 20, range: 8 });

/* One contour as polylines in the plot area (`points` = `audio-analysis.js#contour`'s own
   {t, st}). `from`/`to` (seconds) scope it to a word's window; without them, the whole take.
   `width` is the plot's own width: the word detail's chart is the component's 272, the whole-line
   chart in the summary card is wider. */
export function chartLines(points, { from = 0, to = null, width = CHART.width, range = CHART.range } = {}) {
  if (!points?.length) return [];
  const end = to ?? points[points.length - 1].t;
  return contourPolylines(points, { width, height: CHART.height, range, from, to: end, span: end });
}

export function wordPitchLines(analysis, word, options = {}) {
  if (!word?.offsetKnown || !hasVoice(analysis)) return [];
  const from = Math.max(0, word.offsetMs / 1000);
  const to = from + word.durationMs / 1000;
  return to > from ? chartLines(analysis.contour, { from, to, width: 100, ...options }) : [];
}

/* Keep the prototype's word tiles inside the viewport. Pages use the measured
   tile geometry, and every word stays reachable without horizontal scrolling. */
export function wordPages(words, width, language) {
  const pages = [];
  let page = [], used = 0;
  for (const word of words || []) {
    const size = Math.min(Math.max(1, width), tileMinWidth(word.text, language));
    if (page.length && used + 6 + size > width) { pages.push(page); page = []; used = 0; }
    used += (page.length ? 6 : 0) + size;
    page.push(word);
  }
  if (page.length) pages.push(page);
  return pages;
}

/* Whether a contour has any voiced frame at all: a take of silence draws no line, and says so. */
export const hasVoice = (analysis) => Boolean(analysis?.contour?.some((point) => point.st != null));

/* The stretches of a take where words the provider did not pass sit, as fractions of the take's
   duration, for shading the learner's line (the frame's "Close" / "Needs work" legend). */
export function wordBands(view, durationS) {
  if (!view?.words?.length || !(durationS > 0)) return [];
  return view.words
    .map((word) => {
      const status = wordStatus(word);
      if (status === 'ok' || !word.offsetKnown) return null;
      const from = Math.max(0, word.offsetMs / 1000 / durationS);
      const to = Math.min(1, (word.offsetMs + word.durationMs) / 1000 / durationS);
      return to > from ? { from, to, status } : null;
    })
    .filter(Boolean);
}

/* ---- Playback ---- */

export const PLAYBACK_MODES = Object.freeze(['model_then_you', 'word_by_word', 'model_only', 'you_only']);
export const PLAYBACK_SPEEDS = Object.freeze([0.75, 1, 1.25]);

/* The next speed in the cycle. */
export function nextSpeed(speed) {
  const at = PLAYBACK_SPEEDS.indexOf(speed);
  return PLAYBACK_SPEEDS[(at + 1) % PLAYBACK_SPEEDS.length];
}

/* What the play button plays in a mode: the parts that exist. A reopened attempt without retained
   audio, or a source with no model line, plays what it has (the screen says which). */
export function playPlan(mode, { hasTake, hasWords }) {
  if (mode === 'you_only') return hasTake ? ['you'] : [];
  if (mode === 'model_only') return ['model'];
  if (mode === 'word_by_word') return hasWords && hasTake ? ['words'] : hasTake ? ['model', 'you'] : ['model'];
  return hasTake ? ['model', 'you'] : ['model'];
}

/* The attempt pills (oldest first, "Attempt 1" the first one made) and the crown: the best overall
   score, only when there is more than one attempt to be best of. */
export function pillsFor(takes, selectedId) {
  const best = takes.reduce((top, item) => ((item.overall ?? -1) > (top?.overall ?? -1) ? item : top), null);
  return [...takes].reverse().map((item, at) => ({
    id: item.id,
    n: at + 1,
    score: item.overall ?? null,
    active: item.id === selectedId,
    crown: takes.length > 1 && best?.id === item.id,
  }));
}

/* The tone name key for a pinyin tone number (1-4, 5 neutral): a fact about the reading, not about
   the audio. */
export const toneKey = (tone) => `tone${tone >= 1 && tone <= 5 ? tone : 5}`;
