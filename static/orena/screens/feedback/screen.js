/* Feedback (frame "Feedback" of the 2026-10-09 design export), reached from Profile's "Feedback"
   row. A focus route (shell/routes.js `feedback`): the header stays, the card scrolls in its own
   region.

   No backend takes or lists feedback (model.js), so the form is the design's and works as a draft
   in memory, Send is inert with the reason beside it, and "Your feedback" shows its honest zero.
   Nothing is sent, stored or simulated. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { pageHeader } from '../../kit/components.js';
import { useStyles } from '../../kit/styles.js';
import { shellCopy } from '../../copy/shell.js';
import { t } from './copy.js';
import { AREAS, STAR_COUNT, TEXT_LIMIT, ratingKey, toggleArea, clampText, canSend, history } from './model.js';

export function feedbackMarkup({ stars = 0, areas = [], text = '' } = {}) {
  const past = history();
  const sendable = canSend({ stars });
  return html`<div class="s-fb">
    ${pageHeader({ back: { label: shellCopy('back'), dataset: { back: '1' } }, title: t('title') })}
    <div class="s-fb__scroll" data-scroll-region>
      <div class="s-fb-card">
        <div class="s-fb-form">
          <div class="s-fb-form__head"><div class="s-fb-form__title">${t('rateTitle')}</div><div class="s-fb-form__sub">${t('rateSub')}</div></div>
          <div class="s-fb-rate">
            <div class="s-fb-stars" data-stars>${Array.from({ length: STAR_COUNT }, (_, index) => html`<button type="button" class="s-fb-star" data-star="${index + 1}" aria-label="${t('starAria', { n: index + 1 })}" aria-pressed="${index < stars ? 'true' : 'false'}">${raw(icon('star', { size: 30, stroke: 1.8 }))}</button>`)}</div>
            <span class="s-fb-rate__label" data-rate-label>${t(ratingKey(stars))}</span>
          </div>
          <div class="s-fb-about">
            <div class="s-fb-about__title">${t('aboutTitle')}</div>
            <div class="s-fb-areas">${AREAS.map((area) => html`<button type="button" class="o-chip s-fb-area" data-area="${area}" aria-pressed="${areas.includes(area) ? 'true' : 'false'}">${t(`area_${area}`)}</button>`)}</div>
          </div>
          <textarea class="s-fb-text" rows="3" maxlength="${TEXT_LIMIT}" placeholder="${t('placeholder')}" aria-label="${t('placeholder')}" data-text>${text}</textarea>
          <div class="s-fb-send">
            <button type="button" class="o-btn o-btn--primary s-fb-send__btn" data-send ${sendable ? '' : 'disabled'}>${t('send')}</button>
            <span class="s-fb-send__hint">${t('sendUnavailable')}</span>
          </div>
        </div>
        <div class="s-fb-past">
          <div class="s-fb-past__head"><div class="s-fb-past__title">${t('yourFeedback')}</div><span class="s-fb-past__count">${t.plural('reviewsCount', past.length)}</span></div>
        </div>
      </div>
    </div>
  </div>`;
}

export default async function feedback(element, ctx) {
  await useStyles('screens/feedback/feedback.css');
  if (!ctx.isCurrent()) return undefined;
  const draft = { stars: 0, hover: 0, areas: [], text: '' };

  mount(element, feedbackMarkup(draft));
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());

  const label = element.querySelector('[data-rate-label]');
  const paintStars = () => {
    const shown = draft.hover || draft.stars;
    element.querySelectorAll('[data-star]').forEach((button) => button.setAttribute('aria-pressed', String(Number(button.dataset.star) <= shown)));
    label.textContent = t(ratingKey(shown));
  };
  element.querySelector('[data-stars]').addEventListener('mouseleave', () => { draft.hover = 0; paintStars(); });
  element.querySelectorAll('[data-star]').forEach((button) => {
    button.addEventListener('mouseenter', () => { draft.hover = Number(button.dataset.star); paintStars(); });
    button.addEventListener('click', () => { draft.stars = Number(button.dataset.star); paintStars(); });
  });
  element.querySelectorAll('[data-area]').forEach((button) => {
    button.addEventListener('click', () => {
      draft.areas = toggleArea(draft.areas, button.dataset.area);
      button.setAttribute('aria-pressed', String(draft.areas.includes(button.dataset.area)));
    });
  });
  element.querySelector('[data-text]').addEventListener('input', (event) => { draft.text = clampText(event.target.value); });
  return undefined;
}

export const __internal = { feedbackMarkup };
