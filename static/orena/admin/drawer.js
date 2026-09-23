/* A side panel for one record - an account, a book, a collection - opened
   over the list it came from. A modal <dialog>, so focus stays inside it and
   Escape closes it, and focus returns to the row that opened it. */
import { esc } from '../ui/html.js';

export function openDrawer({ title, body = '', label = 'Close', footer = '', onClose } = {}) {
  const opener = document.activeElement;
  const element = document.createElement('dialog');
  element.className = 'ac-drawer';
  element.setAttribute('aria-label', title);
  /* Head, body, and a footer the primary action sits in. On a phone the design
     pins that footer to the bottom of the sheet, so an operator's decision is
     always reachable without scrolling back through the evidence. */
  element.innerHTML = `<div class="ac-drawer__head"><h2>${esc(title)}</h2><button type="button" class="ac-button" data-drawer-close>${esc(label)}</button></div><div class="ac-drawer__body" data-drawer-body>${body}</div><div class="ac-drawer__foot" data-drawer-foot${footer ? '' : ' hidden'}>${footer}</div>`;
  document.body.append(element);
  const close = () => element.close();
  element.querySelector('[data-drawer-close]').addEventListener('click', close);
  // A click on the backdrop (the dialog element itself, outside its content)
  // closes it the way a pointer user expects.
  element.addEventListener('click', (event) => {
    if (event.target === element) close();
  });
  element.addEventListener(
    'close',
    () => {
      element.remove();
      onClose?.();
      if (opener?.isConnected) opener.focus();
    },
    { once: true },
  );
  element.showModal();
  return {
    element,
    body: element.querySelector('[data-drawer-body]'),
    foot: element.querySelector('[data-drawer-foot]'),
    set(html, footHtml = null) {
      element.querySelector('[data-drawer-body]').innerHTML = html;
      if (footHtml !== null) this.setFooter(footHtml);
    },
    setFooter(html) {
      const foot = element.querySelector('[data-drawer-foot]');
      if (!foot) return;
      foot.innerHTML = html;
      foot.hidden = !html;
    },
    close,
  };
}
