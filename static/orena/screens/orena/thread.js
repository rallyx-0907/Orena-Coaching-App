/* One message of an Orena conversation, drawn for Orena Home (frame 11, `homeMsgs`) or the
   Contextual panel (frame 55, `orenaMsgs`) - the same segments, action cards, sources and error
   rendering, with the two frames' own bubble shapes (Home draws Orena's reply as plain text beside
   its 28px mark, the panel as a bare bubble with no mark). `surface` is 'home' or 'panel' and
   selects the class prefix; `supported` is dispatcher.supported() at paint time. */
import { html } from '../../kit/html.js';
import { intelChip } from '../../kit/brand.js';
import { langAttr } from '../../kit/lang.js';
import { fromContractLang } from '../../agent/contract.js';
import { t } from './copy.js';
import { actionCardMarkup, evidenceMarkup, hasCard } from './cards.js';
import { offerableActions, errorText } from './model.js';
import { seePlansLabel } from '../plan/quota-notice.js';
import { richSegments } from '../../kit/rich-text.js';

/* A reply's text is Markdown (LEX-006): its meaning is rendered - headings, bold, lists, quotes, web links -
   never its syntax, and an app command written as a link is dropped (the action is its own card). The reply's
   segments are rendered as ONE document (kit/rich-text.js richSegments), so a line the server split by
   language stays one line; each run in another language keeps its own `lang`, and a reference segment (a word
   to hear) its reference class. `streaming` holds back a marker not yet closed. */
function segmentsMarkup(prefix, segments, streaming) {
  const langOf = (segment) => langAttr(fromContractLang(segment.lang));
  const { lang, markup } = richSegments(segments, { streaming, langOf, refClass: `${prefix}__ref` });
  return html`<div lang="${lang ? langAttr(fromContractLang(lang)) : ''}">${markup}</div>`;
}

function errorMarkup(prefix, error) {
  // The plan's limit (D-163): the retry button's place and look carry the way to the plans instead; nothing new is drawn.
  const action = error.quota
    ? html`<button type="button" class="${prefix}__retry" data-plans="${String(error.quota.upgrade || '#/plan/pricing')}">${seePlansLabel()}</button>`
    : error.fallback === 'retry' ? html`<button type="button" class="${prefix}__retry" data-retry>${t('errorRetry')}</button>` : '';
  return html`<div class="${prefix}__error"><span>${errorText(error, t('transportError'))}</span>${action}</div>`;
}

export function messageMarkup(message, { surface, ranActions, supported }) {
  const prefix = `s-orena-${surface}`;
  if (message.role === 'learner') {
    return html`<div class="${prefix}__row ${prefix}__row--learner"><div class="${prefix}__msg"><div class="${prefix}__bubble ${prefix}__bubble--learner">${message.text}</div></div></div>`;
  }
  const segments = message.segments || [];
  const offered = offerableActions(message.actions, supported);
  const cards = offered.filter((action) => hasCard(action.display));
  const bare = offered.filter((action) => !cards.includes(action));
  const withMark = surface === 'home';
  // An error-only reply has no bubble: its message stands where the reply would.
  const errorInline = message.error && !segments.length;
  return html`<div class="${prefix}__row ${prefix}__row--orena">
    <div class="${prefix}__msg">
      ${withMark ? intelChip({ size: 28, mark: 22 }) : ''}
      ${segments.length ? html`<div class="${prefix}__bubble ${prefix}__bubble--orena">${segmentsMarkup(prefix, segments, !message.done)}</div>` : ''}
      ${errorInline ? errorMarkup(prefix, message.error) : ''}
    </div>
    ${message.evidence?.length ? html`<div class="${prefix}__sources">${message.evidence.map((evidence) => evidenceMarkup(evidence))}</div>` : ''}
    ${cards.length ? html`<div class="${prefix}__cards">${cards.map((action) => actionCardMarkup(action, { done: ranActions.has(action.id) }))}</div>` : ''}
    ${bare.length ? html`<div class="${prefix}__buttons">${bare.map((action) => actionCardMarkup(action, { done: ranActions.has(action.id) }))}</div>` : ''}
    ${message.error && !errorInline ? errorMarkup(prefix, message.error) : ''}
  </div>`;
}

/* Where the conversation sits after a paint (LEX-042): new messages come into view, but a long answer is read
   from its beginning - once the latest Orena reply is taller than the region, its top stays at the top instead of
   the region following its tail as it grows. A learner who has scrolled up keeps their place. */
export function placeThread(region, prefix) {
  if (!region) return;
  const rows = region.querySelectorAll(`.${prefix}__row`);
  const last = rows[rows.length - 1];
  const wasAtEnd = region.dataset.placed !== '1' || region.scrollHeight - region.scrollTop - region.clientHeight < 80 || region.dataset.follow === '1';
  if (last?.classList.contains(`${prefix}__row--orena`) && last.offsetHeight > region.clientHeight - 24) {
    const top = last.offsetTop - region.offsetTop - 8;
    if (wasAtEnd || region.scrollTop > top) region.scrollTop = Math.max(0, top);
    region.dataset.follow = '0';
  } else if (wasAtEnd) {
    region.scrollTop = region.scrollHeight;
    region.dataset.follow = '1';
  }
  region.dataset.placed = '1';
}
