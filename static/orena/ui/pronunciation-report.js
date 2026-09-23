import { esc } from './html.js';

/* What a pronunciation measurement may say, and what it may not.

   Two different things arrive from the speech services and must never be
   presented as one. Speech recognition says what words it *heard*; pronunciation
   assessment says how a phrase was *pronounced*. A recogniser's transcript, a
   text-similarity percentage or a word-match count is not a pronunciation score,
   and nothing here turns one into the other.

   The sandbox makes the second rule concrete: its provider answers every request
   - including a text file sent as audio - with confident-looking numbers and
   labels itself `score_kind: "synthetic_demo"`. Those are demonstration values,
   so no measurement is shown for them at all. A caveat under a number is not
   enough; a learner reads the number.

   Providers differ, so only dimensions the result actually carries are drawn. */

/* `Number(null)` is 0 and `Number('')` is 0, so coercing would turn a dimension
   the provider did not measure into a confident zero. Only an actual number
   counts as a measurement - the same rule the word timeline keeps. */
const measured = (value) => typeof value === 'number' && Number.isFinite(value);

const DIMENSIONS = [
  ['accuracy_score', 'accuracy'],
  ['fluency_score', 'fluency'],
  ['completeness_score', 'completeness'],
  ['prosody_score', 'prosody'],
];

export function isRealMeasurement(result) {
  if (!result || typeof result !== 'object') return false;
  if (result.score_kind && result.score_kind !== 'measured') return false;
  return DIMENSIONS.some(([key]) => measured(result[key]));
}

/* The words a measurement actually has something to say about - what to work
   on, rather than a number to feel bad about. */
function troubleSpots(c, result, language) {
  const words = (Array.isArray(result?.words) ? result.words : []).filter(
    (word) =>
      word &&
      typeof word.word === 'string' &&
      word.word.trim() &&
      (measured(word.accuracy_score) || String(word.error_type || '').trim()),
  );
  const weak = words
    .filter(
      (word) =>
        (measured(word.accuracy_score) && word.accuracy_score < 80) ||
        !['none', 'None', ''].includes(String(word.error_type || '')),
    )
    .slice(0, 6);
  if (!weak.length) return '';
  return `<p class="speak-verdict">${esc(c.speakStillWobbles || '')}</p><ul class="pronunciation-words">${weak
    .map((word) => {
      const phoneme = (Array.isArray(word.phonemes) ? word.phonemes : [])
        .filter((p) => measured(p?.accuracy_score))
        .sort((a, b) => a.accuracy_score - b.accuracy_score)[0];
      const detail = phoneme?.phoneme ? `/${phoneme.phoneme}/` : String(word.error_type || '');
      return `<li><span lang="${esc(language)}">${esc(word.word)}</span>${detail ? `<small>${esc(detail)}</small>` : ''}</li>`;
    })
    .join('')}</ul>`;
}

/* What comes back is a sentence, not a scorecard (design update 2026-09-20):
   the number, the four dimension bars and the per-word chips are gone. What
   remains is the words that still wobble - the assessment's own, never
   invented - so the learner knows what to say again. */
export function pronunciationReportHtml(c, result, language) {
  if (!isRealMeasurement(result))
    return `<p class="meta">${esc(
      result?.score_kind === 'synthetic_demo' ? c.speakDemoAssessment : c.speakNoAssessment,
    )}</p>`;
  const weak = troubleSpots(c, result, language);
  return `${weak || `<p class="speak-verdict">${esc(c.voiceClear || c.voiceReady)}</p>`}<p class="meta">${esc(c.voiceMeasureNote)}</p>`;
}
