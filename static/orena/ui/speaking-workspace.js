/* The Speaking workspace (D-066, D-067), drawn from Orena Speaking: "Speaking workspace" (desktop,
   1920x1080), "Speaking workspace mobile", "Speaking · recording" and "Speaking · char detail"
   (390x844). Every number is the frame's; colour comes only from theme.css.

   Left: the line - where it sits in the lesson, the model clip, the line with its reading and its
   meaning, the level of the voice while recording, and the three round controls. Right (below on a
   phone): the assessment as PronunciationResult (capabilities/pronunciation-result.js) - a ring, the
   provider's own flags, one row per word - and the four ways on.

   What the frame draws that nothing measures stays empty rather than invented: the waveform moves
   only with the live microphone level, "yours" in the tone comparison says it was not measured,
   and a figure the provider did not return shows 0 (Design Contract rule 40). Loading and error are
   not drawn in the design (rule 39); they are one plain line in the hint slot the frame already has. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { art } from './content.js';
import { speakCopy, fill } from './speaking-copy.js';
import { referenceCopy } from './reference.js';
import { pronunciationView } from '../capabilities/pronunciation-result.js';
import { readingsFor } from '../capabilities/dictation-result.js';
import { createSpeakingTake, TAKE, MAX_TAKE_MS } from '../capabilities/speaking-take.js';
import { createLocalAudioRecorder } from '../capabilities/audio-recorder.js';
import { watchMicrophone } from '../capabilities/mic-readiness.js';
import { decodeAudio, analyse, contourPolylines } from '../capabilities/audio-analysis.js';
import { createAttemptStore, indexedDbAttempts, bestOf } from '../capabilities/speaking-attempts.js';
import { compareHtml, summaryHtml, modeSwitchHtml, shadowCardHtml, micBlockedHtml, offlineHtml, notHeardHtml, barsHtml } from './speaking-views.js';
import {
  mediaPlayer,
  connectMediaPlayer,
  disconnectMediaPlayer,
  replaySegment,
  stopSegmentPlayback,
  setPlaybackRate,
} from '../capabilities/media-player.js';

const BARS = 42;
const RATES = [1, 0.75, 0.5];
const clock = (ms) => {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
};

export { lineUnits, placeWords, sentenceHtml } from './speaking-workspace-line.js';
import { placeWords, sentenceHtml } from './speaking-workspace-line.js';

/* --- The assessment ---------------------------------------------------------------------------- */
const errorLabel = (s, type) => {
  const key = `error_${String(type || '').toLowerCase()}`;
  return s[key] || s.error_other;
};

export function wordNote(s, word) {
  if (!word.flagged) return s.passed;
  const reason = errorLabel(s, word.errorType);
  return word.weakest ? `${reason} · ${fill(s.weakest, { u: word.weakest.label, n: word.weakest.score })}` : reason;
}

function headline(s, view, language) {
  if (!view.measured) return { title: s.noResult, sub: '' };
  const flagged = view.words.filter((word) => word.flagged);
  const unit = language === 'zh' ? 'zh' : 'en';
  const title = !flagged.length
    ? s[`headlineNone_${unit}`]
    : flagged.length === 1
      ? s[`headlineOne_${unit}`]
      : fill(s[`headlineSome_${unit}`], { n: flagged.length });
  const sub = flagged.length
    ? fill(s.subFlagged, { words: flagged.map((word) => word.text).join(language === 'zh' ? ' · ' : ', ') })
    : s.subTap;
  return { title, sub };
}

function paceText(s, timing) {
  if (!timing) return '';
  const seconds = Math.abs(timing.deltaMs / 1000).toFixed(1);
  if (timing.deltaMs === 0) return s.paceSame;
  return fill(timing.deltaMs > 0 ? s.paceSlower : s.paceFaster, { s: seconds });
}

const ring = (value, size, inner) =>
  `<span class="sp-ring sp-ring--${size}" style="--score:${Math.max(0, Math.min(100, value))}%" role="img" aria-label="${value}">${inner}</span>`;

function barHtml(word) {
  return `<span class="sp-bar${word.flagged ? ' sp-bar--flag' : ''}"><i style="width:${Math.max(0, Math.min(100, word.score))}%"></i></span>`;
}

export function resultHtml({ s, view, language, busy = false, hasModel = true }) {
  const { title, sub } = headline(s, view, language);
  const pace = paceText(s, view.timing);
  const unit = language === 'zh' ? 'zh' : 'en';
  const rows = view.words
    .map(
      (word) =>
        `<button type="button" class="sp-row${word.flagged ? ' sp-row--flag' : ''}" data-sp-word="${word.index}"><span class="sp-row__word"><b lang="${esc(language)}">${esc(word.text)}</b>${word.pinyin ? `<small>${esc(word.pinyin)}</small>` : ''}</span><span class="sp-row__mid">${barHtml(word)}<span class="sp-row__note">${esc(wordNote(s, word))}</span></span><span class="sp-row__score">${word.score}</span></button>`,
    )
    .join('');
  return `<div class="sp-head">${ring(view.overall, 'lg', `<span class="sp-ring__text"><b>${view.overall}</b><small>${esc(fill(s.passedOf, { p: view.passedCount, n: view.totalCount }))}</small></span>`)}<div class="sp-head__copy"><strong class="sp-headline">${esc(title)}</strong>${sub ? `<p class="sp-sub">${esc(sub)}</p>` : ''}<div class="sp-metrics"><span>${esc(s.metricPronunciation)} <b>${view.overall}</b></span><span>${esc(s.metricFluency)} <b>${view.fluency}</b></span>${pace ? `<span>${esc(s.metricPace)} <b>${esc(pace)}</b></span>` : ''}</div></div></div>
<div class="sp-body"${busy ? ' aria-busy="true"' : ''}><span class="sp-label">${esc(s[`eachWord_${unit}`])}</span><div class="sp-rows">${rows}</div>
<div class="sp-actions"><button type="button" class="sp-btn sp-btn--accent" data-sp-again>${icon('arrow-counter-clockwise', { size: 18 })}<span>${esc(s.recordAgain)}</span></button><button type="button" class="sp-btn" data-sp-hear-take${view.measured ? '' : ' disabled'}>${icon('speaker-high', { size: 18 })}<span>${esc(s.hearYours)}</span></button><button type="button" class="sp-btn" data-sp-compare${view.measured && hasModel ? '' : ' disabled'}>${icon('columns', { size: 18 })}<span>${esc(s.compare)}</span></button><button type="button" class="sp-btn" data-sp-next>${icon('arrow-right', { size: 18 })}<span>${esc(s.nextLine)}</span></button></div></div>`;
}

/* The phone's card under the line: the ring, the sentence about it, and only the flagged words. */
export function cardHtml({ s, view, language }) {
  const { title, sub } = headline(s, view, language);
  const flagged = view.words.filter((word) => word.flagged);
  const rows = flagged
    .map(
      (word) =>
        `<button type="button" class="sp-mrow" data-sp-word="${word.index}"><b lang="${esc(language)}">${esc(word.text)}</b>${barHtml(word)}<span class="sp-mrow__score">${word.score}</span></button>`,
    )
    .join('');
  // Tapping a line's score opens the comparison with the model (Orena Speaking 06).
  const score = ring(view.overall, 'sm', `<b>${view.overall}</b>`);
  return `<div class="sp-card__head">${view.measured ? `<button type="button" class="sp-ring-btn" data-sp-open-compare aria-label="${esc(s.compare)}">${score}</button>` : score}<div class="sp-card__copy"><strong>${esc(title)}</strong>${sub ? `<small>${esc(sub)}</small>` : ''}</div></div>${rows ? `<div class="sp-mrows">${rows}</div>` : ''}<button type="button" class="sp-textbtn sp-card__next" data-sp-next>${esc(s.nextLine)} →</button>`;
}

/* --- Word detail ------------------------------------------------------------------------------- */
/* The shape of each tone, drawn in a 120x60 box (the frame's polylines: tone 3 falls then rises). */
const TONE_SHAPES = {
  1: [[8, 16], [112, 16]],
  2: [[8, 42], [112, 12]],
  3: [[8, 18], [40, 46], [72, 46], [112, 14]],
  4: [[8, 12], [112, 48]],
  5: [[50, 34], [70, 38]],
};
export function toneSvg(tones) {
  if (!tones?.length) return '<svg viewBox="0 0 120 60" aria-hidden="true"></svg>';
  const width = 120 / tones.length;
  const lines = tones
    .map((tone, at) => {
      const points = (TONE_SHAPES[tone] || []).map(([x, y]) => `${(at * width + (x / 120) * width).toFixed(1)},${y}`).join(' ');
      return points ? `<polyline points="${points}"></polyline>` : '';
    })
    .join('');
  return `<svg viewBox="0 0 120 60" aria-hidden="true">${lines}</svg>`;
}

export function detailHtml({ s, c, word, language }) {
  const zh = language === 'zh';
  const tones = word.toneTarget || [];
  const chip = zh && tones.length === 1
    ? `${word.score} · ${tones[0] === 5 ? s.toneNeutral : fill(s.tone, { n: tones[0] })}`
    : `${word.score}${word.flagged ? ` · ${errorLabel(s, word.errorType)}` : ''}`;
  const toneWords = tones.map((tone) => s[`tone_${tone}`]).filter(Boolean).join(' · ');
  const panels = zh
    ? `<div class="sp-tones"><div class="sp-tone"><span class="sp-label">${esc(s.model)}</span>${toneSvg(tones)}<span>${esc(toneWords)}</span></div><div class="sp-tone sp-tone--yours"><span class="sp-label">${esc(s.yours)}</span><span data-sp-yours-svg>${toneSvg([])}</span><span data-sp-yours-note>${esc(s.toneUnmeasured)}</span></div></div>`
    : '';
  const units = word.phonemes.length ? word.phonemes : word.syllables;
  const sounds = units.length
    ? `<div class="sp-sounds"><span class="sp-label">${esc(s.soundBySound)}</span><div class="sp-sounds__row">${units.map((unit) => `<span class="sp-sound${word.weakest && unit.label === word.weakest.label && unit.score === word.weakest.score ? ' sp-sound--low' : ''}"><b>${esc(unit.label)}</b><small>${unit.score ?? '—'}</small></span>`).join('')}</div></div>`
    : '';
  const said = `${word.flagged ? errorLabel(s, word.errorType) : s.passed}. ${fill(s.detailScore, { n: word.score })}${word.weakest ? ` ${fill(s.weakestLine, { u: word.weakest.label, n: word.weakest.score })}` : ''}`;
  return `<button type="button" class="qs-x" data-sp-close aria-label="${esc(c.quickClose || s.close)}">${icon('x', { size: 18 })}</button><div class="sp-detail__head"><div class="sp-detail__word"><b lang="${esc(language)}">${esc(word.text)}</b><div class="sp-detail__meta">${word.pinyin ? `<span class="sp-detail__reading">${esc(word.pinyin)}</span>` : ''}<span class="sp-chip${word.flagged ? ' sp-chip--flag' : ''}">${esc(chip)}</span></div></div><button type="button" class="sp-detail__speak" data-sp-say aria-label="${esc(s.hearModel)}">${icon('speaker-high', { size: 21, filled: true })}</button></div><div class="sp-detail__rule"></div>${panels}${sounds}<p class="sp-detail__said">${esc(said)}</p><div class="sp-detail__actions"><button type="button" class="sp-dbtn" data-sp-hear-word${word.offsetKnown ? '' : ' disabled'}>${icon('speaker-high', { size: 18 })}<span>${esc(s.hearYou)}</span></button><button type="button" class="sp-dbtn sp-dbtn--accent" data-sp-alone>${icon('microphone', { size: 18, filled: true })}<span>${esc(s[`practiseAlone_${zh ? 'zh' : 'en'}`])}</span></button></div>`;
}

/* --- The room ---------------------------------------------------------------------------------- */
export function roomHtml({ s, c, source, index, language, rate, level }) {
  const line = source.lines[index];
  const total = source.lines.length;
  const segments = source.lines.map((_, at) => `<i${at < index ? ' data-done' : ''}></i>`).join('');
  const span = Math.max(0, (line.endMs || 0) - (line.startMs || 0));
  const kind = source.playback?.kind;
  const bars = Array.from({ length: BARS }, () => '<i></i>').join('');
  const where = [level, fill(s.lineOf, { i: index + 1, n: total })].filter(Boolean).join(' · ');
  return `<section class="sp-room" data-phase="idle">
<header class="sp-top"><button type="button" class="sp-back" data-sp-back aria-label="${esc(source.title)}">${icon('arrow-left', { size: 20 })}<span class="sp-back__caret">${icon('caret-left', { size: 22 })}</span><span class="sp-lesson" lang="${esc(language)}">${esc(source.title)}</span></button><button type="button" class="sp-cancel" data-sp-cancel aria-label="${esc(s.cancelRecording)}">${icon('x', { size: 22 })}</button><h1 class="sp-name">${esc(`${s.room} · ${s.pronunciation}`)}</h1><small class="sp-where">${esc(where)}</small><small class="sp-count">${esc(`${index + 1} / ${total}`)}</small><small class="sp-count sp-count--rec">${esc(fill(s.lineOf, { i: index + 1, n: total }))}</small><span class="sp-streak" title="${esc((referenceCopy[c.ui] || referenceCopy.en).streakUnmeasured)}">${icon('flame', { size: 16, filled: true })}<b>0</b></span></header>
<div class="sp-cols"><section class="sp-task"><div class="sp-state-host" data-sp-state hidden></div><div class="sp-steps" role="progressbar" aria-valuemin="1" aria-valuemax="${total}" aria-valuenow="${index + 1}"><span class="sp-steps__segments">${segments}</span><span class="sp-steps__count">${index + 1}/${total}</span></div><div data-sp-mode-host></div>
${source.playback ? `<div class="sp-clip" data-sp-player data-kind="${esc(kind || '')}"><span class="sp-clip__art">${source.poster || ''}</span>${source.playback ? mediaPlayer(source.playback, source.title, { startMs: line.startMs, endMs: line.endMs, controls: false }) : ''}<span class="sp-glow" aria-hidden="true"></span><button type="button" class="sp-play" data-sp-model aria-label="${esc(s.hearModel)}">${icon('play', { size: 34, filled: true })}</button><span class="sp-badge">${icon('video-camera', { size: 14, filled: true })}<span>${esc(fill(s.clipModel, { t: clock(span) }))}</span></span><button type="button" class="sp-rate" data-sp-rate>${rate}×</button><span class="sp-clipbar"><i data-sp-clipbar></i></span></div>` : ''}
<span class="sp-pill" data-sp-pill aria-live="off"><i></i><span data-sp-pill-text>${esc(fill(s.recordingPill, { t: '00:00' }))}</span></span>
<p class="sp-line" lang="${esc(language)}" data-sp-line>${sentenceHtml(line.text, language, null)}</p>${line.reading ? `<p class="sp-reading">${esc(line.reading)}</p>` : ''}${line.meaning ? `<p class="sp-meaning">${esc(line.meaning)}</p>` : ''}
<div data-sp-shadow-host></div><div class="sp-wave" data-sp-wave aria-hidden="true">${bars}</div>
<aside class="sp-card" data-sp-card aria-live="polite"></aside>
<div class="sp-controls"><button type="button" class="sp-round" data-sp-model aria-label="${esc(s.hearModel)}"${source.playback ? '' : ' disabled'}>${icon('speaker-high', { size: 24 })}</button><button type="button" class="sp-mic" data-sp-mic aria-label="${esc(s.record)}"><span class="sp-mic__icon">${icon('microphone', { size: 44, filled: true })}</span><span class="sp-mic__stop"></span></button><button type="button" class="sp-round" data-sp-again aria-label="${esc(s.recordAgain)}">${icon('arrow-counter-clockwise', { size: 24 })}</button></div>
<p class="sp-hint" data-sp-hint role="status">${esc(s[`tapWord_${language === 'zh' ? 'zh' : 'en'}`])}</p></section>
<section class="sp-result" data-sp-result aria-live="polite" aria-label="${esc(s.pronunciation)}"></section></div>
<audio data-sp-take-audio preload="auto" hidden></audio></section>`;
}

/* --- Behaviour ----------------------------------------------------------------------------------- */
const SHADOW_RATES = [0.75, 0.85, 1];
const SHADOW_TAIL_MS = 800;

export function mountSpeakingWorkspace(root, ctx, source, { startIndex = 0, onLeave = null } = {}) {
  const { api, language, memory } = ctx;
  const s = speakCopy(ctx.ui);
  const c = { ...ctx.c, ui: ctx.ui, lang: ctx.ui };
  let index = Math.max(0, Math.min(source.lines.length - 1, startIndex));
  let rate = 1;
  let disposed = false;
  let take = null;
  let state = { phase: TAKE.IDLE };
  let view = pronunciationView(null);
  let focus = null; // { text, start, end, pinyin } when one word is practised alone
  let ticker = 0;
  let mic = null;
  let sheet = null;
  let compareTimer = 0;
  let shadowTimer = 0;
  let countdownTimer = 0;
  let screen = 'work'; // 'work' | 'compare' | 'summary'
  let blocked = null; // 'mic' | 'offline'
  let listenOnly = false;
  let notHeard = 0;
  let retryQueue = null;
  let youAnalysis = null; // Promise of the current take's analysis
  const levels = new Array(BARS).fill(0);
  const shadowLevels = [];
  const lessonStarted = Date.now();
  const results = new Map(); // line id -> { overall, flagged, pending }
  const missed = new Map(); // flagged word -> { text, reading, count }
  const pending = new Map(); // line id -> { blob, reference, index }
  let anyKept = false;
  const attempts = createAttemptStore({ local: indexedDbAttempts() });
  const modelCache = new Map();
  const alive = () => !disposed && (ctx.alive ? ctx.alive() : true) && root.isConnected;
  const shadowable = Boolean(source.modelAudio);
  let mode = 'listen';
  let shadowRate = (() => {
    try {
      const saved = Number(localStorage.getItem(`orena.speaking.rate.${source.id}`));
      return SHADOW_RATES.includes(saved) ? saved : 0.85;
    } catch {
      return 0.85;
    }
  })();

  const line = () => source.lines[index];
  const reference = () => (focus ? focus.text : line().text);
  const attemptKey = () => `${source.id}#${line().id}${focus ? `#${focus.text}` : ''}`;

  function remember() {
    memory?.enter?.({
      id: source.id,
      title: source.title,
      intent: 'shadowing',
      segment: line().id,
      excerpt: line().text,
      place: { index: index + 1, total: source.lines.length },
    });
  }

  function speak(text) {
    if (!text || typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language === 'zh' ? 'zh-CN' : 'en-US';
    window.speechSynthesis.speak(utterance);
  }

  const q = (selector) => root.querySelector(selector);
  const playerRoot = () => q('[data-sp-player]');

  /* The model line, analysed once per line from the same-origin cut (waveform and pitch). */
  function modelOf(lineItem = line()) {
    if (!source.modelAudio) return Promise.resolve(null);
    if (!modelCache.has(lineItem.id))
      modelCache.set(
        lineItem.id,
        decodeAudio(source.modelAudio(lineItem.id))
          .then((decoded) => analyse(decoded))
          .catch(() => null),
      );
    return modelCache.get(lineItem.id);
  }

  function playModel() {
    const player = playerRoot();
    if (!player || !source.playback) return;
    const current = line();
    replaySegment(player, source.playback, current.startMs, current.endMs, rate);
  }

  function playUrl(audio, url, { fromMs = null, toMs = null, playbackRate = 1 } = {}) {
    if (!audio || !url) return Promise.resolve();
    if (audio.src !== url) audio.src = url;
    audio.playbackRate = playbackRate;
    audio.currentTime = fromMs != null ? fromMs / 1000 : 0;
    return new Promise((resolve) => {
      const done = () => {
        audio.removeEventListener('timeupdate', stopAt);
        audio.removeEventListener('ended', done);
        resolve();
      };
      const stopAt = () => {
        if (toMs != null && audio.currentTime * 1000 >= toMs) {
          audio.pause();
          done();
        }
      };
      audio.addEventListener('timeupdate', stopAt);
      audio.addEventListener('ended', done);
      audio.play().catch(done);
    });
  }

  const playTake = (range = {}) => playUrl(q('[data-sp-take-audio]'), take?.takeUrl, range);

  /* --- Hint, phase, states ------------------------------------------------------------------- */
  function paintHint() {
    const hint = q('[data-sp-hint]');
    if (!hint) return;
    hint.classList.remove('sp-hint--error');
    if (state.phase === TAKE.RECORDING) {
      hint.textContent = s.recordingHint;
      return;
    }
    if (state.phase === TAKE.PROCESSING) {
      hint.textContent = s.scoring;
      return;
    }
    if (state.phase === TAKE.ERROR && state.error && !['no_speech', 'too_short', 'microphone', 'offline'].includes(state.error.kind)) {
      hint.classList.add('sp-hint--error');
      hint.innerHTML = `<span>${esc(s[`err_${state.error.kind}`] || s.err_service)}</span>${state.error.retry ? ` <button type="button" class="sp-link" data-sp-retry>${esc(s.retry)}</button>` : ''}`;
      q('[data-sp-retry]')?.addEventListener('click', () => take?.retry());
      return;
    }
    if (state.phase === TAKE.RESULT && view.synthetic) {
      hint.textContent = s.demoOnly;
      return;
    }
    if (state.phase === TAKE.RESULT && state.kept === false) {
      hint.textContent = s.keptFailed;
      return;
    }
    if (focus) {
      // D-075: practising one word alone always has a way back to the line.
      hint.innerHTML = `<span>${esc(fill(s.practisingAlone, { w: `${focus.text}${focus.pinyin ? ` · ${focus.pinyin}` : ''}` }))}</span> <button type="button" class="sp-link" data-sp-back-line>${esc(s.backToLine)}</button>`;
      q('[data-sp-back-line]').onclick = () => practiseAlone(null);
      return;
    }
    hint.textContent = s[`tapWord_${language === 'zh' ? 'zh' : 'en'}`];
  }

  function paintState() {
    const host = q('[data-sp-state]');
    const room = q('.sp-room');
    if (!host || !room) return;
    room.toggleAttribute('data-listen-only', listenOnly);
    if (blocked) room.dataset.blocked = blocked;
    else room.removeAttribute('data-blocked');
    host.hidden = !blocked;
    if (!blocked) {
      host.innerHTML = '';
      return;
    }
    host.innerHTML = blocked === 'mic' ? micBlockedHtml({ s }) : offlineHtml({ s });
    host.querySelector('[data-sp-mic-retry]')?.addEventListener('click', () => {
      blocked = null;
      paintState();
      void begin();
    });
    host.querySelector('[data-sp-listen-only]')?.addEventListener('click', () => {
      blocked = null;
      listenOnly = true;
      paintState();
    });
    host.querySelector('[data-sp-offline-next]')?.addEventListener('click', () => {
      blocked = null;
      next();
    });
    host.querySelector('[data-sp-offline-retry]')?.addEventListener('click', () => take?.retry());
  }

  function notHeardState() {
    return state.phase === TAKE.ERROR && ['no_speech', 'too_short'].includes(state.error?.kind);
  }

  function paintResult() {
    const busy = state.phase === TAKE.PROCESSING;
    const result = q('[data-sp-result]');
    const card = q('[data-sp-card]');
    const quiet = notHeardState() ? notHeardHtml({ s, kind: state.error.kind, twice: notHeard >= 2 }) : '';
    if (result) result.innerHTML = `${quiet}${resultHtml({ s, view, language, busy, hasModel: Boolean(source.playback) })}`;
    if (card) card.innerHTML = quiet || cardHtml({ s, view, language });
    const lineEl = q('[data-sp-line]');
    if (lineEl) lineEl.innerHTML = sentenceHtml(line().text, language, focus ? null : view, focus);
    root.querySelectorAll('[data-sp-word]').forEach((row) => {
      row.onclick = () => openDetail(Number(row.dataset.spWord), row);
    });
    root.querySelectorAll('[data-sp-again]').forEach((button) => {
      button.onclick = () => (notHeardState() && button.classList.contains('sp-round') ? next() : begin());
      button.disabled = state.phase === TAKE.RECORDING || state.phase === TAKE.PROCESSING;
    });
    // Not heard (Orena Speaking 09 B): the round control on the right skips the line instead.
    const right = q('.sp-controls [data-sp-again]');
    if (right) {
      const skip = notHeardState();
      right.innerHTML = icon(skip ? 'skip-forward' : 'arrow-counter-clockwise', { size: 24 });
      right.setAttribute('aria-label', skip ? s.skipLine : s.recordAgain);
    }
    const hear = q('[data-sp-hear-take]');
    if (hear) hear.onclick = () => playTake();
    const compare = q('[data-sp-compare]');
    if (compare) {
      compare.disabled = !view.measured;
      compare.onclick = () => void openCompare();
    }
    root.querySelectorAll('[data-sp-open-compare]').forEach((button) => (button.onclick = () => void openCompare()));
    // The phone's frame draws no "next line"; its card carries one (UI_BACKEND_GAPS S19).
    root.querySelectorAll('[data-sp-next]').forEach((nextButton) => {
      nextButton.disabled = state.phase === TAKE.RECORDING;
      nextButton.onclick = next;
    });
  }

  function paintPhase() {
    const room = q('.sp-room');
    if (!room) return;
    room.dataset.phase = state.phase;
    room.dataset.mode = mode;
    const micButton = q('[data-sp-mic]');
    if (micButton) {
      micButton.disabled = state.phase === TAKE.PROCESSING;
      micButton.setAttribute('aria-label', state.phase === TAKE.RECORDING ? s.stop : s.record);
      micButton.setAttribute('aria-pressed', String(state.phase === TAKE.RECORDING));
    }
    paintHint();
  }

  function paintWave() {
    const wave = q('[data-sp-wave]');
    if (wave) {
      const bars = wave.children;
      for (let at = 0; at < bars.length; at++) bars[at].style.blockSize = `${Math.max(6, Math.round((levels[at] || 0) * 100))}%`;
    }
    const you = q('[data-sp-shadow-you]');
    if (you) you.innerHTML = barsHtml(shadowLevels);
  }

  function startListening() {
    levels.fill(0);
    shadowLevels.length = 0;
    paintWave();
    mic?.stop?.();
    mic = watchMicrophone({
      onLevel: (peak) => {
        if (!alive() || state.phase !== TAKE.RECORDING) return;
        levels.shift();
        levels.push(Math.min(1, Number(peak) || 0));
        if (mode === 'shadow' && shadowLevels.length < 40) shadowLevels.push(Math.min(1, Number(peak) || 0));
        paintWave();
      },
    });
  }
  function stopListening() {
    mic?.stop?.();
    mic = null;
    levels.fill(0);
    paintWave();
  }

  /* --- Mode switch and the shadowing card (Orena Speaking 07) --------------------------------- */
  async function paintMode() {
    const modeHost = q('[data-sp-mode-host]');
    if (modeHost) modeHost.innerHTML = shadowable && !focus ? modeSwitchHtml({ s, mode }) : '';
    modeHost?.querySelectorAll('[data-sp-mode]').forEach((button) => {
      button.onclick = () => {
        if (state.phase === TAKE.RECORDING || state.phase === TAKE.PROCESSING) return;
        mode = button.dataset.spMode;
        render();
      };
    });
    const shadowHost = q('[data-sp-shadow-host]');
    if (!shadowHost) return;
    if (mode !== 'shadow') {
      shadowHost.innerHTML = '';
      return;
    }
    const model = await modelOf();
    if (!alive() || mode !== 'shadow') return;
    const lag = state.phase === TAKE.RESULT ? firstWordMs(state.result) : null;
    shadowHost.innerHTML = shadowCardHtml({ s, rate: shadowRate, modelBars: model?.bars || [], lagMs: lag });
    paintWave();
  }

  const firstWordMs = (result) => {
    const said = (result?.words || []).filter((word) => Number.isFinite(word?.offset_ms));
    return said.length ? Math.min(...said.map((word) => word.offset_ms)) : null;
  };

  /* --- A take arrives -------------------------------------------------------------------------- */
  function onTake(nextState) {
    if (!alive()) return;
    const previous = state.phase;
    state = nextState;
    if (nextState.phase === TAKE.RESULT && nextState.result) {
      notHeard = 0;
      blocked = null;
      pending.delete(line().id);
      view = pronunciationView(nextState.result, {
        language,
        readings: focus ? [] : line().readings,
        modelSpanMs: focus ? null : Math.max(0, (line().endMs || 0) - (line().startMs || 0)) || null,
      });
      // Where each word sits in the take, for "hear yours" on one word and the measured contour.
      (nextState.result.words || [])
        .filter((word) => String(word?.error_type || '').toLowerCase() !== 'insertion' && String(word?.word || '').trim())
        .forEach((word, at) => {
          if (view.words[at]) {
            view.words[at].offsetMs = word.offset_ms;
            view.words[at].durationMs = word.duration_ms;
            view.words[at].offsetKnown = Number.isFinite(word.offset_ms) && Number.isFinite(word.duration_ms);
          }
        });
      if (focus && view.words[0]) view.words[0].pinyin = focus.pinyin || view.words[0].pinyin;
      const blob = take?.takeBlob;
      youAnalysis = blob ? decodeAudio(blob).then((decoded) => analyse(decoded)).catch(() => null) : null;
      if (view.measured) void keepAttempt(blob);
      if (!focus) {
        noteResult(view);
        void keepShadowingRound();
      }
    }
    if (nextState.kept) anyKept = true;
    if (nextState.phase === TAKE.PROCESSING) view = pronunciationView(null);
    // Any new answer lifts a state it does not itself cause: a take graded after the network came
    // back is shown as what it is (a result, or not heard), not as "offline" still.
    if (nextState.phase === TAKE.PROCESSING || nextState.phase === TAKE.RECORDING) blocked = null;
    if (nextState.phase === TAKE.ERROR) {
      const kind = nextState.error?.kind;
      blocked = null;
      if (kind !== 'offline') pending.delete(line().id);
      if (kind === 'no_speech' || kind === 'too_short') notHeard += 1;
      if (kind === 'microphone') blocked = 'mic';
      if (kind === 'offline') {
        blocked = 'offline';
        if (take?.takeBlob && !focus) {
          pending.set(line().id, { blob: take.takeBlob, reference: reference(), index });
          results.set(line().id, { ...(results.get(line().id) || {}), pending: true });
        }
      }
    }
    if (nextState.phase === TAKE.RECORDING && previous !== TAKE.RECORDING) {
      startListening();
      clearInterval(ticker);
      ticker = setInterval(() => {
        if (!alive() || !take) return clearInterval(ticker);
        const ms = take.elapsedMs();
        const pill = q('[data-sp-pill-text]');
        if (pill) pill.textContent = fill(s.recordingPill, { t: clock(ms) });
        const head = q('[data-sp-shadow-playhead]');
        const model = q('[data-sp-shadow-audio]');
        if (head && model?.duration) head.style.left = `${Math.min(100, (model.currentTime / model.duration) * 100)}%`;
        if (ms >= MAX_TAKE_MS) void take.stop(reference());
      }, 120);
    }
    if (nextState.phase !== TAKE.RECORDING && previous === TAKE.RECORDING) {
      clearInterval(ticker);
      clearTimeout(shadowTimer);
      q('[data-sp-shadow-audio]')?.pause();
      stopListening();
    }
    paintPhase();
    paintState();
    if (nextState.phase !== TAKE.RECORDING || previous !== TAKE.RECORDING) {
      paintResult();
      void paintMode();
    }
  }

  function noteResult(result) {
    const prior = results.get(line().id);
    const flagged = result.words.filter((word) => word.flagged);
    if (!prior || typeof prior.overall !== 'number' || result.overall >= prior.overall)
      results.set(line().id, { overall: result.overall, flagged: flagged.length, pending: false });
    for (const word of flagged) {
      const known = missed.get(word.text) || { text: word.text, reading: word.pinyin || '', count: 0 };
      known.count += 1;
      missed.set(word.text, known);
    }
  }

  async function keepAttempt(blob) {
    if (!blob) return;
    await attempts.add(attemptKey(), {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      at: Date.now(),
      ms: take?.takeMs || 0,
      blob,
      overall: view.overall,
      flagged: view.words.filter((word) => word.flagged).length,
      words: view.words,
    });
  }

  /* Takes kept while offline are graded when the network is back (Orena Speaking 09 C). */
  async function gradePending() {
    for (const [lineId, item] of [...pending]) {
      if (lineId === line().id && blocked === 'offline') {
        take?.retry();
        continue;
      }
      try {
        const result = await api.assessPronunciation(item.blob, language, item.reference);
        if (!alive()) return;
        const graded = pronunciationView(result, { language, readings: source.lines[item.index]?.readings || [] });
        const flagged = graded.words.filter((word) => word.flagged).length;
        results.set(lineId, { overall: graded.overall, flagged, pending: false });
        pending.delete(lineId);
        if (screen === 'summary') renderSummary();
      } catch {}
    }
  }
  const onOnline = () => void gradePending();

  /* The old Shadowing practice counted rounds per line; the count is kept so Progress reads the
     same evidence it did before. Best effort: a failure here is not the learner's. */
  async function keepShadowingRound() {
    if (!source.assetId || typeof api?.saveShadowingProgress !== 'function') return;
    try {
      await ctx.settledWrites?.();
      const records = await api.shadowingProgress(source.assetId);
      const prior = (records?.items || []).find((item) => item.segment_id === line().id);
      await api.saveShadowingProgress({
        asset_id: source.assetId,
        segment_id: line().id,
        completed_rounds: Math.min(1000, (prior?.completed_rounds || 0) + 1),
      });
    } catch {}
  }

  function newTake() {
    take?.dispose();
    take = createSpeakingTake({
      api,
      recorder: createLocalAudioRecorder(),
      language,
      keep: { assetId: source.assetId || '', segmentId: focus ? `${line().id}#${focus.text}` : line().id },
      onChange: onTake,
    });
  }

  async function begin() {
    if (!take || state.phase === TAKE.PROCESSING || state.phase === TAKE.RECORDING || listenOnly) return;
    stopSegmentPlayback(playerRoot(), source.playback);
    q('[data-sp-take-audio]')?.pause();
    if (mode === 'shadow') return beginShadow();
    await take.start();
  }

  /* Shadowing: 3-2-1, then the model and the microphone together; the take stops itself when the
     model ends plus 0.8 s (the frame's note). */
  async function beginShadow() {
    const model = q('[data-sp-shadow-audio]');
    const hint = q('[data-sp-hint]');
    for (const n of [3, 2, 1]) {
      if (!alive() || mode !== 'shadow') return;
      if (hint) hint.textContent = String(n);
      await new Promise((resolve) => (countdownTimer = setTimeout(resolve, 700)));
    }
    if (!alive()) return;
    const started = await take.start();
    if (!started || !model) return;
    model.src = source.modelAudio(line().id);
    model.playbackRate = shadowRate;
    model.currentTime = 0;
    model.onended = () => {
      clearTimeout(shadowTimer);
      shadowTimer = setTimeout(() => state.phase === TAKE.RECORDING && take.stop(reference()), SHADOW_TAIL_MS);
    };
    model.play().catch(() => {});
  }

  async function micPressed() {
    if (state.phase === TAKE.RECORDING) {
      clearTimeout(shadowTimer);
      q('[data-sp-shadow-audio]')?.pause();
      await take.stop(reference());
    } else await begin();
  }

  function next() {
    if (state.phase === TAKE.RECORDING) return;
    if (retryQueue?.length) return moveTo(retryQueue.shift());
    if (retryQueue) retryQueue = null;
    if (index >= source.lines.length - 1) return renderSummary();
    moveTo(index + 1);
  }

  /* --- Word detail ----------------------------------------------------------------------------- */
  function closeDetail() {
    if (!sheet) return;
    sheet.scrim.remove();
    sheet.panel.remove();
    document.removeEventListener('keydown', sheet.onKey);
    const back = sheet.from;
    sheet = null;
    back?.focus?.({ preventScroll: true });
  }

  function openDetail(wordIndex, from) {
    const word = view.words[wordIndex];
    if (!word) return;
    closeDetail();
    const scrim = document.createElement('div');
    scrim.className = 'qs-scrim';
    const panel = document.createElement('div');
    panel.className = 'qs qs--speak';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-label', word.text);
    panel.tabIndex = -1;
    panel.innerHTML = detailHtml({ s, c, word, language });
    document.body.append(scrim, panel);
    // A popover beside the word on a desk; a bottom sheet on a phone (quick-sheet.css).
    if (window.matchMedia('(min-width: 701px)').matches && from?.getBoundingClientRect) {
      const box = from.getBoundingClientRect();
      const width = panel.offsetWidth;
      panel.style.left = `${Math.max(10, Math.min(window.innerWidth - width - 10, box.left))}px`;
      const below = box.bottom + 14;
      const fits = below + panel.offsetHeight < window.innerHeight - 10;
      panel.style.top = `${fits ? below : Math.max(10, box.top - panel.offsetHeight - 14)}px`;
      if (!fits) panel.dataset.placement = 'above';
    }
    const onKey = (event) => event.key === 'Escape' && closeDetail();
    sheet = { scrim, panel, onKey, from };
    scrim.addEventListener('click', closeDetail);
    document.addEventListener('keydown', onKey);
    panel.querySelector('[data-sp-close]').onclick = closeDetail;
    panel.querySelector('[data-sp-say]').onclick = () => speak(word.text);
    const hearWord = panel.querySelector('[data-sp-hear-word]');
    hearWord.onclick = () => playTake({ fromMs: Math.max(0, word.offsetMs - 80), toMs: word.offsetMs + word.durationMs + 120 });
    panel.querySelector('[data-sp-alone]').onclick = () => {
      const range = placeWords(line().text, [word], language)[0];
      closeDetail();
      practiseAlone(range ? { text: word.text, pinyin: word.pinyin, ...range } : null);
    };
    // "Yours": the pitch measured from this take over this word's own time (Chinese only).
    if (language === 'zh' && word.offsetKnown && youAnalysis) {
      void youAnalysis.then((analysis) => {
        if (!analysis || sheet?.panel !== panel) return;
        const from = word.offsetMs / 1000;
        const to = (word.offsetMs + word.durationMs) / 1000;
        const runs = contourPolylines(analysis.contour, { width: 120, height: 60, from, to, span: to });
        if (!runs.length) return;
        panel.querySelector('[data-sp-yours-svg]').innerHTML = `<svg viewBox="0 0 120 60" aria-hidden="true">${runs.map((pts) => `<polyline points="${pts}"></polyline>`).join('')}</svg>`;
        panel.querySelector('[data-sp-yours-note]').textContent = '';
      });
    }
    panel.focus({ preventScroll: true });
  }

  /* One word, on its own: the same line stays on screen with the word lit (the frame's char
     detail draws exactly this), and the next take is assessed against that word only. The hint
     line carries the way back to the whole line (D-075). */
  function practiseAlone(nextFocus) {
    focus = nextFocus;
    view = pronunciationView(null);
    state = { phase: TAKE.IDLE };
    if (focus) mode = 'listen';
    newTake();
    paintPhase();
    paintResult();
    void paintMode();
  }

  function moveTo(nextIndex) {
    if (nextIndex < 0 || nextIndex >= source.lines.length || state.phase === TAKE.RECORDING) return;
    index = nextIndex;
    focus = null;
    blocked = null;
    notHeard = 0;
    view = pronunciationView(null);
    state = { phase: TAKE.IDLE };
    youAnalysis = null;
    render();
    remember();
  }

  /* --- 06 · Compare with the model ------------------------------------------------------------- */
  async function openCompare(selectedId = null) {
    const list = await attempts.list(attemptKey());
    if (!alive() || !list.length) return;
    const best = bestOf(list);
    const selected = list.find((item) => item.id === selectedId) || list[0];
    screen = 'compare';
    closeDetail();
    const analysis = { model: null, you: null, flaggedSpans: [], modelMissing: false };
    const paint = () => {
      root.innerHTML = compareHtml({ s, source, index, language, view, analysis, attempts: list, selectedId: selected.id, bestId: best?.id, ui: ctx.ui, keepRecent: attempts.keepRecent });
      bindCompare(list, selected);
    };
    paint();
    const [model, you] = await Promise.all([
      modelOf(),
      decodeAudio(selected.blob).then((decoded) => analyse(decoded)).catch(() => null),
    ]);
    if (!alive() || screen !== 'compare') return;
    analysis.model = model;
    analysis.modelMissing = Boolean(source.modelAudio) && !model;
    analysis.you = you;
    analysis.flaggedSpans = (selected.words || []).filter((word) => word.flagged && Number.isFinite(word.offsetMs)).map((word) => ({ offsetMs: word.offsetMs, durationMs: word.durationMs || 200 }));
    paint();
  }

  function bindCompare(list, selected) {
    const audio = q('[data-sp-cmp-audio]');
    root.querySelector('[data-sp-cmp-back]').onclick = () => {
      screen = 'work';
      render();
    };
    root.querySelectorAll('[data-sp-cmp-model]').forEach((button) => (button.onclick = () => playUrl(audio, source.modelAudio?.(line().id))));
    root.querySelectorAll('[data-sp-cmp-take]').forEach((button) => (button.onclick = () => playUrl(audio, selected.url)));
    root.querySelectorAll('[data-sp-cmp-alternate]').forEach((button) => {
      // The model, then this take, 0.4 s apart. The frame alternates word by word; the model's own
      // word timing is not measured, so the whole line alternates (UI_BACKEND_GAPS S17).
      button.onclick = async () => {
        await playUrl(audio, source.modelAudio?.(line().id));
        await new Promise((resolve) => setTimeout(resolve, 400));
        if (alive() && screen === 'compare') await playUrl(audio, selected.url);
      };
    });
    root.querySelectorAll('[data-sp-cmp-record]').forEach((button) => {
      button.onclick = () => {
        screen = 'work';
        render();
        void begin();
      };
    });
    root.querySelectorAll('[data-sp-attempt]').forEach((row) => (row.onclick = () => void openCompare(row.dataset.spAttempt)));
    const keep = q('[data-sp-keep]');
    if (keep)
      keep.onchange = async () => {
        await attempts.setKeepRecent(keep.checked);
        void openCompare(selected.id);
      };
  }

  /* --- 05 · Lesson summary ----------------------------------------------------------------------- */
  function renderSummary() {
    screen = 'summary';
    closeDetail();
    if (playerRoot()) disconnectMediaPlayer(playerRoot());
    const rows = source.lines.map((item) => ({ text: item.text, ...(results.get(item.id) || {}) }));
    const minutes = Math.max(1, Math.round((Date.now() - lessonStarted) / 60000));
    const room = (referenceCopy[ctx.ui] || referenceCopy.en).speaking;
    root.innerHTML = summaryHtml({ s, source, language, rows, missed: [...missed.values()].sort((a, b) => b.count - a.count).slice(0, 8), minutes, kept: anyKept, room });
    root.querySelectorAll('[data-sp-sum-line]').forEach((row) => (row.onclick = () => {
      screen = 'work';
      moveTo(Number(row.dataset.spSumLine));
    }));
    const again = q('[data-sp-sum-again]');
    if (again)
      again.onclick = () => {
        retryQueue = source.lines.map((item, at) => (results.get(item.id)?.flagged > 0 ? at : -1)).filter((at) => at >= 0);
        screen = 'work';
        moveTo(retryQueue.shift());
      };
    q('[data-sp-sum-home]').onclick = () => ctx.go('practice', { intent: 'speaking' });
  }

  /* --- 02 · The workspace ------------------------------------------------------------------------ */
  function render() {
    screen = 'work';
    closeDetail();
    clearTimeout(compareTimer);
    if (playerRoot()) disconnectMediaPlayer(playerRoot());
    root.innerHTML = roomHtml({ s, c, source, index, language, rate, level: source.level });
    root.querySelector('.sp-room').insertAdjacentHTML('beforeend', '<audio data-sp-shadow-audio preload="auto" hidden></audio>');
    const player = playerRoot();
    if (player && source.playback) {
      connectMediaPlayer(player, source.playback);
      player.addEventListener('orena:media-time', (event) => {
        const current = line();
        const span = Math.max(1, current.endMs - current.startMs);
        const bar = q('[data-sp-clipbar]');
        if (bar) bar.style.width = `${Math.max(0, Math.min(100, ((event.detail.time_ms - current.startMs) / span) * 100))}%`;
      });
    }
    root.querySelectorAll('[data-sp-model]').forEach((button) => {
      button.onclick = () => {
        if (mode === 'shadow' && button.classList.contains('sp-round')) {
          // In shadowing the left control is the model's speed (0.75 / 0.85 / 1, kept per lesson).
          shadowRate = SHADOW_RATES[(SHADOW_RATES.indexOf(shadowRate) + 1) % SHADOW_RATES.length];
          try {
            localStorage.setItem(`orena.speaking.rate.${source.id}`, String(shadowRate));
          } catch {}
          void paintMode();
          return;
        }
        playModel();
      };
    });
    if (mode === 'shadow') {
      const left = q('.sp-controls [data-sp-model]');
      if (left) {
        left.disabled = false;
        left.innerHTML = icon('gauge', { size: 22 });
        left.setAttribute('aria-label', s.modelSpeed);
      }
    }
    q('[data-sp-mic]').onclick = micPressed;
    q('[data-sp-cancel]').onclick = () => {
      clearTimeout(shadowTimer);
      q('[data-sp-shadow-audio]')?.pause();
      take?.cancel();
    };
    q('[data-sp-back]').onclick = () => (onLeave ? onLeave() : history.back());
    const rateButton = q('[data-sp-rate]');
    if (rateButton)
      rateButton.onclick = (event) => {
        rate = RATES[(RATES.indexOf(rate) + 1) % RATES.length];
        event.currentTarget.textContent = `${rate}×`;
        setPlaybackRate(playerRoot(), source.playback, rate);
      };
    q('[data-sp-line]').onclick = (event) => {
      const token = event.target.closest('[data-sp-tok]');
      if (!token) return;
      if (focus && token.closest('.sp-tok--focus')) {
        practiseAlone(null);
        return;
      }
      speak(token.textContent);
    };
    newTake();
    paintPhase();
    paintState();
    paintResult();
    void paintMode();
  }

  const onKey = (event) => {
    if (event.key === 'Escape' && state.phase === TAKE.RECORDING && !sheet) take?.cancel();
  };
  document.addEventListener('keydown', onKey);
  window.addEventListener('online', onOnline);
  render();
  remember();

  return () => {
    disposed = true;
    clearInterval(ticker);
    clearTimeout(compareTimer);
    clearTimeout(shadowTimer);
    clearTimeout(countdownTimer);
    document.removeEventListener('keydown', onKey);
    window.removeEventListener('online', onOnline);
    closeDetail();
    stopListening();
    take?.dispose();
    attempts.release();
    root.querySelectorAll('audio').forEach((audio) => audio.pause());
    if (playerRoot()) disconnectMediaPlayer(playerRoot());
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
  };
}

/* The reading under the line. The reviewed whole-line reading keeps words together ("wǒmen"),
   so it is used when it is the reading of exactly what is said; when the line said is not the line
   written (speakers' names are not said), the aligned per-character reading of what is said is used
   instead, and when neither agrees nothing is shown rather than a reading of other words. */
function lineReading(segment, catalog) {
  const spoken = segment.spoken_text || segment.original_text;
  const whole = catalog.pinyin_by_segment?.[segment.segment_id] || '';
  if (whole && spoken === segment.original_text) return whole;
  const chars = readingsFor(spoken, segment.original_text, catalog.pinyin_chars_by_segment?.[segment.segment_id]);
  if (chars.length) return chars.map((item) => item?.pinyin || '').join(' ');
  return '';
}

/* A Listening lesson as a Speaking source: its lines are the lines to say, its clip the model. */
export function sourceFromLesson(id, payload, model, support) {
  const catalog = payload.catalog || {};
  const title = payload.asset?.title || catalog.title || '';
  return {
    id,
    title,
    level: catalog.reviewed_level || catalog.level || '',
    assetId: payload.asset?.asset_id || '',
    playback: payload.playback || null,
    // The model line, same-origin, for its waveform and pitch (a published catalogue lesson only).
    modelAudio: id.startsWith('media:')
      ? (segmentId) => `/api/speaking/model-audio/${encodeURIComponent(id.slice(6))}/${encodeURIComponent(segmentId)}`
      : null,
    poster: art({ ...catalog, id, title, kind: payload.playback?.kind }),
    lines: model.segments.map((segment) => ({
      id: segment.segment_id,
      text: segment.spoken_text || segment.original_text,
      original: segment.original_text,
      // What is said can be shorter than what is written (a speaker's label is not said); the
      // reading follows what is said, and a reading that does not align is not shown at all.
      reading: lineReading(segment, catalog),
      readings: readingsFor(segment.spoken_text, segment.original_text, catalog.pinyin_chars_by_segment?.[segment.segment_id]),
      meaning: model.meaning(segment.segment_id) || '',
      startMs: segment.start_ms,
      endMs: segment.end_ms,
    })),
    support,
  };
}

/* An item from the Speaking catalogue: lines to say, with their reading and meaning, and no model
   clip (the clip card is not drawn for it, and "hear the model" is off). */
export function sourceFromItem(item, support) {
  return {
    id: item.id,
    title: item.title,
    level: item.level || '',
    assetId: '',
    playback: null,
    poster: '',
    lines: (item.lines || []).map((line) => ({
      id: `${item.id}:${line.line_id}`,
      text: line.text,
      original: line.text,
      reading: line.reading || '',
      readings: [],
      meaning: line.translations?.[support] || '',
      startMs: 0,
      endMs: 0,
    })),
    support,
  };
}
