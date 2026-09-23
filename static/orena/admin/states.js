/* The five states every Admin view owes, from the canonical design.

   `Orena-Admin-Control-Center.dc.html` study 01 settles these for the whole
   surface, and they are not decoration - each one answers a different question
   an operator is actually asking:

   * **Loading** - is it coming? A skeleton at the real geometry, so the page
     does not jump when the data lands. Never a sentence in the middle of the
     room.
   * **Empty** - is it broken, or is there genuinely nothing? A title, why it
     is empty, and the action that would put something in it.
   * **Error** - whose fault, and what now? What the server said, when it said
     it, the request id an operator can quote, and a retry.
   * **Unavailable** - different from empty and from broken: the feature exists
     but this deployment cannot answer. Says what would make it available.
   * **Pending / success** - an action that is running says so on its own
     button, and a finished one is confirmed where it happened, with the way
     back if the design gives one.

   The design writes its copy in Vietnamese; the console speaks English and
   Chinese, so what is carried over is the structure and the promises, with the
   words in `copy.js` like every other admin string. */
import { esc } from './format.js';

/* Skeleton shapes, in the geometry of the thing being loaded: a table draws
   rows, a panel draws lines, a grid draws cards. The design's loading frame is
   the list's own geometry greyed out, not a spinner. */
export function loadingBlock(t, { shape = 'rows', rows = 4, label = '' } = {}) {
  const piece =
    shape === 'cards'
      ? '<span class="ac-skeleton ac-skeleton--card"></span>'
      : shape === 'lines'
        ? '<span class="ac-skeleton ac-skeleton--line"></span>'
        : '<span class="ac-skeleton ac-skeleton--row"></span>';
  return `<div class="ac-loading" role="status" aria-busy="true" data-shape="${esc(shape)}"><span class="sr-only">${esc(label || t.loading)}</span>${piece.repeat(Math.max(1, rows))}</div>`;
}

export function emptyBlock(t, { title = '', note = '', action = '' } = {}) {
  return `<div class="ac-state" data-state="empty"><p class="ac-state__title">${esc(title || t.stateEmptyTitle)}</p>${
    note ? `<p class="ac-state__note">${esc(note)}</p>` : ''
  }${action ? `<div class="ac-state__actions">${action}</div>` : ''}</div>`;
}

/* An error names what happened, when, and what to quote. `reference` is the
   request id the server returned: an operator reporting a failure should not
   have to describe it in prose. */
export function errorBlock(t, { title = '', detail = '', reference = '', retry = true, link = '' } = {}) {
  const actions = [
    retry ? `<button type="button" class="ac-button" data-ac-retry>${esc(t.retry)}</button>` : '',
    link,
  ].filter(Boolean).join('');
  return `<div class="ac-state" data-state="error" role="alert"><p class="ac-state__title">${esc(title || t.stateErrorTitle)}</p>${
    detail ? `<p class="ac-state__note">${esc(detail)}</p>` : ''
  }${reference ? `<p class="ac-state__ref"><code class="ac-code">${esc(reference)}</code></p>` : ''}${
    actions ? `<div class="ac-state__actions">${actions}</div>` : ''
  }</div>`;
}

/* Not empty and not broken: the deployment cannot answer this yet. The design
   is explicit that this is its own state, because "0" and "we do not know" are
   different numbers and only one of them is a number. */
export function unavailableBlock(t, { title = '', note = '' } = {}) {
  return `<div class="ac-state" data-state="unavailable"><p class="ac-state__title">${esc(title || t.stateUnavailableTitle)}</p><p class="ac-state__note">${esc(note || t.stateUnavailableNote)}</p></div>`;
}

/* A future control is shown, disabled, and says so - the design keeps these in
   the frame rather than hiding them, so the shape of the product is visible
   before every part of it works. */
export function futureBadge(t) {
  return `<span class="ac-badge" data-kind="future">${esc(t.stateFuture)}</span>`;
}

export function gapNote(t, text) {
  return `<p class="ac-note" data-kind="gap">${esc(text || t.stateBackendGap)}</p>`;
}

/* One action, three moments: idle, running, failed. The design shows all three
   on the same button rather than moving the answer somewhere else. */
export function pending(button, t, state) {
  if (!button) return;
  if (state === 'running') {
    button.dataset.acBusy = '1';
    button.disabled = true;
    button.dataset.acIdle = button.dataset.acIdle || button.textContent;
    button.textContent = t.statePending;
    return;
  }
  button.disabled = false;
  delete button.dataset.acBusy;
  if (state === 'failed') {
    button.textContent = `${button.dataset.acIdle || ''} · ${t.stateFailedRetry}`.trim();
    button.dataset.acFailed = '1';
    return;
  }
  delete button.dataset.acFailed;
  if (button.dataset.acIdle) button.textContent = button.dataset.acIdle;
}

/* What the server actually said, in the words an operator can act on: a
   category the console knows, the sentence otherwise, and the request id when
   the envelope carried one. */
export function failureDetail(error, t) {
  const category = error?.category || error?.body?.detail?.category || '';
  const known = category ? t[`error_${category}`] : '';
  return {
    detail: known || error?.message || t.loadFailed,
    reference: error?.context?.request_id || error?.body?.detail?.context?.request_id || '',
    category,
  };
}
