/* React / Reuse (design route `react`, frame 33, D-091, D-088). A focus workspace: Listen ->
   Understand -> Reveal -> New context -> Result, real end to end, for one line of a Listening
   lesson (`?seg=` names it, the same key Dictation and Shadowing read). See
   SCRATCH/reports/listening.md for the measurement diff and every deviation from the frame:
   - Understand's multiple choice is built from this lesson's own real segment translations (one
     correct + two real distractors), never a generated question (rule 40); a line with fewer than
     two other real translations goes straight from Listen to Reveal.
   - Result: "Phrase reused?" is a real containment check on the catalogued phrase; "Intent
     achieved?" shows only when the coaching returned a real verdict (S-26), and neither tile is drawn as a bare 0 (rule 40, HX-2). The frame's
     "One natural alternative" is the coaching's own `another_way`; what carried / what would land
     differently / the next attempt are the same real answer, drawn in the frame's own field style.
   - The Listen step's waveform is the frame's, dim until the line is playing (the frame binds it to
     the Dictation room's playing flag - E3's prototype wiring bug - so it never lit here).
   - Its play control is the official play/pause icon, not a text glyph (rule 46). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy as s } from '../../copy/shell.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { encounter } from '../../product/encounter.js';
import {
  connectMediaPlayer, disconnectMediaPlayer, mediaPlayer, playbackAvailable, replaySegment, togglePlayback,
} from '../../capabilities/media-player.js';
import { createLocalAudioRecorder, localAudioRecordingSupported } from '../../capabilities/audio-recorder.js';
import { registerActionHandler } from '../../agent/dispatcher.js';
import { micGate, openMicState } from '../mic/sheet.js';
import { saveResponse } from '../../product/account-records.js';
import { t } from './copy.js';
import { openMedia } from '../../product/media-source.js';
import { usefulPhrase, buildUnderstandCheck, mapCoaching, phraseReused, resultTiles, waveBars, promptKey } from './model.js';

const STEPS = ['stepListen', 'stepUnderstand', 'stepReveal', 'stepContext', 'stepResult'];
const WAVE_BARS = 32;

export default async function reactReuse(element, ctx) {
  await useStyles('screens/react/react.css');
  const support = languages().support;
  const lessonId = ctx.params.id;
  const requestedSegment = ctx.query.get('seg') || '';

  const payload = await openMedia(lessonId, {api, support, language: ctx.context.language, owner: ctx.context.owner || 'local', alive: () => ctx.isCurrent()});
  if (!ctx.isCurrent()) return undefined;
  const catalog = payload?.catalog || {};
  const title = catalog.title || payload?.asset?.title || '';
  const language = catalog.language || payload?.asset?.source_language || ctx.context.language;
  const vocabulary = Array.isArray(catalog.vocabulary) ? catalog.vocabulary : [];
  const enc = encounter(payload, support);
  const segments = enc.segments;
  const playback = payload?.playback || null;
  const playbackOk = playbackAvailable(playback);

  const seg = segments.find((x) => x.segment_id === requestedSegment) || segments[0] || null;
  if (!seg) throw new Error('React/Reuse: this lesson has no transcript to work from.');
  const segNo = segments.indexOf(seg) + 1;
  const phrase = usefulPhrase(vocabulary, seg.original_text);
  const bars = waveBars(WAVE_BARS, segNo);
  const check = buildUnderstandCheck(segments, seg.segment_id, (id) => enc.meaning(id), [...seg.segment_id].reduce((sum, ch) => sum + ch.charCodeAt(0), 0));

  /* A lesson whose media cannot be played (rights, a missing asset) has no Listen step to give: the
     room opens on the first step it can honestly show, so there is never a dead end. */
  let step = playbackOk ? 0 : (check ? 1 : 2);
  let picked = null;
  let contextIndex = 0;
  let answerText = '';
  let recording = false;
  let transcribing = false;
  let micUnsupported = !localAudioRecordingSupported();
  let checking = false;
  let result = null;
  let resultError = false;
  let playing = false;
  let recorder = null;
  let stopTimer = 0;
  const playerHost = { current: null };

  const promptText = () => {
    const key = promptKey(Boolean(phrase), contextIndex);
    return phrase ? t(key, { phrase }) : t(key);
  };

  element.classList.add('s-react');
  mount(
    element,
    html`<div class="s-react__head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${s('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-react__titles">
        <div class="s-react__title">${s('reactReuse')}</div>
        <div class="s-react__meta"><span lang="${langAttr(language)}">${title}</span> · ${t('segmentNo', { n: segNo })}</div>
      </div>
    </div>
    <div class="s-react__steps" data-steps></div>
    <div class="s-react__card">
      <div class="s-react__body" data-scroll-region data-body></div>
      <div class="s-react__foot" data-footer></div>
    </div>`,
  );
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  const bodyEl = element.querySelector('[data-body]');
  const footEl = element.querySelector('[data-footer]');

  function paintSteps() {
    mount(
      element.querySelector('[data-steps]'),
      html`${STEPS.map((key, i) => html`<div class="${['s-react__step', i <= step && 'is-reached', i === step && 'is-current'].filter(Boolean).join(' ')}">
        <span class="s-react__step-bar"></span><span class="s-react__step-label">${t(key)}</span>
      </div>`)}`,
    );
  }

  /* ------------------------------------------------------------ Listen ---- */
  function listenMarkup() {
    return html`
      <div class="s-react__media" aria-hidden="true" data-media>${raw(mediaPlayer(playback, title, { startMs: seg.start_ms, endMs: seg.end_ms, controls: false }))}</div>
      <div class="s-react__listen">
        <button type="button" class="s-react__play" data-play aria-label="${t(playing ? 'pauseLabel' : 'playLabel')}">${raw(icon(playing ? 'pause' : 'play', { size: 26 }))}</button>
        <div class="s-react__wave${playing ? ' is-playing' : ''}" data-wave>${bars.map((bar) => html`<span style="height:${bar.height}%;animation-delay:${bar.delay}ms"></span>`)}</div>
      </div>`;
  }
  function bindListen() {
    const host = bodyEl.querySelector('[data-media]');
    if (!host || !playbackOk) return;
    playerHost.current = host;
    host.addEventListener('orena:media-time', (event) => {
      const now = event.detail?.player_state === 1;
      if (now === playing) return;
      playing = now;
      bodyEl.querySelector('[data-wave]')?.classList.toggle('is-playing', playing);
      const button = bodyEl.querySelector('[data-play]');
      if (button) {
        mount(button, raw(icon(playing ? 'pause' : 'play', { size: button.classList.contains('s-react__replay') ? 18 : 26 })));
        button.setAttribute('aria-label', t(button.classList.contains('s-react__replay') ? 'replayLabel' : playing ? 'pauseLabel' : 'playLabel'));
      }
    });
    connectMediaPlayer(host, playback);
    bodyEl.querySelector('[data-play]')?.addEventListener('click', () => {
      // Mid-line it pauses; stopped, it plays the line again from its start.
      if (playing) togglePlayback(host, playback);
      else replaySegment(host, playback, seg.start_ms, seg.end_ms, 1);
    });
    // The Listen step opens paused on ▶ as the design does (nav("react",{playing:false})); the learner starts it.
    // Starting it here played only when the browser still held a recent tap - from Listening, not on a direct
    // open (L-10).
  }
  function releaseListen() {
    if (playerHost.current) disconnectMediaPlayer(playerHost.current);
    playerHost.current = null;
    playing = false;
  }

  /* --------------------------------------------------------- Understand ---- */
  function understandMarkup() {
    return html`
      ${playbackOk ? html`<div class="s-react__media" aria-hidden="true" data-media>${raw(mediaPlayer(playback, title, { startMs: seg.start_ms, endMs: seg.end_ms, controls: false }))}</div>` : ''}
      <div class="s-react__qrow">
        <div class="s-react__question">${t('question')}</div>
        ${playbackOk ? html`<button type="button" class="o-iconbtn s-react__replay" data-play aria-label="${t('replayLabel')}">${raw(icon('play', { size: 18 }))}</button>` : ''}
      </div>
      <div class="s-react__options">${check.options.map((text, i) => {
        const tone = picked == null ? '' : i === check.correctIndex ? 'is-correct' : (i === picked ? 'is-wrong' : '');
        // The chosen option is named as the learner's, and the right one carries a check: colour is never the only signal.
        const mark = picked == null ? '' : i === picked ? html`<span class="s-react__option-mark">${raw(icon(i === check.correctIndex ? 'check' : 'x', { size: 14 }))}${t('yourAnswer')}</span>` : i === check.correctIndex ? html`<span class="s-react__option-mark">${raw(icon('check', { size: 14 }))}</span>` : '';
        return html`<button type="button" class="${['s-react__option', tone].filter(Boolean).join(' ')}" data-pick="${i}" aria-pressed="${picked === i ? 'true' : 'false'}"${picked != null ? ' aria-disabled="true"' : ''}><span>${text}</span>${mark}</button>`;
      })}</div>`;
  }
  function bindUnderstand() {
    bindListen();
    bodyEl.querySelectorAll('[data-pick]').forEach((button) => button.addEventListener('click', () => {
      if (picked != null) return;
      picked = Number(button.dataset.pick);
      paintBody();
    }));
  }

  /* -------------------------------------------------------------- Reveal ---- */
  function markedTranscript() {
    const text = seg.original_text;
    const at = phrase ? text.toLowerCase().indexOf(phrase.toLowerCase()) : -1;
    if (at < 0) return html`<span lang="${langAttr(language)}">${text}</span>`;
    return html`<span lang="${langAttr(language)}">${text.slice(0, at)}<span class="s-react__mark">${text.slice(at, at + phrase.length)}</span>${text.slice(at + phrase.length)}</span>`;
  }
  function revealMarkup() {
    const meaning = enc.meaning(seg.segment_id);
    return html`
      <div class="s-react__label">${t('transcriptLabel')}</div>
      <div class="s-react__transcript">${markedTranscript()}</div>
      ${meaning ? html`<div class="s-react__vi">${meaning}</div>` : ''}
      ${phrase ? html`<div class="s-react__callout"><b>${t('usefulPhrase')} · “${phrase}”</b></div>` : ''}`;
  }

  /* ---------------------------------------------------------- New context ---- */
  function contextMarkup() {
    return html`
      <span class="s-react__chip">${t('newContextChip')}</span>
      <div class="s-react__source" lang="${langAttr(language)}" aria-label="${t('sentenceLabel')}">${markedTranscript()}</div>
      <div class="s-react__prompt" lang="${langAttr(support)}">${promptText()}</div>
      <textarea class="s-react__textarea" rows="3" lang="${langAttr(language)}" placeholder="${t('placeholderAnswer')}" data-answer>${answerText}</textarea>`;
  }
  function bindContext() {
    const textarea = bodyEl.querySelector('[data-answer]');
    textarea?.addEventListener('input', () => {
      answerText = textarea.value;
      const button = footEl.querySelector('[data-check]');
      if (button) button.disabled = !answerText.trim() || checking || transcribing;
    });
  }

  /* -------------------------------------------------------------- Result ---- */
  function fieldBlock(titleKey, items, withInstead) {
    if (!items.length) return '';
    return html`<div class="s-react__field">
      <div class="s-react__field-title">${t(titleKey)}</div>
      ${items.map((item) => html`<div class="s-react__quote"><span lang="${langAttr(language)}">“${item.quote}”</span>${withInstead && item.instead ? html` → <b lang="${langAttr(language)}">${item.instead}</b>` : ''}<div class="s-react__quote-why">${item.why}</div></div>`)}
    </div>`;
  }
  function resultMarkup() {
    const reused = phraseReused(phrase, answerText);
    const tiles = resultTiles(reused, result?.intent);
    const alternative = result?.available ? (result.anotherWay || result.sayAgain) : '';
    return html`
      <div class="s-react__echo" lang="${langAttr(language)}">“${answerText}”</div>
      ${tiles.length ? html`<div class="s-react__tiles">
        ${tiles.map((tile) => tile.key === 'intentAchieved'
          ? html`<div class="s-react__tile${tile.verdict === 'yes' ? ' is-good' : ''}"><div class="s-react__tile-label">${t('intentAchieved')}</div><div class="s-react__tile-value${tile.verdict === 'yes' ? ' is-good' : ''}">${t(`intent_${tile.verdict}`)}</div></div>`
          : html`<div class="s-react__tile${tile.good ? ' is-good' : ''}"><div class="s-react__tile-label">${t('phraseReused')}</div><div class="s-react__tile-value${tile.good ? ' is-good' : ' is-warn'}">${t(tile.valueKey)}</div></div>`)}
      </div>` : ''}
      ${resultError ? html`<div class="s-react__empty">${t('coachingError')}</div>`
        : !result?.available ? html`<div class="s-react__empty">${t('notPrepared')}</div>`
        : html`
          ${alternative ? html`<div class="s-react__callout"><b>${t('anotherWayLabel')}</b> · <span lang="${langAttr(language)}">${alternative}</span></div>` : ''}
          ${fieldBlock('carriedLabel', result.carried, false)}
          ${fieldBlock('landedLabel', result.landedDifferently, true)}
          ${result.nextAttempt ? html`<div class="s-react__field"><div class="s-react__field-title">${t('nextAttemptLabel')}</div><div class="s-react__quote">${result.nextAttempt}</div></div>` : ''}`}`;
  }

  /* --------------------------------------------------------------- paint ---- */
  const onward = (label, extra = '') => html`<span class="s-react__spacer"></span><button type="button" class="o-btn o-btn--primary s-react__cta${extra}" data-next>${label}${raw(icon('arrow-right', { size: 16 }))}</button>`;

  function paintFooter() {
    if (step === 0) mount(footEl, onward(t('continueLabel'), ' s-react__cta--listen'));
    else if (step === 1 && check) {
      mount(footEl, picked != null
        ? html`<span class="s-react__verdict ${picked === check.correctIndex ? 'is-correct' : 'is-wrong'}">${picked === check.correctIndex ? t('correctLabel') : t('incorrectLabel')}</span>${onward(t('reveal'))}`
        : html``);
    } else if (step === 2 || (step === 1 && !check)) mount(footEl, onward(t('newContextChip')));
    else if (step === 3) {
      mount(footEl, html`
        ${!micUnsupported ? html`<button type="button" class="s-react__mic${recording ? ' is-recording' : ''}" data-mic aria-pressed="${String(recording)}">${raw(icon('mic', { size: 16 }))}${recording ? t('listening') : (transcribing ? '…' : t('speak'))}</button>` : ''}
        <span class="s-react__spacer"></span>
        <button type="button" class="o-btn o-btn--primary s-react__cta" data-check ${answerText.trim() && !checking && !transcribing ? '' : 'disabled'}>${t('checkLabel')}</button>`);
    } else {
      mount(footEl, html`
        <button type="button" class="o-btn o-btn--secondary s-react__ghost" data-retry>${s('retry')}</button>
        <button type="button" class="o-btn o-btn--secondary s-react__ghost" data-again>${t('newContextAgain')}</button>
        <span class="s-react__spacer"></span>
        <button type="button" class="o-btn o-btn--primary s-react__cta" data-finish>${t('finishLabel')}</button>`);
    }
    footEl.querySelector('[data-next]')?.addEventListener('click', onNext);
    footEl.querySelector('[data-mic]')?.addEventListener('click', onMicTap);
    footEl.querySelector('[data-check]')?.addEventListener('click', onCheck);
    footEl.querySelector('[data-retry]')?.addEventListener('click', onRetry);
    footEl.querySelector('[data-again]')?.addEventListener('click', () => { contextIndex += 1; onRetry(); });
    footEl.querySelector('[data-finish]')?.addEventListener('click', () => {
      // Back to where the learner came from - the Listening line - and the Practice Hub only when they entered from
      // there or opened this room directly (LEX-085).
      if (ctx.hasHistory()) ctx.back();
      else ctx.go(ctx.href('practice'));
    });
  }

  function paintBody() {
    releaseListen();
    if (step === 0) { mount(bodyEl, listenMarkup()); bindListen(); }
    else if (step === 1 && check) { mount(bodyEl, understandMarkup()); bindUnderstand(); }
    else if (step === 2 || (step === 1 && !check)) mount(bodyEl, revealMarkup());
    else if (step === 3) { mount(bodyEl, contextMarkup()); bindContext(); }
    else mount(bodyEl, resultMarkup());
    paintFooter();
    paintSteps();
    bodyEl.scrollTop = 0;
  }

  /* -------------------------------------------------------------- the mic ---- */
  async function onMicTap() {
    if (recording) return stopRecording();
    await micGate(ctx, startRecording);
  }

  async function startRecording() {
    recorder = createLocalAudioRecorder();
    const ok = await recorder.start();
    if (!ok) { micUnsupported = true; paintFooter(); return; }
    recording = true;
    paintFooter();
    stopTimer = setTimeout(() => stopRecording(), 30000);
  }

  async function stopRecording() {
    clearTimeout(stopTimer);
    recording = false;
    const captured = await recorder?.stop();
    if (!ctx.isCurrent()) return;
    if (!captured) { paintFooter(); return; }
    transcribing = true;
    paintFooter();
    let text = '';
    try {
      const res = await api.transcribeSpeech(captured.blob, language);
      text = String(res?.text || '').trim();
    } catch {
      transcribing = false;
      if (!ctx.isCurrent()) return;
      paintFooter();
      openMicState(ctx, { state: 'provider', onAction: async () => true });
      return;
    }
    transcribing = false;
    if (!ctx.isCurrent()) return;
    if (!text) {
      paintFooter();
      openMicState(ctx, {
        state: 'notheard',
        onAction: async (key) => {
          if (key === 'tryagain') { await micGate(ctx, startRecording); return false; }
          return true;
        },
      });
      return;
    }
    answerText = text;
    const textarea = bodyEl.querySelector('[data-answer]');
    if (textarea) textarea.value = text;
    paintFooter();
  }

  /* --------------------------------------------------------------- check ---- */
  async function onCheck() {
    const text = answerText.trim();
    if (!text || checking) return;
    checking = true;
    resultError = false;
    paintFooter();
    try {
      const res = await api.spokenResponseCoaching({ transcript: text, source_language: language, target_language: support, situation: promptText() });
      if (!ctx.isCurrent()) return;
      result = mapCoaching(res);
      // The answer is the learner's own work, kept with the account when it keeps work (D4 I8).
      void saveResponse({ kind: 'react', source: { kind: 'media', id: lessonId }, mode: 'react', answer: text, coaching: res, sentenceRef: seg.segment_id });
    } catch {
      if (!ctx.isCurrent()) return;
      result = null;
      resultError = true;
    }
    checking = false;
    step = 4;
    paintBody();
  }

  function onNext() {
    if (step === 0) step = check ? 1 : 2;
    else if (step === 1) step = 2;
    else if (step === 2) step = 3;
    paintBody();
  }

  /* Retry and New context both go back to the answer, the second on the other prompt. */
  function onRetry() {
    step = 3;
    answerText = '';
    result = null;
    resultError = false;
    paintBody();
  }

  paintBody();

  /* AGENT_CONTRACT.md §7: `play_model` = "play reference audio" - only meaningful while the
     Listen step's player is actually mounted; the other steps have no media element to replay.
     `play_user`/`say_again`/`compare_with_model` do not apply here: the New Context answer is
     scored as text (`POST /api/dictionary/spoken-response`), never played back or compared
     against a model recording. */
  const releasePlayModel = registerActionHandler('play_model', () => {
    if (!playbackOk || !playerHost.current) return { ok: false, reason: 'not_available' };
    replaySegment(playerHost.current, playback, seg.start_ms, seg.end_ms, 1);
    return { ok: true };
  });

  return () => {
    clearTimeout(stopTimer);
    if (recorder) recorder.stop().catch(() => {});
    releasePlayModel();
    releaseListen();
  };
}
