/* Plans (frame "Pricing" of the 2026-10-09 design export), reached from Plan & usage ("See all
   plans", the plan card's button). A focus route (shell/routes.js `pricing`).

   Real data only (rule 40): the plans are GET /api/product/plans (Free, Plus and Pro with their monthly
   and yearly prices and entitlements, set in Platform Admin - D-153), the current one GET
   /api/product/commerce. The Monthly/Yearly switch and its saving are computed from those prices; the
   currency follows the interface (dong in Vietnamese, dollars otherwise, as the design does). Not drawn,
   and why: the "Most popular"/"Most capable" tags (no such measure) and the Questions list (its answers
   state billing behaviour that does not exist). The plan button opens the Billing sheet, whose confirm is
   inert while `billing_ready` is false. Recorded in docs/project/UI_BACKEND_GAPS.md ("New export frames"). */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { pageHeader } from '../../kit/components.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy, planName, planDescription } from '../../copy/shell.js';
import { t } from './copy.js';
import { pricingPlans, compareRows, changeKind, featureCopyKey, formatNumber, priceView, yearlySaving, CYCLES } from './model.js';
import { openBillingSheet } from './sheet.js';

const number = (value) => formatNumber(value, languages().ui);

function featureLine(feature) {
  const label = t(featureCopyKey(feature.key));
  return feature.limit == null ? label : t('monthlyLimit', { label, n: number(feature.limit) });
}

function ctaMarkup(plan, current) {
  const kind = changeKind(plan, current);
  if (kind === 'current') return html`<button type="button" class="o-btn o-btn--secondary s-pricing-card__cta" disabled>${t('ctaCurrent')}</button>`;
  const label = t(kind === 'upgrade' ? 'ctaUpgrade' : 'ctaSwitch', { plan: planName(plan) });
  return html`<button type="button" class="${cls('o-btn s-pricing-card__cta', kind === 'upgrade' ? 'o-btn--primary' : 'o-btn--secondary')}" data-choose="${plan.id}">${label}</button>`;
}

function planCard(plan, current, cycle) {
  const price = priceView(plan, cycle, languages().ui);
  return html`<section class="s-plan-card s-pricing-card">
    <div class="s-pricing-card__head"><span class="s-pricing-card__name">${planName(plan)}</span>${plan.isCurrent ? html`<span class="s-plan-pill s-plan-pill--accent">${t('tagCurrent')}</span>` : ''}</div>
    <div class="s-pricing-card__tagline">${planDescription(plan)}</div>
    <div class="s-pricing-card__pricerow"><span class="s-pricing-card__price">${price.free ? t('priceFree') : price.price}</span>${price.free || price.price === '—' ? '' : html`<span class="s-pricing-card__per">${t('perMonth')}</span>`}</div>
    <div class="s-pricing-card__billed">${price.billedKey ? t(price.billedKey, { amount: price.billedAmount }) : ''}</div>
    ${ctaMarkup(plan, current)}
    <div class="s-pricing-card__rule"></div>
    <div class="s-pricing-card__feats">${plan.features.map((feature) => html`<div class="s-pricing-card__feat"><span class="s-pricing-card__tick">${raw(icon('check', { size: 17, stroke: 2.4 }))}</span><span>${featureLine(feature)}</span></div>`)}</div>
  </section>`;
}

function cellMarkup(cell) {
  if (cell.kind === 'limit') return html`<span class="s-pricing-cell">${number(cell.value)}</span>`;
  if (cell.kind === 'yes') return html`<span class="s-pricing-cell" role="img" aria-label="${t('featureIncluded')}">${raw(icon('check', { size: 17, stroke: 2.4 }))}</span>`;
  return html`<span class="s-pricing-cell s-pricing-cell--none" role="img" aria-label="${t('featureNotIncluded')}">—</span>`;
}

function cyclesMarkup(cycle, saving) {
  return html`<div class="s-pricing__cycles" role="group" aria-label="${t('billingCycle')}">${CYCLES.map((key) => html`<button type="button" class="s-pricing__cycle" aria-pressed="${key === cycle ? 'true' : 'false'}" data-cycle="${key}">${t(key === 'yearly' ? 'cycleYearly' : 'cycleMonthly')}${key === 'yearly' && saving > 0 ? html`<span class="s-pricing__save">−${saving}%</span>` : ''}</button>`)}</div>`;
}

export function pricingMarkup({ plans, commerce, cycle = 'monthly' }) {
  const list = pricingPlans({ plans, commerce });
  const current = list.find((plan) => plan.isCurrent) || null;
  const rows = compareRows(list);
  return html`<div class="s-plan s-pricing">
    ${pageHeader({ back: { label: shellCopy('back'), dataset: { back: '1' } }, title: t('plansTitle') })}
    <div class="s-plan__scroll" data-scroll-region>
      <div class="s-pricing__hero"><h2 class="s-pricing__headline">${t('pricingHero')}</h2><p class="s-pricing__sub">${t('pricingSub')}</p>${cyclesMarkup(cycle, yearlySaving(list, languages().ui))}</div>
      <div class="s-pricing__plans">${list.map((plan) => planCard(plan, current, cycle))}</div>
      ${rows.length ? html`<section class="s-plan-card s-pricing-compare" style="--cols:${list.length}">
        <h2 class="s-plan-card__title">${t('comparePlans')}</h2>
        <div class="s-pricing-compare__row s-pricing-compare__row--head"><span></span>${list.map((plan) => html`<span class="${cls('s-pricing-compare__plan', plan.isCurrent && 's-pricing-compare__plan--current')}">${planName(plan)}</span>`)}</div>
        ${rows.map((row) => html`<div class="s-pricing-compare__row"><span class="s-pricing-compare__label">${t(featureCopyKey(row.key))}</span>${row.cells.map(cellMarkup)}</div>`)}
      </section>` : ''}
    </div>
  </div>`;
}

export default async function pricing(element, ctx) {
  const [plansAnswer, commerce] = await Promise.all([
    api.productPlans().catch(() => null),
    api.productCommerce().catch(() => null),
  ]);
  if (!ctx.isCurrent()) return undefined;
  const plans = plansAnswer && Array.isArray(plansAnswer.plans) ? plansAnswer.plans : null;
  if (!plans) throw new Error('plans_unavailable');

  const list = pricingPlans({ plans, commerce });
  const current = list.find((plan) => plan.isCurrent) || null;
  let cycle = 'monthly';
  const paint = () => {
    const scroll = element.querySelector('[data-scroll-region]')?.scrollTop || 0;
    mount(element, pricingMarkup({ plans, commerce, cycle }));
    const region = element.querySelector('[data-scroll-region]');
    if (region) region.scrollTop = scroll;
  };
  paint();
  element.addEventListener('click', (event) => {
    if (event.target.closest('[data-back]')) return ctx.back();
    const cycleButton = event.target.closest('[data-cycle]');
    if (cycleButton && cycleButton.dataset.cycle !== cycle) {
      cycle = cycleButton.dataset.cycle;
      paint();
      element.querySelector(`[data-cycle="${cycle}"]`)?.focus();
      return undefined;
    }
    const choose = event.target.closest('[data-choose]');
    const target = choose && list.find((plan) => plan.id === choose.dataset.choose);
    if (target) openBillingSheet({ target, current, cycle });
    return undefined;
  });
  return undefined;
}

export const __internal = { pricingMarkup, planCard, featureLine, cellMarkup, cyclesMarkup };
