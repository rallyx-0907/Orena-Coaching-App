import { esc, focusRegion } from './html.js';
import { progressReporter, hint } from './patterns.js';
import { openUnderstanding, selectionWithin } from './understanding.js';
import { voiceEvidence } from './voice-evidence.js';
import { loadSpokenCoaching } from './spoken-coaching.js';
import { createLocalAudioRecorder } from '../capabilities/audio-recorder.js';
import { MIC_STATES, watchMicrophone } from '../capabilities/mic-readiness.js';
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
    /* A room composed as a learning workspace hands in its result region, so
       what was heard lands beside the take instead of under it; `resultIdle`
       is what that region says before a take has been answered, and
       `onResult` lets the room move a narrow screen to it. */
    resultHost = null,
    resultIdle = '',
    onResult = () => {},
  },
) {
  const { c, api, language, memory } = ctx;
  let disposed = false,
    recording = false,
    take = null,
    takeId = '',
    busy = false;
  const alive = () => !disposed && ctx.alive() && root.isConnected;
  /* Where the recording lives is worth knowing and not worth reading before
     every take, so it sits beside the control as a hint. What to do - reply
     in your own words, within two minutes - stays on screen. */
  root.innerHTML = `<div class="voice-response"><blockquote class="voice-prompt practice-line" data-practice-line lang="${language}">${esc(prompt)}</blockquote><p>${esc(c.voiceTryNote)}</p><div class="mic-readiness" data-mic hidden><span class="mic-readiness__state" data-mic-state></span><span class="mic-readiness__device" data-mic-device></span><span class="mic-readiness__level" aria-hidden="true"><span data-mic-level></span></span></div><div class="button-row"><button class="primary" data-record>● ${esc(c.record)}</button>${hint({ text: c.localAudio })}<span class="meta" data-clock aria-live="off"></span></div><p role="status" data-record-status></p><div data-take></div>${resultHost ? '' : '<section data-voice-result></section>'}<details class="voice-history"><summary>${esc(c.voiceHistory)}</summary><div data-voice-history></div></details></div>`;
  /* Before a learner speaks, say whether the microphone is there and which one
     it is. State is words plus a level, never colour alone. */
  const micPanel = root.querySelector('[data-mic]');
  const micLabels = {
    [MIC_STATES.CHECKING]: c.micChecking,
    [MIC_STATES.READY]: c.micReady,
    [MIC_STATES.DENIED]: c.micDenied,
    [MIC_STATES.NO_DEVICE]: c.micNoDevice,
    [MIC_STATES.UNSUPPORTED]: c.microphone,
  };
  const mic = watchMicrophone({
    onState: ({ state, facts }) => {
      // Readiness is an enhancement: it never decides whether the room works.
      if (!alive() || !micPanel?.dataset) return;
      micPanel.hidden = false;
      micPanel.dataset.state = state;
      const label = micPanel.querySelector?.('[data-mic-state]');
      if (label) label.textContent = micLabels[state] || '';
      const device = micPanel.querySelector?.('[data-mic-device]');
      if (device) device.textContent = facts?.label || '';
      if (facts)
        // The negotiated capture settings, for diagnosing a bad take rather
        // than guessing at one. Device diagnostic only; nothing is sent.
        console.info('[Orena Speaking] capture', facts);
    },
    onLevel: (peak) => {
      const bar = micPanel?.querySelector?.('[data-mic-level]');
      if (bar?.style) bar.style.inlineSize = `${Math.round(Math.min(1, peak) * 100)}%`;
    },
  });
  const record = root.querySelector('[data-record]');
  const state = root.querySelector('[data-record-status]');
  const result = resultHost || root.querySelector('[data-voice-result]');
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
    result.innerHTML = `<div class="heading-with-hint"><h3>${esc(c.heard)}</h3>${hint({ text: c.voiceTranscriptNote, tone: 'warning', icon: 'warning' })}</div><p class="voice-transcript" lang="${language}" data-heard>${esc(value.heard)}</p><div class="button-row"><button class="outline" data-understand>${esc(c.lookCloser)} ↗</button><button class="outline" data-develop>${esc(c.develop)} ↗</button></div><details><summary>${esc(c.measuredHere)}</summary>${voiceEvidence(c, value.evaluation, language)}</details><div data-coaching></div><p role="status" data-saved></p><p class="meta">${esc(c.voiceReflect)}</p>`;
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
    onResult();
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
        /* A take that is almost silent is worth saying so about before the
           learner sends it for recognition and wonders why nothing came back.
           Opus spends about 2.5-4 kB a second on speech; a fraction of that is
           a signal problem - a virtual input, a muted device, or a microphone
           too far away - not something to score. It is a hint, not a
           measurement, and it never blocks the take. */
        const seconds = Math.max(1, (Date.now() - startedAt) / 1000);
        if (take.size && take.size / seconds < 1200) report.note(c.micVeryQuiet);
        root.querySelector('[data-take]').innerHTML =
          `<audio controls aria-label="${esc(c.voicePlayback)}" src="${esc(take.url)}"></audio><button class="outline" data-feedback>${esc(c.voiceHearWords)} ↗</button>`;
        root.querySelector('[data-feedback]').onclick = feedback;
        if (!(take.size && take.size / seconds < 1200)) report.note(c.voiceReady);
      } else {
        result.innerHTML = resultIdle;
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
    mic.stop();
    recorder.cleanup();
    onRecording(false);
  };
}
