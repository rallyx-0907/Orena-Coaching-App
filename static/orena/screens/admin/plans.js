/* Admin > Users > Plans & pricing (the human's request 2026-10-09): each plan is drawn as the learner's
   Pricing card (screens/plan/pricing.js) and "Edit" FLIPS the card to a form on its back - the plan's
   prices (monthly and yearly, USD and VND) and each entitlement (enabled, and a whole-number monthly
   limit when the feature is metered). Save sends the WHOLE catalogue (PUT /api/product/admin/plans);
   the server validates it and stamps who changed it and when, which the header shows as the moment the
   new values apply from. Cancel flips back and drops that card's edits; a refusal (422) is shown on the
   back of the card with the edits kept.

   The flip is a CSS 3D turn (rotateY, backface-visibility hidden, 0.5 s); with prefers-reduced-motion
   the two faces swap with no movement (admin.css `.a-plan`). Both faces always exist in the DOM; the
   turned-away face is `inert` so a keyboard never lands on it. */
import { html, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { languages } from '../../copy/index.js';
import { planName, planDescription } from '../../copy/shell.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { t as planCopy } from '../plan/copy.js';
import { FEATURE_ORDER, featureCopyKey } from '../plan/model.js';
import { t } from './copy.js';
import { block, pageHead, skeleton } from './blocks.js';
import { createHost } from './host.js';
import { humanKey } from './model.js';

export const PERIODS = Object.freeze(['monthly', 'yearly']);
export const CURRENCIES = Object.freeze(['USD', 'VND']);

const text = (value) => (value == null ? '' : String(value));

/* The editable copy of one catalogue plan: every number a string, as the operator types it. */
export function draftOf(plan) {
  return {
    id: plan.id,
    prices: Object.fromEntries(PERIODS.map((period) => [period, Object.fromEntries(CURRENCIES.map((currency) => [currency, text(plan.prices?.[period]?.[currency] ?? 0)]))])),
    entitlements: (plan.entitlements || []).map((item) => ({ key: item.key, enabled: item.enabled === true, metered: item.monthly_limit != null, monthly_limit: item.monthly_limit == null ? null : text(item.monthly_limit) })),
  };
}

/* What the operator typed, as the number the server reads. Anything that is not a number is sent
   as typed, so the server's own message names it (nothing is corrected silently here). */
function numeric(value) {
  const typed = text(value).trim();
  return typed !== '' && Number.isFinite(Number(typed)) ? Number(typed) : typed;
}

/* The PUT body: the whole catalogue, in the order given. Free's prices are always 0 and a feature
   without a limit carries none. Pure, so the gate can check the shape. */
export function plansPayload(drafts) {
  return {
    version: 1,
    plans: drafts.map((draft) => ({
      id: draft.id,
      prices: Object.fromEntries(PERIODS.map((period) => [period, Object.fromEntries(CURRENCIES.map((currency) => [currency, draft.id === 'free' ? 0 : numeric(draft.prices?.[period]?.[currency])]))])),
      entitlements: draft.entitlements.map((item) => ({ key: item.key, enabled: item.enabled === true, monthly_limit: item.metered ? numeric(item.monthly_limit) : null })),
    })),
  };
}

function money(value, currency, ui) {
  const amount = Number(value) || 0;
  return new Intl.NumberFormat(ui, { style: 'currency', currency, minimumFractionDigits: currency === 'VND' || Number.isInteger(amount) ? 0 : 2, maximumFractionDigits: currency === 'VND' ? 0 : 2 }).format(amount);
}

export function featureLabel(key) {
  const copyKey = featureCopyKey(key);
  return planCopy.has(copyKey) ? planCopy(copyKey) : humanKey(key.replace(/[._]/g, ' '));
}

/* The catalogue's feature keys in the learner's order, then any key this build has no place for yet. */
function orderedKeys(keys) {
  return [...FEATURE_ORDER.filter((key) => keys.includes(key)), ...keys.filter((key) => !FEATURE_ORDER.includes(key))];
}

function frontFace(plan, ui, flipped) {
  const free = plan.id === 'free';
  const byKey = Object.fromEntries((plan.entitlements || []).map((item) => [item.key, item]));
  const lines = orderedKeys(Object.keys(byKey)).filter((key) => byKey[key].enabled).map((key) => {
    const item = byKey[key];
    const label = featureLabel(key);
    return item.monthly_limit == null ? label : planCopy('monthlyLimit', { label, n: new Intl.NumberFormat(ui).format(item.monthly_limit) });
  });
  const month = plan.prices?.monthly || {};
  const year = plan.prices?.yearly || {};
  return html`<div class="a-plan__face a-plan__front"${raw(flipped ? ' inert aria-hidden="true"' : '')}>
    <div class="a-plan__name">${planName(plan)}</div>
    <div class="a-plan__tagline">${planDescription(plan)}</div>
    <div class="a-plan__price">${free ? t('plansFree') : money(month.USD, 'USD', ui)}</div>
    <div class="a-plan__billed">${free ? '' : html`<div>${t('plansPerMonth', { price: money(month.VND, 'VND', ui) })}</div><div>${t('plansPerYear', { price: `${money(year.USD, 'USD', ui)} · ${money(year.VND, 'VND', ui)}` })}</div>`}</div>
    <button type="button" class="a-btn a-btn--md a-plan__edit" data-a="plan-edit" data-plan="${plan.id}">${raw(icon('pencil', { size: 16 }))}<span>${t('plansEdit')}</span></button>
    <div class="a-plan__rule"></div>
    <div class="a-plan__feats">${lines.map((line) => html`<div class="a-plan__feat"><span class="a-plan__tick">${raw(icon('check', { size: 17, stroke: 2.4 }))}</span><span>${line}</span></div>`)}</div>
  </div>`;
}

function priceField(plan, period, currency, draft) {
  const id = `${plan.id}|${period}|${currency}`;
  const label = t(`plans${period === 'monthly' ? 'Monthly' : 'Yearly'}${currency === 'USD' ? 'Usd' : 'Vnd'}`);
  return html`<label class="a-field"><span class="a-field__label"><span>${label}</span></span><input class="a-input" name="${id}" type="text" inputmode="${currency === 'USD' ? 'decimal' : 'numeric'}" autocomplete="off" spellcheck="false" value="${draft.prices[period][currency]}" data-a-input="price|${id}"></label>`;
}

function backFace(plan, draft, flipped, { busy, error }) {
  const free = plan.id === 'free';
  return html`<div class="a-plan__face a-plan__back"${raw(flipped ? '' : ' inert aria-hidden="true"')}>
    <div class="a-plan__name">${t('plansEditing', { plan: planName(plan) })}</div>
    ${free
    ? html`<div class="a-plan__note">${t('plansFreePrices')}</div>`
    : html`<div class="a-plan__prices">${PERIODS.map((period) => CURRENCIES.map((currency) => priceField(plan, period, currency, draft)))}</div>`}
    <div class="a-plan__rule"></div>
    <div class="a-plan__sectionlabel">${t('plansLimits')}</div>
    <div class="a-plan__ents">${orderedKeys(draft.entitlements.map((item) => item.key)).map((key) => {
    const item = draft.entitlements.find((entry) => entry.key === key);
    const id = `${plan.id}|${key}`;
    return html`<div class="a-plan__ent"><span class="a-plan__entname">${featureLabel(key)}</span>
      <button type="button" class="a-toggle" role="switch" aria-checked="${item.enabled ? 'true' : 'false'}" aria-label="${featureLabel(key)} · ${t('plansIncluded')}" data-a="plan-toggle" data-id="${id}" data-plan="${plan.id}" data-key="${key}"><span class="a-toggle__track"><span class="a-toggle__knob"></span></span></button>
      ${item.metered ? html`<input class="a-input a-plan__limit" name="${id}" type="text" inputmode="numeric" autocomplete="off" spellcheck="false" value="${item.monthly_limit}" aria-label="${featureLabel(key)} · ${t('plansLimit')}" data-a-input="limit|${id}"${raw(item.enabled ? '' : ' disabled')}>` : html`<span class="a-plan__limit a-plan__limit--none"></span>`}
    </div>`;
  })}</div>
    ${error ? html`<div class="a-error" role="alert">${error}</div>` : ''}
    <div class="a-actions a-actions--end">
      <button type="button" class="a-btn a-btn--md" data-a="plan-cancel" data-plan="${plan.id}">${t('plansCancel')}</button>
      <button type="button" class="a-btn a-btn--md a-btn--primary" data-a="plan-save" data-plan="${plan.id}"${raw(busy ? ' disabled' : '')}>${busy ? t('plansSaving') : t('plansSave')}</button>
    </div>
  </div>`;
}

export function planCard(plan, draft, { flipped = false, busy = false, error = '', ui = 'en' } = {}) {
  return html`<article class="a-plan${flipped ? ' is-flipped' : ''}" data-plan-card="${plan.id}"><div class="a-plan__inner">${frontFace(plan, ui, flipped)}${backFace(plan, draft, flipped, { busy, error })}</div></article>`;
}

function appliesLine(doc, ui) {
  if (doc.source !== 'stored' || !doc.updated_at) return t('plansDefault');
  const date = new Date(doc.updated_at);
  const when = Number.isNaN(date.getTime()) ? String(doc.updated_at) : new Intl.DateTimeFormat(ui, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
  return [t('plansFrom', { when }), doc.updated_by ? t('plansBy', { name: doc.updated_by }) : ''].filter(Boolean).join(' · ');
}

export function plansPage({ doc, drafts, editing = {}, busy = false, error = null, failed = false, ui = 'en', href }) {
  const back = { href: href('adminUsers'), label: t('navUsers') };
  const label = 'data-screen-label="Plans & pricing"';
  if (failed) return html`<section class="a-page" ${raw(label)}>${pageHead({ back, title: t('plansTitle') })}${block({ body: t('opUnavailable') })}</section>`;
  if (!doc) return html`<section class="a-page" ${raw(label)}>${pageHead({ back, title: t('plansTitle'), sub: t('plansSub') })}${skeleton(t('loading'))}</section>`;
  return html`<section class="a-page" ${raw(label)}>
    ${pageHead({ back, title: t('plansTitle'), sub: appliesLine(doc, ui) })}
    <div class="a-plans">${doc.plans.map((plan) => planCard(plan, drafts[plan.id], { flipped: editing[plan.id] === true, busy, error: error && error.plan === plan.id ? error.message : '', ui }))}</div>
    <p class="a-plans__note">${t('plansBilling')}</p>
  </section>`;
}

export async function mountPlans(shell, ctx) {
  const host = createHost(shell, ctx);
  const view = { doc: null, drafts: {}, editing: {}, busy: false, error: null, failed: false };
  const ui = () => languages().ui;
  const reset = (plan) => { view.drafts[plan.id] = draftOf(plan); };
  host.setBuilder(() => ({ title: t('plansTitle'), markup: plansPage({ doc: view.doc, drafts: view.drafts, editing: view.editing, busy: view.busy, error: view.error, failed: view.failed, ui: ui(), href: ctx.href }) }));

  const card = (id) => shell.page.querySelector?.(`[data-plan-card="${id}"]`);
  /* Turn one card: the class change on the live element is what animates; a repaint redraws a card
     already in its final state, so it never replays the turn. */
  function turn(id, flipped) {
    view.editing[id] = flipped;
    const element = card(id);
    if (!element) return;
    [['.a-plan__front', flipped], ['.a-plan__back', !flipped]].forEach(([selector, hidden]) => {
      const face = element.querySelector(selector);
      if (!face) return;
      face.toggleAttribute('inert', hidden);
      if (hidden) face.setAttribute('aria-hidden', 'true');
      else face.removeAttribute('aria-hidden');
    });
    element.classList.toggle('is-flipped', flipped);
  }

  async function load() {
    try {
      view.doc = await adminApi.plans();
      view.doc.plans.forEach(reset);
    } catch {
      view.failed = true;
    }
    host.paint();
  }

  host.on('go', (control, dataset) => { if (dataset.to) ctx.go(dataset.to); });
  host.on('plan-edit', (control, dataset) => { view.error = null; turn(dataset.plan, true); });
  host.on('plan-cancel', (control, dataset) => {
    const plan = view.doc.plans.find((entry) => entry.id === dataset.plan);
    if (plan) reset(plan);
    if (view.error?.plan === dataset.plan) view.error = null;
    host.paint();
    card(dataset.plan)?.offsetWidth; // eslint-disable-line no-unused-expressions -- settle the redrawn card before it turns back
    turn(dataset.plan, false);
  });
  host.on('plan-toggle', (control, dataset) => {
    const item = view.drafts[dataset.plan]?.entitlements.find((entry) => entry.key === dataset.key);
    if (!item) return;
    item.enabled = !item.enabled;
    host.paint();
  });
  host.onInput((name, value) => {
    const [kind, plan, a, b] = name.split('|');
    const draft = view.drafts[plan];
    if (!draft) return;
    if (kind === 'price') draft.prices[a][b] = value;
    else if (kind === 'limit') {
      const item = draft.entitlements.find((entry) => entry.key === a);
      if (item) item.monthly_limit = value;
    }
  });
  host.on('plan-save', async (control, dataset) => {
    if (view.busy) return;
    view.busy = true;
    view.error = null;
    host.paint();
    try {
      view.doc = await adminApi.savePlans(plansPayload(view.doc.plans.map((plan) => view.drafts[plan.id])));
      view.doc.plans.forEach(reset);
      view.busy = false;
      host.paint();
      for (const id of Object.keys(view.editing)) {
        if (!view.editing[id]) continue;
        card(id)?.offsetWidth; // eslint-disable-line no-unused-expressions
        turn(id, false);
      }
    } catch (failure) {
      view.busy = false;
      view.error = { plan: dataset.plan, message: failure?.message || t('plansSaveFailed') };
      host.paint();
    }
  });
  host.paint();
  await load();
  return () => host.cleanup();
}
