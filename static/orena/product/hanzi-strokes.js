/* Drawing a Hanzi character from the vendored stroke pack (Make Me a Hanzi, via
 * `/api/chinese/stroke-order`). Pure: no DOM, no fetch, no provider - the same
 * geometry every renderer of this data needs, moved here once so Word Detail's
 * Stroke Practice sheet and the older word-strokes.js panel share it rather
 * than each carrying their own copy (D-091: pure logic lives in product/,
 * presentation stays with its screen).
 */

/* How many steps a "stroke order" strip shows at most. A character with fewer
   strokes than this shows one step per stroke instead. */
export const STEPS = 5;

/* Which strokes each step has drawn by, evenly spread across the character so
   the last step is always the whole of it - a strip that stopped short would
   be showing an unfinished character as if it were the word. */
export function stepsFor(count, steps = STEPS) {
  const total = Math.max(0, Number(count) || 0);
  if (!total) return [];
  const many = Math.min(steps, total);
  return Array.from({ length: many }, (_, at) => Math.round(((at + 1) * total) / many));
}

function escapeAttr(value) {
  return String(value ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* The character as it stands after `upto` strokes: the strokes written so far
   in full, and the rest of it faint (or absent when `faint` is false). The
   pack's glyph box has y running upward, so every renderer flips it once -
   without the transform the character renders upside down. */
export function glyphSvg(character, { upto = 0, size = 1024, faint = true, className = '' } = {}) {
  const paths = character?.stroke_paths || [];
  const drawn = paths
    .map((path, at) =>
      at < upto
        ? `<path d="${escapeAttr(path)}" class="stroke-glyph__on"></path>`
        : faint
          ? `<path d="${escapeAttr(path)}" class="stroke-glyph__off"></path>`
          : '',
    )
    .join('');
  return `<svg class="stroke-glyph ${className}" viewBox="0 0 ${size} ${size}" aria-hidden="true"><g transform="scale(1, -1) translate(0, -900)">${drawn}</g></svg>`;
}
