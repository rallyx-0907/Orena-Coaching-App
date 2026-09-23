/* The Speaking workspace's other views, drawn from Orena Speaking at its source (read 2026-09-23):
   06 "Compare with model" (desktop, mobile), 05 "Lesson summary mobile" (desktop: the same content
   centred), 07 "Shadowing mobile" (desktop: the mode switch above the line), 09 "Speaking mic blocked
   mobile", "Speaking not heard mobile", "Speaking offline grading mobile".

   Markup only. What is drawn is what was measured: the waveforms are the recordings' loudness, the
   contours their measured pitch, the colours the provider's own flags (D-076: a line to practise
   again is a line with a flagged word; there is no score threshold). The frames' written verdicts
   ("mẫu xuống rồi lên, bạn đi ngang") are not written (D-076). */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { fill } from './speaking-copy.js';
import { sentenceHtml } from './speaking-workspace-line.js';
import { contourPolylines } from '../capabilities/audio-analysis.js';

const clock = (ms) => {
  const seconds = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
};
const time = (at, ui) => {
  try {
    return new Date(at).toLocaleTimeString(ui === 'vi' ? 'vi-VN' : ui === 'zh' ? 'zh-CN' : 'en-GB', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
};

/* Loudness bars, `count` of them, from 0-1 values. */
export function barsHtml(values, cls = '') {
  return (values || []).map((value) => `<i class="${cls}" style="block-size:${Math.max(4, Math.round(value * 100))}%"></i>`).join('');
}

/* The pitch contour of the model and of one take, in the frame's 1000x200 box, with a band over each
   flagged word (placed by the provider's timing inside the take). */
export function toneSvgHtml({ model, you, youDuration, flaggedSpans = [], stroke = 4 }) {
  const grid = '<g class="sp-grid"><line x1="0" y1="40" x2="1000" y2="40"></line><line x1="0" y1="100" x2="1000" y2="100"></line><line x1="0" y1="160" x2="1000" y2="160"></line></g>';
  const lines = (points, cls) => contourPolylines(points || [], {}).map((pts) => `<polyline class="${cls}" stroke-width="${stroke}" points="${pts}"></polyline>`).join('');
  const bands = youDuration
    ? flaggedSpans
        .map(({ offsetMs, durationMs }) => {
          const x = Math.max(0, (offsetMs / 1000 / youDuration) * 1000);
          const w = Math.max(24, (durationMs / 1000 / youDuration) * 1000);
          return `<rect class="sp-band" x="${x.toFixed(1)}" y="10" width="${w.toFixed(1)}" height="180" rx="10"></rect>`;
        })
        .join('')
    : '';
  return `<svg class="sp-tone-svg" viewBox="0 0 1000 200" preserveAspectRatio="none" aria-hidden="true">${grid}${bands}${lines(model, 'sp-curve-model')}${lines(you, 'sp-curve-you')}</svg>`;
}

/* 06 · the attempts list. */
export function attemptsHtml({ s, attempts, selectedId, bestId, ui, keepRecent }) {
  const total = attempts.length;
  const rows = attempts
    .map((attempt, at) => {
      const n = total - at;
      const best = attempt.id === bestId;
      const name = best ? fill(s.attemptBest, { n }) : fill(s.attemptName, { n });
      const score = typeof attempt.overall === 'number' ? Math.round(attempt.overall) : '—';
      return `<button type="button" class="sp-attempt${best ? ' sp-attempt--best' : ''}${attempt.id === selectedId ? ' is-selected' : ''}" data-sp-attempt="${esc(attempt.id)}">${icon('play-circle', { size: 30, filled: true })}<span class="sp-attempt__text"><b>${esc(name)}</b><small>${esc(`${s.today} ${time(attempt.at, ui)} · ${clock(attempt.ms)}`)}</small></span><span class="sp-attempt__score${attempt.flagged ? ' is-flagged' : ' is-clear'}">${score}</span></button>`;
    })
    .join('');
  return `<span class="sp-label">${esc(s.attemptsLabel)}</span>${rows}<label class="sp-keep"><input type="checkbox" data-sp-keep${keepRecent ? ' checked' : ''}><span><b>${esc(s.keepRecent)}</b><small>${esc(keepRecent ? s.keepRecentOn : s.keepRecentOff)}</small></span></label>`;
}

/* 06 · compare with the model (both frames; CSS shows the one that belongs). */
export function compareHtml({ s, source, index, language, view, analysis, attempts, selectedId, bestId, ui, keepRecent }) {
  const line = source.lines[index];
  const takeNumber = attempts.length - Math.max(0, attempts.findIndex((item) => item.id === selectedId));
  const flaggedSpans = (analysis.flaggedSpans || []);
  const tone = language === 'zh'
    ? `<span class="sp-label sp-cmp__tone-label">${esc(s.toneLabel)}</span>${toneSvgHtml({ model: analysis.model?.contour, you: analysis.you?.contour, youDuration: analysis.you?.duration, flaggedSpans })}`
    : '';
  const wave = `<div class="sp-cmp__waves"><div class="sp-cmp__wave sp-cmp__wave--model">${barsHtml(analysis.model?.bars)}</div><div class="sp-cmp__wave sp-cmp__wave--you">${barsHtml(analysis.you?.bars)}</div></div>`;
  const legend = (short) => `<div class="sp-cmp__legend"><span class="sp-label">${esc(s.waveLabel)}</span><span><i class="sp-swatch sp-swatch--model"></i>${esc(s.legendModel)}</span><span><i class="sp-swatch sp-swatch--you"></i>${esc(short ? s.legendYouShort : fill(s.legendYou, { n: takeNumber }))}</span></div>`;
  const next = attempts.length + 1;
  return `<section class="sp-room sp-cmp" data-view="compare" data-tone="${language === 'zh'}">
<header class="sp-top sp-cmp__top"><button type="button" class="sp-back" data-sp-cmp-back><span class="sp-cmp__arrow">${icon('arrow-left', { size: 20 })}</span><span class="sp-back__caret">${icon('caret-left', { size: 22 })}</span><span class="sp-lesson sp-cmp__desk" lang="${esc(language)}">${esc(`${source.title} · ${fill(s.lineOf, { i: index + 1, n: source.lines.length })}`)}</span><span class="sp-lesson sp-cmp__phone">${esc(fill(s.compareTitle, { i: index + 1 }))}</span></button></header>
<div class="sp-cmp__grid"><div class="sp-cmp__main"><p class="sp-cmp__line" lang="${esc(language)}">${sentenceHtml(line.text, language, view)}</p>
<div class="sp-cmp__card">${legend(false)}${wave}${tone}${analysis.modelMissing ? `<p class="sp-cmp__note">${esc(s.modelUnavailable)}</p>` : ''}</div>
<div class="sp-cmp__buttons"><button type="button" class="sp-pillbtn" data-sp-cmp-model${source.playback ? '' : ' disabled'}>${icon('speaker-high', { size: 20 })}<span>${esc(s.listenModel)}</span></button><button type="button" class="sp-pillbtn" data-sp-cmp-take>${icon('play', { size: 20 })}<span>${esc(fill(s.listenTake, { n: takeNumber }))}</span></button><button type="button" class="sp-pillbtn" data-sp-cmp-alternate${source.playback ? '' : ' disabled'}>${icon('shuffle', { size: 20 })}<span>${esc(s.interleave)}</span></button><button type="button" class="sp-pillbtn sp-pillbtn--accent" data-sp-cmp-record>${icon('microphone', { size: 20, filled: true })}<span>${esc(fill(s.tryTake, { n: next }))}</span></button></div></div>
<aside class="sp-cmp__attempts" data-sp-attempts>${attemptsHtml({ s, attempts, selectedId, bestId, ui, keepRecent })}</aside></div>
<div class="sp-cmp__bar"><button type="button" class="sp-fbtn" data-sp-cmp-alternate${source.playback ? '' : ' disabled'}>${icon('shuffle', { size: 17 })}<span>${esc(s.interleave)}</span></button><button type="button" class="sp-fbtn sp-fbtn--accent" data-sp-cmp-record>${icon('microphone', { size: 17, filled: true })}<span>${esc(fill(s.tryTake, { n: next }))}</span></button></div>
<audio data-sp-cmp-audio preload="auto" hidden></audio></section>`;
}

/* 05 · the lesson summary. `rows` are the lesson's lines with their best measured take. */
export function summaryHtml({ s, source, language, rows, missed, minutes, kept, room }) {
  const scored = rows.filter((row) => typeof row.overall === 'number');
  const average = scored.length ? Math.round(scored.reduce((sum, row) => sum + row.overall, 0) / scored.length) : null;
  const again = rows.filter((row) => row.flagged > 0).length;
  const list = rows
    .map((row, at) => {
      const value = row.pending ? s.pending : typeof row.overall === 'number' ? Math.round(row.overall) : '—';
      const tone = row.pending ? 'is-pending' : typeof row.overall !== 'number' ? '' : row.flagged ? 'is-flagged' : 'is-clear';
      return `<button type="button" class="sp-sum__row" data-sp-sum-line="${at}"><span class="sp-sum__n">${at + 1}</span><span class="sp-sum__text" lang="${esc(language)}">${esc(row.text)}</span><span class="sp-sum__score ${tone}">${esc(String(value))}</span></button>`;
    })
    .join('');
  const chips = missed
    .map((item) => `<span class="sp-sum__chip"><b lang="${esc(language)}">${esc(item.text)}</b><small>${esc([item.reading, item.count > 1 ? fill(s.missedTimes, { n: item.count }) : ''].filter(Boolean).join(' · '))}</small></span>`)
    .join('');
  return `<section class="sp-room sp-sum" data-view="summary"><div class="sp-sum__body"><div class="sp-sum__head"><span class="sp-label">${esc(fill(s.summaryMeta, { title: source.title, n: rows.length, m: minutes }))}</span><h1 class="sp-sum__title">${esc(average == null ? s.summaryTitleNone : fill(s.summaryTitle, { avg: average }))}</h1></div>
<div class="sp-sum__cols"><div class="sp-sum__list">${list}</div><div class="sp-sum__side">${chips ? `<div class="sp-sum__missed"><span class="sp-label">${esc(s[`missedLabel_${language === 'zh' ? 'zh' : 'en'}`])}</span><div class="sp-sum__chips">${chips}</div></div>` : ''}${kept ? `<span class="sp-sum__kept">${icon('check-circle', { size: 16, filled: true })}${esc(s.summaryKept)}</span>` : ''}
<div class="sp-sum__actions">${again ? `<button type="button" class="sp-bigbtn sp-bigbtn--accent" data-sp-sum-again>${esc(fill(s.retryFlagged, { n: again }))}</button>` : ''}<button type="button" class="sp-bigbtn" data-sp-sum-home>${esc(fill(s.backToRoom, { room }))}</button></div></div></div></div></section>`;
}

/* 07 · the mode switch, and the shadowing card. */
export function modeSwitchHtml({ s, mode }) {
  return `<div class="sp-mode" role="radiogroup" aria-label="${esc(s.modeShadow)}"><button type="button" role="radio" aria-checked="${mode === 'listen'}" data-sp-mode="listen">${esc(s.modeListen)}</button><button type="button" role="radio" aria-checked="${mode === 'shadow'}" data-sp-mode="shadow">${esc(s.modeShadow)}</button></div>`;
}

export function shadowCardHtml({ s, rate, modelBars, lagMs }) {
  return `<div class="sp-shadow"><div class="sp-shadow__head"><span>${esc(s.legendModel.toUpperCase())}</span><span>${rate}×</span></div><div class="sp-shadow__waves"><div class="sp-shadow__model">${barsHtml(modelBars)}</div><div class="sp-shadow__you" data-sp-shadow-you></div><span class="sp-shadow__head-line" data-sp-shadow-playhead></span></div>${lagMs != null ? `<span class="sp-shadow__lag">${esc(fill(s.shadowLag, { s: (Math.max(0, lagMs) / 1000).toFixed(1) }))}</span>` : ''}</div><p class="sp-shadow__hint">${esc(s.headphones)}</p>`;
}

/* 09 · the three states the workspace can be in besides working. */
export function micBlockedHtml({ s }) {
  return `<div class="sp-state"><span class="sp-state__icon sp-state__icon--mic">${icon('microphone-slash', { size: 30 })}</span><strong class="sp-state__title">${esc(s.micTitle)}</strong><p class="sp-state__text">${esc(s.micText)}</p><div class="sp-state__actions"><button type="button" class="sp-bigbtn sp-bigbtn--accent" data-sp-mic-retry>${esc(s.retry)}</button><button type="button" class="sp-textbtn" data-sp-listen-only>${esc(s.listenOnly)}</button></div></div>`;
}

export function offlineHtml({ s }) {
  return `<div class="sp-state"><span class="sp-state__icon sp-state__icon--warn">${icon('wifi-slash', { size: 30 })}</span><strong class="sp-state__title">${esc(s.offlineTitle)}</strong><p class="sp-state__text">${esc(s.offlineText)}</p><div class="sp-state__actions"><button type="button" class="sp-bigbtn sp-bigbtn--accent" data-sp-offline-next>${esc(s.goNext)}</button><button type="button" class="sp-textbtn" data-sp-offline-retry>${esc(s.rescore)}</button></div></div>`;
}

export function notHeardHtml({ s, kind, twice }) {
  return `<div class="sp-notheard" role="alert">${icon('waveform', { size: 22 })}<div><strong>${esc(s.notHeardTitle)}</strong><p>${esc(kind === 'too_short' ? s.notHeardShort : s.notHeardText)}${twice ? ` ${esc(s.notHeardTwice)}` : ''}</p></div></div>`;
}
