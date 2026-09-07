import { esc, focusRegion } from './html.js';
import { progressReporter } from './patterns.js';
import { openUnderstanding, selectionWithin } from './understanding.js';
import { voiceEvidence } from './voice-evidence.js';
import { loadSpokenCoaching } from './spoken-coaching.js';
import { createLocalAudioRecorder } from '../capabilities/audio-recorder.js';
import { evaluateVoice } from '../capabilities/voice-feedback.js';
import { link } from '../product/intent.js';

/* Whether a speech service is attached at all, asked once per session.

   Every room that invites a take needs the same answer, and asking on each
   redraw would put a request behind every keystroke that repaints a composer.
   It fails open: if the check itself cannot be read, the recorder stays
   available and the transcription path reports whatever it actually finds.
   Being wrongly hopeful costs a learner one take; being wrongly discouraging
   would hide a working capability. */
let speechAnswer = null;
export function speechConfigured(api) {
  // A caller that cannot answer the question is not evidence of absence, so it
  // is treated like any other unreadable check rather than throwing inside the
  // mount and taking the whole recorder down with it.
  if (typeof api?.speechStatus !== 'function') return Promise.resolve(true);
  if (!speechAnswer)
    speechAnswer = api
      .speechStatus()
      .then((status) => status?.configured !== false)
      .catch(() => true);
  return speechAnswer;
}

// One free-response experience in a situation, a passage or a media moment.
// The prompt supplies context, never words the learner must reproduce.
export function mountVoiceResponse(
  root,
  ctx,
  {
    id,
    title,
    prompt,
    assetId = '',
    segmentId = id,
    onRecording = () => {},
    recorder = createLocalAudioRecorder(),
    onUse = null,
  },
) {
  const { c, api, language, memory } = ctx;
  let disposed = false,
    recording = false,
    take = null,
    takeId = '',
    busy = false;
  const alive = () => !disposed && ctx.alive() && root.isConnected;
  root.innerHTML = `<div class="voice-response"><blockquote class="voice-prompt" lang="${language}">${esc(prompt)}</blockquote><p>${esc(c.voiceTryNote)}</p><div class="button-row"><button class="primary" data-record>● ${esc(c.record)}</button><span class="meta" data-clock aria-live="off"></span></div><p role="status" data-record-status></p><div data-take></div><p class="meta">${esc(c.localAudio)}</p><section data-voice-result></section><details class="voice-history"><summary>${esc(c.voiceHistory)}</summary><div data-voice-history></div></details></div>`;
  const record = root.querySelector('[data-record]');
  const state = root.querySelector('[data-record-status]');
  const result = root.querySelector('[data-voice-result]');
  const history = root.querySelector('[data-voice-history]');
  const report = progressReporter(state, ctx, alive);
  let ticker, startedAt;
  const remember = () =>
    memory.enter({
      id,
      title,
      intent: 'speaking',
      excerpt: prompt,
      segment: assetId ? segmentId : undefined,
    });
  const historyLoad = async () => {
    try {
      const response = await api.speakingAttempts(12, assetId, segmentId);
      if (!alive()) return;
      const items = (response.items || []).filter((x) => !x.reference_text);
      history.innerHTML = items.length
        ? `<p class="meta">${esc(c.voiceHistoryNote)}</p>${items.map((x) => `<article class="voice-history-take"><small>${esc(x.created_at ? new Date(x.created_at).toLocaleString(ctx.ui) : '')}</small><p lang="${language}">${esc(x.transcript_text)}</p></article>`).join('')}`
        : `<p class="meta">${esc(c.voiceNoHistory)}</p>`;
    } catch {
      if (alive())
        progressReporter(history, ctx, alive).failed(
          c.unavailable,
          historyLoad,
        );
    }
  };
  void historyLoad();
  // Say so before the learner records, not after a take they already made.
  void speechConfigured(api).then((ready) => {
    if (!alive() || ready) return;
    record.disabled = true;
    state.textContent = c.voiceUnavailable;
  });
  const showResult = (value) => {
    const resultTakeId = takeId;
    result.innerHTML = `<h3>${esc(c.heard)}</h3><p class="meta">${esc(c.voiceTranscriptNote)}</p><p class="voice-transcript" lang="${language}" data-heard>${esc(value.heard)}</p><div class="button-row"><button class="outline" data-understand>${esc(c.lookCloser)} ↗</button><button class="outline" data-develop>${esc(c.develop)} ↗</button></div><details><summary>${esc(c.measuredHere)}</summary>${voiceEvidence(c, value.evaluation, language)}</details><div data-coaching></div><p role="status" data-saved></p><p class="meta">${esc(c.voiceReflect)}</p>`;
    const saved = progressReporter(
      result.querySelector('[data-saved]'),
      ctx,
      alive,
    );
    const retrySave = async () => {
      saved.saving();
      try {
        await ctx.mutate(() =>
          api.saveSpeakingAttempt({
            language,
            take_id: resultTakeId,
            asset_id: assetId,
            segment_id: segmentId,
            reference_text: '',
            transcript_text: value.heard,
            evaluation: value.evaluation,
          }),
        );
        saved.saved();
        void historyLoad();
      } catch {
        saved.failed(c.failedSave, retrySave);
      }
    };
    if (value.saved) {
      saved.saved();
      void historyLoad();
    } else saved.failed(c.failedSave, retrySave);
    result.querySelector('[data-understand]').onclick = () => {
      const selected = selectionWithin(result.querySelector('[data-heard]'));
      openUnderstanding(ctx, {
        origin: { id, where: title, why: 'from_speaking' },
        selection: selected?.text || value.heard,
        context: `${prompt}\n${value.heard}`.slice(0, 2400),
        title,
      });
    };
    result.querySelector('[data-develop]').onclick = () => {
      // Each take has its own response identity; an existing draft is never replaced.
      const draftId = `expression:voice:${resultTakeId}`;
      if (!memory.value.expressions[draftId])
        memory.write(draftId, value.heard);
      memory.enter({ id: draftId, title, intent: 'writing', excerpt: prompt });
      window.location.hash = link('expression', { id: draftId });
    };
    focusRegion(result.querySelector('h3'));
    if (onUse) {
      const use = document.createElement('button');
      use.className = 'primary';
      use.textContent = c.conversationUse;
      use.onclick = () => onUse({ heard: value.heard, takeId: resultTakeId });
      result.querySelector('.button-row').prepend(use);
    }
    // Coaching is a separate request about the words, and it must not hold up
    // the transcript or the evidence the learner already has.
    void loadSpokenCoaching(result.querySelector('[data-coaching]'), ctx, {
      transcript: value.heard,
      situation: prompt,
    });
  };
  const feedback = async () => {
    if (busy || !take) return;
    busy = true;
    record.disabled = true;
    root.querySelector('[data-feedback]').disabled = true;
    report.saving();
    try {
      const value = await ctx.mutate(() =>
        evaluateVoice({
          api,
          blob: take.blob,
          language,
          assetId,
          segmentId,
          takeId,
        }),
      );
      if (!alive()) return;
      remember();
      showResult(value);
      state.textContent = '';
    } catch {
      report.failed(c.feedbackUnavailable, feedback);
      if (alive()) root.querySelector('[data-feedback]').disabled = false;
    } finally {
      busy = false;
      if (alive()) record.disabled = false;
    }
  };
  record.onclick = async () => {
    if (busy) return;
    busy = true;
    record.disabled = true;
    try {
      if (recording) {
        take = await recorder.stop();
        clearInterval(ticker);
        recording = false;
        onRecording(false);
        if (!alive()) return;
        record.textContent = `● ${c.voiceAnother}`;
        if (!take) {
          report.note(c.microphone);
          return;
        }
        takeId = crypto.randomUUID();
        root.querySelector('[data-take]').innerHTML =
          `<audio controls aria-label="${esc(c.voicePlayback)}" src="${esc(take.url)}"></audio><button class="outline" data-feedback>${esc(c.voiceHearWords)} ↗</button>`;
        root.querySelector('[data-feedback]').onclick = feedback;
        report.note(c.voiceReady);
      } else {
        result.innerHTML = '';
        root.querySelector('[data-take]').innerHTML = '';
        take = null;
        onRecording(true);
        const started = await recorder.start();
        if (!alive()) {
          recorder.cleanup();
          return;
        }
        recording = started;
        onRecording(started);
        record.textContent = started ? `■ ${c.stop}` : `● ${c.record}`;
        report.note(started ? c.recording : c.microphone);
        if (started) {
          remember();
          startedAt = Date.now();
          ticker = setInterval(() => {
            if (!alive()) return;
            const seconds = Math.floor((Date.now() - startedAt) / 1000);
            root.querySelector('[data-clock]').textContent =
              `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
            if (seconds >= 120 && !busy) record.click();
          }, 500);
        }
      }
    } finally {
      busy = false;
      if (alive()) record.disabled = false;
    }
  };
  return () => {
    disposed = true;
    clearInterval(ticker);
    recorder.cleanup();
    onRecording(false);
  };
}
