import { esc } from './html.js';
import { sceneAsset, feelingAsset } from '../content/brand-library.js';

/* One way to put approved artwork on a page.

   Two things have to be true at once. The artwork is canonical and must not be
   recoloured, cropped to taste or repainted to match the page. And the page has
   two themes, so a composed illustration carrying its own painted daylight
   cannot simply sit on a dark ground.

   The answer is framing, not editing: a scene keeps its own ground inside a
   rounded frame that reads as a picture in both themes, while a character on
   transparency needs no frame at all and sits directly on the page. That is why
   `kind` is part of the library rather than a styling choice made per surface. */

export function scene(state, { size = 'medium', label = '' } = {}) {
  return render(sceneAsset(state), size, label);
}

export function feeling(name, { size = 'small', label = '' } = {}) {
  return render(feelingAsset(name), size, label);
}

function render(asset, size, label) {
  // A state with no approved artwork shows nothing. Content is the protagonist,
  // and a missing illustration is not a reason to substitute a different one.
  if (!asset) return '';
  return `<figure class="brand-art" data-kind="${esc(asset.kind)}" data-size="${esc(size)}" data-state="${esc(asset.state)}"${label ? '' : ' aria-hidden="true"'}><img src="${esc(asset.src)}" alt="${esc(label)}" loading="lazy" decoding="async" style="aspect-ratio:${asset.ratio}"></figure>`;
}

/* The arrival companion. Named separately because the discover surface has
   composed around it since the reset, and its meaning there is "this is
   Orena", not a state the learner is in. */
export function companionArt() {
  return scene('discovery', { size: 'hero' });
}
