/* Plans (frame "Pricing" of the 2026-10-09 design export), reached from Plan & usage ("See all
   plans", the plan card's button). A focus route (shell/routes.js `pricing`).

   Real data only (rule 40): the plans are GET /api/product/plans (Free and Premium with their
   entitlements), the current one GET /api/product/commerce. Not drawn, and why: the Monthly/Yearly
   switch and its "-33%" (no price or cycle exists), the "Most popular"/"Most capable" tags (no such
   field), the three-tier price numbers (the catalogue's `price_label` is a name, not an amount), and
   the Questions list (its answers state billing behaviour that does not exist). The plan button
   opens the Billing sheet, whose confirm is inert while `billing_ready` is false. Recorded in
   docs/project/UI_BACKEND_GAPS.md ("New export frames"). */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { pageHeader } from '../../kit/components.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy, planName, planDescription } from '../../copy/shell.js';
import { t } from './copy.js';
import { pricingPlans, compareRows, changeKind, featureCopyKey, formatNumber } from './model.js';
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

function planCard(plan, current) {
  return html`<section class="s-plan-card s-pricing-card">
    <div class="s-pricing-card__head"><span class="s-pricing-card__name">${planName(plan)}</span>${plan.isCurrent ? html`<span class="s-plan-pill s-plan-pill--accent">${t('tagCurrent')}</span>` : ''}</div>
    <div class="s-pricing-card__tagline">${planDescription(plan)}</div>
    <div class="s-pricing-card__price">${plan.isFree ? t('priceFree') : '—'}</div>
    <div class="s-pricing-card__billed">${plan.isFree ? t('freeForever') : t('pricingNotPublished')}</div>
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

export function pricingMarkup({ plans, commerce }) {
  const list = pricingPlans({ plans, commerce });
  const current = list.find((plan) => plan.isCurrent) || null;
  const rows = compareRows(list);
  return html`<div class="s-plan s-pricing">
    ${pageHeader({ back: { label: shellCopy('back'), dataset: { back: '1' } }, title: t('plansTitle') })}
    <div class="s-plan__scroll" data-scroll-region>
      <div class="s-pricing__hero"><h2 class="s-pricing__headline">${t('pricingHero')}</h2><p class="s-pricing__sub">${t('pricingSub')}</p></div>
      <div class="s-pricing__plans">${list.map((plan) => planCard(plan, current))}</div>
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

  mount(element, pricingMarkup({ plans, commerce }));
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  const list = pricingPlans({ plans, commerce });
  const current = list.find((plan) => plan.isCurrent) || null;
  element.querySelectorAll('[data-choose]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = list.find((plan) => plan.id === button.dataset.choose);
      if (target) openBillingSheet({ target, current });
    });
  });
  return undefined;
}

export const __internal = { pricingMarkup, planCard, featureLine, cellMarkup };
