/* The frame-level states the design draws (Design Contract rule 39): the loading skeleton and the
   load error that cover the main column, the sticky banner, and the empty state. Words come from
   the caller in the learner's language; nothing here invents copy. */
import { html, raw } from './html.js';
import { icon } from './icons.js';

/* Frame "Loading": a skeleton of the room, a spinner and one status line. */
export function loadingMarkup(label) {
  return html`<div class="o-loading" role="status" aria-live="polite"><div class="o-loading__inner">
    <div class="o-loading__row"><div class="o-loading__avatar"></div><div class="o-loading__lines"><div class="o-bone o-bone--strong" style="height:12px;width:55%"></div><div class="o-bone" style="height:10px;width:32%"></div></div></div>
    <div class="o-loading__hero"></div>
    <div class="o-bone" style="height:12px;width:100%"></div><div class="o-bone" style="height:12px;width:86%"></div><div class="o-bone" style="height:12px;width:64%"></div>
    <div class="o-loading__status"><span class="o-spinner"></span><div>${label}</div></div>
  </div></div>`;
}

/* Frame "Load error": a card with the reason and Back / Retry. */
export function errorMarkup({ title, text, backLabel, retryLabel }) {
  return html`<div class="o-error" role="alert"><div class="o-error__card">
    <div class="o-error__icon">${raw(icon('circle-alert', { size: 26 }))}</div>
    <div class="o-error__title">${title}</div>
    <div class="o-error__text">${text}</div>
    <div class="o-error__actions">
      <button type="button" class="o-btn o-btn--text" data-error-back>${backLabel}</button>
      <button type="button" class="o-btn o-btn--secondary o-btn--sm" data-error-retry>${raw(icon('refresh-cw', { size: 16 }))}${retryLabel}</button>
    </div>
  </div></div>`;
}

const GLYPH = { ok: '✓', info: '✦', warn: '!', err: '!' };

/* Frame "Banner": one sticky message with an optional action and a dismiss button. */
export function bannerMarkup({ kind = 'info', title = '', text = '', actionLabel = '', dismissLabel }) {
  return html`<div class="o-banner o-banner--${kind}" role="status"><div class="o-banner__box">
    <span class="o-banner__glyph" aria-hidden="true">${GLYPH[kind] || GLYPH.info}</span>
    <div class="o-banner__text">${title ? html`<b>${title}</b> ` : ''}${text}</div>
    ${actionLabel ? html`<button type="button" class="o-banner__action" data-banner-action>${actionLabel}</button>` : ''}
    <button type="button" class="o-iconbtn o-iconbtn--ghost" style="width:32px;height:32px;border-radius:10px" data-banner-close aria-label="${dismissLabel}">${raw(icon('x', { size: 16 }))}</button>
  </div></div>`;
}

/* Discover's empty state: the placeholder art, one plain sentence, one action (rule 50). */
export function emptyMarkup({ text, actionLabel = '', iconName = 'inbox' }) {
  return html`<div class="o-empty">
    <div class="o-empty__art o-art">${raw(icon(iconName, { size: 22 }))}</div>
    <div>${text}</div>
    ${actionLabel ? html`<button type="button" class="o-btn o-btn--secondary o-btn--sm" style="margin-top:12px" data-empty-action>${actionLabel}</button>` : ''}
  </div>`;
}
