/* The Platform Admin's building blocks, drawn as Orena-Admin.dc.html draws them (its one page frame:
   header, banners, tabs, then a grid of blocks - rows, key/value, metrics, form, state). Markup only:
   every function returns escaped html`` and takes its words already translated, so a later area
   (Reading pipeline, Imports, Content) builds its pages from the same pieces (D-101 E).

   Classes are `a-*`, styled by admin.css from the semantic tokens; nothing here writes a colour.
   Interaction is by `data-a` (a button) and `data-go` (a row that opens another place): the screen
   binds one listener to its container. */
import { html, raw, esc } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';

/* A tone is one of ok / warn / err / info / mute / fut (model.js TONES). */
export function pill({ label, tone = 'mute' }) {
  return html`<span class="a-pill" data-tone="${tone}">${label}</span>`;
}

/* A button. `kind`: primary, danger, future or none (the plain outlined one); `size`: md 40, sm 36,
   xs 32. `a` names what it does (data-a) and `data` adds data-* pairs. */
export function button({ label, kind = '', size = 'md', a = '', data = {}, disabled = false, tip = '', type = 'button' }) {
  const extra = Object.entries(data).map(([key, value]) => ` data-${key}="${esc(value)}"`).join('');
  return html`<button type="${type}" class="a-btn${kind ? ` a-btn--${kind}` : ''} a-btn--${size}"${raw(a ? ` data-a="${esc(a)}"` : '')}${raw(extra)}${raw(disabled ? ' disabled' : '')}${raw(tip ? ` title="${esc(tip)}"` : '')}>${label}</button>`;
}

export function actions(list, className = 'a-actions') {
  return list && list.length ? html`<div class="${className}">${list.map(button)}</div>` : '';
}

/* The banner under the page header: a tone-soft strip with a title, a sentence and actions. */
export function banner({ tone = 'info', title, text = '', actions: list = [] }) {
  return html`<div class="a-banner" data-tone="${tone}" role="status"><div class="a-banner__text"><div class="a-banner__title">${title}</div>${text ? html`<div class="a-banner__body">${text}</div>` : ''}</div>${actions(list, 'a-banner__actions')}</div>`;
}

/* Tabs with a count, as the page frame draws them. */
export function tabs(items) {
  return html`<div class="a-tabs" role="tablist">${items.map((item) => html`<button type="button" role="tab" class="a-tab" data-a="tab" data-tab="${item.id}" aria-selected="${item.selected ? 'true' : 'false'}"><span class="a-tab__label">${item.label}${item.count == null ? '' : html`<span class="a-tab__count">${item.count}</span>`}</span><span class="a-tab__bar"></span></button>`)}</div>`;
}

/* The page header: back link, status pills, the h1, one sentence and the page's actions. */
export function pageHead({ back = null, pills = [], title, sub = '', actions: list = [] }) {
  return html`${back ? html`<button type="button" class="a-back" data-go="${back.href}">${raw(icon('chevron-left', { size: 18 }))}${back.label}</button>` : ''}
    <div class="a-head"><div class="a-head__text">${pills.length ? html`<div class="a-pills">${pills.map(pill)}</div>` : ''}<h1 class="a-h1">${title}</h1>${sub ? html`<p class="a-sub">${sub}</p>` : ''}</div>${actions(list)}</div>`;
}

/* A block of the page grid: a white card (or `flat`, no card) with an optional head. */
export function block({ title = '', sub = '', pills = [], actions: list = [], span = false, flat = false, foot = '', body }) {
  const head = title
    ? html`<div class="a-block__head"><div class="a-block__title"><div class="a-block__name"><span>${title}</span>${pills.map(pill)}</div>${sub ? html`<div class="a-block__sub">${sub}</div>` : ''}</div>${actions(list)}</div>`
    : '';
  return html`<div class="a-block${span ? ' a-block--full' : ''}${flat ? ' a-block--flat' : ''}">${head}${body}${foot ? html`<div class="a-foot">${foot}</div>` : ''}</div>`;
}

/* A list of rows. Each row: `tile` (the two letters on a tile), title, meta, detail, pills, a right
   note, actions; `go` makes the row open another place. */
export function rowList(list, empty = null) {
  if (!list.length && empty) return stateBody({ kind: 'empty', title: empty.title, text: empty.text, compact: true });
  return html`<div class="a-rows">${list.map((row) => {
    const open = row.go ? html` data-go="${row.go}" role="link" tabindex="0"` : '';
    return html`<div class="a-row${row.go ? ' a-row--open' : ''}"${open}>
      ${row.tile ? html`<span class="a-row__tile" aria-hidden="true">${row.tile}</span>` : ''}
      <div class="a-row__body"><div class="a-row__title">${row.title}</div>${row.meta ? html`<div class="a-row__meta">${row.meta}</div>` : ''}${row.detail ? html`<div class="a-row__detail">${row.detail}</div>` : ''}</div>
      ${row.pills && row.pills.length ? html`<div class="a-pills a-pills--row">${row.pills.map(pill)}</div>` : ''}
      ${row.right ? html`<span class="a-row__right">${row.right}</span>` : ''}
      ${row.actions && row.actions.length ? html`<div class="a-actions">${row.actions.map(button)}</div>` : ''}
    </div>`;
  })}</div>`;
}

/* Key / value pairs. `mono` sets the value in the mono face. */
export function kv(items) {
  return html`<div class="a-kv">${items.map((item) => html`<div class="a-kv__item"><span class="a-kv__key">${item.key}</span><span class="a-kv__value${item.mono ? ' a-kv__value--mono' : ''}" data-tone="${item.tone || ''}">${item.value}</span></div>`)}</div>`;
}

/* Metric tiles: a label, a big value and a note. */
export function metrics(items, { columns = 2 } = {}) {
  return html`<div class="a-metrics" style="--a-cols:${columns}">${items.map((item) => html`<div class="a-metric"><div class="a-metric__label">${item.label}</div><div class="a-metric__value${String(item.value).length > 9 ? ' a-metric__value--long' : ''}" data-tone="${item.tone || ''}">${item.value}</div>${item.note ? html`<div class="a-metric__note">${item.note}</div>` : ''}</div>`)}</div>`;
}

const STATE_ICON = { empty: 'circle', unavail: 'ban', future: 'clock', error: 'circle-alert', ok: 'check' };

function stateBody({ kind = 'empty', title, text = '', actions: list = [], compact = false }) {
  return html`<div class="a-state${compact ? ' a-state--compact' : ''}" data-kind="${kind}"><span class="a-state__icon" aria-hidden="true">${raw(icon(STATE_ICON[kind] || 'circle', { size: 20 }))}</span><div class="a-state__title">${title}</div>${text ? html`<div class="a-state__text">${text}</div>` : ''}${actions(list, 'a-state__actions')}</div>`;
}

/* A state as a block of its own (loading is the skeleton; empty, unavailable, future, error, ok). */
export function stateBlock({ title = '', kind = 'empty', heading, text = '', actions: list = [], foot = '', span = false }) {
  return block({ title, span, foot, body: stateBody({ kind, title: heading, text, actions: list }) });
}

/* Form fields. A field is { id, label, tag, hint, hintTone, span, kind, ... } by kind: text
   (value, type, placeholder, invalid), seg (options [{id, label, sub, on, disabled, tip}]), toggle
   (on, label). */
function field(item) {
  const label = html`<div class="a-field__label"><span>${item.label}</span>${item.tag ? html`<span class="a-field__tag">${item.tag}</span>` : ''}</div>`;
  let control;
  if (item.kind === 'seg') {
    control = html`<div class="a-seg" role="group" aria-label="${item.label}">${item.options.map((option) => html`<button type="button" class="a-seg__option" data-a="pick" data-field="${item.id}" data-value="${option.id}" aria-pressed="${option.on ? 'true' : 'false'}"${raw(option.disabled ? ' disabled' : '')}${option.tip ? html` title="${option.tip}"` : ''}><span>${option.label}</span>${option.sub ? html`<span class="a-seg__sub">${option.sub}</span>` : ''}</button>`)}</div>`;
  } else if (item.kind === 'select') {
    control = html`<select class="a-input" name="${item.id}" data-a-input="${item.id}" aria-label="${item.label}"${raw(item.disabled ? ' disabled' : '')}>${item.options.map((option) => html`<option value="${option.id}"${raw(option.on ? ' selected' : '')}>${option.label}</option>`)}</select>`;
  } else if (item.kind === 'area') {
    control = html`<textarea class="a-input a-input--area" name="${item.id}" rows="${item.rows || 6}" placeholder="${item.placeholder || ''}" spellcheck="false" aria-label="${item.label}" data-a-input="${item.id}"${raw(item.readOnly ? ' readonly' : '')}>${item.value || ''}</textarea>`;
  } else if (item.kind === 'file') {
    control = html`<label class="a-file"><span class="a-file__icon" aria-hidden="true">${raw(icon('upload', { size: 18 }))}</span><span class="a-file__text"><span class="a-file__label">${item.fileLabel}</span><span class="a-file__accept">${item.accept}</span></span><input type="file" class="a-file__input" data-a-file="${item.id}" accept="${item.acceptAttr || ''}"${raw(item.multiple ? ' multiple' : '')}></label>`;
  } else if (item.kind === 'toggle') {
    control = html`<button type="button" class="a-toggle" role="switch" aria-checked="${item.on ? 'true' : 'false'}" data-a="toggle" data-field="${item.id}"${raw(item.disabledToggle ? ' disabled' : '')}><span class="a-toggle__track"><span class="a-toggle__knob"></span></span><span class="a-toggle__label">${item.toggleLabel}</span></button>`;
  } else {
    control = html`<input class="a-input${item.invalid ? ' a-input--invalid' : ''}" name="${item.id}" type="${item.type || 'text'}" value="${item.value || ''}" placeholder="${item.placeholder || ''}" autocomplete="${item.type === 'password' ? 'new-password' : 'off'}" spellcheck="false" aria-label="${item.label}" data-a-input="${item.id}"${raw(item.readOnly ? ' readonly' : '')}>`;
  }
  return html`<div class="a-field${item.span ? ' a-field--full' : ''}">${label}${control}${item.hint ? html`<span class="a-field__hint" data-tone="${item.hintTone || ''}">${item.hint}</span>` : ''}</div>`;
}

/* A form block: its fields, an inline error and the buttons. */
export function formBlock({ title = '', sub = '', fields, error = '', status = '', actions: list = [], span = false, justify = 'end' }) {
  return block({
    title,
    sub,
    span,
    body: html`<div class="a-form">${fields.map(field)}</div>${error ? html`<div class="a-error" role="alert">${error}</div>` : ''}${status ? html`<div class="a-status" role="status">${status}</div>` : ''}<div class="a-actions a-actions--${justify}">${list.map(button)}</div>`,
  });
}

/* The loading skeleton the page frame draws: four cards and a word. */
export function skeleton(label) {
  return html`<div class="a-skeleton" role="status" aria-live="polite">${[0, 1, 2, 3].map(() => html`<div class="a-skeleton__card"><span class="a-skeleton__bone a-skeleton__bone--short"></span><span class="a-skeleton__bone"></span></div>`)}</div><div class="a-loading">${label}</div>`;
}

/* The confirm dialog: title, sentence, an optional list of consequences, a word to type or a reason
   to give (a rejection keeps its reason). */
export function dialog({ title, body, list = [], typeWord = '', typeLabel = '', typed = '', reason = null, cancel, confirm, danger = true, ready = true }) {
  return html`<div class="a-scrim" data-a="dialog-cancel"></div>
    <div class="a-dialog" role="dialog" aria-modal="true" aria-label="${title}">
      <div class="a-dialog__title">${title}</div>
      <div class="a-dialog__body">${body}</div>
      ${list.length ? html`<div class="a-dialog__list${danger ? '' : ' a-dialog__list--warn'}">${list.map((line) => html`<div class="a-dialog__item"><span aria-hidden="true">•</span><span>${line}</span></div>`)}</div>` : ''}
      ${typeWord ? html`<label class="a-dialog__type"><span>${typeLabel}</span><input class="a-input" name="confirm-word" value="${typed}" autocomplete="off" spellcheck="false" data-a-typed></label>` : ''}
      ${reason ? html`<label class="a-dialog__type"><span>${reason.label}</span><textarea class="a-input a-input--area" name="confirm-reason" rows="2" placeholder="${reason.placeholder || ''}" data-a-reason>${reason.value || ''}</textarea></label>` : ''}
      <div class="a-actions a-actions--end"><button type="button" class="a-btn a-btn--md" data-a="dialog-cancel">${cancel}</button><button type="button" class="a-btn a-btn--md ${danger ? 'a-btn--danger' : 'a-btn--primary'}" data-a="dialog-confirm"${raw(ready ? '' : ' disabled')}>${confirm}</button></div>
    </div>`;
}

/* ---- pieces the Reading, Imports and Content pages draw ---------------------------------------- */

/* A row of filter pills with a label (the page frame's `filters`). */
export function chipRow({ label = '', options, a = 'filter', field = '' }) {
  return html`<div class="a-chiprow">${label ? html`<span class="a-chiprow__label">${label}</span>` : ''}${options.map((option) => html`<button type="button" class="a-chipbtn" data-a="${a}" data-field="${field}" data-value="${option.id}" aria-pressed="${option.on ? 'true' : 'false'}">${option.label}</button>`)}</div>`;
}

/* The search field above a list. */
export function searchField({ id = 'q', value = '', placeholder }) {
  return html`<input class="a-input a-search" type="search" name="${id}" value="${value}" placeholder="${placeholder}" aria-label="${placeholder}" autocomplete="off" data-a-input="${id}">`;
}

/* Clickable metric tiles (Reading overview): a label, a big value in a tone, a note. */
export function tiles(items) {
  return html`<div class="a-tiles">${items.map((item) => html`<button type="button" class="a-tile"${item.go ? html` data-go="${item.go}"` : ''}${raw(item.go ? '' : ' disabled')}><span class="a-tile__label">${item.label}</span><span class="a-tile__value" data-tone="${item.tone || ''}">${item.value}</span><span class="a-tile__note">${item.note || ''}</span></button>`)}</div>`;
}

/* A vertical run of stages: done, the one in progress, the one that failed, the ones to come. */
export function stepsBlock({ title = '', span = false, items }) {
  return block({
    title,
    span,
    body: html`<ol class="a-steps">${items.map((item, index) => html`<li class="a-step" data-state="${item.state}"><span class="a-step__dot" aria-hidden="true">${item.state === 'done' ? raw(icon('check', { size: 13, stroke: 3 })) : item.state === 'fail' ? raw(icon('x', { size: 13, stroke: 3 })) : item.state === 'active' ? '•' : ''}</span><span class="a-step__text"><span class="a-step__label">${item.label}</span>${item.note ? html`<span class="a-step__note">${item.note}</span>` : ''}</span></li>`)}</ol>`,
  });
}

/* Text set in a well: a learner preview, a technical detail. */
export function textBlock({ title = '', sub = '', actions: list = [], span = false, text, mono = false, maxHeight = '' }) {
  return block({ title, sub, actions: list, span, body: html`<div class="a-text${mono ? ' a-text--mono' : ''}"${maxHeight ? html` style="max-height:${maxHeight}"` : ''}>${text}</div>` });
}

/* The dashed card the design draws for what it marks Future: a name, a Future pill, one sentence. */
export function futureCard({ title, text, pill }) {
  return html`<div class="a-future"><span class="a-future__icon" aria-hidden="true">${raw(icon('clock', { size: 20 }))}</span><div class="a-future__body"><div class="a-future__head"><span class="a-future__title">${title}</span><span class="a-pill" data-tone="fut">${pill}</span></div><div class="a-future__text">${text}</div></div></div>`;
}

/* The overlay panel the design opens from a row (a learner preview): scrim, a side panel with a
   head, a scrolling body and a foot of actions. */
export function panelOverlay({ kicker, title, meta = '', body, actions: list = [], closeLabel }) {
  return html`<div class="a-scrim a-scrim--panel" data-a="panel-close"></div><aside class="a-panel" role="dialog" aria-modal="true" aria-label="${title}"><div class="a-panel__head"><div><div class="a-panel__kicker">${kicker}</div><div class="a-panel__title">${title}</div>${meta ? html`<div class="a-panel__meta">${meta}</div>` : ''}</div><button type="button" class="a-panel__close" data-a="panel-close" aria-label="${closeLabel}">${raw(icon('x', { size: 16 }))}</button></div><div class="a-panel__body">${body}</div>${list.length ? html`<div class="a-panel__foot">${list.map(button)}</div>` : ''}</aside>`;
}
