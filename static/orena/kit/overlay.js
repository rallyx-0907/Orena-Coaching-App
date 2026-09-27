/* Sheets of the new learner UI (Design Contract rule 33): one layer over the whole frame, a
   panel docked at the right on a desk (440px) and a bottom sheet on a phone, both from the same
   --sheet-* variables the design sets per device. One sheet is open at a time, as in the design
   (opening one closes the other; navigating closes all). Focus moves into the sheet and returns
   to what opened it; Escape and the scrim close it (accessibility behaviour, not a new visual). */
import { html, mount, raw } from './html.js';
import { icon } from './icons.js';

let layer = null;
let open = null;

export function setOverlayLayer(element) {
  layer = element;
}

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])';

function trap(event, sheet) {
  if (event.key !== 'Tab') return;
  const items = [...sheet.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null);
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

/* Open a sheet. `render(body, api)` fills it and may return a cleanup. `label` names the dialog
   for assistive technology. `scrim: false` for the overlays the design gives their own backdrop. */
export function openSheet({ label = '', className = '', full = false, scrim = true, render, onClose } = {}) {
  closeSheet();
  if (!layer) throw new Error('Overlay layer not mounted');
  const opener = document.activeElement;
  const backdrop = scrim ? document.createElement('div') : null;
  if (backdrop) {
    backdrop.className = 'o-scrim';
    backdrop.addEventListener('click', () => closeSheet());
    layer.append(backdrop);
  }
  const sheet = document.createElement('div');
  sheet.className = `o-sheet${full ? ' o-sheet--full' : ''}${className ? ` ${className}` : ''}`;
  sheet.setAttribute('role', 'dialog');
  sheet.setAttribute('aria-modal', 'true');
  if (label) sheet.setAttribute('aria-label', label);
  sheet.tabIndex = -1;
  layer.append(sheet);
  const onKey = (event) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      closeSheet();
    } else trap(event, sheet);
  };
  sheet.addEventListener('keydown', onKey);
  const handle = {
    element: sheet,
    close: () => {
      if (open === handle) closeSheet();
    },
  };
  let cleanup = null;
  open = {
    handle,
    dispose() {
      try {
        cleanup?.();
      } finally {
        sheet.remove();
        backdrop?.remove();
        onClose?.();
        if (opener?.isConnected) opener.focus({ preventScroll: true });
      }
    },
  };
  cleanup = render?.(sheet, handle) || null;
  const first = sheet.querySelector('[autofocus]') || sheet;
  first.focus({ preventScroll: true });
  return handle;
}

export function closeSheet() {
  if (!open) return;
  const current = open;
  open = null;
  current.dispose();
}

export function sheetIsOpen() {
  return Boolean(open);
}

/* The header the design draws on its sheets: a title and a round close button. */
export function sheetHead({ title, closeLabel, flush = false }) {
  return html`<div class="o-sheet__head${flush ? ' o-sheet__head--flush' : ''}"><div class="o-sheet__title">${title}</div><button type="button" class="o-iconbtn o-iconbtn--close" data-sheet-close aria-label="${closeLabel}">${raw(icon('x', { size: 17 }))}</button></div>`;
}

/* Wire a sheet's close buttons after its markup is mounted. */
export function bindClose(sheet, handle) {
  for (const button of sheet.querySelectorAll('[data-sheet-close]')) button.addEventListener('click', () => handle.close());
}

export function fillSheet(sheet, handle, markup) {
  mount(sheet, markup);
  bindClose(sheet, handle);
}
