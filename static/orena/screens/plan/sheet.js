/* Billing sheet (frame "Billing Sheet" of the 2026-10-09 design export), opened by a plan's button on
   Plans. The design's sheet has three kinds (change plan, cancel, update card) and a processing and
   a done step; only the change-plan summary is reachable here, and its confirm is inert: payments
   are a human gate and `billing_ready` is false, so there is no call, no processing step and no
   success state (UI_BACKEND_GAPS.md "New export frames"). Price is the catalogue's for the chosen cycle
   (D-153); Due today reads "—" (nothing can be charged), Starts and Payment are not drawn. */
import { openSheet, fillSheet, sheetHead } from '../../kit/overlay.js';
import { html } from '../../kit/html.js';
import { shellCopy, planName } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { t } from './copy.js';
import { changeKind, priceView } from './model.js';

function sheetPrice(target, cycle) {
  const view = priceView(target, cycle, languages().ui);
  if (view.free) return t('priceFree');
  if (view.price === '—') return '—';
  return cycle === 'yearly' ? t('pricePerYear', { amount: view.billedAmount }) : t('pricePerMonth', { amount: view.price });
}

export function sheetMarkup({ target, current, cycle = 'monthly' }) {
  const kind = changeKind(target, current);
  const name = planName(target);
  const title = t(kind === 'upgrade' ? 'sheetUpgrade' : 'sheetSwitch', { plan: name });
  const price = sheetPrice(target, cycle);
  return html`${sheetHead({ title, closeLabel: shellCopy('close') })}
    <div class="o-sheet__body s-plan-sheet">
      <div class="s-plan-sheet__summary">
        <div class="s-plan-sheet__row"><span>${t('rowPlan')}</span><b>${name}</b></div>
        <div class="s-plan-sheet__row"><span>${t('rowPrice')}</span><b>${price}</b></div>
        <div class="s-plan-sheet__row s-plan-sheet__row--due"><span>${t('dueToday')}</span><b>${target.isFree ? t('priceFree') : '—'}</b></div>
      </div>
      <p class="s-plan-sheet__note">${t('billingNote')}</p>
    </div>
    <div class="o-sheet__foot">
      <button type="button" class="o-btn o-btn--secondary" data-sheet-close>${t('sheetBack')}</button>
      <button type="button" class="o-btn o-btn--primary" disabled>${t('sheetConfirm')}</button>
    </div>`;
}

export function openBillingSheet({ target, current, cycle = 'monthly' }) {
  return openSheet({
    label: t(changeKind(target, current) === 'upgrade' ? 'sheetUpgrade' : 'sheetSwitch', { plan: planName(target) }),
    render: (sheet, handle) => {
      fillSheet(sheet, handle, sheetMarkup({ target, current, cycle }));
      return null;
    },
  });
}
