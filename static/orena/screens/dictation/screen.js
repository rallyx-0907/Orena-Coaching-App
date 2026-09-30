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
import { toast } from '../../kit/toast.js';
import { markGlyph } from '../../kit/brand.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { askOrena } from '../../shell/agent-bridge.js';
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
import { dictationEvidence, recoverListeningEvidence } from '../../product/evidence.js';
import { t } from './copy.js';
import {
  mapLesson,
  startIndex,
  rateLabel,
  nextRate,
  waveBars,
  dotStates,
  doneCount,
  progressBySegment,
  previousEvidence,
  checkAnswer,
  chipsFor,
  scoreOf,
  scoreNoteKey,
  hintNoteKey,
  hintButton,
  liveView,
  MAX_HINT_LEVEL,
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
  const [payload] = await Promise.all([api.listeningLibraryLesson(lessonId, support), useStyles('screens/dictation/dictation.css')]);
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
  const localById = new Map(); // this session's latest real check per segment
  // `seg` is the Listening Workspace's hand-off key; `segment` is the one the Speaking rooms use.
  let index = Math.min(lesson.segments.length - 1, startIndex(lesson.segments, ctx.query?.get('seg') || ctx.query?.get('segment')));
  let rate = 1;
  let answer = '';
  let hintLevel = 0;
  let checked = false;
  let lastResult = null;
  let evidence = null;
  let recover = null; // set while this attempt's evidence began without the stored record
  let playTimer = 0;
  let playing = false;

  element.classList.add('s-dict');
  mount(
    element,
    html`<div class="s-dict__head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-dict__headcol">
        <div class="s-dict__title" data-title></div>
        <div class="s-dict__sub" data-sub lang="${langAttr(lesson.language)}"></div>
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
  function draftKey() {
    return `${lesson.assetId || lesson.id}:${segment().id}`;
  }
  function saveDraft(value) {
    try {
      memory?.write(draftKey(), value, 'answers');
    } catch {
      /* device memory unavailable: the answer simply is not kept across a leave */
    }
  }
  function readDraft() {
    try {
      return String(memory?.value?.answers?.[draftKey()] || '');
    } catch {
      return '';
    }
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

  /* ---- Before Check: the answer box, the live strip, the hint row ---- */

  function liveMarkup() {
    const view = liveView({ expected: segment().text, answer, language: lesson.language, level: hintLevel });
    return html`<div class="s-dict__livehead"><span class="s-dict__livelabel">${t('liveLabel')}</span><span class="s-dict__livecount">${t.plural('liveCount', view.total, { n: view.found, total: view.total })}</span></div>
      <div class="s-dict__livechips" lang="${langAttr(lesson.language)}">
        ${view.chips.map(
          (chip) =>
            html`<span class="s-dict__livechip s-dict__livechip--${chip.kind}">${chip.text}${chip.kind === 'ok' ? html`${raw(icon('check', { size: 14 }))}` : ''}</span>`,
        )}
      </div>`;
  }

  function paintLive() {
    const box = q('[data-live]');
    if (!box) return;
    box.hidden = hintLevel <= 0;
    if (hintLevel > 0) mount(box, liveMarkup());
  }

  function paintHint() {
    const button = q('[data-hint]');
    const note = q('[data-hint-note]');
    if (!button || !note) return;
    const view = hintButton(hintLevel);
    setText(button, t(view.key, view.values));
    button.disabled = view.disabled;
    setText(note, t(hintNoteKey(hintLevel)));
  }

  function paintPre() {
    mount(
      q('[data-stage]'),
      html`<textarea class="s-dict__input" data-input rows="3" lang="${langAttr(lesson.language)}" aria-label="${t('placeholder')}" placeholder="${t('placeholder')}">${answer}</textarea>
      <div class="s-dict__live" data-live hidden></div>`,
    );
    mount(
      q('[data-dock]'),
      html`<div class="s-dict__hintrow">
        <button type="button" class="s-dict__hint" data-hint></button>
        <span class="s-dict__hintnote" data-hint-note></span>
        <span class="s-dict__spacer"></span>
        <button type="button" class="o-btn o-btn--primary s-dict__check" data-check>${t('checkButton')}</button>
      </div>`,
    );
    const input = q('[data-input]');
    input.addEventListener('input', (event) => {
      answer = event.target.value;
      saveDraft(answer);
      if (hintLevel > 0) paintLive();
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        void check();
      }
    });
    q('[data-hint]').addEventListener('click', () => {
      if (hintLevel >= MAX_HINT_LEVEL) return;
      hintLevel += 1;
      paintHint();
      paintLive();
    });
    q('[data-check]').addEventListener('click', () => void check());
    paintHint();
    paintLive();
  }

  /* ---- After Check: score, the two chip rows, Retry / Explain / Next ---- */

  function paintPost() {
    const seg = segment();
    const score = scoreOf(lastResult);
    const chips = chipsFor(lastResult, { expected: seg.text, answer, language: lesson.language });
    const last = index >= lesson.segments.length - 1;
    mount(
      q('[data-stage]'),
      html`<div class="s-dict__result">
        <div class="s-dict__scorerow">
          <span class="s-dict__score">${score.correct}/${score.total}</span>
          <span class="s-dict__scorenote">${t(scoreNoteKey(score.tier))}</span>
          ${hintLevel > 0 ? html`<span class="s-dict__hintbadge">${t('usedHintBadge')}</span>` : ''}
        </div>
        <div class="s-dict__chipblock">
          <div class="s-dict__chiplabel">${t('youWrote')}</div>
          <div class="s-dict__chips" lang="${langAttr(lesson.language)}">
            ${chips.mine.map((chip) => html`<span class="s-dict__chip s-dict__chip--mine-${chip.kind}">${chip.text}</span>`)}
            ${chips.mineEmpty ? html`<span class="s-dict__chipempty">${t('emptyAnswer')}</span>` : ''}
          </div>
        </div>
        <div class="s-dict__chipblock">
          <div class="s-dict__chiplabel">${t('transcript')}</div>
          <div class="s-dict__chips" lang="${langAttr(lesson.language)}">
            ${chips.src.map((chip) => html`<span class="s-dict__chip s-dict__chip--src-${chip.kind}">${chip.text}</span>`)}
          </div>
          ${seg.support ? html`<div class="s-dict__support">${seg.support}</div>` : ''}
        </div>
      </div>`,
    );
    mount(
      q('[data-dock]'),
      html`<div class="s-dict__actions">
        <button type="button" class="s-dict__navbtn s-dict__retry" data-retry>${t('retry')}</button>
        <button type="button" class="s-dict__ai" data-explain>${markGlyph({ size: 20, symbol: 'ol-intel-still' })}${t('explainLine')}</button>
        <span class="s-dict__spacer"></span>
        <button type="button" class="o-btn o-btn--primary s-dict__next" data-next>${last ? t('finish') : t('nextSegment')}</button>
      </div>`,
    );
    q('[data-retry]').addEventListener('click', retry);
    q('[data-explain]').addEventListener('click', () => {
      askOrena({
        surface: 'listening.dictation',
        activity_type: 'listening',
        content_id: lesson.id,
        selected_item: { type: 'sentence', id: seg.id, text: seg.text, lang: lesson.language },
      });
    });
    q('[data-next]').addEventListener('click', () => {
      if (last) ctx.back();
      else goTo(index + 1);
    });
  }

  function paintStage() {
    if (checked) paintPost();
    else paintPre();
    paintHead();
  }

  function ensureEvidence() {
    const target = segment().id;
    evidence = dictationEvidence({
      asset: lesson.assetId,
      segment: { segment_id: target, spoken_text: segment().text },
      language: lesson.language,
      previous: previousEvidence(byId.get(target)),
    });
    // The stored record could not be read at mount and this room has not saved this line yet: fold
    // the server's copy into the evidence at save time instead of replacing it (never lowers a value).
    recover = !priorRead && !byId.has(target)
      ? recoverListeningEvidence(async () => {
          const stored = await api.listeningProgress(lesson.assetId);
          return (stored?.items || []).find((item) => item.segment_id === target) || {};
        })
      : null;
  }

  async function check() {
    const seg = segment();
    lastResult = checkAnswer({ expected: seg.text, answer, language: lesson.language });
    checked = true;
    const attempted = Boolean(answer.trim());
    // A blank submission is not a real attempt (the evaluator itself refuses to align nothing
    // against the line) - it shows the honest "everything missing" comparison and is never
    // persisted, nor counted in the dots.
    if (attempted) localById.set(seg.id, { exact: lastResult.exact });
    stopClip();
    paintStage();
    if (!attempted) return;
    evidence.compare(answer, { hintLevel });
    let outgoing = evidence.value;
    if (recover) {
      try {
        outgoing = await recover(outgoing);
      } catch {
        toast(t('progressUnread'));
        return;
      }
    }
    try {
      const saved = await api.saveListeningProgress(outgoing);
      if (saved?.item) {
        // The stored score is the server's (D-103.2): once acknowledged it replaces the browser's own
        // instant mark, which was only ever feedback.
        byId.set(seg.id, saved.item);
        localById.delete(seg.id);
        paintHead();
      }
    } catch {
      toast(t('saveFailed'));
    }
  }

  function retry() {
    answer = '';
    saveDraft('');
    hintLevel = 0;
    checked = false;
    lastResult = null;
    ensureEvidence();
    paintStage();
    q('[data-input]')?.focus();
  }

  function goTo(nextIndex) {
    if (nextIndex < 0 || nextIndex >= lesson.segments.length) return;
    stopClip();
    index = nextIndex;
    answer = readDraft();
    hintLevel = 0;
    checked = false;
    lastResult = null;
    ensureEvidence();
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

  answer = readDraft();
  ensureEvidence();
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
