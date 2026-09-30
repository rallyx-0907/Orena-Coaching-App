/* One shared take store for `screens/speak`, `screens/compare` and `screens/attempts` (D-076):
   session-only by default, IndexedDB retention only when the learner opts in
   (`capabilities/speaking-attempts.js`, unchanged - this wraps it, it does not reimplement it).
   A module singleton, not one instance per screen mount: Compare and Attempt History need to see
   a take `screens/speak` just recorded without a network round trip, so the three routes share one
   store keyed by `lineKey(sourceId, lineId)`.

   Every recorded take mints a `take_ref` (Ask Orena's `speaking.compare` surface and D5/E2's
   Attempt History rows both need one stable id per take, and the design draws none) so Compare,
   Attempt History and the agent bridge can all point at the same recording. What
   `capabilities/speaking-attempts.js#createAttemptStore` actually persists per take is its own
   reduced `{text, flagged, offsetMs, durationMs}` shape (D-076's own honesty rule: a reopened
   older attempt shows less than the one just recorded, never an invented per-word score for it) -
   the full `pronunciationView()` result stays in this module's own session-only map, keyed by
   `take_ref`, for as long as this tab remembers it. */
import { createAttemptStore, indexedDbAttempts, bestOf, MAX_PER_LINE } from '../capabilities/speaking-attempts.js';

let store = null;
const rich = new Map(); // take_ref -> the full pronunciationView() result, this tab only
const attemptIds = new Map(); // take_ref -> the id of the audio-free record the server stored for it

function attempts() {
  if (!store) store = createAttemptStore({ local: indexedDbAttempts() });
  return store;
}

export function lineKey(sourceId, lineId) {
  return `${sourceId}#${lineId}`;
}

function mintTakeRef(key) {
  return `${key}::${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

/* `view` is the full `pronunciationView()` result for this take. Returns the minted `take_ref`
   and the line's attempts, newest first. */
export async function recordTake(key, { blob, ms, view }) {
  const take_ref = mintTakeRef(key);
  rich.set(take_ref, view);
  const list = await attempts().add(key, {
    id: take_ref,
    at: Date.now(),
    ms,
    blob,
    overall: view.overall,
    accuracy: view.accuracy,
    fluency: view.fluencyMeasured ? view.fluency : null,
    completeness: view.completeness,
    flagged: view.words.filter((word) => word.flagged).length,
    words: view.words,
  });
  return { take_ref, list };
}

/* The full assessment for a take, only while this tab still has it in memory (typically: the one
   just recorded). `null` for an attempt reopened from a past visit or from IndexedDB retention -
   the caller falls back to the reduced stored shape rather than inventing scores it does not have. */
export function richView(take_ref) {
  return rich.get(take_ref) || null;
}

/* The server's audio-free record for a take, once it exists (it lands a moment after the result
   does). Ask Orena's `attempt_id`; absent when no record was stored. */
export function noteAttemptId(take_ref, attemptId) {
  if (take_ref && attemptId) attemptIds.set(take_ref, attemptId);
}

export function attemptIdOf(take_ref) {
  return attemptIds.get(take_ref) || '';
}

/* A word as a reopened attempt still knows it: the text, whether the provider flagged it and where
   it sat in the take. No score, no miscue type, no phoneme: those were not kept (D-076). */
function reducedWord(word, index) {
  return {
    index,
    text: word.text,
    pinyin: '',
    score: null,
    scoreKnown: false,
    flagged: Boolean(word.flagged),
    errorType: '',
    weakest: null,
    phonemes: [],
    syllables: [],
    offsetMs: word.offsetMs ?? null,
    durationMs: word.durationMs ?? null,
    offsetKnown: Number.isFinite(word.offsetMs) && Number.isFinite(word.durationMs),
    toneTarget: [],
    toneActual: [],
  };
}

/* One take as a `pronunciationView()`-shaped object every Speaking screen reads the same way:
   the full assessment while this tab still holds it (`reduced: false`), otherwise the honest,
   smaller shape a reopened attempt really has (`reduced: true` - the overall score, the flagged
   words and where they sat; every other number is unknown, not zero). */
export function viewOfTake(take) {
  if (!take) return null;
  const full = richView(take.id);
  if (full) return { ...full, reduced: false, words: full.words.map((word) => ({ ...word, scoreKnown: word.scoreMeasured !== false })) };
  const words = (take.words || []).map(reducedWord);
  return {
    measured: true,
    reduced: true,
    synthetic: false,
    overall: take.overall ?? 0,
    accuracy: take.accuracy ?? null,
    fluency: take.fluency ?? 0,
    fluencyMeasured: take.fluency != null,
    completeness: take.completeness ?? null,
    prosody: null,
    timing: null,
    heard: '',
    passedCount: words.filter((word) => !word.flagged).length,
    totalCount: words.length,
    words,
  };
}

export function listTakes(key) {
  return attempts().list(key);
}

export function bestTake(list) {
  return bestOf(list);
}

export const keepRecent = {
  get value() {
    return attempts().keepRecent;
  },
  set(on) {
    return attempts().setKeepRecent(on);
  },
};

export { MAX_PER_LINE };
