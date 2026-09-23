/* One Speaking take, from the microphone to an assessed line (idle → recording → processing →
   result | error). No markup here: the workspace draws whatever state this reports.

   - The recorder is the shared one (`audio-recorder.js`); nothing records twice.
   - Raw audio lives only in this tab, for as long as the take is the current one: it is sent once
     to Orena's own route for assessment and never stored. What is kept is the normalized
     assessment, through the audio-free `speaking_attempts` record.
   - Every assessment carries a generation. A newer take, a cancel or leaving the room moves the
     generation on, so an answer that arrives late is dropped instead of overwriting a newer one.
   - A take that is too short is refused here, before anything is uploaded; one that runs to the
     provider's limit is stopped by the room (`MAX_TAKE_MS`).
   - A failure says whose it is: the learner's (no speech, too short, microphone) or the service's
     (retry the same take without recording again). A service failure is never the learner's. */

export const TAKE = Object.freeze({
  IDLE: 'idle',
  RECORDING: 'recording',
  PROCESSING: 'processing',
  RESULT: 'result',
  ERROR: 'error',
});

// Under this, a take holds no line worth assessing. Over the upper one, the provider's short-audio
// limit (and the server's normalizer, `-t 60`) would cut it.
export const MIN_TAKE_MS = 600;
export const MAX_TAKE_MS = 60_000;

/* What went wrong, from the route's canonical error envelope. */
export function failureOf(error) {
  if (error?.name === 'AbortError') return { kind: 'aborted', retry: false };
  const category = String(error?.category || '');
  if (category === 'pronunciation_no_speech') return { kind: 'no_speech', retry: false };
  if (category === 'pronunciation_audio_empty') return { kind: 'too_short', retry: false };
  if (category === 'pronunciation_audio_unsupported') return { kind: 'audio_unsupported', retry: false };
  if (category === 'pronunciation_payload_too_large') return { kind: 'too_long', retry: false };
  if (category === 'pronunciation_unconfigured' || error?.status === 503) return { kind: 'unavailable', retry: false };
  if (category === 'pronunciation_reference_invalid' || category === 'pronunciation_invalid_language') return { kind: 'line_invalid', retry: false };
  return { kind: 'service', retry: true };
}

export function createSpeakingTake({
  api,
  recorder,
  language,
  now = () => Date.now(),
  urls = globalThis.URL,
  keep = null,
  onChange = () => {},
}) {
  let generation = 0;
  let disposed = false;
  let startedAt = 0;
  let take = null; // { blob, url, ms }
  const state = { phase: TAKE.IDLE, result: null, error: null, kept: null, reference: '' };

  const emit = () => {
    if (!disposed) onChange({ ...state, take: take ? { url: take.url, ms: take.ms } : null, elapsedMs: elapsedMs() });
  };
  const set = (patch) => {
    Object.assign(state, patch);
    emit();
  };
  const elapsedMs = () => (state.phase === TAKE.RECORDING ? Math.max(0, now() - startedAt) : 0);
  const release = () => {
    if (take?.url) {
      try {
        urls?.revokeObjectURL?.(take.url);
      } catch {}
    }
    take = null;
  };

  async function start() {
    if (disposed || state.phase === TAKE.RECORDING || state.phase === TAKE.PROCESSING) return false;
    const mine = ++generation;
    const started = await recorder.start();
    if (disposed || mine !== generation) {
      recorder.cleanup();
      return false;
    }
    if (!started) {
      const reason = recorder.snapshot?.().error || '';
      set({ phase: TAKE.ERROR, error: { kind: reason === 'recording_unsupported' ? 'unsupported' : 'microphone', retry: false } });
      return false;
    }
    startedAt = now();
    set({ phase: TAKE.RECORDING, error: null });
    return true;
  }

  /* Leaving a recording without sending it. The take before it, and its result, stay: that audio
     is this controller's own copy, not the recorder's, so it can still be heard. */
  function cancel() {
    if (state.phase !== TAKE.RECORDING) return;
    generation++;
    recorder.cleanup();
    set({ phase: state.result ? TAKE.RESULT : TAKE.IDLE, error: null });
  }

  async function stop(reference) {
    if (state.phase !== TAKE.RECORDING) return;
    const mine = ++generation;
    const ms = Math.max(0, now() - startedAt);
    const recorded = await recorder.stop();
    if (disposed || mine !== generation) return;
    if (!recorded?.blob) {
      set({ phase: TAKE.ERROR, error: { kind: 'recording_failed', retry: false } });
      return;
    }
    if (ms < MIN_TAKE_MS || !recorded.blob.size) {
      set({ phase: TAKE.ERROR, error: { kind: 'too_short', retry: false } });
      return;
    }
    release();
    take = { blob: recorded.blob, url: urls?.createObjectURL ? urls.createObjectURL(recorded.blob) : recorded.url, ms };
    recorder.discard?.();
    await assess(reference, mine);
  }

  async function assess(reference, mine = ++generation) {
    if (!take) return;
    const line = String(reference || '').trim();
    set({ phase: TAKE.PROCESSING, error: null, result: null, kept: null, reference: line });
    try {
      const result = await api.assessPronunciation(take.blob, language, line);
      if (disposed || mine !== generation) return;
      set({ phase: TAKE.RESULT, result });
      if (keep) void remember(result, mine);
    } catch (error) {
      if (disposed || mine !== generation) return;
      const failure = failureOf(error);
      if (failure.kind === 'aborted') return;
      set({ phase: TAKE.ERROR, error: failure });
    }
  }

  /* The assessment, kept as the learner's evidence through the audio-free attempt record.
     A take the provider heard nothing in has no transcript and is not an attempt. */
  async function remember(result, mine) {
    const heard = String(result?.recognized_text || '').trim();
    if (!heard || result?.score_kind !== 'measured') return;
    try {
      const evaluation = await api.evaluateSpeaking({
        language,
        reference_text: result.reference_text || state.reference,
        transcript_text: heard,
        pronunciation: result,
      });
      await api.saveSpeakingAttempt({
        language,
        take_id: `${keep.segmentId}:${mine}:${now()}`,
        asset_id: keep.assetId || '',
        segment_id: keep.segmentId,
        reference_text: result.reference_text || state.reference,
        transcript_text: heard,
        evaluation,
      });
      if (mine === generation) set({ kept: true });
    } catch {
      if (mine === generation) set({ kept: false });
    }
  }

  return {
    start,
    stop,
    cancel,
    /* The same take, again, after a service failure: the learner does not record twice. */
    retry: () => (state.phase === TAKE.ERROR && state.error?.retry && take ? assess(state.reference) : undefined),
    elapsedMs,
    get phase() {
      return state.phase;
    },
    get takeUrl() {
      return take?.url || '';
    },
    dispose() {
      disposed = true;
      generation++;
      recorder.cleanup();
      release();
    },
  };
}
