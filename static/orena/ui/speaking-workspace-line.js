/* The line as it is drawn in the Speaking views: tappable units, the provider's flagged words
   marked, a word being practised alone lit. Shared by the workspace and its other views.

   `lineUnits`/`placeWords` moved (not copied, D-091 migration) to `product/speaking-line.js`,
   which the new `screens/speak`/`screens/compare` also import: both were already DOM-free, and
   this file's own contribution is only `sentenceHtml`'s markup below, which still belongs to the
   old presentation. */
import { esc } from './html.js';
import { lineUnits, placeWords } from '../product/speaking-line.js';

export { lineUnits, placeWords };

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
