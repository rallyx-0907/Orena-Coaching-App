/* The Word Card's Hanzi block (frames 13, 22, 36: "Stroke order", one 76px tile per character, then
   "Practise strokes"). Shared by Review Session and the Daily Feed's flipped card - the same block
   Word Detail draws, from the same real data: `GET /api/chinese/stroke-order` (the vendored stroke
   pack) drawn by `product/hanzi-strokes.js#glyphSvg`, finished. A character the pack does not carry
   gets no tile (rule 40 - nothing is drawn over nothing); the row goes with it when none is left. The
   tiles are placeholders at once and fill as the answer arrives, so the card never waits on it. */
import { html, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { glyphSvg } from '../../product/hanzi-strokes.js';

const HAN = /[㐀-鿿]/;
const cache = new Map();

export function hanCharacters(word) {
  return Array.from(String(word || '')).filter((character) => HAN.test(character));
}

/* `prefix` is the calling screen's own class prefix (`s-review`, `s-feed`); the calling screen's
   stylesheet draws the block (a colour lives with its owner). */
export function strokesMarkup({ word, prefix, label, buttonLabel, buttonAttr, buttonClass = '' }) {
  const characters = hanCharacters(word);
  return html`<div class="${prefix}-strokes">
    <div class="${prefix}-strokes__label">${label}</div>
    ${characters.length ? html`<div class="${prefix}-strokes__tiles" data-stroke-word="${characters.join('')}">${characters.map((character) => html`<span class="${prefix}-strokes__tile" data-stroke-char="${character}"></span>`)}</div>` : ''}
    <button type="button" class="o-btn o-btn--secondary ${buttonClass}" ${raw(buttonAttr)}>${raw(icon('pencil', { size: 16 }))}${buttonLabel}</button>
  </div>`;
}

/* Fill every `[data-stroke-word]` row under `root` (once per word - the answer is cached). */
export async function hydrateStrokes(root, chineseStrokeOrder, isCurrent = () => true) {
  const rows = [...root.querySelectorAll('[data-stroke-word]')];
  await Promise.all(
    rows.map(async (row) => {
      const word = row.dataset.strokeWord;
      if (!cache.has(word)) {
        cache.set(
          word,
          chineseStrokeOrder(word)
            .then((payload) => Object.fromEntries((payload?.characters || []).map((character) => [character.character, glyphSvg(character, { upto: character.stroke_count, faint: false })])))
            .catch(() => {
              cache.delete(word);
              return {};
            }),
        );
      }
      const svgs = await cache.get(word);
      if (!isCurrent() || !row.isConnected) return;
      [...row.children].forEach((tile) => {
        const svg = svgs[tile.dataset.strokeChar];
        if (svg) tile.innerHTML = svg;
        else tile.remove();
      });
      if (!row.children.length) row.remove();
    }),
  );
}
