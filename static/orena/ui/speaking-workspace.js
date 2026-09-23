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
import {
  mediaPlayer,
  connectMediaPlayer,
  disconnectMediaPlayer,
  replaySegment,
  stopSegmentPlayback,
  setPlaybackRate,
  segmentPlaybackDelayMs,
} from '../capabilities/media-player.js';

const BARS = 42;
const RATES = [1, 0.75, 0.5];
const isHan = (text) => /^\p{Script=Han}$/u.test(text);
const clock = (ms) => {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
};

/* --- The line as tappable units ---------------------------------------------------------------
   Chinese: one unit per Han character. Other languages: one unit per word. Punctuation and spaces
   stay as they are written. Each unit knows its character range, so the provider's words can be
   laid over it to mark the ones it flagged. */
export function lineUnits(text, language) {
  const units = [];
  const value = String(text || '');
  if (language === 'zh') {
    let at = 0;
    for (const ch of value) {
      units.push({ text: ch, start: at, end: at + ch.length, unit: isHan(ch) });
      at += ch.length;
    }
    return units;
  }
  const pattern = /[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu;
  let last = 0;
  for (const match of value.matchAll(pattern)) {
    if (match.index > last) units.push({ text: value.slice(last, match.index), start: last, end: match.index, unit: false });
    units.push({ text: match[0], start: match.index, end: match.index + match[0].length, unit: true });
    last = match.index + match[0].length;
  }
  if (last < value.length) units.push({ text: value.slice(last), start: last, end: value.length, unit: false });
  return units;
}

/* Where each assessed word sits in the line, found in order; a word that cannot be placed is not
   marked anywhere rather than marked somewhere wrong. */
export function placeWords(text, words, language) {
  const haystack = String(text || '').toLocaleLowerCase();
  let cursor = 0;
  return words.map((word) => {
    const needle = String(word.text || '').toLocaleLowerCase();
    if (!needle) return null;
    const at = haystack.indexOf(needle, cursor);
    if (at < 0) return null;
    // An English word must not be found inside a longer word.
    if (language !== 'zh') {
      const before = haystack[at - 1] || ' ';
      const after = haystack[at + needle.length] || ' ';
      if (/[\p{L}\p{N}]/u.test(before) || /[\p{L}\p{N}]/u.test(after)) return null;
    }
    cursor = at + needle.length;
    return { start: at, end: at + needle.length };
  });
}

export function sentenceHtml(text, language, view, focus = null) {
  const units = lineUnits(text, language);
  const placed = view?.measured ? placeWords(text, view.words, language) : [];
  const flagged = placed
    .map((range, index) => (range && view.words[index].flagged ? range : null))
    .filter(Boolean);
  const markOf = (unit) => {
    if (focus && unit.start < focus.end && unit.end > focus.start) return 'focus';
    const range = flagged.find((item) => unit.start < item.end && unit.end > item.start);
    return range ? `flag:${range.start}` : '';
  };
  /* A word the provider flagged is one mark, however many characters it has, as the frame marks
     it; each character or word inside stays its own tappable unit. */
  let html = '';
  let open = '';
  units.forEach((unit, index) => {
    const mark = unit.unit ? markOf(unit) : '';
    if (mark !== open) {
      if (open) html += '</span>';
      if (mark) html += `<span class="${mark === 'focus' ? 'sp-tok--focus' : 'sp-tok--flag'}">`;
      open = mark;
    }
    html += unit.unit ? `<span class="sp-tok" data-sp-tok="${index}">${esc(unit.text)}</span>` : esc(unit.text);
  });
  if (open) html += '</span>';
  return html;
}

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
    ? s.headlineNone
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

export function resultHtml({ s, view, language, busy = false }) {
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
<div class="sp-actions"><button type="button" class="sp-btn sp-btn--accent" data-sp-again>${icon('arrow-counter-clockwise', { size: 18 })}<span>${esc(s.recordAgain)}</span></button><button type="button" class="sp-btn" data-sp-hear-take${view.measured ? '' : ' disabled'}>${icon('speaker-high', { size: 18 })}<span>${esc(s.hearYours)}</span></button><button type="button" class="sp-btn" data-sp-compare${view.measured ? '' : ' disabled'}>${icon('columns', { size: 18 })}<span>${esc(s.compare)}</span></button><button type="button" class="sp-btn" data-sp-next>${icon('arrow-right', { size: 18 })}<span>${esc(s.nextLine)}</span></button></div></div>`;
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
  return `<div class="sp-card__head">${ring(view.overall, 'sm', `<b>${view.overall}</b>`)}<div class="sp-card__copy"><strong>${esc(title)}</strong>${sub ? `<small>${esc(sub)}</small>` : ''}</div></div>${rows ? `<div class="sp-mrows">${rows}</div>` : ''}`;
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
    ? `<div class="sp-tones"><div class="sp-tone"><span class="sp-label">${esc(s.model)}</span>${toneSvg(tones)}<span>${esc(toneWords)}</span></div><div class="sp-tone sp-tone--yours"><span class="sp-label">${esc(s.yours)}</span>${toneSvg([])}<span>${esc(s.toneUnmeasured)}</span></div></div>`
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
<div class="sp-cols"><section class="sp-task"><div class="sp-steps" role="progressbar" aria-valuemin="1" aria-valuemax="${total}" aria-valuenow="${index + 1}"><span class="sp-steps__segments">${segments}</span><span class="sp-steps__count">${index + 1}/${total}</span></div>
<div class="sp-clip" data-sp-player data-kind="${esc(kind || '')}"><span class="sp-clip__art">${source.poster || ''}</span>${source.playback ? mediaPlayer(source.playback, source.title, { startMs: line.startMs, endMs: line.endMs, controls: false }) : ''}<span class="sp-glow" aria-hidden="true"></span><button type="button" class="sp-play" data-sp-model aria-label="${esc(s.hearModel)}">${icon('play', { size: 34, filled: true })}</button><span class="sp-badge">${icon('video-camera', { size: 14, filled: true })}<span>${esc(fill(s.clipModel, { t: clock(span) }))}</span></span><button type="button" class="sp-rate" data-sp-rate>${rate}×</button><span class="sp-clipbar"><i data-sp-clipbar></i></span></div>
<span class="sp-pill" data-sp-pill aria-live="off"><i></i><span data-sp-pill-text>${esc(fill(s.recordingPill, { t: '00:00' }))}</span></span>
<p class="sp-line" lang="${esc(language)}" data-sp-line>${sentenceHtml(line.text, language, null)}</p>${line.reading ? `<p class="sp-reading">${esc(line.reading)}</p>` : ''}${line.meaning ? `<p class="sp-meaning">${esc(line.meaning)}</p>` : ''}
<div class="sp-wave" data-sp-wave aria-hidden="true">${bars}</div>
<aside class="sp-card" data-sp-card aria-live="polite"></aside>
<div class="sp-controls"><button type="button" class="sp-round" data-sp-model aria-label="${esc(s.hearModel)}">${icon('speaker-high', { size: 24 })}</button><button type="button" class="sp-mic" data-sp-mic aria-label="${esc(s.record)}"><span class="sp-mic__icon">${icon('microphone', { size: 44, filled: true })}</span><span class="sp-mic__stop"></span></button><button type="button" class="sp-round" data-sp-again aria-label="${esc(s.recordAgain)}">${icon('arrow-counter-clockwise', { size: 24 })}</button></div>
<p class="sp-hint" data-sp-hint role="status">${esc(s[`tapWord_${language === 'zh' ? 'zh' : 'en'}`])}</p></section>
<section class="sp-result" data-sp-result aria-live="polite" aria-label="${esc(s.pronunciation)}"></section></div>
<audio data-sp-take-audio preload="auto" hidden></audio></section>`;
}

/* --- Behaviour ----------------------------------------------------------------------------------- */
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
  const levels = new Array(BARS).fill(0);
  const alive = () => !disposed && (ctx.alive ? ctx.alive() : true) && root.isConnected;

  const line = () => source.lines[index];
  const reference = () => (focus ? focus.text : line().text);

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

  function playModel() {
    const player = playerRoot();
    if (!player || !source.playback) return;
    const current = line();
    replaySegment(player, source.playback, current.startMs, current.endMs, rate);
  }

  function playTake({ fromMs = null, toMs = null } = {}) {
    const audio = q('[data-sp-take-audio]');
    if (!audio || !take?.takeUrl) return;
    if (audio.src !== take.takeUrl) audio.src = take.takeUrl;
    audio.currentTime = fromMs != null ? fromMs / 1000 : 0;
    audio.play().catch(() => {});
    if (toMs != null) {
      const stopAt = () => {
        if (audio.currentTime * 1000 >= toMs) {
          audio.pause();
          audio.removeEventListener('timeupdate', stopAt);
        }
      };
      audio.addEventListener('timeupdate', stopAt);
    }
  }

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
    if (state.phase === TAKE.ERROR && state.error) {
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
    hint.textContent = focus ? `${focus.text}${focus.pinyin ? ` · ${focus.pinyin}` : ''}` : s[`tapWord_${language === 'zh' ? 'zh' : 'en'}`];
  }

  function paintResult() {
    const busy = state.phase === TAKE.PROCESSING;
    const result = q('[data-sp-result]');
    const card = q('[data-sp-card]');
    if (result) result.innerHTML = resultHtml({ s, view, language, busy });
    if (card) card.innerHTML = cardHtml({ s, view, language });
    const lineEl = q('[data-sp-line]');
    if (lineEl) lineEl.innerHTML = sentenceHtml(line().text, language, focus ? null : view, focus);
    root.querySelectorAll('[data-sp-word]').forEach((row) => {
      row.onclick = () => openDetail(Number(row.dataset.spWord), row);
    });
    root.querySelectorAll('[data-sp-again]').forEach((button) => {
      button.onclick = () => begin();
      button.disabled = state.phase === TAKE.RECORDING || state.phase === TAKE.PROCESSING;
    });
    const hear = q('[data-sp-hear-take]');
    if (hear) hear.onclick = () => playTake();
    const compare = q('[data-sp-compare]');
    if (compare) compare.onclick = compareWithModel;
    const next = q('[data-sp-next]');
    if (next) {
      next.disabled = index >= source.lines.length - 1 || state.phase === TAKE.RECORDING;
      next.onclick = () => moveTo(index + 1);
    }
  }

  function paintPhase() {
    const room = q('.sp-room');
    if (!room) return;
    room.dataset.phase = state.phase;
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
    if (!wave) return;
    const bars = wave.children;
    for (let at = 0; at < bars.length; at++) {
      const level = levels[at] || 0;
      bars[at].style.blockSize = `${Math.max(6, Math.round(level * 100))}%`;
    }
  }

  function startListening() {
    levels.fill(0);
    paintWave();
    mic?.stop?.();
    mic = watchMicrophone({
      onLevel: (peak) => {
        if (!alive() || state.phase !== TAKE.RECORDING) return;
        levels.shift();
        levels.push(Math.min(1, Number(peak) || 0));
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

  function onTake(next) {
    if (!alive()) return;
    const previous = state.phase;
    state = next;
    if (next.phase === TAKE.RESULT && next.result) {
      view = pronunciationView(next.result, {
        language,
        readings: focus ? [] : line().readings,
        modelSpanMs: focus ? null : Math.max(0, (line().endMs || 0) - (line().startMs || 0)) || null,
      });
      // Where each word sits in the take, for "hear yours" on one word.
      (next.result.words || [])
        .filter((word) => String(word?.error_type || '').toLowerCase() !== 'insertion' && String(word?.word || '').trim())
        .forEach((word, at) => {
          if (view.words[at]) {
            view.words[at].offsetMs = word.offset_ms;
            view.words[at].durationMs = word.duration_ms;
            view.words[at].offsetKnown = Number.isFinite(word.offset_ms) && Number.isFinite(word.duration_ms);
          }
        });
      if (focus && view.words[0]) view.words[0].pinyin = focus.pinyin || view.words[0].pinyin;
      if (!focus) void keepShadowingRound();
    }
    if (next.phase === TAKE.PROCESSING) view = pronunciationView(null);
    if (next.phase === TAKE.RECORDING && previous !== TAKE.RECORDING) {
      startListening();
      clearInterval(ticker);
      ticker = setInterval(() => {
        if (!alive() || !take) return clearInterval(ticker);
        const ms = take.elapsedMs();
        const pill = q('[data-sp-pill-text]');
        if (pill) pill.textContent = fill(s.recordingPill, { t: clock(ms) });
        if (ms >= MAX_TAKE_MS) void take.stop(reference());
      }, 250);
    }
    if (next.phase !== TAKE.RECORDING && previous === TAKE.RECORDING) {
      clearInterval(ticker);
      stopListening();
    }
    paintPhase();
    if (next.phase !== TAKE.RECORDING || previous !== TAKE.RECORDING) paintResult();
  }

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
    if (!take || state.phase === TAKE.PROCESSING) return;
    if (state.phase === TAKE.RECORDING) return;
    stopSegmentPlayback(playerRoot(), source.playback);
    q('[data-sp-take-audio]')?.pause();
    await take.start();
  }

  async function micPressed() {
    if (state.phase === TAKE.RECORDING) await take.stop(reference());
    else await begin();
  }

  function compareWithModel() {
    clearTimeout(compareTimer);
    playModel();
    const current = line();
    const delay = segmentPlaybackDelayMs(current.startMs, current.endMs, rate);
    compareTimer = setTimeout(() => alive() && playTake(), (delay || 0) + 350);
  }

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
    panel.focus({ preventScroll: true });
  }

  /* One word, on its own: the same line stays on screen with the word lit (the frame's char
     detail draws exactly this), and the next take is assessed against that word only. Tapping the
     lit word again goes back to the whole line. */
  function practiseAlone(next) {
    focus = next;
    view = pronunciationView(null);
    state = { phase: TAKE.IDLE };
    newTake();
    paintPhase();
    paintResult();
  }

  function moveTo(next) {
    if (next < 0 || next >= source.lines.length || state.phase === TAKE.RECORDING) return;
    index = next;
    focus = null;
    view = pronunciationView(null);
    state = { phase: TAKE.IDLE };
    render();
    remember();
  }

  function render() {
    closeDetail();
    clearTimeout(compareTimer);
    if (playerRoot()) disconnectMediaPlayer(playerRoot());
    root.innerHTML = roomHtml({ s, c, source, index, language, rate, level: source.level });
    const player = playerRoot();
    if (player && source.playback) {
      connectMediaPlayer(player, source.playback);
      player.addEventListener('orena:media-time', (event) => {
        const current = line();
        const span = Math.max(1, current.endMs - current.startMs);
        const bar = q('[data-sp-clipbar]');
        if (bar) bar.style.width = `${Math.max(0, Math.min(100, ((event.detail.time_ms - current.startMs) / span) * 100))}%`;
      });
      player.addEventListener('orena:media-state', () => {});
    }
    root.querySelectorAll('[data-sp-model]').forEach((button) => (button.onclick = playModel));
    q('[data-sp-mic]').onclick = micPressed;
    q('[data-sp-cancel]').onclick = () => take?.cancel();
    q('[data-sp-back]').onclick = () => (onLeave ? onLeave() : history.back());
    q('[data-sp-rate]').onclick = (event) => {
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
    paintResult();
  }

  const onKey = (event) => {
    if (event.key === 'Escape' && state.phase === TAKE.RECORDING && !sheet) take?.cancel();
  };
  document.addEventListener('keydown', onKey);
  render();
  remember();

  return () => {
    disposed = true;
    clearInterval(ticker);
    clearTimeout(compareTimer);
    document.removeEventListener('keydown', onKey);
    closeDetail();
    stopListening();
    take?.dispose();
    q('[data-sp-take-audio]')?.pause();
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
