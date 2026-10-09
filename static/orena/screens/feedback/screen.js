/* Feedback (frame "Feedback" of the 2026-10-09 design export), reached from Profile's "Feedback"
   row. A focus route (shell/routes.js `feedback`): the header stays, the card scrolls in its own
   region.

   Send posts one review (api.feedbackSend, D-156) with the learner's learning language and interface
   language; it is disabled while it sends. On success the draft clears, the hint reads "Sent. Thank
   you!", the design's toast shows, and the new review is the first card of "Your feedback", which
   lists the learner's own reviews (api.feedbackMine). A refusal or failure is said under the button. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { pageHeader } from '../../kit/components.js';
import { toast } from '../../kit/toast.js';
import { useStyles } from '../../kit/styles.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy } from '../../copy/shell.js';
import { t } from './copy.js';
import { AREAS, STAR_COUNT, TEXT_LIMIT, ratingKey, toggleArea, clampText, canSend, history, starsText, sendBody, errorKey, prepend } from './model.js';

function whenOf(iso, ui) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat(ui, { dateStyle: 'medium' }).format(date);
}

export function historyMarkup(items, ui = languages().ui) {
  return html`${history(items).map((item) => html`<div class="s-fb-item">
    <div class="s-fb-item__row"><span class="s-fb-item__stars" aria-label="${t('starAria', { n: item.stars })}">${starsText(item.stars)}</span><span class="s-fb-item__when">${whenOf(item.createdAt, ui)}</span></div>
    ${item.text ? html`<div class="s-fb-item__text">${item.text}</div>` : ''}
    <div class="s-fb-item__tags">${item.areas.map((area) => html`<span class="s-fb-item__tag">${t(`area_${area}`)}</span>`)}<span class="s-fb-item__status">${t('statusSent')}</span></div>
  </div>`)}`;
}

export function feedbackMarkup({ stars = 0, areas = [], text = '', items = [], sending = false, hint = '', error = '' } = {}) {
  const sendable = canSend({ stars }) && !sending;
  const shownHint = hint || (stars > 0 ? '' : t('hintChoose'));
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
            <button type="button" class="o-btn o-btn--primary s-fb-send__btn" data-send ${sendable ? '' : 'disabled'}>${sending ? t('sending') : t('send')}</button>
            <span class="s-fb-send__hint" data-hint>${shownHint}</span>
          </div>
          <div class="s-fb-error" data-error role="alert">${error}</div>
        </div>
        <div class="s-fb-past">
          <div class="s-fb-past__head"><div class="s-fb-past__title">${t('yourFeedback')}</div><span class="s-fb-past__count" data-count>${t.plural('reviewsCount', history(items).length)}</span></div>
          <div class="s-fb-past__list" data-history>${historyMarkup(items)}</div>
        </div>
      </div>
    </div>
  </div>`;
}

export default async function feedback(element, ctx) {
  await useStyles('screens/feedback/feedback.css');
  if (!ctx.isCurrent()) return undefined;
  const draft = { stars: 0, hover: 0, areas: [], text: '', items: [], sending: false, hint: '' };

  mount(element, feedbackMarkup(draft));
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());

  const label = element.querySelector('[data-rate-label]');
  const send = element.querySelector('[data-send]');
  const hint = element.querySelector('[data-hint]');
  const error = element.querySelector('[data-error]');
  const list = element.querySelector('[data-history]');
  const count = element.querySelector('[data-count]');
  const paintSend = () => {
    send.disabled = !canSend({ stars: draft.stars }) || draft.sending;
    send.textContent = draft.sending ? t('sending') : t('send');
    hint.textContent = draft.hint || (draft.stars > 0 ? '' : t('hintChoose'));
  };
  const paintHistory = () => {
    mount(list, historyMarkup(draft.items));
    count.textContent = t.plural('reviewsCount', history(draft.items).length);
  };
  const paintStars = () => {
    const shown = draft.hover || draft.stars;
    element.querySelectorAll('[data-star]').forEach((button) => button.setAttribute('aria-pressed', String(Number(button.dataset.star) <= shown)));
    label.textContent = t(ratingKey(shown));
  };
  const paintDraft = () => {
    paintStars();
    element.querySelectorAll('[data-area]').forEach((button) => button.setAttribute('aria-pressed', String(draft.areas.includes(button.dataset.area))));
    element.querySelector('[data-text]').value = draft.text;
  };
  element.querySelector('[data-stars]').addEventListener('mouseleave', () => { draft.hover = 0; paintStars(); });
  element.querySelectorAll('[data-star]').forEach((button) => {
    button.addEventListener('mouseenter', () => { draft.hover = Number(button.dataset.star); paintStars(); });
    button.addEventListener('click', () => {
      draft.stars = Number(button.dataset.star);
      draft.hint = '';
      error.textContent = '';
      paintStars();
      paintSend();
    });
  });
  element.querySelectorAll('[data-area]').forEach((button) => {
    button.addEventListener('click', () => {
      draft.areas = toggleArea(draft.areas, button.dataset.area);
      button.setAttribute('aria-pressed', String(draft.areas.includes(button.dataset.area)));
    });
  });
  element.querySelector('[data-text]').addEventListener('input', (event) => { draft.text = clampText(event.target.value); });

  send.addEventListener('click', async () => {
    if (draft.sending || !canSend({ stars: draft.stars })) return;
    draft.sending = true;
    draft.hint = '';
    error.textContent = '';
    paintSend();
    try {
      const { review } = await api.feedbackSend(sendBody(draft, { language: ctx.context.language, interfaceLanguage: languages().ui }));
      if (!ctx.isCurrent()) return;
      draft.items = prepend(draft.items, review);
      Object.assign(draft, { stars: 0, hover: 0, areas: [], text: '', hint: t('hintSent') });
      paintDraft();
      paintHistory();
      toast(t('thanks'));
    } catch (failure) {
      if (!ctx.isCurrent()) return;
      error.textContent = t(errorKey(failure?.status));
    } finally {
      draft.sending = false;
      if (ctx.isCurrent()) paintSend();
    }
  });

  try {
    const mine = await api.feedbackMine();
    if (ctx.isCurrent() && Array.isArray(mine?.items)) {
      draft.items = mine.items;
      paintHistory();
    }
  } catch {
    /* The history is the learner's own record; if it cannot be read the form still works. */
  }
  return undefined;
}

export const __internal = { feedbackMarkup, historyMarkup };
