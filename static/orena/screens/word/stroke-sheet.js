/* Stroke Practice (frame 60, an overlay of Word Detail - and of the Daily Feed, Review and Word
   Quick Sheet card back, per D7/E4's shared "wordCard" note, though only Word Detail wires it in
   this pass). Real vendored stroke data throughout (`/api/chinese/stroke-order`, the same Make Me
   a Hanzi pack `ui/word-strokes.js` already reads) and real geometric scoring
   (`product/stroke-trace.js`'s median comparison) - never the hanzi-writer CDN, and never a
   canned "watch"/"traced" demo. */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { glyphSvg } from '../../product/hanzi-strokes.js';
import { tracedStroke } from '../../product/stroke-trace.js';
import { hanziCharsOf, mapStrokeCharacters } from './model.js';

const GLYPH_SIZE = 1024;
const WATCH_STEP_MS = 700;
const WRONG_FLASH_MS = 900;

/* A pointer position (client px) to the pack's own coordinate space: the ink overlay's viewBox is
   the same 0..1024 box glyphSvg draws in, but glyphSvg's own `scale(1,-1) translate(0,-900)`
   means a pack point (x, y) renders at visual (x, 900 - y) - so recovering pack space from a
   drawn point is that subtraction run backwards: pack_y = 900 - visual_y. */
function packPoint(point, rect) {
  const vx = ((point.clientX - rect.left) / rect.width) * GLYPH_SIZE;
  const vy = ((point.clientY - rect.top) / rect.height) * GLYPH_SIZE;
  return [vx, 900 - vy];
}

function toVisual([px, py]) {
  return [px, 900 - py];
}

export function mountStrokeSheet(sheet, handle, { word, titleWord = word, chineseStrokeOrder, t, closeLabel }) {
  const state = {
    chars: hanziCharsOf(word).map((ch) => ({ ch, data: null, available: false })),
    index: 0,
    mode: 'watch',
    watchUpto: 0,
    traceIndex: 0,
    wrong: false,
    done: false,
    loading: true,
    points: [],
  };
  let watchTimer = 0;
  let wrongTimer = 0;
  let dragging = false;

  function current() {
    return state.chars[state.index] || null;
  }

  function clearWatch() {
    clearInterval(watchTimer);
    watchTimer = 0;
  }

  function startWatch() {
    clearWatch();
    const item = current();
    const count = Number(item?.data?.stroke_count) || 0;
    state.mode = 'watch';
    state.watchUpto = 0;
    paintBody();
    if (!count) return;
    watchTimer = setInterval(() => {
      state.watchUpto += 1;
      if (state.watchUpto >= count) {
        clearWatch();
        state.watchUpto = count;
      }
      paintBody();
    }, WATCH_STEP_MS);
  }

  function startTrace() {
    clearWatch();
    state.mode = 'trace';
    state.traceIndex = 0;
    state.wrong = false;
    state.done = false;
    state.points = [];
    paintBody();
  }

  function pickChar(index) {
    if (index === state.index) return;
    state.index = index;
    startWatch();
  }

  function nextChar() {
    const at = (state.index + 1) % Math.max(1, state.chars.length);
    pickChar(at);
  }

  async function load() {
    try {
      const payload = await chineseStrokeOrder(word);
      state.chars = mapStrokeCharacters(word, payload);
    } catch {
      /* Left as unavailable (rule 40): a lookup failure is not a stroke count of zero. */
    }
    state.loading = false;
    paintHead();
    startWatch();
  }

  function statusFor() {
    const item = current();
    const count = Number(item?.data?.stroke_count) || 0;
    if (!item?.available) return { text: t('strokeUnavailable'), color: 'var(--muted)' };
    if (state.mode === 'watch') return { text: t('strokeWatching'), color: 'var(--muted)' };
    if (state.done) return { text: t('strokeComplete'), color: 'var(--green)' };
    if (state.wrong) return { text: t('strokeTryAgain'), color: 'var(--red)' };
    return { text: t('strokeStep', { n: state.traceIndex + 1, total: count }), color: 'var(--muted)' };
  }

  function stageMarkup() {
    const item = current();
    if (!item?.available) {
      return html`<div class="s-word-stage" data-stage></div>`;
    }
    const count = Number(item.data.stroke_count) || 0;
    const upto = state.mode === 'watch' ? state.watchUpto : state.done ? count : state.traceIndex;
    const glyph = raw(glyphSvg(item.data, { upto, size: GLYPH_SIZE, animate: state.mode === 'watch' && upto < count, className: state.mode === 'trace' ? 'is-tracing' : '' }));
    const ink =
      state.mode === 'trace'
        ? html`<svg class="s-word-ink" viewBox="0 0 ${GLYPH_SIZE} ${GLYPH_SIZE}" data-ink></svg>`
        : '';
    return html`<div class="${cls('s-word-stage', state.wrong && 'is-wrong')}" data-stage>${glyph}${ink}</div>`;
  }

  function paintBody() {
    const body = sheet.querySelector('[data-body]');
    if (!body) return;
    const item = current();
    const count = Number(item?.data?.stroke_count) || 0;
    const status = statusFor();
    mount(
      body,
      html`
      <div class="s-word-chars">
        ${state.chars.map(
          (c, i) => html`<button type="button" class="${cls('s-word-char', i === state.index && 'is-selected')}" data-char="${i}" lang="zh">${c.ch}</button>`,
        )}
      </div>
      <div class="s-word-info">${state.loading ? t('strokeLoading') : item?.available ? t.plural('strokeCount', count) : ''}</div>
      ${stageMarkup()}
      <div class="s-word-status" style="color:${status.color}">${status.text}</div>
      <div class="s-word-actions">
        <button type="button" class="o-btn o-btn--secondary" data-watch>${t('watchStrokes')}</button>
        <button type="button" class="o-btn o-btn--secondary s-word-action--accent" data-write>${t('writeIt')}</button>
        <button type="button" class="o-btn o-btn--primary" data-next>${t('nextCharacter')}</button>
      </div>`,
    );
    bindBody();
  }

  function paintHead() {
    const head = sheet.querySelector('[data-head-word]');
    if (head) head.textContent = `${t('strokePracticeTitle', { word: titleWord })}`;
    paintBody();
  }

  function onPointerDown(event) {
    if (state.mode !== 'trace' || state.done) return;
    const ink = sheet.querySelector('[data-ink]');
    if (!ink) return;
    dragging = true;
    state.points = [];
    const rect = ink.getBoundingClientRect();
    state.points.push(packPoint(event, rect));
    drawInk(ink);
    ink.setPointerCapture?.(event.pointerId);
  }

  function onPointerMove(event) {
    if (!dragging) return;
    const ink = sheet.querySelector('[data-ink]');
    if (!ink) return;
    const rect = ink.getBoundingClientRect();
    state.points.push(packPoint(event, rect));
    drawInk(ink);
  }

  function onPointerUp() {
    if (!dragging) return;
    dragging = false;
    judgeTrace();
  }

  function drawInk(ink) {
    const visual = state.points.map(toVisual);
    const d = visual.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
    ink.innerHTML = `<path d="${d}" class="s-word-ink__path"></path>`;
  }

  function judgeTrace() {
    const item = current();
    const medians = item?.data?.medians || [];
    const median = medians[state.traceIndex];
    const result = median ? tracedStroke(state.points, median, { size: GLYPH_SIZE }) : { ok: false };
    state.points = [];
    if (result.ok) {
      state.wrong = false;
      state.traceIndex += 1;
      if (state.traceIndex >= medians.length) state.done = true;
      paintBody();
      return;
    }
    state.wrong = true;
    paintBody();
    clearTimeout(wrongTimer);
    wrongTimer = setTimeout(() => {
      state.wrong = false;
      paintBody();
    }, WRONG_FLASH_MS);
  }

  function bindBody() {
    sheet.querySelectorAll('[data-char]').forEach((button) => {
      button.addEventListener('click', () => pickChar(Number(button.dataset.char)));
    });
    sheet.querySelector('[data-watch]')?.addEventListener('click', startWatch);
    sheet.querySelector('[data-write]')?.addEventListener('click', startTrace);
    sheet.querySelector('[data-next]')?.addEventListener('click', nextChar);
    const ink = sheet.querySelector('[data-ink]');
    if (ink) {
      ink.addEventListener('pointerdown', onPointerDown);
      ink.addEventListener('pointermove', onPointerMove);
      ink.addEventListener('pointerup', onPointerUp);
      ink.addEventListener('pointercancel', onPointerUp);
    }
  }

  mount(
    sheet,
    html`<div class="s-word-sk-head"><span data-head-word class="s-word-sk-title">${t('strokePracticeTitle', { word: titleWord })}</span><button type="button" class="o-iconbtn o-iconbtn--close" data-sheet-close aria-label="${closeLabel}">${raw(icon('x', { size: 17 }))}</button></div>
    <div class="s-word-sk-body" data-body></div>`,
  );
  sheet.querySelector('[data-sheet-close]')?.addEventListener('click', () => handle.close());
  load();
  paintBody();

  return () => {
    clearWatch();
    clearTimeout(wrongTimer);
  };
}
