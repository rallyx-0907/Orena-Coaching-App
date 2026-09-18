/* One compact bar of learner actions, shared.

   A learner action that repeats - hear this line again, practise it, show what
   it means, show how it is read, colour the word classes - belongs to the
   thing being learned, not to every row of it. Putting those controls inside
   each transcript row meant the active row had to grow a block of buttons the
   moment the voice arrived, and shrink again when it left: the list breathed
   in and out under the learner's eyes, and on a phone it was unusable
   (DESIGN_CONTRACT: active state before structural expansion).

   So the actions live here, once, in a bar with a fixed place in the
   workspace, and they act on whatever line is current or selected. The bar is
   icon-first: a stable semantic symbol carries a reusable action, and the
   support language supplies the tooltip and the accessible name - never a wall
   of large text buttons (DESIGN_CONTRACT: icon-first shared actions).

   Three shapes, and nothing more:

     action  - does something now (replay)
     toggle  - a display preference that stays on (meaning, pinyin, colours)
     menu    - deeper intentions, named plainly inside (practice, more)

   Listening uses it first. Reading, Speaking and Writing can adopt it without
   this file learning anything about them: it is given labels and names, and it
   reports names back. */
import { esc } from './html.js';
import { symbol } from './symbols.js';

const EDGE = 8;

/* A menu item is usually a plain instruction. It can also be a piece of the
   learner's own material - a line of a transcript, say - in which case the
   content is the label and a mark says where the learner stands in it. That is
   what keeps navigation legible: "Using this scale the universe slowed" tells
   a learner which line they are choosing; "03" does not. */
function menuItemHtml(entry) {
  const marks = entry.done ? '✓' : entry.current ? '●' : '';
  const state = entry.current ? ' aria-current="true"' : '';
  const note = entry.note ? ` <span class="learning-menu__note">${esc(entry.note)}</span>` : '';
  // The mark is a glyph, so what it means is said in words for anyone who
  // cannot see it - in the support language, like every other word Orena says.
  const said = entry.done && entry.doneLabel
    ? `<span class="sr-only">${esc(entry.doneLabel)}, </span>` : '';
  return `<button type="button" role="menuitem" data-action="${esc(entry.name)}"${state}${entry.done ? ' data-done' : ''}><span class="learning-menu__mark" aria-hidden="true">${marks}</span>${said}<span class="learning-menu__label"${entry.lang ? ` lang="${esc(entry.lang)}"` : ''}>${esc(entry.label)}</span>${note}</button>`;
}

function actionHtml(action) {
  const { name, icon, label, kind = 'action' } = action;
  const tip = `data-tip="${esc(label)}" aria-label="${esc(label)}"`;
  if (kind === 'toggle')
    return `<button type="button" class="learning-action" data-toggle="${esc(name)}" aria-pressed="${action.pressed ? 'true' : 'false'}" ${tip}>${symbol(icon, 18)}</button>`;
  if (kind === 'menu')
    return `<span class="learning-action-menu"><button type="button" class="learning-action" data-menu-toggle="${esc(name)}" aria-haspopup="menu" aria-expanded="false" ${tip}>${symbol(icon, 18)}</button><div class="learning-menu${action.wide ? ' learning-menu--wide' : ''}" data-menu="${esc(name)}" role="menu" hidden>${(action.items || [])
      .map(menuItemHtml)
      .join('')}</div></span>`;
  return `<button type="button" class="learning-action" data-action="${esc(name)}" ${tip}>${symbol(icon, 18)}</button>`;
}

/* The bar itself. `actions` is the order they appear in; an entry that is
   `null` is simply not part of this surface - pinyin is not a control at all
   when the learning language has no reading to show. */
export function learningToolbar(actions, { label = '' } = {}) {
  return `<div class="learning-toolbar" role="toolbar" aria-label="${esc(label)}">${actions
    .filter(Boolean)
    .map(actionHtml)
    .join('')}</div>`;
}

/* Where a menu may open is a measurement, never a coordinate written into the
   source. The menu is placed, measured against the viewport and against the
   pane it lives in, and flipped to whichever side it fits - so a bar near the
   right edge or near the bottom of a short window opens inward instead of
   pushing the page sideways. On a phone the stylesheet makes the menu a sheet
   at the bottom of the screen, which needs no measuring at all. */
function placeMenu(menu) {
  menu.removeAttribute('data-align');
  menu.removeAttribute('data-drop');
  if (matchMedia('(max-width: 600px)').matches) return;
  const pane = menu.closest('.learning-toolbar')?.getBoundingClientRect();
  const limit = {
    start: EDGE,
    end: Math.min(window.innerWidth - EDGE, pane ? window.innerWidth - EDGE : Infinity),
  };
  let box = menu.getBoundingClientRect();
  if (box.right > limit.end) {
    menu.dataset.align = 'end';
    box = menu.getBoundingClientRect();
  }
  if (box.left < limit.start) menu.dataset.align = 'clamp';
  box = menu.getBoundingClientRect();
  const below = window.innerHeight - EDGE - box.top;
  if (box.height > below && box.top > window.innerHeight - box.bottom)
    menu.dataset.drop = 'up';
}

/* Wire a bar that is already in the page.

   `onAction(name)` is called for a plain action and for a menu item, because
   from the caller's side both are "the learner asked for this". `onToggle(name,
   on)` is called for a display preference, with the state it just reached. */
export function bindLearningToolbar(bar, { onAction, onToggle } = {}) {
  if (!bar) return { close: () => {}, setToggle: () => {} };
  const close = (except = null) => {
    bar.querySelectorAll('[data-menu]').forEach((menu) => {
      if (menu === except) return;
      menu.hidden = true;
      menu.removeAttribute('data-align');
      menu.removeAttribute('data-drop');
      bar
        .querySelector(`[data-menu-toggle="${menu.dataset.menu}"]`)
        ?.setAttribute('aria-expanded', 'false');
    });
  };
  bar.addEventListener('click', (event) => {
    const opener = event.target.closest('[data-menu-toggle]');
    if (opener) {
      const menu = bar.querySelector(`[data-menu="${opener.dataset.menuToggle}"]`);
      const open = menu.hidden;
      close(open ? menu : null);
      menu.hidden = !open;
      opener.setAttribute('aria-expanded', String(open));
      if (open) {
        placeMenu(menu);
        menu.querySelector('button')?.focus({ preventScroll: true });
      }
      return;
    }
    const toggle = event.target.closest('[data-toggle]');
    if (toggle) {
      const on = toggle.getAttribute('aria-pressed') !== 'true';
      toggle.setAttribute('aria-pressed', String(on));
      close(null);
      onToggle?.(toggle.dataset.toggle, on);
      return;
    }
    const action = event.target.closest('[data-action]');
    if (!action) return;
    close(null);
    onAction?.(action.dataset.action);
  });
  bar.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const open = bar.querySelector('[data-menu]:not([hidden])');
    if (!open) return;
    bar
      .querySelector(`[data-menu-toggle="${open.dataset.menu}"]`)
      ?.focus({ preventScroll: true });
    close(null);
  });
  const away = (event) => {
    if (!bar.isConnected) return;
    if (event.target.closest?.('.learning-toolbar') === bar) return;
    close(null);
  };
  document.addEventListener('click', away);
  const reposition = () => {
    const open = bar.querySelector('[data-menu]:not([hidden])');
    if (open) placeMenu(open);
  };
  window.addEventListener('resize', reposition, { passive: true });
  return {
    close: () => close(null),
    /* The caller owns the preference; the bar only shows it. */
    setToggle: (name, on) =>
      bar
        .querySelector(`[data-toggle="${name}"]`)
        ?.setAttribute('aria-pressed', String(Boolean(on))),
    setHidden: (name, hidden) => {
      const node = bar.querySelector(
        `[data-action="${name}"], [data-toggle="${name}"], [data-menu-toggle="${name}"]`,
      );
      const host = node?.closest('.learning-action-menu') || node;
      if (host) host.hidden = Boolean(hidden);
    },
    dispose: () => {
      document.removeEventListener('click', away);
      window.removeEventListener('resize', reposition);
    },
  };
}
