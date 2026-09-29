/* One recorder for every Speaking room that records a line (`screens/speak`, and Compare With
   Model's own record card - the frame draws a recorder in both): the take
   (`capabilities/speaking-take.js`, unchanged), the microphone's live level, the clock, the stop at
   the provider's limit, and what a finished take becomes - this line's attempt in
   `product/take-store.js`, one task in the session ledger, and the id of the record the server
   keeps. No DOM and no words: the screen paints whatever this reports and decides how to say a
   failure.

   A finished take is turned into an attempt exactly once. The take controller emits its state
   again when the audio-free record has been saved (`kept`, `attemptId`), and that second emission
   carries the same result - reading it as a new take was recording every attempt twice. */
import { createSpeakingTake, TAKE, MAX_TAKE_MS } from '../capabilities/speaking-take.js';
import { createLocalAudioRecorder } from '../capabilities/audio-recorder.js';
import { watchMicrophone } from '../capabilities/mic-readiness.js';
import { pronunciationView } from '../capabilities/pronunciation-result.js';
import { recordTake, noteAttemptId } from './take-store.js';
import { logSpeakingTask } from './speaking-session.js';

export { TAKE, MAX_TAKE_MS };

const BARS = 40;

/* `source` is what `product/speaking-source.js` resolves; `key` its `lineKey`. `facts(view)` gives
   the ledger entry's own facts (the screen owns their labels). `on` callbacks:
   `change(state)` after every change, `failure(error)` once per failed take. */
export function createSpeakingRecorder({
  api,
  source,
  key,
  language,
  facts = () => [],
  kind = 'scripted_pronunciation',
  on = {},
  deps = {}, // tests only: { createRecorder, createTake, watchMic, recordTake, now, urls }
}) {
  const makeRecorder = deps.createRecorder || createLocalAudioRecorder;
  const makeTake = deps.createTake || createSpeakingTake;
  const watchMic = deps.watchMic || watchMicrophone;
  const record = deps.recordTake || recordTake;
  const modelSpanMs = Math.max(0, source.line.endMs - source.line.startMs) || null;

  const levels = new Array(BARS).fill(0);
  let take = null;
  let mic = null;
  let clock = 0;
  let stopTimer = 0;
  let disposed = false;
  let lastResult = null;
  let state = { phase: TAKE.IDLE, elapsedMs: 0, error: null };
  let latest = null; // { take_ref, list, view } of the newest finished take, this recorder's own

  const emit = () => {
    if (!disposed) on.change?.(snapshot());
  };

  function snapshot() {
    return {
      phase: state.phase,
      error: state.error,
      elapsedMs: take ? take.elapsedMs() : 0,
      levels: levels.slice(),
      latest,
    };
  }

  function startListening() {
    levels.fill(0);
    mic?.stop?.();
    mic = watchMic({
      onLevel: (peak) => {
        if (disposed || state.phase !== TAKE.RECORDING) return;
        levels.shift();
        levels.push(Math.min(1, Number(peak) || 0));
        on.level?.(levels.slice());
      },
    });
    clearInterval(clock);
    clock = setInterval(() => {
      if (state.phase === TAKE.RECORDING && take) on.tick?.(take.elapsedMs());
    }, 200);
    // A take that runs to the provider's limit is stopped here, not cut by the provider.
    clearTimeout(stopTimer);
    stopTimer = setTimeout(() => void stop(), MAX_TAKE_MS);
  }

  function stopListening() {
    mic?.stop?.();
    mic = null;
    clearInterval(clock);
    clearTimeout(stopTimer);
    levels.fill(0);
  }

  async function onTake(next) {
    if (disposed) return;
    const previous = state.phase;
    const wasError = previous === TAKE.ERROR;
    state = { phase: next.phase, elapsedMs: next.elapsedMs || 0, error: next.error || null };
    if (next.phase === TAKE.RESULT && next.result && next.result !== lastResult) {
      lastResult = next.result;
      const view = pronunciationView(next.result, { language, readings: [], modelSpanMs });
      view.heard = String(next.result.recognized_text || '').trim();
      if (view.measured) {
        const saved = await record(key, { blob: take.takeBlob, ms: take.takeMs, view });
        if (disposed) return;
        latest = { take_ref: saved.take_ref, list: saved.list, view };
        logSpeakingTask({ kind, contentId: source.sourceId, facts: facts(view) });
      } else {
        latest = { take_ref: '', list: latest?.list || [], view };
      }
    }
    // The record the server keeps for this take lands a moment after the result does.
    if (next.attemptId && latest?.take_ref) noteAttemptId(latest.take_ref, next.attemptId);
    if (next.phase === TAKE.RECORDING && previous !== TAKE.RECORDING) startListening();
    if (next.phase !== TAKE.RECORDING && previous === TAKE.RECORDING) stopListening();
    if (next.phase === TAKE.ERROR && next.error && next.error.kind !== 'aborted' && !wasError) on.failure?.(next.error);
    emit();
  }

  function fresh() {
    take?.dispose();
    take = makeTake({
      api,
      recorder: makeRecorder(),
      language,
      now: deps.now,
      urls: deps.urls,
      keep: { assetId: source.assetId || '', segmentId: source.line.lineId },
      onChange: onTake,
    });
  }
  fresh();

  async function stop() {
    if (state.phase !== TAKE.RECORDING) return;
    await take.stop(source.line.text);
  }

  return {
    /* The caller gates the microphone first (`screens/mic/sheet.js#micGate`), then starts. */
    start: () => (state.phase === TAKE.RECORDING || state.phase === TAKE.PROCESSING ? undefined : take.start()),
    stop,
    /* The same take, scored again, after a service failure - the learner does not record twice. */
    retry: () => take.retry(),
    get phase() {
      return state.phase;
    },
    get busy() {
      return state.phase === TAKE.RECORDING || state.phase === TAKE.PROCESSING;
    },
    snapshot,
    dispose() {
      disposed = true;
      stopListening();
      take?.dispose();
    },
  };
}
