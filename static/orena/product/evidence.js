import {
  evaluateListeningReconstruction,
  listeningReconstructionDiff,
} from '../capabilities/dictation-evaluator.js';
// Adapt existing server evidence contracts without a screen-oriented session.
export function dictationEvidence({ asset, segment, language, previous = {} }) {
  let evidence = {
    asset_id: asset,
    segment_id: segment.segment_id,
    presentation: 'prompt',
    revealed: Boolean(previous.revealed),
    checked_attempt_count: previous.checked_attempt_count || 0,
    best_accuracy_percent: previous.best_accuracy_percent ?? null,
    best_exact: Boolean(previous.best_exact),
    last_answer: previous.last_answer || '',
    last_used_hint: Boolean(previous.last_used_hint),
    last_hint_level: previous.last_hint_level || 0,
  };
  return {
    get value() {
      return { ...evidence };
    },
    compare(answer, { hintLevel = 0 } = {}) {
      const result = evaluateListeningReconstruction({
        source_language: language,
        expected: segment.spoken_text || segment.original_text,
        answer,
      });
      evidence = {
        ...evidence,
        presentation: 'checked',
        checked_attempt_count: Math.min(
          1000,
          evidence.checked_attempt_count + 1,
        ),
        best_accuracy_percent: Math.max(
          evidence.best_accuracy_percent ?? 0,
          result.accuracy_percent,
        ),
        best_exact: evidence.best_exact || result.exact,
        last_answer: answer,
        // The attempt's own fact: no hint, or how far the hint went. It changes no score.
        last_used_hint: hintLevel > 0,
        last_hint_level: Math.max(0, Math.min(3, hintLevel)),
      };
      return {
        result,
        diff: listeningReconstructionDiff({
          source_language: language,
          expected: segment.spoken_text || segment.original_text,
          answer,
        }),
      };
    },
    reveal() {
      evidence = { ...evidence, presentation: 'revealed', revealed: true };
      return this.value;
    },
  };
}

/* The server replaces a segment's record wholesale, so the client is the only
   thing standing between a transient read failure and a learner's lost best
   score. When practice started without the stored record, the local evidence
   counts only this session; fold it into whatever the server actually holds
   rather than writing over it. Never lowers a stored value. */
export function mergeListeningEvidence(stored, local) {
  if (!stored || typeof stored !== 'object') return { ...local };
  const number = (value) =>
    Number.isFinite(Number(value)) ? Number(value) : 0;
  const bestStored = stored.best_accuracy_percent;
  const bestLocal = local.best_accuracy_percent;
  return {
    ...local,
    revealed: Boolean(stored.revealed) || Boolean(local.revealed),
    checked_attempt_count: Math.min(
      1000,
      number(stored.checked_attempt_count) +
        number(local.checked_attempt_count),
    ),
    best_accuracy_percent:
      bestStored == null && bestLocal == null
        ? null
        : Math.max(number(bestStored), number(bestLocal)),
    best_exact: Boolean(stored.best_exact) || Boolean(local.best_exact),
    last_answer: local.last_answer || stored.last_answer || '',
    // The last attempt is this session's: what the local attempt says about its hint replaces the stored one.
    last_used_hint: Boolean(local.last_used_hint),
    last_hint_level: local.last_hint_level || 0,
  };
}

// Capture one recovered baseline for this attempt accumulator. Re-reading a
// record after our own successful write would count those attempts twice.
// Retrying the same snapshot is an idempotent replacement, including when a
// server write succeeded but its response was lost. A failed read can retry.
export function recoverListeningEvidence(read) {
  let baseline;
  return async (local) => {
    if (!baseline)
      baseline = Promise.resolve()
        .then(read)
        .catch((error) => {
          baseline = null;
          throw error;
        });
    return mergeListeningEvidence(await baseline, local);
  };
}
