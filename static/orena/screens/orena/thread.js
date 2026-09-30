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

function segmentsMarkup(prefix, segments) {
  return segments.map((segment) => html`<span lang="${langAttr(fromContractLang(segment.lang))}" class="${segment.voice_style === 'reference' ? `${prefix}__ref` : ''}">${segment.text}</span>`);
}

function errorMarkup(prefix, error) {
  return html`<div class="${prefix}__error"><span>${errorText(error, t('transportError'))}</span>${error.fallback === 'retry' ? html`<button type="button" class="${prefix}__retry" data-retry>${t('errorRetry')}</button>` : ''}</div>`;
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
      ${segments.length ? html`<div class="${prefix}__bubble ${prefix}__bubble--orena">${segmentsMarkup(prefix, segments)}</div>` : ''}
      ${errorInline ? errorMarkup(prefix, message.error) : ''}
    </div>
    ${message.evidence?.length ? html`<div class="${prefix}__sources">${message.evidence.map((evidence) => evidenceMarkup(evidence))}</div>` : ''}
    ${cards.length ? html`<div class="${prefix}__cards">${cards.map((action) => actionCardMarkup(action, { done: ranActions.has(action.id) }))}</div>` : ''}
    ${bare.length ? html`<div class="${prefix}__buttons">${bare.map((action) => actionCardMarkup(action, { done: ranActions.has(action.id) }))}</div>` : ''}
    ${message.error && !errorInline ? errorMarkup(prefix, message.error) : ''}
  </div>`;
}
