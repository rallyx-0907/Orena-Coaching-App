/* The stroke-order tiles frame 53 (Word Quick Sheet) and Word Detail both draw: each character in a 76px tile
   writing itself stroke by stroke on a loop (the design's looping stroke writer), its radical's strokes in the
   radical colour. One implementation for both surfaces, so the order reads the same wherever the word is opened
   (LEX-021). Reduced motion shows the whole character still.

   `createStrokeTiles(characters)` takes the stroke pack's characters (`/api/chinese/stroke-order`). `markup()`
   renders the tiles at their current step and may be called on every repaint; `start(root)` runs the loop on the
   tiles inside `root` and `stop()` ends it. The loop stops by itself once `root` leaves the document. */

import { html, raw } from '../../kit/html.js';
import { glyphSvg } from '../../product/hanzi-strokes.js';

// One stroke per step (Stroke Practice's own pace), then a pause before the character writes itself again
// (the design writer's delayBetweenLoops).
export const STROKE_STEP_MS = 700;
export const STROKE_LOOP_HOLD_MS = 1400;

const strokeCount = (character) => Number(character?.stroke_count) || character?.stroke_paths?.length || 0;
const reducedMotion = () => Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);

export function createStrokeTiles(characters = []) {
  const list = Array.isArray(characters) ? characters.filter(Boolean) : [];
  const upto = list.map(() => 0);
  let root = null;
  let timer = 0;
  let hold = 0;

  function glyph(index) {
    const character = list[index];
    const count = strokeCount(character);
    const at = reducedMotion() ? count : Math.min(upto[index] ?? 0, count);
    return raw(glyphSvg(character, { upto: at, animate: at < count, radical: true }));
  }

  function markup() {
    if (!list.length) return '';
    return html`<div class="o-stroke-tiles" lang="zh">${list.map(
      (_, index) => html`<span class="o-stroke-tile" data-stroke-tile="${index}">${glyph(index)}</span>`,
    )}</div>`;
  }

  function stop() {
    clearInterval(timer);
    clearTimeout(hold);
    timer = 0;
    hold = 0;
  }

  function tick() {
    if (!root?.isConnected) return stop();
    let finished = true;
    list.forEach((character, index) => {
      if ((upto[index] ?? 0) < strokeCount(character)) {
        upto[index] = (upto[index] ?? 0) + 1;
        finished = false;
      }
      const tile = root.querySelector(`[data-stroke-tile="${index}"]`);
      if (tile) tile.innerHTML = String(glyph(index));
    });
    if (finished) {
      clearInterval(timer);
      timer = 0;
      hold = window.setTimeout(() => start(root), STROKE_LOOP_HOLD_MS);
    }
  }

  function start(element) {
    stop();
    root = element || root;
    if (!root || !list.length || reducedMotion()) return;
    upto.fill(0);
    timer = window.setInterval(tick, STROKE_STEP_MS);
  }

  return { markup, start, stop };
}
