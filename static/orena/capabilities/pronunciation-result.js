/* PronunciationResult (docs/design/canonical-ui/data-contracts/PronunciationResult.json) from one
   provider-neutral assessment (`POST /api/speech/pronunciation`).

   This is the only place that reads the server's assessment. Nothing here knows which provider
   answered, and nothing here scores anything itself:

   - "passed" is the provider's own miscue verdict on a word (human decision, 2026-09-23). A word
     the provider flagged (Mispronunciation, Omission, ...) is not passed; Orena sets no threshold.
   - a number the provider did not measure is not a measurement: the canonical component shows 0
     for it (Design Contract rule 40) and `measured` says so. `Number(null)` is 0, so only a real
     number counts.
   - a word's reading (pinyin) comes from the lesson's own aligned reading, never from the
     provider's syllable labels, and `toneTarget` is the tone of that reading. `toneActual` is
     always empty: no provider in use measures pitch, and a phoneme or syllable score is never a
     tone score.
   - a synthetic demo result is never a measurement. */

export const isNumber = (value) => typeof value === 'number' && Number.isFinite(value);
const number = (value) => (isNumber(value) ? Math.round(value) : 0);
const isHan = (text) => /^\p{Script=Han}$/u.test(text);

export function isMeasurement(result) {
  if (!result || typeof result !== 'object' || result.score_kind !== 'measured') return false;
  return ['pron_score', 'accuracy_score', 'fluency_score', 'completeness_score'].some((key) => isNumber(result[key]));
}

const errorKind = (word) => String(word?.error_type || 'None').trim();
export const isFlagged = (word) => !['', 'none'].includes(errorKind(word).toLowerCase());
const isInsertion = (word) => errorKind(word).toLowerCase() === 'insertion';

/* 1-4 from the tone mark of one pinyin syllable, 5 for a neutral (unmarked) one. */
export function toneOf(syllable) {
  const text = String(syllable || '').normalize('NFD');
  if (!/\p{L}/u.test(text)) return null;
  if (text.includes('̄')) return 1;
  if (text.includes('́')) return 2;
  if (text.includes('̌')) return 3;
  if (text.includes('̀')) return 4;
  return 5;
}

/* The lowest-scored unit the provider measured inside a word: phonemes first, syllables if the
   provider gave no phonemes. */
function weakestUnit(word) {
  const units = [
    ...(Array.isArray(word.phonemes) ? word.phonemes.map((unit) => ({ label: unit?.phoneme, score: unit?.accuracy_score })) : []),
  ];
  const pool = units.length
    ? units
    : Array.isArray(word.syllables)
      ? word.syllables.map((unit) => ({ label: unit?.syllable, score: unit?.accuracy_score }))
      : [];
  const scored = pool.filter((unit) => String(unit.label || '').trim() && isNumber(unit.score));
  if (!scored.length) return null;
  const low = scored.reduce((a, b) => (b.score < a.score ? b : a));
  return { label: String(low.label).trim(), score: Math.round(low.score) };
}

/* For a Chinese line, the Han characters of each assessed word are found, in order, in the
   reference, and take the lesson's reading for those characters. A word that cannot be placed
   gets no reading rather than somebody else's. */
function placeReadings(words, reference, readings) {
  const han = [...String(reference || '')].filter(isHan);
  const aligned = Array.isArray(readings) && readings.length === han.length ? readings : null;
  let cursor = 0;
  return words.map((word) => {
    const chars = [...String(word.word || '')].filter(isHan);
    if (!chars.length || !aligned) return [];
    const at = han.join('').indexOf(chars.join(''), cursor);
    if (at < 0) return [];
    cursor = at + chars.length;
    return aligned.slice(at, at + chars.length).map((item) => String(item?.pinyin || item || ''));
  });
}

/* How much longer (positive) or shorter the learner's speech was than the model line, from the
   provider's word timings and the line's own span. Absent unless both are measured. */
function timingDelta(words, modelSpanMs) {
  const said = words.filter((word) => isNumber(word.offset_ms) && isNumber(word.duration_ms));
  if (!said.length || !isNumber(modelSpanMs) || modelSpanMs <= 0) return null;
  const start = Math.min(...said.map((word) => word.offset_ms));
  const end = Math.max(...said.map((word) => word.offset_ms + word.duration_ms));
  if (end <= start) return null;
  return { learnerMs: end - start, modelMs: modelSpanMs, deltaMs: Math.round((end - start - modelSpanMs) / 100) * 100 };
}

export function pronunciationView(result, { language = 'en', readings = [], modelSpanMs = null } = {}) {
  if (!isMeasurement(result)) {
    return {
      measured: false,
      synthetic: result?.score_kind === 'synthetic_demo',
      overall: 0,
      accuracy: 0,
      fluency: 0,
      completeness: 0,
      prosody: null,
      timing: null,
      passedCount: 0,
      totalCount: 0,
      words: [],
    };
  }
  const assessed = (Array.isArray(result.words) ? result.words : []).filter(
    (word) => word && String(word.word || '').trim() && !isInsertion(word),
  );
  const pinyin = language === 'zh' ? placeReadings(assessed, result.reference_text, readings) : assessed.map(() => []);
  const words = assessed.map((word, index) => {
    const syllables = pinyin[index];
    return {
      index,
      text: String(word.word).trim(),
      pinyin: syllables.join(' '),
      score: number(word.accuracy_score),
      scoreMeasured: isNumber(word.accuracy_score),
      flagged: isFlagged(word),
      errorType: errorKind(word),
      weakest: weakestUnit(word),
      phonemes: (word.phonemes || []).filter((unit) => String(unit?.phoneme || '').trim()).map((unit) => ({ label: String(unit.phoneme).trim(), score: isNumber(unit.accuracy_score) ? Math.round(unit.accuracy_score) : null })),
      syllables: (word.syllables || []).filter((unit) => String(unit?.syllable || '').trim()).map((unit) => ({ label: String(unit.syllable).trim(), score: isNumber(unit.accuracy_score) ? Math.round(unit.accuracy_score) : null })),
      toneTarget: syllables.map(toneOf).filter((tone) => tone != null),
      toneActual: [],
    };
  });
  return {
    measured: true,
    synthetic: false,
    overall: number(result.pron_score ?? result.accuracy_score),
    accuracy: number(result.accuracy_score),
    fluency: number(result.fluency_score),
    fluencyMeasured: isNumber(result.fluency_score),
    completeness: number(result.completeness_score),
    prosody: isNumber(result.prosody_score) ? Math.round(result.prosody_score) : null,
    timing: timingDelta(assessed, modelSpanMs),
    passedCount: words.filter((word) => !word.flagged).length,
    totalCount: words.length,
    words,
  };
}
