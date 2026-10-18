/* Billing sheet (frame "Billing Sheet", Orena.dc.html line 1865), PR-MON-9 (design revision 3.1, D-MON-033).

   Kinds (the design's `change` and `cancel`; its `card` kind is not built - Orena never takes card data, Update opens
   Polar's portal) and steps `form` → `processing` → `done`, plus the approved fallback when activation is slow (Q3):
   - a first purchase (no live card subscription): the base price and "Continue to payment", which opens Polar's
     embedded checkout; Polar owns the total, tax and card;
   - an existing subscriber's immediate change (upgrade, monthly → yearly): one operation through the server, "Charged
     now: the prorated difference, calculated by Polar" (case B: no amount is shown or computed by Orena);
   - a downgrade or yearly → monthly is not sold in v1 (§3.6.1): the sheet says so and offers cancelling instead;
   - cancel, with the design's optional reasons.

   Truth sources never mix: an embed event or a route's answer moves the sheet to `processing`; only the server's
   record (fed by Polar's webhook) moves it to `done`. */
import { openSheet, fillSheet, sheetHead, closeSheet } from '../../kit/overlay.js';
import { html, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { shellCopy, planName } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { openPolarCheckout } from '../../product/polar-embed.js';
import { t } from './copy.js';
import {
  PLAN_CURRENCY, cancelLosses, changeIsImmediate, classifyChange, cycleOf, formatDate, formatMoney, formatNumber,
  offerFor, offerKey, periodOf, priceView, cardBrand,
} from './model.js';

const POLL_MS = 2000;
const ACTIVATION_MS = 60000;
const REASONS = Object.freeze(['too_expensive', 'not_using', 'missing_feature', 'taking_a_break']);
const wait = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });
const newOperation = () => (globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : null);

function locale() {
  return languages().ui;
}

/* The base price of an offer the server sells (minor units), or the catalogue's when no offer is open. */
function basePrice(target, cycle, offer) {
  if (offer && Number.isFinite(Number(offer.amount_minor))) {
    const amount = formatMoney(Number(offer.amount_minor) / 100, String(offer.currency || PLAN_CURRENCY).toUpperCase(), locale());
    return t(cycle === 'yearly' ? 'pricePerYear' : 'pricePerMonth', { amount });
  }
  const view = priceView(target, cycle, locale());
  if (view.free) return t('priceFree');
  if (view.price === '—') return '—';
  return cycle === 'yearly' ? t('pricePerYear', { amount: view.billedAmount }) : t('pricePerMonth', { amount: view.price });
}

function cardText(card) {
  return card ? t('cardLabel', { brand: cardBrand(card.brand), last4: card.last4 }) : t('cardOnFile');
}

function row(label, value) {
  return html`<div class="s-plan-sheet__row"><span>${label}</span><b>${value}</b></div>`;
}

function amountOf(unit, value) {
  const n = formatNumber(value, locale());
  return unit === 'minute' ? t('amountMinutes', { n }) : n;
}

/* The pure description of what the sheet shows: tests read it without a DOM. */
export function sheetModel({ target, current, cycle = 'monthly', subscription = {}, offers = [], free = null, kind = 'change' }) {
  const name = planName(target);
  const currentName = current ? planName(current) : '';
  const renews = subscription.renewsAt ? formatDate(subscription.renewsAt, locale()) : '';
  // §3.5: paid -> Free is the cancel flow, never a product change.
  if (target?.isFree && subscription.polar && subscription.live) kind = 'cancel';
  if (kind === 'cancel') {
    const losses = cancelLosses(current, free).map((loss) => ({
      label: t(`feature_${loss.key.replace(/\./g, '_')}`),
      value: t('loseLine', { from: amountOf(loss.unit, loss.from), to: amountOf(loss.unit, loss.to) }),
    }));
    return { kind: 'cancel', title: t('cancelTitle', { plan: currentName }), note: t('cancelNote', { plan: currentName, date: renews }), losses };
  }
  const offer = offerFor(offers, target.id, cycle);
  const first = !subscription.polar || !subscription.live;
  if (first) {
    return {
      kind: 'first', title: t('sheetUpgrade', { plan: name }), offer,
      rows: [[t('rowPlan'), `${name} · ${t(cycle === 'yearly' ? 'cycleYearly' : 'cycleMonthly')}`],
        [t('rowPrice'), basePrice(target, cycle, offer)], [t('rowStarts'), t('startsToday')]],
      primary: offer ? t('continuePayment') : '', note: offer ? '' : t('billingNote'),
    };
  }
  const change = classifyChange({ rank: current?.rank, period: subscription.period }, { rank: target.rank, period: periodOf(cycle) });
  const title = t(change === 'upgrade' ? 'sheetUpgrade' : 'sheetSwitch', { plan: name });
  if (change === 'none') return { kind: 'none', title, rows: [], note: '', primary: '' };
  if (!changeIsImmediate(change)) {
    return {
      kind: 'unavailable', title, rows: [],
      note: t('changeUnavailable', { plan: name, current: currentName, date: renews }),
      primary: subscription.cancelling ? '' : t('changeUnavailableCta', { current: currentName }),
    };
  }
  return {
    kind: 'immediate', title, offer,
    rows: [[t('rowPlan'), `${name} · ${t(cycle === 'yearly' ? 'cycleYearly' : 'cycleMonthly')}`],
      [t('rowPrice'), basePrice(target, cycle, offer)], [t('rowStarts'), t('startsToday')],
      [t('rowPayment'), cardText(subscription.card)], [t('chargedNow'), t('chargedNowValue')]],
    primary: offer ? t('sheetConfirm') : '', note: offer ? '' : t('billingNote'),
  };
}

function formMarkup(model, state) {
  const error = state.error ? html`<div class="s-plan-sheet__error" role="alert">${state.error}</div>` : '';
  if (model.kind === 'cancel') {
    return html`<div class="o-sheet__body s-plan-sheet">
        <p class="s-plan-sheet__lead">${model.note}</p>
        <div class="s-plan-sheet__losses">${model.losses.map((loss) => html`<div class="s-plan-sheet__loss"><span>${loss.label}</span><span>${loss.value}</span></div>`)}
          <div class="s-plan-sheet__loss"><span>${t('cancelKept')}</span><span>${t('cancelKeptValue')}</span></div></div>
        <div class="s-plan-sheet__why">${t('cancelWhy')}</div>
        <div class="s-plan-sheet__reasons">${REASONS.map((reason) => html`<button type="button" class="s-plan-sheet__reason" aria-pressed="${state.reason === reason ? 'true' : 'false'}" data-reason="${reason}">${t(`reason_${reason}`)}</button>`)}</div>
        ${error}
      </div>
      <div class="o-sheet__foot">
        <button type="button" class="o-btn o-btn--secondary s-plan-sheet__danger" data-sheet-do="cancel">${t('cancelPlan')}</button>
        <button type="button" class="o-btn o-btn--primary" data-sheet-close>${t('keepPlan', { plan: planName(state.current) })}</button>
      </div>`;
  }
  return html`<div class="o-sheet__body s-plan-sheet">
      ${model.rows.length ? html`<div class="s-plan-sheet__summary">${model.rows.map(([label, value]) => row(label, value))}</div>` : ''}
      ${model.note ? html`<p class="s-plan-sheet__note">${model.note}</p>` : ''}
      ${error}
    </div>
    <div class="o-sheet__foot">
      <button type="button" class="o-btn o-btn--secondary" data-sheet-close>${t('sheetBack')}</button>
      ${model.primary ? html`<button type="button" class="o-btn o-btn--primary" data-sheet-do="${model.kind}">${model.primary}</button>` : ''}
    </div>`;
}

function stepMarkup(state) {
  if (state.step === 'processing') {
    return html`<div class="o-sheet__body s-plan-sheet"><div class="s-plan-sheet__state" role="status" aria-live="polite"><span class="s-plan-sheet__spin" aria-hidden="true"></span><div class="s-plan-sheet__statetitle">${state.label}</div></div></div>`;
  }
  return html`<div class="o-sheet__body s-plan-sheet"><div class="s-plan-sheet__state" role="status" aria-live="polite">
      <span class="s-plan-sheet__check" aria-hidden="true">${raw(icon('check', { size: 28, stroke: 2.4 }))}</span>
      <div class="s-plan-sheet__donetitle">${state.doneTitle}</div><div class="s-plan-sheet__donetext">${state.doneText}</div></div></div>
    <div class="o-sheet__foot"><button type="button" class="o-btn o-btn--primary" data-sheet-finish>${t('done')}</button></div>`;
}

/* Wait until the server's own record shows `ready(view)`; false after `ms` (the fallback, Q3). */
async function until(ready, ms = ACTIVATION_MS) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try {
      if (ready(await api.billingSubscription())) return true;
    } catch { /* a failed read is retried until the bound */ }
    await wait(POLL_MS);
  }
  return false;
}

/* An operation's outcome by reads only (the server never re-sends it): done, refused or not applied. */
async function settle(operationId, first, ms = ACTIVATION_MS) {
  let answer = first;
  const end = Date.now() + ms;
  while (['pending', 'sent', 'provider_unknown'].includes(answer?.state) && Date.now() < end) {
    await wait(POLL_MS);
    try { answer = await api.billingOperation(operationId); } catch { /* retried until the bound */ }
  }
  return answer?.state || 'unknown';
}

function failure(error) {
  return error?.status === 402 ? t('declined') : t('genericError');
}

export function openBillingSheet({ target, current, cycle = 'monthly', subscription = {}, offers = [], free = null, kind = 'change', onFinish = null }) {
  const state = { kind, step: 'form', error: '', reason: null, current, label: '', doneTitle: '', doneText: '' };
  let handle = null;
  let sheet = null;
  let closeEmbed = null;
  const model = () => sheetModel({ target, current, cycle, subscription, offers, free, kind: state.kind });

  const paint = () => {
    const shown = model();
    fillSheet(sheet, handle, html`${sheetHead({ title: state.step === 'done' ? t('allSet') : shown.title, closeLabel: shellCopy('close') })}
      ${state.step === 'form' ? formMarkup(shown, state) : stepMarkup(state)}`);
  };
  const go = (patch) => { Object.assign(state, patch); paint(); };
  const done = (doneTitle, doneText) => go({ step: 'done', doneTitle, doneText });
  const activated = (view) => view && view.plan === target.id && view.status === 'active';

  async function firstPurchase(offer) {
    go({ step: 'processing', label: t('processingPayment'), error: '' });
    let started;
    try {
      started = await api.billingCheckout({ price: offer.key, operation_id: newOperation(), amount_minor: offer.amount_minor,
        currency: offer.currency, embed: true });
    } catch (error) {
      go({ step: 'form', error: failure(error) });
      return;
    }
    let confirmed = false;
    try {
      closeEmbed = await openPolarCheckout(started.redirect_url, {
        confirmed: () => { confirmed = true; go({ step: 'processing', label: t('processingPayment') }); },
        success: async () => {
          go({ step: 'processing', label: t('activatingPlan') });
          if (await until(activated)) done(t('doneUpgradeTitle', { plan: planName(target) }), t('doneUpgradeText'));
          else done(t('fallbackTitle'), t('fallbackText'));
        },
        // Closed before Polar confirmed anything: nothing was submitted. Closed after: never read as a failure.
        close: async () => {
          if (!confirmed) { go({ step: 'form', error: '' }); return; }
          go({ step: 'processing', label: t('activatingPlan') });
          if (await until(activated)) done(t('doneUpgradeTitle', { plan: planName(target) }), t('doneUpgradeText'));
          else done(t('fallbackTitle'), t('fallbackText'));
        },
      });
      go({ step: 'form', error: '' }); // the embed is over the sheet; the summary stays beneath it
    } catch (error) {
      go({ step: 'form', error: failure(error) });
    }
  }

  async function changeNow(offer) {
    const operation = newOperation();
    go({ step: 'processing', label: t('confirmingChange'), error: '' });
    try {
      const answer = await api.billingChange({ price: offer.key, operation_id: operation });
      const outcome = await settle(operation, answer);
      if (outcome !== 'done') { go({ step: 'form', error: t('genericError') }); return; }
      const period = periodOf(cycle);
      if (await until((view) => view && view.plan === target.id && view.period === period)) {
        done(t('doneUpgradeTitle', { plan: planName(target) }), t('doneUpgradeText'));
      } else done(t('fallbackTitle'), t('fallbackText'));
    } catch (error) {
      go({ step: 'form', error: failure(error) });
    }
  }

  async function cancel() {
    const operation = newOperation();
    go({ step: 'processing', label: t('cancelling'), error: '' });
    try {
      const answer = await api.billingCancel({ operation_id: operation, reason: state.reason });
      if ((await settle(operation, answer)) !== 'done') { go({ step: 'form', error: t('genericError') }); return; }
      await until((view) => view && view.cancel_at_period_end === true);
      const date = subscription.renewsAt ? formatDate(subscription.renewsAt, locale()) : '';
      done(t('cancelDoneTitle'), t('cancelDoneText', { plan: planName(current), date }));
    } catch (error) {
      go({ step: 'form', error: failure(error) });
    }
  }

  return openSheet({
    label: model().title,
    className: 's-plan-billsheet',
    onClose: () => { closeEmbed?.(); onFinish?.(state.step === 'done'); },
    render: (body, sheetHandle) => {
      sheet = body;
      handle = sheetHandle;
      paint();
      body.addEventListener('click', (event) => {
        const reason = event.target.closest('[data-reason]');
        if (reason && state.step === 'form') {
          state.reason = state.reason === reason.dataset.reason ? null : reason.dataset.reason;
          paint();
          return;
        }
        if (event.target.closest('[data-sheet-finish]')) { closeSheet(); return; }
        const action = event.target.closest('[data-sheet-do]')?.dataset.sheetDo;
        if (!action || state.step !== 'form') return;
        const shown = model();
        if (action === 'first' && shown.offer) firstPurchase(shown.offer);
        else if (action === 'immediate' && shown.offer) changeNow(shown.offer);
        else if (action === 'unavailable') go({ kind: 'cancel', error: '' });
        else if (action === 'cancel') cancel();
      });
      return null;
    },
  });
}

export const __internal = { sheetModel, formMarkup, stepMarkup, basePrice, offerKey, cycleOf };
