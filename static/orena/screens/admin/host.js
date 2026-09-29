/* The Admin page host: what every area's wiring needs from a browser and none of them should write
   twice - one paint that keeps the operator's focus, one click listener over `data-a` controls, the
   confirm dialog (with a reason or a typed word), the learner-preview panel, the header filter and a
   clean way out. An area registers its page builder and its handlers; the host owns the DOM.

   Handlers are keyed by the control's `data-a`; each receives the control and its dataset. A row that
   opens another place also holds buttons: the button acts, the row does not (stopPropagation). */
import { mount } from '../../kit/html.js';
import { toast } from '../../kit/toast.js';
import { t } from './copy.js';
import { dialog, panelOverlay } from './blocks.js';

function focusSelector(element) {
  if (!element || !element.dataset) return '';
  const { aInput, aFile, a, field, value, id, side, tab } = element.dataset;
  if (aInput) return `[data-a-input="${CSS.escape(aInput)}"]`;
  if (aFile) return `[data-a-file="${CSS.escape(aFile)}"]`;
  if (!a) return '';
  return `[data-a="${CSS.escape(a)}"]${field ? `[data-field="${CSS.escape(field)}"]` : ''}${value !== undefined ? `[data-value="${CSS.escape(value)}"]` : ''}${id ? `[data-id="${CSS.escape(id)}"]` : ''}${side ? `[data-side="${CSS.escape(side)}"]` : ''}${tab ? `[data-tab="${CSS.escape(tab)}"]` : ''}`;
}

export function createHost(shell, ctx) {
  let alive = true;
  let builder = () => ({ title: '', markup: '' });
  let filterEnabled = false;
  let ask = null;
  const handlers = new Map();
  const listeners = { input: () => {}, file: () => {}, filter: () => {} };

  function paint() {
    if (!alive) return;
    const page = builder();
    shell.setTitle(page.title || '');
    if (page.crumb) ctx.setCrumb(page.crumb);
    shell.setFilter({ enabled: filterEnabled, value: page.filterValue ?? '' });
    const active = document.activeElement;
    const selector = active && shell.page.contains(active) ? focusSelector(active) : '';
    const range = selector && typeof active.selectionStart === 'number' ? [active.selectionStart, active.selectionEnd] : null;
    const scroll = shell.main.scrollTop;
    mount(shell.page, page.markup);
    if (page.keepScroll) shell.main.scrollTop = scroll;
    if (!selector) return;
    const again = shell.page.querySelector(selector);
    if (!again) return;
    again.focus({ preventScroll: true });
    if (range && typeof again.setSelectionRange === 'function') again.setSelectionRange(range[0], range[1]);
  }

  function onClick(event) {
    const control = event.target.closest?.('[data-a]');
    if (!control || !shell.page.contains(control)) return;
    event.stopPropagation();
    if (control.tagName === 'INPUT' || control.tagName === 'TEXTAREA') return;
    event.preventDefault();
    if (control.disabled) return;
    const handler = handlers.get(control.dataset.a);
    if (handler) handler(control, control.dataset);
  }

  function onInput(event) {
    const input = event.target.closest?.('[data-a-input]');
    if (input) listeners.input(input.dataset.aInput, input.value, input);
  }

  function onChange(event) {
    const input = event.target.closest?.('[data-a-file]');
    if (input) listeners.file(input.dataset.aFile, [...(input.files || [])]);
    const select = event.target.closest?.('select[data-a-input]');
    if (select) listeners.input(select.dataset.aInput, select.value, select);
  }

  function onFilter() {
    listeners.filter(shell.filter.value);
  }

  /* ---- the dialog: resolves { confirmed, reason } ---- */
  function paintDialog(config, state) {
    if (!config) {
      mount(shell.layer.querySelector('[data-part="dialog"]') || shell.layer, '');
      return;
    }
    const ready = (!config.typeWord || state.typed.trim() === config.typeWord) && (!config.reason?.required || state.reason.trim().length > 0);
    mount(dialogHost(), dialog({ ...config, typed: state.typed, reason: config.reason ? { ...config.reason, value: state.reason } : null, ready }));
    dialogHost().querySelector('[data-a-typed], [data-a-reason]')?.focus({ preventScroll: true });
  }

  function dialogHost() {
    let host = shell.layer.querySelector('[data-part="dialog"]');
    if (!host) {
      host = document.createElement('div');
      host.dataset.part = 'dialog';
      shell.layer.append(host);
    }
    return host;
  }

  function confirm(config) {
    closeAsk(false);
    return new Promise((resolve) => {
      const state = { typed: '', reason: '' };
      ask = { config, state, resolve };
      paintDialog(config, state);
    });
  }

  function closeAsk(confirmed) {
    if (!ask) return;
    const { resolve, state } = ask;
    ask = null;
    mount(dialogHost(), '');
    resolve({ confirmed, reason: state.reason.trim() });
  }

  function onLayerClick(event) {
    const control = event.target.closest?.('[data-a]');
    if (!control) return;
    const which = control.dataset.a;
    if (which === 'dialog-cancel') closeAsk(false);
    else if (which === 'dialog-confirm' && !control.disabled) closeAsk(true);
    else if (which === 'panel-close') closePanel();
    else {
      const handler = handlers.get(which);
      if (handler) handler(control, control.dataset);
    }
  }

  function onLayerInput(event) {
    if (!ask) return;
    const typed = event.target.closest?.('[data-a-typed]');
    const reason = event.target.closest?.('[data-a-reason]');
    if (!typed && !reason) return;
    if (typed) ask.state.typed = typed.value;
    if (reason) ask.state.reason = reason.value;
    const { config, state } = ask;
    const ready = (!config.typeWord || state.typed.trim() === config.typeWord) && (!config.reason?.required || state.reason.trim().length > 0);
    const button = dialogHost().querySelector('[data-a="dialog-confirm"]');
    if (button) button.disabled = !ready;
  }

  /* ---- the panel: a learner preview over the page ---- */
  function panelHost() {
    let host = shell.layer.querySelector('[data-part="panel"]');
    if (!host) {
      host = document.createElement('div');
      host.dataset.part = 'panel';
      shell.layer.append(host);
    }
    return host;
  }

  function showPanel(config) {
    mount(panelHost(), panelOverlay({ ...config, closeLabel: t('close') }));
    panelHost().querySelector('.a-panel__close')?.focus({ preventScroll: true });
  }

  function closePanel() {
    mount(panelHost(), '');
  }

  function onKey(event) {
    if (event.key !== 'Escape') return;
    if (ask) closeAsk(false);
    else if (panelHost().innerHTML) closePanel();
  }

  shell.page.addEventListener('click', onClick);
  shell.page.addEventListener('input', onInput);
  shell.page.addEventListener('change', onChange);
  shell.layer.addEventListener('click', onLayerClick);
  shell.layer.addEventListener('input', onLayerInput);
  shell.filter.addEventListener('input', onFilter);
  document.addEventListener('keydown', onKey);

  return {
    paint,
    alive: () => alive,
    setBuilder(fn, { filter = false } = {}) {
      builder = fn;
      filterEnabled = filter;
    },
    on(name, fn) {
      handlers.set(name, fn);
    },
    onInput(fn) {
      listeners.input = fn;
    },
    onFile(fn) {
      listeners.file = fn;
    },
    onFilter(fn) {
      listeners.filter = fn;
    },
    confirm,
    showPanel,
    closePanel,
    toast(text) {
      toast(text);
    },
    cleanup() {
      alive = false;
      closeAsk(false);
      shell.page.removeEventListener('click', onClick);
      shell.page.removeEventListener('input', onInput);
      shell.page.removeEventListener('change', onChange);
      shell.layer.removeEventListener('click', onLayerClick);
      shell.layer.removeEventListener('input', onLayerInput);
      shell.filter.removeEventListener('input', onFilter);
      document.removeEventListener('keydown', onKey);
    },
  };
}
