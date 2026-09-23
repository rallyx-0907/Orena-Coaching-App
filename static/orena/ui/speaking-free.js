/* Free talk (D-066, D-067), drawn from Orena Speaking, "Speaking · free talk" (390x844; the design
   draws no desktop frame, so a desk shows the same column, centred - a recorded gap).

   The topic, what the learner just said (with how long they spoke), one line of comment, and three
   ways on: deeper suggestions, the microphone, another topic. This is a different capability from
   pronunciation: nothing here is a pronunciation score. The plumbing is the free-response one that
   already existed - recognition, the per-take evidence envelope, the audio-free attempt record and
   the spoken coaching - so nothing is recorded or evaluated twice. What the old room offered beyond
   the frame (look closer, turn it into writing, start a conversation) is kept behind "deeper
   suggestions", in a sheet, rather than as controls the frame does not draw (rule 43). */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { speakCopy, fill } from './speaking-copy.js';
import { voiceEvidence } from './voice-evidence.js';
import { spokenCoaching } from './spoken-coaching.js';
import { openUnderstanding } from './understanding.js';
import { speechConfigured } from './voice-response.js';
import { startConversation } from './conversation.js';
import { createLocalAudioRecorder } from '../capabilities/audio-recorder.js';
import { evaluateVoice } from '../capabilities/voice-feedback.js';
import { MIN_TAKE_MS } from '../capabilities/speaking-take.js';
import { link } from '../product/intent.js';

const MAX_FREE_MS = 120_000;
const clock = (ms) => {
  const seconds = Math.max(0, Math.round(ms / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
};

export function freeTalkHtml({ s, title, topic, cue, language }) {
  return `<section class="sp-room sp-free" data-phase="idle">
<header class="sp-top sp-free__top"><button type="button" class="sp-back sp-free__back" data-sp-back aria-label="${esc(s.room)}"><span class="sp-back__caret">${icon('caret-left', { size: 22 })}</span><span class="sp-lesson">${esc(title)}</span></button></header>
<div class="sp-free__body"><section class="sp-topic"><span class="sp-label">${esc(s.topic)}</span><h1 lang="${esc(language)}">${esc(topic)}</h1>${cue ? `<p lang="${esc(language)}">${esc(cue)}</p>` : ''}</section>
<section class="sp-said" data-sp-said hidden></section>
<p class="sp-hint" data-sp-hint role="status"></p></div>
<div class="sp-free__controls"><button type="button" class="sp-fbtn" data-sp-deeper disabled>${icon('sparkle', { size: 17 })}<span>${esc(s.deeper)}</span></button><button type="button" class="sp-mic sp-mic--free" data-sp-mic aria-label="${esc(s.record)}"><span class="sp-mic__icon">${icon('microphone', { size: 31, filled: true })}</span><span class="sp-mic__stop"></span></button><button type="button" class="sp-fbtn" data-sp-other>${icon('arrow-right', { size: 17 })}<span>${esc(s.otherTopic)}</span></button></div></section>`;
}

export function saidHtml({ s, heard, ms, comment, language }) {
  return `<span class="sp-label">${esc(fill(s.youSaid, { t: clock(ms) }))}</span><p class="sp-said__words" lang="${esc(language)}">${esc(heard)}</p>${comment ? `<div class="sp-said__comment">${icon('check-circle', { size: 17, filled: true })}<span>${esc(comment)}</span></div>` : ''}`;
}

export function mountFreeTalk(root, ctx, { id, title, topic, cue, next }) {
  const { api, c, language, memory } = ctx;
  const s = speakCopy(ctx.ui);
  let disposed = false;
  let phase = 'idle';
  let recorder = createLocalAudioRecorder();
  let startedAt = 0;
  let ticker = 0;
  let generation = 0;
  let last = null; // { heard, evaluation, ms, coaching, takeId }
  let sheet = null;
  const alive = () => !disposed && (ctx.alive ? ctx.alive() : true) && root.isConnected;

  root.innerHTML = freeTalkHtml({ s, title, topic, cue, language });
  const q = (selector) => root.querySelector(selector);
  const hint = q('[data-sp-hint]');
  const mic = q('[data-sp-mic]');

  const setPhase = (value, message = '') => {
    phase = value;
    q('.sp-room').dataset.phase = value;
    mic.disabled = value === 'processing';
    mic.setAttribute('aria-label', value === 'recording' ? s.stop : s.record);
    mic.setAttribute('aria-pressed', String(value === 'recording'));
    hint.textContent = message;
    hint.classList.toggle('sp-hint--error', value === 'error');
  };

  memory?.enter?.({ id, title, intent: 'speaking', excerpt: topic });

  void speechConfigured(api).then((ready) => {
    if (!alive() || ready) return;
    mic.disabled = true;
    setPhase('error', c.voiceUnavailable);
  });

  async function start() {
    const mine = ++generation;
    const started = await recorder.start();
    if (!alive() || mine !== generation) return recorder.cleanup();
    if (!started) return setPhase('error', recorder.snapshot?.().error === 'recording_unsupported' ? s.err_unsupported : s.err_microphone);
    startedAt = Date.now();
    setPhase('recording', s.freeReady);
    clearInterval(ticker);
    ticker = setInterval(() => {
      if (!alive()) return clearInterval(ticker);
      if (Date.now() - startedAt >= MAX_FREE_MS) void stop();
    }, 500);
  }

  async function stop() {
    if (phase !== 'recording') return;
    clearInterval(ticker);
    const mine = ++generation;
    const ms = Date.now() - startedAt;
    const take = await recorder.stop();
    if (!alive() || mine !== generation) return;
    if (!take?.blob) return setPhase('error', s.err_recording_failed);
    if (ms < MIN_TAKE_MS) return setPhase('error', s.err_too_short);
    setPhase('processing', s.listening);
    const takeId = crypto.randomUUID();
    try {
      const value = await ctx.mutate(() =>
        evaluateVoice({ api, blob: take.blob, language, assetId: '', segmentId: id, takeId }),
      );
      if (!alive() || mine !== generation) return;
      last = { ...value, ms, takeId, coaching: null };
      paintSaid();
      setPhase('result', value.saved ? '' : s.keptFailed);
      q('[data-sp-deeper]').disabled = false;
      void coach(mine);
    } catch (error) {
      if (!alive() || mine !== generation || error?.name === 'AbortError') return;
      setPhase('error', /No speech/.test(String(error?.message)) ? s.err_no_speech : s.err_service);
    }
  }

  function paintSaid() {
    const host = q('[data-sp-said]');
    host.hidden = !last;
    if (!last) return;
    host.innerHTML = saidHtml({ s, heard: last.heard, ms: last.ms, comment: last.coaching?.next_attempt || '', language });
  }

  /* The comment is the coaching's own next step for the learner, requested in the support
     language; while it is on its way, or when it does not come, the card has no comment line. */
  async function coach(mine) {
    try {
      const result = await api.spokenResponseCoaching({
        transcript: last.heard.slice(0, 2400),
        source_language: language,
        target_language: ctx.support,
        situation: String(topic || '').slice(0, 1200),
      });
      if (!alive() || mine !== generation) return;
      last.coaching = result?.available ? result : null;
      paintSaid();
    } catch {}
  }

  function closeSheet() {
    if (!sheet) return;
    sheet.scrim.remove();
    sheet.panel.remove();
    document.removeEventListener('keydown', sheet.onKey);
    sheet = null;
    q('[data-sp-deeper]')?.focus({ preventScroll: true });
  }

  function openDeeper() {
    if (!last) return;
    closeSheet();
    const scrim = document.createElement('div');
    scrim.className = 'qs-scrim';
    const panel = document.createElement('div');
    panel.className = 'qs qs--speak qs--free';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-label', s.deeper);
    panel.tabIndex = -1;
    const coaching = last.coaching ? spokenCoaching(c, last.coaching, language) : `<p class="meta">${esc(c.coachingUnavailable)}</p>`;
    panel.innerHTML = `<button type="button" class="qs-x" data-sp-close aria-label="${esc(s.close)}">${icon('x', { size: 18 })}</button><span class="sp-label">${esc(s.deeper)}</span>${coaching}<details class="sp-free__evidence"><summary>${esc(c.measuredHere)}</summary>${voiceEvidence(c, last.evaluation, language)}</details><div class="sp-free__ways"><button type="button" class="sp-dbtn" data-free-understand>${esc(c.lookCloser)}</button><button type="button" class="sp-dbtn" data-free-develop>${esc(c.develop)}</button><button type="button" class="sp-dbtn" data-free-talk>${esc(c.conversationStart)}</button></div>`;
    document.body.append(scrim, panel);
    const onKey = (event) => event.key === 'Escape' && closeSheet();
    sheet = { scrim, panel, onKey };
    scrim.addEventListener('click', closeSheet);
    document.addEventListener('keydown', onKey);
    panel.querySelector('[data-sp-close]').onclick = closeSheet;
    panel.querySelector('[data-free-understand]').onclick = () => {
      closeSheet();
      openUnderstanding(ctx, { origin: { id, where: title, why: 'from_speaking' }, selection: last.heard, context: `${topic}\n${last.heard}`.slice(0, 2400), title });
    };
    panel.querySelector('[data-free-develop]').onclick = () => {
      // Each take has its own draft identity; an existing draft is never replaced.
      const draftId = `expression:voice:${last.takeId}`;
      if (!memory.value.expressions[draftId]) memory.write(draftId, last.heard);
      memory.enter({ id: draftId, title, intent: 'writing', excerpt: topic });
      closeSheet();
      window.location.hash = link('expression', { id: draftId });
    };
    panel.querySelector('[data-free-talk]').onclick = () => {
      closeSheet();
      startConversation(ctx, { title, situation: topic });
    };
    panel.focus({ preventScroll: true });
  }

  mic.onclick = () => (phase === 'recording' ? stop() : phase === 'processing' ? undefined : start());
  q('[data-sp-deeper]').onclick = openDeeper;
  q('[data-sp-other]').onclick = () => next && ctx.go('practice', { intent: 'speaking', id: next });
  q('[data-sp-back]').onclick = () => ctx.go('practice', { intent: 'speaking' });

  return () => {
    disposed = true;
    generation++;
    clearInterval(ticker);
    closeSheet();
    recorder.cleanup();
  };
}
