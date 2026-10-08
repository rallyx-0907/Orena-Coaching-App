/* How closely a learner's take follows the model, measured from the two pitch contours and, where both
   have verified word timing, from when each word is said (frame 16's "Similarity to model" and
   "Intonation"; D-139 HD-7 note, D-141). Pure functions over the contours `capabilities/audio-analysis.js`
   returns: `[{ t, st }]`, semitones against the recording's own median, `st` null where unvoiced.

   Nothing here estimates what it cannot measure: a take or model without enough voice, a model with no
   melody, or words without verified timing give `null`, and the surface then keeps the assessment's own
   numbers and shows no figure of this kind.

   - Intonation (0-100): the correlation of the two melodies after each is stretched over its own voiced
     span (so pace and a low or high voice do not matter), the negative half counted as 0.
     Identical shape 100, opposite shape 0.
   - Timing (0-100): per word, how far the word's start and end sit from the model's, each against its own
     speech span; a word 15 % of the span apart counts as 0. Averaged over the paired words.
   - Similarity (0-100): 0.6 x intonation + 0.4 x timing, only when both are known. */

const POINTS = 100;
const MIN_VOICED = 10; // frames (about 0.1 s) of voice a contour needs to be compared
const MIN_SPAN_S = 0.3;
const FLAT_ST = 0.3; // a melody that never moves more than this standard deviation has no shape to follow
const TIMING_TOLERANCE = 0.15;
export const SIMILARITY_WEIGHTS = Object.freeze({ intonation: 0.6, timing: 0.4 });

const finite = (value) => typeof value === 'number' && Number.isFinite(value);

/* The melody over its voiced span as `count` evenly spaced values (gaps bridged by a straight line), or
   null when there is too little voice to compare. */
export function melody(contour, count = POINTS) {
  const voiced = (Array.isArray(contour) ? contour : []).filter((point) => point && finite(point.t) && finite(point.st));
  if (voiced.length < MIN_VOICED) return null;
  const from = voiced[0].t;
  const to = voiced.at(-1).t;
  if (to - from < MIN_SPAN_S) return null;
  const out = [];
  let at = 0;
  for (let i = 0; i < count; i++) {
    const t = from + ((to - from) * i) / (count - 1);
    while (at < voiced.length - 2 && voiced[at + 1].t < t) at++;
    const a = voiced[at];
    const b = voiced[at + 1];
    const span = b.t - a.t;
    const ratio = span > 0 ? Math.min(1, Math.max(0, (t - a.t) / span)) : 0;
    out.push(a.st + (b.st - a.st) * ratio);
  }
  return out;
}

const mean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;
const spread = (values, centre) => Math.sqrt(mean(values.map((value) => (value - centre) ** 2)));

export function intonation(youContour, modelContour) {
  const you = melody(youContour);
  const model = melody(modelContour);
  if (!you || !model) return null;
  const youMean = mean(you);
  const modelMean = mean(model);
  const modelSpread = spread(model, modelMean);
  if (modelSpread < FLAT_ST) return null;
  const youSpread = spread(you, youMean);
  if (youSpread < FLAT_ST) return 0;
  const covariance = mean(you.map((value, at) => (value - youMean) * (model[at] - modelMean)));
  const r = covariance / (youSpread * modelSpread);
  return Math.round(Math.min(1, Math.max(0, r)) * 100);
}

const timed = (word) => word && finite(word.offsetMs) && finite(word.durationMs) && word.durationMs > 0;

/* `pairs`: `[{ you: { offsetMs, durationMs }, model: { offsetMs, durationMs } }]` for the words both sides
   timed. Needs at least two to say anything about the rhythm. */
export function timingAgreement(pairs) {
  const valid = (Array.isArray(pairs) ? pairs : []).filter((pair) => timed(pair?.you) && timed(pair?.model));
  if (valid.length < 2) return null;
  const frame = (side) => {
    const from = Math.min(...valid.map((pair) => pair[side].offsetMs));
    const to = Math.max(...valid.map((pair) => pair[side].offsetMs + pair[side].durationMs));
    return { from, length: to - from };
  };
  const you = frame('you');
  const model = frame('model');
  if (you.length <= 0 || model.length <= 0) return null;
  const agreements = valid.map((pair) => {
    const start = (pair.you.offsetMs - you.from) / you.length - (pair.model.offsetMs - model.from) / model.length;
    const end = (pair.you.offsetMs + pair.you.durationMs - you.from) / you.length - (pair.model.offsetMs + pair.model.durationMs - model.from) / model.length;
    return Math.max(0, 1 - (Math.abs(start) + Math.abs(end)) / 2 / TIMING_TOLERANCE);
  });
  return Math.round(mean(agreements) * 100);
}

export function similarity(intonationScore, timingScore) {
  if (!finite(intonationScore) || !finite(timingScore)) return null;
  return Math.round(SIMILARITY_WEIGHTS.intonation * intonationScore + SIMILARITY_WEIGHTS.timing * timingScore);
}

/* Everything a take has with the model, or null for each part that cannot be measured. */
export function matchOf({ you, model, pairs = [] } = {}) {
  const shape = intonation(you?.contour, model?.contour);
  const timing = timingAgreement(pairs);
  return { intonation: shape, timing, similarity: similarity(shape, timing) };
}
