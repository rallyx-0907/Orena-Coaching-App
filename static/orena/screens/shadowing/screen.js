/* Shadowing (frame 28, D-091; route `#/listen/:id/shadow`, focus, lesson:true). Model → Countdown
   → Speak with the model → Result, one Listening-lesson line at a time.

   The assessment is the same provider-neutral contract every other Speaking surface already uses
   (`capabilities/speaking-take.js`, `capabilities/pronunciation-result.js`) — real audio in, a real
   measured result or a real, honest failure out. The old prototype's retry-count lag/timing formula
   (C5 §1) is not reproduced: "Start lag" and "Timing match" here come only from the provider's own
   per-word offsets, already on `pronunciationView`'s own `view.words[i].offsetMs`/`.durationMs`
   (`model.js#lagMs`/`matchPercent`), null (shown as "—") when the provider measured nothing. Mic
   states (permission/blocked/not-heard/offline/provider trouble) are the shared sheet
   (`screens/mic/sheet.js`) — no mic UI is built here. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { langAttr } from '../../kit/lang.js';
import { api } from '../../infrastructure/api.js';
import { registerActionHandler } from '../../agent/dispatcher.js';
import { openMicState, micGate } from '../mic/sheet.js';
import {
  connectMediaPlayer,
  disconnectMediaPlayer,
  mediaPlayer,
  replaySegment,
  stopSegmentPlayback,
  playbackAvailable,
  setPlaybackRate,
  segmentPlaybackDelayMs,
} from '../../capabilities/media-player.js';
import { pronunciationView } from '../../capabilities/pronunciation-result.js';
import { createSpeakingTake, TAKE } from '../../capabilities/speaking-take.js';
import { createLocalAudioRecorder } from '../../capabilities/audio-recorder.js';
import { watchMicrophone } from '../../capabilities/mic-readiness.js';
import { showAssessmentRefusal } from '../plan/quota-notice.js';
import { t } from './copy.js';
import { openMedia } from '../../product/media-source.js';
import {
  mapLesson,
  startIndex,
  rateLabel,
  nextRate,
  COUNTDOWN,
  clock,
  lagMs,
  matchPercent,
  lagSeconds,
  elapsedSeconds,
  percentLabel,
  issueWord,
  errorLabelKey,
  phaseLabelKey,
  phaseTone,
  waveState,
  waveBars,
  levelHeights,
  WAVE_BARS,
  roundsBySegment,
  nextRounds,
} from './model.js';

const COUNT_STEP_MS = 1000; // the frame's countdown: 3, 2, 1, one second each
const SPEAK_TAIL_MS = 800;

/* Plain text into an element: copy and lesson data are text, never markup (`mount` sets innerHTML). */
function setText(target, value) {
  if (target) target.textContent = String(value ?? '');
}

function waveMarkup() {
  return html`${waveBars().map((bar) => html`<span class="s-shadow__bar" style="height:${bar.height}%;animation-delay:${bar.delay}ms"></span>`)}`;
}

export default async function mountShadowing(element, ctx) {
  const support = languages().support;
  const lessonId = String(ctx.params?.id || '').trim();
  const [payload] = await Promise.all([openMedia(lessonId, {api, support, language: ctx.context.language, owner: ctx.context.owner || 'local', alive: () => ctx.isCurrent()}), useStyles('screens/shadowing/shadowing.css')]);
  if (!ctx.isCurrent()) return undefined;

  const lesson = mapLesson(payload);
  if (!lesson.segments.length) throw new Error(`Shadowing: lesson "${lessonId}" has no lines to shadow.`);
  ctx.setCrumb(lesson.title || shellCopy('shadowing'));

  // `seg` is the Listening Workspace's hand-off key; `segment` is the one the Speaking rooms use.
  let index = Math.min(lesson.segments.length - 1, startIndex(lesson.segments, ctx.query?.get('seg') || ctx.query?.get('segment')));
  let rate = 1;
  let roundRate = 1; // the speed the round on screen was shadowed at (the result's "Speed")
  let phase = 'idle';
  let countdown = 3;
  let view = pronunciationView(null);
  let take = null;
  let token = 0; // invalidates a stale countdown/model/speak chain on navigation
  let speakStopTimer = 0;
  let elapsedTicker = 0;
  let mic = null; // the live microphone level while the learner speaks (the bars are real then)
  const levels = new Array(WAVE_BARS).fill(0);
  let awaitingOnline = null; // a take whose assessment failed for want of a network

  element.classList.add('s-shadow');
  mount(
    element,
    html`<div class="s-shadow__head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-shadow__headcol">
        <div class="s-shadow__title">${shellCopy('shadowing')}</div>
        <div class="s-shadow__sub" data-sub lang="${langAttr(lesson.language)}"></div>
      </div>
      <button type="button" class="s-shadow__rate" data-rate>${rateLabel(rate)}</button>
    </div>
    <div class="s-shadow__card">
      <div class="s-shadow__body" data-scroll-region data-body></div>
      <div class="s-shadow__dock" data-dock></div>
    </div>
    <div class="s-shadow__foot">
      <button type="button" class="s-shadow__navbtn" data-prev>${t('previousLine')}</button>
      <button type="button" class="s-shadow__navbtn" data-next>${t('nextLine')}${raw(icon('arrow-right', { size: 16 }))}</button>
    </div>
    <div class="s-shadow__media" data-media aria-hidden="true"></div>
    <audio data-take-audio hidden></audio>`,
  );
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());

  const mediaRoot = element.querySelector('[data-media]');
  const hasClip = playbackAvailable(lesson.playback);
  if (hasClip) {
    mount(mediaRoot, raw(mediaPlayer(lesson.playback, lesson.title, { startMs: 0, controls: false })));
    connectMediaPlayer(mediaRoot, lesson.playback);
  }
  const takeAudio = element.querySelector('[data-take-audio]');

  function segment() {
    return lesson.segments[index];
  }
  function span() {
    const seg = segment();
    return Math.max(0, seg.endMs - seg.startMs) || null;
  }

  function paintHead() {
    const seg = segment();
    setText(element.querySelector('[data-sub]'), t('subtitle', { title: lesson.title, n: index + 1, time: `${clock(seg.startMs)}–${clock(seg.endMs)}` }));
    setText(element.querySelector('[data-rate]'), rateLabel(rate));
    element.querySelector('[data-prev]').disabled = index === 0;
    element.querySelector('[data-next]').disabled = index >= lesson.segments.length - 1;
  }

  function waveClass() {
    const wave = waveState(phase);
    return `s-shadow__wave${wave.active ? ' is-active' : ''}${wave.speaking ? ' is-speaking' : ''}`;
  }

  /* What sits under the line: the result (stats, the one thing to fix) scrolls with the body; the
     start call-to-action and the result's buttons are docked below it, so a primary control is
     never scrolled away (rule 49). */
  function resultMarkup() {
    const lag = lagSeconds(lagMs(view));
    const pct = matchPercent(view.timing);
    const issue = issueWord(view);
    return html`<div class="s-shadow__stats">
        <div class="s-shadow__stat"><div class="s-shadow__statlabel">${t('statLag')}</div><div class="s-shadow__statvalue">${lag == null ? '—' : t('seconds', { n: lag })}</div></div>
        <div class="s-shadow__stat"><div class="s-shadow__statlabel">${t('statMatch')}</div><div class="s-shadow__statvalue">${percentLabel(pct)}</div></div>
        <div class="s-shadow__stat"><div class="s-shadow__statlabel">${t('statSpeed')}</div><div class="s-shadow__statvalue">${rateLabel(roundRate)}</div></div>
      </div>
      ${issue ? html`<div class="s-shadow__issue"><b>${t('issueLabel')}</b> · ${issue.text} · ${t(errorLabelKey(issue.errorType))}</div>` : ''}`;
  }

  function dockMarkup() {
    if (phase === 'idle')
      return html`<button type="button" class="o-btn o-btn--primary s-shadow__start" data-start>${raw(icon('play', { size: 14 }))}${t('startCta')}</button>
      <div class="s-shadow__note">${t('headphonesNote')}</div>`;
    if (phase === 'result')
      return html`<div class="s-shadow__resultrow">
        <button type="button" class="s-shadow__resultbtn" data-play-model${hasClip ? '' : ' disabled'}>${raw(icon('play', { size: 14 }))}${t('model')}</button>
        <button type="button" class="s-shadow__resultbtn" data-play-mine${take?.takeUrl ? '' : ' disabled'}>${raw(icon('play', { size: 14 }))}${t('mine')}</button>
        <button type="button" class="s-shadow__resultbtn" data-rehearse>${t('rehearse')}</button>
        <button type="button" class="o-btn o-btn--primary s-shadow__retry" data-retry>${t('retry')}</button>
      </div>`;
    return '';
  }

  function paintCard() {
    const seg = segment();
    mount(
      element.querySelector('[data-body]'),
      html`<div class="s-shadow__phase s-shadow__phase--${phaseTone(phase)}">${t(phaseLabelKey(phase))}</div>
      <div class="s-shadow__line" lang="${langAttr(lesson.language)}">${seg.text}</div>
      ${phase === 'count' ? html`<div class="s-shadow__count">${countdown}</div>` : ''}
      <div class="${waveClass()}">${waveMarkup()}</div>
      ${phase === 'speak' ? html`<div class="s-shadow__recording" data-recording>● ${t('recordingLabel', { t: t('seconds', { n: '0.0' }) })}</div>` : ''}
      ${phase === 'result' ? resultMarkup() : ''}`,
    );
    mount(element.querySelector('[data-dock]'), dockMarkup());
    bindCard();
  }

  function bindCard() {
    element.querySelector('[data-start]')?.addEventListener('click', () => micGate(ctx, () => void beginShadow()));
    element.querySelector('[data-play-model]')?.addEventListener('click', playModelOnly);
    element.querySelector('[data-play-mine]')?.addEventListener('click', () => {
      if (!take?.takeUrl) return;
      takeAudio.src = take.takeUrl;
      takeAudio.currentTime = 0;
      takeAudio.play().catch(() => {});
    });
    element.querySelector('[data-rehearse]')?.addEventListener('click', () => {
      ctx.go(ctx.href('speak', { id: `media:${lesson.id}` }, { segment: segment().id }));
    });
    element.querySelector('[data-retry]')?.addEventListener('click', () => micGate(ctx, () => void beginShadow()));
  }

  function playModelOnly() {
    if (!hasClip) return;
    stopSegmentPlayback(mediaRoot, lesson.playback);
    replaySegment(mediaRoot, lesson.playback, segment().startMs, segment().endMs, rate);
  }

  function setPhase(next) {
    if (next !== 'speak') stopLevels();
    phase = next;
    paintCard();
    paintHead();
  }

  /* While the learner speaks the bars are the microphone's own level (never a made-up shape); a
     silent room reads as a flat row. The design's resting bars are what every other phase draws. */
  function startLevels() {
    stopLevels();
    levels.fill(0);
    mic = watchMicrophone({
      onLevel: (peak) => {
        if (phase !== 'speak') return;
        levels.shift();
        levels.push(Math.min(1, Number(peak) || 0));
        const heights = levelHeights(levels);
        element.querySelectorAll('.s-shadow__wave.is-speaking .s-shadow__bar').forEach((bar, at) => {
          bar.style.height = `${heights[at]}%`;
        });
      },
    });
  }
  function stopLevels() {
    mic?.stop?.();
    mic = null;
  }

  async function beginShadow() {
    const mine = ++token;
    clearTimeout(speakStopTimer);
    clearInterval(elapsedTicker);
    take?.dispose();
    take = null;
    awaitingOnline = null;
    view = pronunciationView(null);
    roundRate = rate;

    // Model.
    setPhase('model');
    if (hasClip) {
      stopSegmentPlayback(mediaRoot, lesson.playback);
      replaySegment(mediaRoot, lesson.playback, segment().startMs, segment().endMs, rate);
    }
    const modelDelay = hasClip ? segmentPlaybackDelayMs(segment().startMs, segment().endMs, rate) || 1200 : 400;
    await wait(modelDelay);
    if (mine !== token) return;

    // Countdown.
    for (const n of COUNTDOWN) {
      if (mine !== token) return;
      countdown = n;
      setPhase('count');
      await wait(COUNT_STEP_MS);
    }
    if (mine !== token) return;

    // Speak: record and play the model together.
    setPhase('speak');
    take = newTake();
    const started = await take.start();
    if (mine !== token) return;
    if (!started) return; // take's own onChange already routed the real failure to the mic sheet.
    startLevels();
    elapsedTicker = setInterval(() => {
      if (mine !== token) return clearInterval(elapsedTicker);
      setText(element.querySelector('[data-recording]'), `● ${t('recordingLabel', { t: t('seconds', { n: elapsedSeconds(take.elapsedMs()) }) })}`);
    }, 200);
    if (hasClip) {
      stopSegmentPlayback(mediaRoot, lesson.playback);
      replaySegment(mediaRoot, lesson.playback, segment().startMs, segment().endMs, rate);
    }
    const speakDelay = (hasClip ? segmentPlaybackDelayMs(segment().startMs, segment().endMs, rate) || 1200 : 1200) + SPEAK_TAIL_MS;
    speakStopTimer = setTimeout(() => {
      if (mine === token && take?.phase === TAKE.RECORDING) void take.stop(segment().text);
    }, speakDelay);
  }

  function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function newTake() {
    return createSpeakingTake({
      api,
      recorder: createLocalAudioRecorder(),
      language: lesson.language,
      keep: { assetId: lesson.assetId, segmentId: segment().id },
      onChange: onTakeChange,
    });
  }

  function onTakeChange(state) {
    if (state.phase === TAKE.PROCESSING) {
      clearInterval(elapsedTicker);
      setPhase('processing');
      return;
    }
    if (state.phase === TAKE.RESULT && state.result) {
      // The take announces itself again once its attempt is kept (`kept`, `attemptId`): the same
      // result, not a second round - one round is counted and drawn once.
      if (phase === 'result') return;
      view = pronunciationView(state.result, { language: lesson.language, modelSpanMs: span() });
      setPhase('result');
      void keepRound();
      return;
    }
    if (state.phase === TAKE.ERROR) {
      clearInterval(elapsedTicker);
      setPhase('idle');
      routeFailure(state.error);
    }
  }

  /* A failed take is kept in this tab (the blob never leaves it), so "retry the assessment" scores
     the same recording again - the learner does not record twice - and the offline sheet's promise
     ("assessed automatically when you're back online") is kept for as long as the room is open. */
  function retryAssessment() {
    if (take?.phase === TAKE.ERROR) take.retry();
    else micGate(ctx, () => void beginShadow());
  }

  function routeFailure(error) {
    const kind = error?.kind;
    if (showAssessmentRefusal(ctx, error)) return;
    if (kind === 'no_speech' || kind === 'too_short') {
      void openMicState(ctx, {
        state: 'notheard',
        onAction: (key) => {
          if (key === 'tryagain') micGate(ctx, () => void beginShadow());
        },
      });
      return;
    }
    if (kind === 'microphone' || kind === 'unsupported') {
      void openMicState(ctx, { state: 'blocked', textFallback: false, onAction: (key) => key === 'retry' && micGate(ctx, () => void beginShadow()) });
      return;
    }
    if (kind === 'offline') {
      awaitingOnline = take;
      void openMicState(ctx, { state: 'offline', onAction: () => undefined });
      return;
    }
    void openMicState(ctx, {
      state: 'provider',
      onAction: (key) => {
        if (key === 'retry') error?.retry && take ? retryAssessment() : micGate(ctx, () => void beginShadow());
      },
    });
  }

  function onOnline() {
    const held = awaitingOnline;
    awaitingOnline = null;
    if (held && held === take && take.phase === TAKE.ERROR) take.retry();
  }
  window.addEventListener('online', onOnline);

  /* Best effort, real evidence: how many rounds of this line the learner has shadowed, the same
     count Progress already reads (C5 §3). The server replaces the record wholesale, so the running
     total is read fresh right before each write and a failed read writes nothing - a count the room
     could not read is never overwritten with 1. A failure here is not the learner's. */
  async function keepRound() {
    if (!lesson.assetId) return;
    try {
      const seg = segment();
      const stored = roundsBySegment((await api.shadowingProgress(lesson.assetId))?.items || []);
      await api.saveShadowingProgress({ asset_id: lesson.assetId, segment_id: seg.id, completed_rounds: nextRounds(stored, seg.id) });
    } catch {
      /* not persisted this time; the next real round tries again */
    }
  }

  function goTo(nextIndex) {
    if (nextIndex < 0 || nextIndex >= lesson.segments.length) return;
    token += 1;
    clearTimeout(speakStopTimer);
    clearInterval(elapsedTicker);
    stopLevels();
    take?.dispose();
    take = null;
    awaitingOnline = null;
    if (hasClip) stopSegmentPlayback(mediaRoot, lesson.playback);
    index = nextIndex;
    phase = 'idle';
    view = pronunciationView(null);
    paintCard();
    paintHead();
  }

  element.querySelector('[data-rate]').addEventListener('click', () => {
    rate = nextRate(rate);
    if (hasClip) setPlaybackRate(mediaRoot, lesson.playback, rate);
    paintHead();
  });
  element.querySelector('[data-prev]').addEventListener('click', () => goTo(index - 1));
  element.querySelector('[data-next]').addEventListener('click', () => goTo(index + 1));

  paintHead();
  paintCard();

  const releasePlayModel = registerActionHandler('play_model', () => {
    playModelOnly();
    return { ok: true };
  });
  const releasePlayUser = registerActionHandler('play_user', () => {
    if (!take?.takeUrl) return { ok: false, reason: 'no_take' };
    takeAudio.src = take.takeUrl;
    takeAudio.currentTime = 0;
    takeAudio.play().catch(() => {});
    return { ok: true };
  });
  const releaseSayAgain = registerActionHandler('say_again', () => {
    if (phase === 'speak' || phase === 'processing') return { ok: false, reason: 'busy' };
    micGate(ctx, () => void beginShadow());
    return { ok: true };
  });

  return () => {
    token += 1;
    clearTimeout(speakStopTimer);
    clearInterval(elapsedTicker);
    stopLevels();
    window.removeEventListener('online', onOnline);
    take?.dispose();
    releasePlayModel();
    releasePlayUser();
    releaseSayAgain();
    takeAudio.pause();
    if (hasClip) disconnectMediaPlayer(mediaRoot);
  };
}
