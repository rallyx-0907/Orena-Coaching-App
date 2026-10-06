/* Dictation (frame 07, D-091; route `#/listen/:id/dictation`, focus, lesson:true). One segment of
   a Listening lesson at a time: Play → Type → Hint (optional) → Check → Compare → Retry/Next.

   The comparison, hint and evidence math are the same pure, already-tested modules the old
   Dictation panel used (`capabilities/dictation-result.js`, `capabilities/dictation-hints.js`,
   `product/evidence.js`) - this screen only wires them to the real backend
   (`GET /api/listening/library/{id}`, `GET`/`POST /api/listening/progress`) and draws what frame
   07 draws, including the "Live check" strip that appears while a hint is in use (`dLiveOn`).
   No per-character pinyin on the result chips (a real gap in the source frame itself, D4 §1/§6).
   Rule 50: the player's own "tap to replay as often as you need" sub-line is dropped (D4 §7 names
   it as a removal candidate).

   Rule 49: the card is content-height on a roomy screen and shrinks on a small one; only its body
   scrolls (`data-scroll-region`), the hint/check row (or the result's Retry / Explain / Next row)
   stays docked under it, so a primary control is never scrolled away. The typed answer is device
   memory (`memory.answers`, the same key the old Dictation used) so leaving and coming back keeps
   it. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { registerActionHandler } from '../../agent/dispatcher.js';
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
import { t } from './copy.js';
import { createLinePractice } from './line-practice.js';
import { openMedia } from '../../product/media-source.js';
import {
  mapLesson,
  startIndex,
  rateLabel,
  nextRate,
  waveBars,
  dotStates,
  doneCount,
  progressBySegment,
  clock,
} from './model.js';

/* Plain text into an element: copy and lesson data are text, never markup (`mount` sets innerHTML). */
function setText(target, value) {
  if (target) target.textContent = String(value ?? '');
}

function waveMarkup(seed) {
  return html`${waveBars(seed).map((bar) => html`<span class="s-dict__bar" style="height:${bar.height}%;animation-delay:${bar.delay}ms"></span>`)}`;
}

export default async function mountDictation(element, ctx) {
  const support = languages().support;
  const lessonId = String(ctx.params?.id || '').trim();
  const [payload] = await Promise.all([openMedia(lessonId, {api, support, language: ctx.context.language, owner: ctx.context.owner || 'local', alive: () => ctx.isCurrent()}), useStyles('screens/dictation/dictation.css')]);
  if (!ctx.isCurrent()) return undefined;

  const lesson = mapLesson(payload);
  if (!lesson.segments.length) throw new Error(`Dictation: lesson "${lessonId}" has no dictation segments.`);
  ctx.setCrumb(lesson.title || shellCopy('dictation'));

  // Progress is keyed by the media asset, not the catalogue lesson id - only known once the
  // lesson itself has loaded, so this fetch cannot start in parallel with it. The server replaces a
  // segment's record wholesale, so a stored record this room could not read must never be written
  // over by a session that only knows its own attempts (see `check`).
  let priorRead = true;
  const progress = lesson.assetId
    ? await api.listeningProgress(lesson.assetId).catch(() => {
        priorRead = false;
        return { items: [] };
      })
    : { items: [] };
  if (!ctx.isCurrent()) return undefined;
  const memory = ctx.context?.memory || null;
  const byId = progressBySegment(progress?.items || []);
  // `seg` is the Listening Workspace's hand-off key; `segment` is the one the Speaking rooms use.
  let index = Math.min(lesson.segments.length - 1, startIndex(lesson.segments, ctx.query?.get('seg') || ctx.query?.get('segment')));
  let rate = 1;
  let playTimer = 0;
  let playing = false;

  element.classList.add('s-dict');
  mount(
    element,
    html`<div class="s-dict__head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-dict__headcol">
        <div class="s-dict__title" data-title></div>
        <div class="s-dict__sub" data-sub ${langAttr(lesson.language)}></div>
      </div>
    </div>
    <div class="s-dict__dots" data-dots></div>
    <div class="s-dict__card">
      <div class="s-dict__body" data-scroll-region data-body>
        <div class="s-dict__player">
          <button type="button" class="s-dict__play" data-play></button>
          <div class="s-dict__playcopy">
            <div class="s-dict__playlabel" data-play-label></div>
            <div class="s-dict__playtime" data-play-time></div>
          </div>
          <button type="button" class="s-dict__rate" data-rate></button>
        </div>
        <div class="s-dict__wave" data-wave></div>
        <div class="s-dict__stage" data-stage></div>
      </div>
      <div class="s-dict__dock" data-dock></div>
    </div>
    <div class="s-dict__foot">
      <button type="button" class="s-dict__navbtn" data-prev>${t('previous')}</button>
      <span class="s-dict__donelabel" data-done></span>
      <button type="button" class="s-dict__navbtn" data-skip>${t('next')}${raw(icon('arrow-right', { size: 16 }))}</button>
    </div>
    <div class="s-dict__media" data-media aria-hidden="true"></div>`,
  );
  const q = (selector) => element.querySelector(selector);
  q('[data-back]').addEventListener('click', () => ctx.back());

  const mediaRoot = q('[data-media]');
  const hasClip = playbackAvailable(lesson.playback);
  if (hasClip) {
    mount(mediaRoot, raw(mediaPlayer(lesson.playback, lesson.title, { startMs: 0, controls: false })));
    connectMediaPlayer(mediaRoot, lesson.playback);
  }
  q('[data-play]').disabled = !hasClip;

  function segment() {
    return lesson.segments[index];
  }
  function paintHead() {
    setText(q('[data-title]'), t('headerTitle', { n: index + 1, total: lesson.segments.length }));
    setText(q('[data-sub]'), lesson.title);
    mount(
      q('[data-dots]'),
      html`${dotStates(lesson.segments, byId, localById, index).map((state) => html`<span class="s-dict__dot s-dict__dot--${state}"></span>`)}`,
    );
    setText(q('[data-done]'), t('doneLabel', { n: doneCount(lesson.segments, byId, localById), total: lesson.segments.length }));
    q('[data-prev]').disabled = index === 0;
    q('[data-skip]').disabled = index >= lesson.segments.length - 1;
  }

  function paintPlayer() {
    const seg = segment();
    setText(q('[data-play-time]'), `${clock(seg.startMs)}–${clock(seg.endMs)} · ${rateLabel(rate)}`);
    setText(q('[data-rate]'), rateLabel(rate));
    mount(q('[data-wave]'), waveMarkup(index));
    setPlaying(false);
  }

  function setPlaying(on) {
    playing = on;
    mount(q('[data-play]'), raw(icon(on ? 'pause' : 'play', { size: 20 })));
    q('[data-play]').setAttribute('aria-label', on ? t('playing') : t('play'));
    setText(q('[data-play-label]'), on ? t('playing') : t('play'));
    q('[data-wave]').classList.toggle('is-playing', on);
  }

  function stopClip() {
    clearTimeout(playTimer);
    if (hasClip) stopSegmentPlayback(mediaRoot, lesson.playback);
    setPlaying(false);
  }

  function playClip() {
    if (!hasClip) return;
    if (playing) return stopClip();
    clearTimeout(playTimer);
    stopSegmentPlayback(mediaRoot, lesson.playback);
    const seg = segment();
    if (!replaySegment(mediaRoot, lesson.playback, seg.startMs, seg.endMs, rate)) return;
    setPlaying(true);
    const delay = segmentPlaybackDelayMs(seg.startMs, seg.endMs, rate) || 1200;
    playTimer = setTimeout(() => setPlaying(false), delay);
  }

  /* One line's answer, hint, Check and saved evidence: the same piece the Listening workspace's
     Dictation mode mounts (line-practice.js). */
  const practice = createLinePractice({
    lesson,
    byId,
    priorRead,
    memory,
    onChange: () => paintHead(),
    onCheck: () => stopClip(),
    onNext: () => {
      if (index >= lesson.segments.length - 1) ctx.back();
      else goTo(index + 1);
    },
  });
  const localById = practice.localById;

  function paintStage() {
    const last = index >= lesson.segments.length - 1;
    practice.show(segment(), { stage: q('[data-stage]'), dock: q('[data-dock]'), next: last ? t('finish') : t('nextSegment') });
    paintHead();
  }

  function goTo(nextIndex) {
    if (nextIndex < 0 || nextIndex >= lesson.segments.length) return;
    stopClip();
    index = nextIndex;
    paintPlayer();
    paintStage();
  }

  q('[data-play]').addEventListener('click', playClip);
  q('[data-rate]').addEventListener('click', () => {
    rate = nextRate(rate);
    if (hasClip) setPlaybackRate(mediaRoot, lesson.playback, rate);
    const seg = segment();
    setText(q('[data-rate]'), rateLabel(rate));
    setText(q('[data-play-time]'), `${clock(seg.startMs)}–${clock(seg.endMs)} · ${rateLabel(rate)}`);
  });
  q('[data-prev]').addEventListener('click', () => goTo(index - 1));
  q('[data-skip]').addEventListener('click', () => goTo(index + 1));

  paintPlayer();
  paintStage();

  const releasePlayModel = registerActionHandler('play_model', () => {
    if (!hasClip) return { ok: false, reason: 'no_audio' };
    if (!playing) playClip();
    return { ok: true };
  });

  return () => {
    clearTimeout(playTimer);
    releasePlayModel();
    if (hasClip) {
      stopSegmentPlayback(mediaRoot, lesson.playback);
      disconnectMediaPlayer(mediaRoot);
    }
  };
}
