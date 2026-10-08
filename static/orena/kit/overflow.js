/* The design's overflow ("⋯") pattern, as the Reader frame draws it (frame 14, `rdMenuMore` / `rdMenuItems`): a 34px
   square "⋯" control, and - when open - a surface row of 32px pill actions with a close control at its end. It is
   one primitive so every room that gains a "⋯" draws it the same way. The design draws no confirmation for any
   action behind it; none is drawn here (docs/project/UI_BACKEND_GAPS.md records that for the destructive one). */
import { html, raw } from './html.js';
import { icon } from './icons.js';

export function moreButton({ label, open = false, dataset = '' }) {
  return html`<button type="button" class="o-more" data-more="${dataset}" data-on="${open ? 1 : 0}" aria-haspopup="true" aria-expanded="${open ? 'true' : 'false'}" title="${label}" aria-label="${label}">⋯</button>`;
}

/* `items`: [{ key, label }]. The caller binds `[data-menu-item]` (value = key) and `[data-menu-close]`. */
export function moreMenu({ items, closeLabel, scope = '' }) {
  return html`<div class="o-more-menu" role="group" data-menu="${scope}">${items.map((item) => html`<button type="button" class="o-more-menu__item" data-menu-item="${item.key}">${item.label}</button>`)}<span class="o-more-menu__spacer"></span><button type="button" class="o-more-menu__close" data-menu-close aria-label="${closeLabel}">${raw(icon('x', { size: 17 }))}</button></div>`;
}
