/* Free talk (D-066, D-067), drawn from Orena Speaking at its source: "Speaking · free talk" (390x844;
   no desktop frame, so a desk shows the same column, centred) and 04 "Free talk result" (desktop and
   mobile).

   A different capability from pronunciation of a given line, and scored only on what is measured
   (D-076): pronunciation and fluency come from the provider's free-speech (unscripted) assessment;
   grammar and vocabulary have no approved evaluator yet, so they show 0 as the metric rule says; no
   overall score is computed while a component it would need is missing, and there is no "last time".
   The corrections and the line to say again come from the existing spoken coaching - feedback, not a
   score. Recognition, the evidence envelope, the audio-free attempt record and the coaching are the
   plumbing that already existed; nothing is recorded or evaluated twice. The recording itself lives
   in this tab only.

   What the old room offered beyond the frames (look closer, turn it into writing, start a
   conversation) stays reachable under the result (UI_BACKEND_GAPS S20). */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { speakCopy, fill } from './speaking-copy.js';
import { judgementLabel } from './understanding.js';
import { openUnderstanding } from './understanding.js';
import { speechConfigured } from './voice-response.js';
import { startConversation } from './conversation.js';
import { createLocalAudioRecorder } from '../capabilities/audio-recorder.js';
import { evaluateVoice } from '../capabilities/voice-feedback.js';
import { MIN_TAKE_MS } from '../capabilities/speaking-take.js';
import { decodeAudio, waveformBars } from '../capabilities/audio-analysis.js';
import { link } from '../product/intent.js';

const MAX_FREE_MS = 120_000;
const clock = (ms) => {
  const seconds = Math.max(0, Math.round(ms / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
};
const short = (ms) => {
  const seconds = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
};
const measured = (value) => typeof value === 'number' && Number.isFinite(value);

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

/* The corrections the coaching found, up to three (the frame's "3 CHỖ NÊN SỬA"). */
export function fixesOf(coaching) {
  return (coaching?.landed_differently || []).filter((item) => item?.quote).slice(0, 3);
}

/* The transcript with each corrected quote marked where it occurs. */
export function markedTranscript(heard, fixes, language) {
  let html = esc(heard);
  for (const fix of fixes) {
    const quote = esc(fix.quote);
    if (quote && html.includes(quote)) html = html.replace(quote, `<mark class="sp-fix-mark">${quote}</mark>`);
  }
  return `<span lang="${esc(language)}">${html}</span>`;
}

function criterion(label, value, isMeasured) {
  const shown = isMeasured ? Math.round(value) : 0;
  return `<div class="sp-crit"><span class="sp-crit__label">${esc(label)}</span><span class="sp-bar"><i style="width:${shown}%"></i></span><span class="sp-crit__value">${shown}</span></div>`;
}

/* 04 · the free talk result, both frames (CSS shows the one that belongs). */
export function freeResultHtml({ s, c, title, name = '', topic, language, ms, heard, coaching, scores, bars }) {
  const fixes = fixesOf(coaching);
  const headline = coaching == null ? c.coachingWorking : fixes.length === 1 ? s.ftHeadlineFixOne : fixes.length ? fill(s.ftHeadlineFix, { n: fixes.length }) : s.ftHeadlineNone;
  const criteria = `${criterion(s.critFluency, scores?.fluency, measured(scores?.fluency))}${criterion(s.critGrammar, 0, false)}${criterion(s.critVocab, 0, false)}${criterion(s.critPron, scores?.pron, measured(scores?.pron))}`;
  const cards = fixes
    .map((fix) => `<div class="sp-fix"><span class="sp-fix__label">${esc((judgementLabel(c, fix.judgement) || '').toUpperCase())}</span><span class="sp-fix__change"><s lang="${esc(language)}">${esc(fix.quote)}</s>${fix.instead ? ` → <b lang="${esc(language)}">${esc(fix.instead)}</b>` : ''}</span>${fix.why ? `<span class="sp-fix__why">${esc(fix.why)}</span>` : ''}</div>`)
    .join('');
  const first = fixes[0];
  const phoneCard = first
    ? `<div class="sp-fix sp-fix--phone"><span class="sp-fix__label">${esc([fill(s.ftFixOf, { i: 1, n: fixes.length }), (judgementLabel(c, first.judgement) || '').toUpperCase()].filter(Boolean).join(' · '))}</span><span class="sp-fix__change"><s lang="${esc(language)}">${esc(first.quote)}</s>${first.instead ? ` → <b lang="${esc(language)}">${esc(first.instead)}</b>` : ''}</span>${first.why ? `<span class="sp-fix__why">${esc(first.why)}</span>` : ''}</div>`
    : '';
  // The coaching's one line in the learning language (never its advice in the support language).
  const again = String(coaching?.say_again || '').trim();
  const langName = s[`langName_${language === 'zh' ? 'zh' : 'en'}`];
  const wave = (bars || []).map((value) => `<i class="${value > 0.6 ? 'is-strong' : ''}" style="block-size:${Math.max(6, Math.round(value * 100))}%"></i>`).join('');
  const ring = `<span class="sp-ring sp-ring--ft" style="--score:0%" role="img" aria-label="0"><b>0</b></span>`;
  return `<section class="sp-room sp-ftr" data-view="free-result">
<header class="sp-top sp-ftr__top"><button type="button" class="sp-back" data-sp-ftr-back><span class="sp-ftr__arrow">${icon('arrow-left', { size: 20 })}</span><span class="sp-back__caret">${icon('caret-left', { size: 22 })}</span><span class="sp-lesson sp-ftr__desk">${esc(`${title} · `)}<span lang="${esc(language)}">${esc(name || topic)}</span></span><span class="sp-lesson sp-ftr__phone" lang="${esc(language)}">${esc(name || topic)}</span></button><span class="sp-ftr__meta"><span class="sp-ftr__desk">${esc(`${langName} · `)}</span>${esc(short(ms))}</span><button type="button" class="sp-ftr__morebtn" data-sp-ftr-more aria-haspopup="dialog" aria-label="${esc(s.ftMore)}">${icon('dots-three', { size: 22 })}</button></header>
<div class="sp-ftr__grid"><div class="sp-ftr__main"><div class="sp-ftr__said"><div class="sp-ftr__play"><button type="button" class="sp-ftr__playbtn" data-sp-ftr-play aria-label="${esc(s.ftPlay)}">${icon('play', { size: 22, filled: true })}</button><div class="sp-ftr__wave">${wave}</div></div><span class="sp-label">${esc(s.ftSaid)}</span><p class="sp-ftr__words">${markedTranscript(heard, fixes, language)}</p></div>
${cards ? `<div class="sp-ftr__fixes"><span class="sp-label">${esc(fixes.length === 1 ? s.ftFixesOne : fill(s.ftFixes, { n: fixes.length }))}</span><div class="sp-ftr__cards">${cards}</div></div>` : ''}</div>
<div class="sp-ftr__side"><div class="sp-ftr__score"><div class="sp-ftr__head">${ring}<div><strong>${esc(headline)}</strong></div></div><div class="sp-crits">${criteria}</div></div>
${again ? `<div class="sp-ftr__again"><span class="sp-label">${esc(s.ftSayAgainLabel)}</span><p lang="${esc(language)}">${esc(again)}</p></div>` : ''}
<div class="sp-ftr__buttons">${again ? `<button type="button" class="sp-ftbtn" data-sp-ftr-fixed>${icon('microphone', { size: 18 })}<span>${esc(s.ftSayFixed)}</span></button>` : ''}<button type="button" class="sp-ftbtn sp-ftbtn--accent" data-sp-ftr-again>${icon('microphone', { size: 18, filled: true })}<span>${esc(s.ftSpeakAgain)}</span></button></div>
</div></div>
${phoneCard ? `<template data-sp-ftr-phonecard>${phoneCard}</template>` : ''}
<audio data-sp-ftr-audio preload="auto" hidden></audio></section>`;
}

/* The three older ways on from a free-talk take, one step in (S14). */
export const MORE_WAYS = [
  { name: 'understand', icon: 'magnifying-glass', label: 'lookCloser' },
  { name: 'develop', icon: 'pen-nib', label: 'develop' },
  { name: 'talk', icon: 'chats-circle', label: 'conversationStart' },
];

export function moreSheetHtml({ s, c, heard, language }) {
  const ways = MORE_WAYS.map(
    (way) => `<button type="button" class="ls-way" data-way="${way.name}">${icon(way.icon, { size: 20 })}<span class="ls-way__text"><strong>${esc(c[way.label])}</strong></span></button>`,
  ).join('');
  return `<button type="button" class="qs-x" data-way="close" aria-label="${esc(c.quickClose || '')}">${icon('x', { size: 18 })}</button><span class="ds-label ls-title">${esc(s.ftMore)}</span><p class="ls-line" lang="${esc(language)}">${esc(heard)}</p><div class="ls-ways">${ways}</div>`;
}

function openMoreSheet({ s, c, heard, language, onPick }) {
  const scrim = document.createElement('div');
  scrim.className = 'qs-scrim';
  const sheet = document.createElement('div');
  sheet.className = 'qs qs--deep';
  sheet.setAttribute('role', 'dialog');
  sheet.setAttribute('aria-modal', 'true');
  sheet.setAttribute('aria-label', s.ftMore);
  sheet.tabIndex = -1;
  sheet.innerHTML = moreSheetHtml({ s, c, heard, language });
  const opener = document.activeElement;
  document.body.append(scrim, sheet);
  sheet.focus({ preventScroll: true });
  let open = true;
  const close = () => {
    if (!open) return;
    open = false;
    window.removeEventListener('hashchange', close);
    document.removeEventListener('keydown', onKey);
    scrim.remove();
    sheet.remove();
    if (opener?.isConnected) opener.focus();
  };
  const onKey = (event) => {
    if (event.key === 'Escape') close();
  };
  scrim.addEventListener('click', close);
  sheet.addEventListener('click', (event) => {
    const way = event.target.closest('[data-way]')?.dataset.way;
    if (!way) return;
    close();
    if (way !== 'close') onPick(way);
  });
  // A sheet must not outlive the screen it was opened from.
  window.addEventListener('hashchange', close);
  document.addEventListener('keydown', onKey);
}

export function mountFreeTalk(root, ctx, { id, title, name = '', topic, cue, next }) {
  const { api, c, language, memory } = ctx;
  const s = speakCopy(ctx.ui);
  let disposed = false;
  let phase = 'idle';
  const recorder = createLocalAudioRecorder();
  let startedAt = 0;
  let ticker = 0;
  let generation = 0;
  let last = null; // { heard, evaluation, ms, coaching, takeId, blob, url, scores, bars }
  let screen = 'talk';
  const alive = () => !disposed && (ctx.alive ? ctx.alive() : true) && root.isConnected;
  const q = (selector) => root.querySelector(selector);

  memory?.enter?.({ id, title, intent: 'speaking', excerpt: topic });

  function setPhase(value, message = '') {
    phase = value;
    const room = q('.sp-free');
    if (!room) return;
    room.dataset.phase = value;
    const mic = q('[data-sp-mic]');
    mic.disabled = value === 'processing';
    mic.setAttribute('aria-label', value === 'recording' ? s.stop : s.record);
    mic.setAttribute('aria-pressed', String(value === 'recording'));
    const hint = q('[data-sp-hint]');
    hint.textContent = message;
    hint.classList.toggle('sp-hint--error', value === 'error');
  }

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
    // The free-speech measurement runs beside recognition; its failure is not the learner's and
    // simply leaves pronunciation and fluency unmeasured.
    const unscripted = api.assessPronunciation(take.blob, language, '', 'unscripted').catch(() => null);
    try {
      const value = await ctx.mutate(() => evaluateVoice({ api, blob: take.blob, language, assetId: '', segmentId: id, takeId }));
      if (!alive() || mine !== generation) return;
      if (last?.url) URL.revokeObjectURL(last.url);
      last = { ...value, ms, takeId, coaching: undefined, blob: take.blob, url: URL.createObjectURL(take.blob), scores: null, bars: [] };
      paintSaid();
      setPhase('result', value.saved ? '' : s.keptFailed);
      q('[data-sp-deeper]').disabled = false;
      void coach(mine);
      void unscripted.then((result) => {
        if (!alive() || mine !== generation || !result || result.score_kind !== 'measured') return;
        last.scores = { pron: result.pron_score ?? result.accuracy_score, fluency: result.fluency_score };
        if (screen === 'result') paintResult();
      });
      void decodeAudio(take.blob)
        .then((decoded) => {
          if (!alive() || mine !== generation) return;
          last.bars = waveformBars(decoded.samples, 40);
          if (screen === 'result') paintResult();
        })
        .catch(() => {});
    } catch (error) {
      if (!alive() || mine !== generation || error?.name === 'AbortError') return;
      setPhase('error', /No speech/.test(String(error?.message)) ? s.err_no_speech : s.err_service);
    }
  }

  function paintSaid() {
    const host = q('[data-sp-said]');
    if (!host) return;
    host.hidden = !last;
    if (!last) return;
    host.innerHTML = saidHtml({ s, heard: last.heard, ms: last.ms, comment: last.coaching?.next_attempt || '', language });
  }

  /* The comment is the coaching's own next step, requested in the support language; while it is on
     its way, or when it does not come, the card has no comment line. */
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
    } catch {
      if (!alive() || mine !== generation) return;
      last.coaching = null;
    }
    if (screen === 'talk') paintSaid();
    else paintResult();
  }

  function paintTalk() {
    screen = 'talk';
    root.innerHTML = freeTalkHtml({ s, title, topic, cue, language });
    const mic = q('[data-sp-mic]');
    mic.onclick = () => (phase === 'recording' ? stop() : phase === 'processing' ? undefined : start());
    q('[data-sp-deeper]').onclick = () => last && paintResult();
    q('[data-sp-other]').onclick = () => next && ctx.go('practice', { intent: 'speaking', id: next });
    q('[data-sp-back]').onclick = () => ctx.go('practice', { intent: 'speaking' });
    if (last) {
      paintSaid();
      q('[data-sp-deeper]').disabled = false;
    }
    setPhase(phase === 'recording' ? 'idle' : phase === 'processing' ? 'processing' : last ? 'result' : 'idle');
    void speechConfigured(api).then((ready) => {
      if (!alive() || ready || screen !== 'talk') return;
      q('[data-sp-mic]').disabled = true;
      setPhase('error', c.voiceUnavailable);
    });
  }

  function paintResult() {
    if (!last) return;
    screen = 'result';
    root.innerHTML = freeResultHtml({ s, c, title, name, topic, language, ms: last.ms, heard: last.heard, coaching: last.coaching, scores: last.scores, bars: last.bars });
    // The phone draws one correction card under what you said.
    const template = q('[data-sp-ftr-phonecard]');
    if (template) q('.sp-ftr__said').insertAdjacentHTML('afterend', template.innerHTML);
    q('[data-sp-ftr-back]').onclick = paintTalk;
    q('[data-sp-ftr-play]').onclick = () => {
      const audio = q('[data-sp-ftr-audio]');
      audio.src = last.url;
      audio.currentTime = 0;
      audio.play().catch(() => {});
    };
    q('[data-sp-ftr-again]').onclick = () => {
      paintTalk();
      void start();
    };
    const fixed = q('[data-sp-ftr-fixed]');
    if (fixed)
      fixed.onclick = () => {
        // Saying the corrected line is pronunciation of a given line: the Speaking workspace.
        const text = String(last.coaching?.say_again || '').trim().slice(0, 400);
        ctx.go('practice', { intent: 'shadowing', id: `say:${text}` });
      };
    // Free talk's older ways on (look closer, write it up, talk it through) are kept, one step in:
    // behind "⋯", in the same sheet Listening uses for its deeper ways (Design Contract; S14).
    const ways = {
      understand: () => openUnderstanding(ctx, { origin: { id, where: title, why: 'from_speaking' }, selection: last.heard, context: `${topic}\n${last.heard}`.slice(0, 2400), title }),
      develop: () => {
        // Each take has its own draft identity; an existing draft is never replaced.
        const draftId = `expression:voice:${last.takeId}`;
        if (!memory.value.expressions[draftId]) memory.write(draftId, last.heard);
        memory.enter({ id: draftId, title, intent: 'writing', excerpt: topic });
        window.location.hash = link('expression', { id: draftId });
      },
      talk: () => startConversation(ctx, { title, situation: topic }),
    };
    q('[data-sp-ftr-more]').onclick = () => openMoreSheet({ s, c, heard: last.heard, language, onPick: (way) => ways[way]?.() });
  }

  paintTalk();

  return () => {
    disposed = true;
    generation++;
    clearInterval(ticker);
    recorder.cleanup();
    root.querySelectorAll('audio').forEach((audio) => audio.pause());
    if (last?.url) URL.revokeObjectURL(last.url);
  };
}
