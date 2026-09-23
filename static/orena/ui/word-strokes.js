/* Nét chữ: how a character is written.
 *
 * The canonical frame "Vocabulary strokes" (05), which is also the right-hand
 * column of "Vocabulary deep desktop" (26) - that frame's own note says the
 * phone keeps them as two screens and the desktop puts them side by side, so
 * this is one panel used in both places.
 *
 * Everything drawn here comes from Orena's existing Chinese stroke capability
 * (`/api/chinese/stroke-order`, the vendored Make Me a Hanzi pack): the stroke
 * count, the stroke paths in writing order, the medians that say which way
 * each stroke runs, and the glyph box they are drawn in. Nothing is inferred.
 *
 * The one thing the capability deliberately does not answer is what a
 * character is *made of* - its radical and components, and what each one
 * contributes. `writing_coach/languages/chinese/orthography.py` says so in as
 * many words: it "does not infer readings, radicals, components, or
 * etymology; callers must supply those facts with their own provenance". So
 * that section is drawn from the catalogue entry when the entry carries it,
 * and is absent when it does not - never guessed from the glyph.
 */
import { esc } from './html.js';
import { icon } from './phosphor.js';

/* How many steps the "thứ tự nét" strip shows. The frame draws five, which is
   what fits a phone; a character with fewer strokes shows one step per
   stroke. */
export const STEPS = 5;

/* Which strokes each step has drawn by. Evenly spread across the character, so
   the last step is always the whole of it - a strip that stopped at stroke 11
   of 13 would be showing an unfinished character as if it were the word. */
export function stepsFor(count, steps = STEPS) {
  const total = Math.max(0, Number(count) || 0);
  if (!total) return [];
  const many = Math.min(steps, total);
  return Array.from({ length: many }, (_, at) => Math.round(((at + 1) * total) / many));
}

/* The character as it stands after `upto` strokes: the strokes written so far
   in full, and the rest of it faint - which is what the frame's dimmed later
   cells are showing. */
export function glyphSvg(character, { upto = 0, size = 1024, faint = true, className = '' } = {}) {
  const paths = character?.stroke_paths || [];
  const drawn = paths
    .map(
      (path, at) =>
        at < upto
          ? `<path d="${esc(path)}" class="stroke-glyph__on"></path>`
          : faint
            ? `<path d="${esc(path)}" class="stroke-glyph__off"></path>`
            : '',
    )
    .join('');
  /* The pack's glyph box has y running upward, which is why every renderer of
     this data flips it. Without the transform the character is upside down. */
  return `<svg class="stroke-glyph ${className}" viewBox="0 0 ${size} ${size}" aria-hidden="true"><g transform="scale(1, -1) translate(0, -900)">${drawn}</g></svg>`;
}

function componentCard(item) {
  const surface = String(item?.surface || '');
  if (!surface) return '';
  const role = [item.reading, item.role].filter(Boolean).join(' · ');
  return `<div class="stroke-part"><span class="stroke-part__glyph" lang="zh">${esc(surface)}</span>${
    role ? `<span class="stroke-part__role ds-data">${esc(role)}</span>` : ''
  }${item.gloss ? `<span class="stroke-part__gloss">${esc(item.gloss)}</span>` : ''}</div>`;
}

function label(text) {
  return `<span class="ds-label stroke-label">${esc(text)}</span>`;
}

/* The panel: the parts, the order, the way to watch it, and the square to
   trace in. Shared by the phone screen and the desktop deep column. */
export function strokesPanel(c, state) {
  const { character = null, parts = [], playing = false, tracing = false, at = 0, wrong = false } = state;
  if (!character) return '';
  const count = Number(character.stroke_count) || 0;
  const partsBlock = parts.length
    ? `<section class="stroke-section">${label(c.strokesParts)}<div class="stroke-parts">${parts
        .map(componentCard)
        .join('')}</div></section>`
    : '';
  const strip = stepsFor(count)
    .map(
      (upto) =>
        `<span class="stroke-step">${glyphSvg(character, { upto, size: character.glyph_size })}</span>`,
    )
    .join('');
  return `${partsBlock}<section class="stroke-section">${label(c.strokesOrder)}<div class="stroke-strip">${strip}</div></section><button type="button" class="stroke-watch" data-strokes-play aria-pressed="${playing}">${icon(
    playing ? 'pause' : 'play',
    { size: 19, filled: true },
  )}<span class="stroke-watch__text"><strong>${esc(String(c.strokesWatch).replace('{n}', String(count)))}</strong><small>${esc(c.strokesWatchNote)}</small></span></button><section class="stroke-section">${label(
    c.strokesTrace,
  )}<div class="stroke-square" data-strokes-square data-tracing="${tracing}"${wrong ? ' data-wrong="true"' : ''}><span class="stroke-square__frame" aria-hidden="true"></span><span class="stroke-square__cross" aria-hidden="true"></span>${glyphSvg(
    character,
    { upto: tracing ? at : count, size: character.glyph_size, className: 'stroke-glyph--trace' },
  )}${
    tracing
      ? `<svg class="stroke-square__ink" viewBox="0 0 ${character.glyph_size} ${character.glyph_size}" data-strokes-ink></svg><span class="stroke-square__step ds-data">${esc(
          String(c.strokesTraceStep).replace('{n}', String(at + 1)).replace('{total}', String(count)),
        )}</span>`
      : ''
  }</div></section>`;
}

/* Frame 05 as its own screen: the panel with the head and foot the phone frame
   draws around it. */
export function wordStrokesHtml(c, state) {
  const { word = '', character = null, busy = false, tracing = false } = state;
  const count = Number(character?.stroke_count) || 0;
  const head = `<header class="word-strokes__head"><button type="button" class="icon-button" data-strokes-back aria-label="${esc(c.back)}">${icon('caret-right', { size: 22, className: 'is-flipped' })}</button><strong>${esc(c.strokesTitle)} · ${esc(word)}</strong>${
    count ? `<span class="word-strokes__count ds-data">${esc(String(c.strokesCount).replace('{n}', String(count)))}</span>` : ''
  }</header>`;
  if (!character)
    return `<section class="word-strokes">${head}<p class="word-strokes__none">${esc(
      busy ? c.loading : c.strokesUnavailable,
    )}</p></section>`;
  return `<section class="word-strokes">${head}<div class="word-strokes__body">${strokesPanel(c, state)}</div><footer class="word-strokes__foot"><button type="button" class="stroke-action" data-strokes-trace aria-pressed="${tracing}">${icon(
    'scribble-loop',
    { size: 17 },
  )}<span>${esc(c.strokesTrace)}</span></button><button type="button" class="primary stroke-action" data-strokes-free>${icon('pen-nib', { size: 17 })}<span>${esc(c.strokesFree)}</span></button></footer></section>`;
}
