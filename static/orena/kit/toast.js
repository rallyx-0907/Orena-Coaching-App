/* The design's toast: one at a time, bottom-anchored above the phone bar (--toast-b), gone after
   1.8s, or 4s when it offers Undo. It confirms a result; it never celebrates (rule 50). */
import { html, mount, raw } from './html.js';
import { icon } from './icons.js';

let layer = null;
let timer = 0;
let current = null;

export function setToastLayer(element) {
  layer = element;
}

export function toast(text, { undo = null, undoLabel = 'Undo', iconName = 'check' } = {}) {
  clearTimeout(timer);
  current?.remove();
  if (!layer) return;
  const element = document.createElement('div');
  element.className = 'o-toast';
  element.setAttribute('role', 'status');
  mount(
    element,
    html`<span class="o-toast__icon">${raw(icon(iconName, { size: 14 }))}</span><span class="o-toast__text">${text}</span>${
      undo ? html`<button type="button" class="o-toast__undo">${undoLabel}</button>` : ''
    }<span class="o-toast__end"></span>`,
  );
  if (undo) {
    element.querySelector('.o-toast__undo').addEventListener('click', () => {
      clearTimeout(timer);
      element.remove();
      current = null;
      undo();
    });
  }
  layer.append(element);
  current = element;
  timer = setTimeout(() => {
    element.remove();
    if (current === element) current = null;
  }, undo ? 4000 : 1800);
}
