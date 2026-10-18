/* Plan & usage (frame "Plan & usage" of the 2026-10-09 design export), reached from Profile's
   "Plan & usage" row; "See all plans" and the plan card's button open Plans (./pricing.js).
   A focus route (shell/routes.js `billing`): the header stays, the cards scroll in their own region.

   Real data only (Design Contract rule 40): GET /api/product/commerce gives the plan, the
   subscription state and, for each meter enforcement counts, its use in the current window against the
   plan's limit and when it resets (the quota buckets - D-161). A meter nothing counts on this
   deployment, or whose use cannot be read, shows "—" and "Not available", never 0 used. The design's
   Plus/Pro tiers, prices and renewal date, the 14-day "Orena messages" chart, the card on file,
   the billing email, the invoices and the amber "cancels/changes" banner have no backend
   (`billing_ready: false`): the chart, the email and the banner are not drawn; the payment method
   and the invoices are drawn at their honest empty state with the update control inert. Recorded
   in docs/project/UI_BACKEND_GAPS.md ("New export frames"). */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { intelChip } from '../../kit/brand.js';
import { pageHeader } from '../../kit/components.js';
import { useStyles } from '../../kit/styles.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy, planName, planDescription } from '../../copy/shell.js';
import { toast } from '../../kit/toast.js';
import { t } from './copy.js';
import {
  planView, usageRows, featureCopyKey, formatNumber, pricingPlans, subscriptionView, priceView, cycleOf, cardBrand,
  formatDate, invoiceAmount,
} from './model.js';
import { openBillingSheet } from './sheet.js';
import pricing from './pricing.js';
import { t as creditCopy } from '../../copy/credit-topup.js';
import { loadOffers } from '../../product/credit-topup.js';
import { ensureSpark, sparkTile } from '../credits/spark.js';

const STATUS_TONE = { status_active: 'green', status_past_due: 'red', status_trialing: 'amber', status_pending: 'amber', status_paused: 'amber' };

const numberLabel = (value) => formatNumber(value, languages().ui);

/* An amount in the row's own unit: minutes say so ("3 min"), counts are bare numbers (the design). */
function amount(row, value) {
  return row.unit === 'minute' ? t('amountMinutes', { n: numberLabel(value) }) : numberLabel(value);
}

function usageNote(row) {
  if (row.unknown) return { text: t('usageNotRead'), tone: '' };
  if (row.tone === 'red') return { text: t('limitReached'), tone: 'red' };
  if (row.tone === 'amber') return { text: t('almostLimit'), tone: 'amber' };
  return { text: t('usageLeft', { n: amount(row, row.left) }), tone: '' };
}

/* When the window resets, from the server's own `resets_at` (the learner's local midnight, or local 00:00 on
   the 1st - D-161): a day counts down ("Resets in 5h 12m"), a month names its date ("Resets Nov 1"). */
export function resetLabel(row, now = new Date()) {
  const at = row.resetsAt ? new Date(row.resetsAt) : null;
  if (!at || Number.isNaN(at.getTime())) return t(row.window === 'day' ? 'resetsDaily' : 'resetsMonthly');
  if (row.window === 'day') {
    const minutes = Math.max(1, Math.round((at.getTime() - now.getTime()) / 60000));
    return t('resetsIn', { h: String(Math.floor(minutes / 60)), m: String(minutes % 60) });
  }
  return t('resetsOn', { date: new Intl.DateTimeFormat(languages().ui, { month: 'short', day: 'numeric' }).format(at) });
}

function usageRowMarkup(row) {
  const note = usageNote(row);
  return html`<div class="s-plan-usage__row">
    <div class="s-plan-usage__line"><span class="s-plan-usage__label">${t(featureCopyKey(row.key))}</span><span class="s-plan-usage__figure"><b>${row.unknown ? '—' : amount(row, row.used)}</b><span> / ${amount(row, row.limit)}</span></span></div>
    <div class="s-plan-usage__track"><div class="${cls('s-plan-usage__fill', row.tone !== 'ok' && `s-plan-usage__fill--${row.tone}`)}" style="width:${row.percent}%"></div></div>
    <div class="s-plan-usage__foot"><span>${resetLabel(row)}</span><span class="${cls('s-plan-usage__note', note.tone && `s-plan-usage__note--${note.tone}`)}">${note.text}</span></div>
  </div>`;
}

/* The Credits card (2026-10-14 design): drawn only while the backend offers credit packs. The balance has no learner
   endpoint yet (CT-2), so it reads "—". Credits are separate from the plan: this card never touches the plan above. */
function creditsCard() {
  return html`<section class="s-plan-credits">
    <div class="s-plan-credits__top">${sparkTile(48, 26, { radius: 14 })}<div class="s-plan-credits__id"><div class="s-plan-credits__eyebrow">${creditCopy('credits')}</div><div class="s-plan-credits__bal"><span class="s-plan-credits__num">—</span><span class="s-plan-credits__unit">${creditCopy('left')}</span></div></div></div>
    <div class="s-plan-credits__text">${creditCopy('cardText')}</div>
    <div class="s-plan-credits__actions"><button type="button" class="s-plan-credits__add" data-open-credits>${creditCopy('addCredits')}</button><button type="button" class="s-plan-credits__history" data-open-credits>${creditCopy('viewHistory')}</button></div>
  </section>`;
}

/* PR-MON-9: the card subscription the server reports (GET /api/billing/subscription) - the plan card's price line,
   renewal and status, the cancelling banner, the card on file, the billing email and the invoices. */
function planLines(view, sub, catalogue) {
  const plan = (catalogue || []).find((item) => item.id === view.plan?.id) || null;
  if (!sub.polar || !sub.live || !plan) return { priceLine: '', note: '' };
  const cycle = cycleOf(sub.period);
  const price = priceView(plan, cycle, languages().ui);
  const amount = cycle === 'yearly' ? price.billedAmount : price.price;
  const priceLine = amount && amount !== '—' ? t(cycle === 'yearly' ? 'priceLineYearly' : 'priceLineMonthly', { amount }) : '';
  const date = sub.renewsAt ? formatDate(sub.renewsAt, languages().ui) : '';
  let note = '';
  if (date && !sub.cancelling) {
    note = sub.card ? t('renewsNoteCard', { date, card: t('cardLabel', { brand: cardBrand(sub.card.brand), last4: sub.card.last4 }) })
      : t('renewsNote', { date });
  }
  return { priceLine, note };
}

function cardSub(card) {
  const month = String(card.exp_month || '').padStart(2, '0');
  const year = String(card.exp_year || '').slice(-2);
  return month && year ? t('cardExpires', { date: `${month}/${year}` }) : '';
}

function invoiceRow(item) {
  const plan = item.plan ? planName({ id: item.plan }) : '';
  const cycle = item.period ? t(item.period === 'year' ? 'cycleYearly' : 'cycleMonthly') : '';
  const status = ['paid', 'refunded', 'pending'].includes(item.status) ? t(`invoice_${item.status}`) : '';
  return html`<div class="s-plan-invoice" data-invoice-row="${item.id}">
    <div class="s-plan-invoice__id"><div class="s-plan-invoice__date">${formatDate(item.created_at, languages().ui)}</div>
      <div class="s-plan-invoice__desc" data-invoice-note>${plan ? t('invoiceLine', { plan, cycle }) : ''}</div></div>
    <span class="s-plan-invoice__amt">${invoiceAmount(item, languages().ui)}</span>
    ${status ? html`<span class="${cls('s-plan-pill', item.status === 'paid' ? 's-plan-pill--green' : 's-plan-pill--amber', 's-plan-invoice__status')}">${status}</span>` : ''}
    <button type="button" class="s-plan-invoice__dl" data-invoice="${item.id}" title="${t('downloadInvoice')}" aria-label="${t('downloadInvoice')}">${raw(icon('download', { size: 17 }))}</button>
  </div>`;
}

export function billingMarkup(commerce, { credits = false, subscription = null, catalogue = null, invoices = null } = {}) {
  const view = planView(commerce);
  const sub = subscriptionView(subscription);
  const rows = usageRows(commerce);
  const tone = sub.cancelling ? 'amber' : STATUS_TONE[view.statusKey] || 'neutral';
  const name = view.plan ? planName(view.plan) : '';
  const description = view.plan ? planDescription(view.plan) : '';
  const lines = planLines(view, sub, catalogue);
  const pill = sub.cancelling && sub.renewsAt
    ? t('pillCancels', { date: formatDate(sub.renewsAt, languages().ui, { year: false }) }) : t(view.statusKey);
  const banner = sub.cancelling ? t('bannerCancelling', { plan: name, date: sub.renewsAt ? formatDate(sub.renewsAt, languages().ui) : '' }) : '';
  const items = Array.isArray(invoices?.items) ? invoices.items : [];
  return html`<div class="s-plan">
    ${pageHeader({
      back: { label: shellCopy('back'), dataset: { back: '1' } },
      title: t('title'),
      actions: [html`<button type="button" class="o-btn o-btn--secondary s-plan__all" data-open-plans>${t('seePlans')}</button>`],
    })}
    <div class="s-plan__scroll" data-scroll-region>
      ${banner ? html`<div class="s-plan-banner" role="status"><span class="s-plan-banner__dot" aria-hidden="true"></span><span class="s-plan-banner__text">${banner}</span><button type="button" class="s-plan-banner__btn" data-resume>${t('resumePlan', { plan: name })}</button></div>` : ''}
      <div class="s-plan__grid">
        <div class="s-plan__col">
          <section class="s-plan-card s-plan-current">
            <div class="s-plan-current__top">
              ${intelChip({ size: 56, mark: 40 })}
              <div class="s-plan-current__id">
                <div class="s-plan-current__eyebrow">${t('currentPlan')}</div>
                <div class="s-plan-current__name">${name}</div>
                ${view.isFree ? html`<div class="s-plan-current__sub">${t('noCharge')}</div>` : lines.priceLine ? html`<div class="s-plan-current__sub">${lines.priceLine}</div>` : ''}
              </div>
              <span class="s-plan-pill s-plan-pill--${tone}">${pill}</span>
            </div>
            ${lines.note || description ? html`<p class="s-plan-note">${lines.note || description}</p>` : ''}
            <div class="s-plan-actions"><button type="button" class="o-btn o-btn--primary s-plan__change" data-open-plans>${view.isFree ? t('upgrade') : t('changePlan')}</button>${sub.live && !sub.cancelling ? html`<button type="button" class="o-btn o-btn--secondary s-plan__cancel" data-open-cancel>${t('cancelPlan')}</button>` : ''}</div>
          </section>
          <section class="s-plan-card s-plan-usage">
            <h2 class="s-plan-card__title">${t('usage')}</h2>
            ${rows.length ? rows.map(usageRowMarkup) : html`<p class="s-plan-empty">${t('usageUnavailable')}</p>`}
          </section>
        </div>
        <div class="s-plan__col">
          ${credits ? creditsCard() : ''}
          <section class="s-plan-card s-plan-pay">
            <h2 class="s-plan-card__title">${t('paymentMethod')}</h2>
            <div class="s-plan-pay__row">
              <span class="s-plan-pay__tile">${raw(icon('credit-card', { size: 22 }))}</span>
              ${sub.polar ? html`<div class="s-plan-pay__text"><div class="s-plan-pay__label">${sub.card ? t('cardLabel', { brand: cardBrand(sub.card.brand), last4: sub.card.last4 }) : t('cardOnFile')}</div><div class="s-plan-pay__sub">${sub.card ? cardSub(sub.card) : ''}</div></div>
              <button type="button" class="o-btn o-btn--secondary s-plan-pay__update" data-update-card>${t('update')}</button>`
              : html`<div class="s-plan-pay__text"><div class="s-plan-pay__label">${t('noPaymentMethod')}</div><div class="s-plan-pay__sub">${subscription ? t('addedOnSubscribe') : t('paymentMethodSub')}</div></div>
              <button type="button" class="o-btn o-btn--secondary s-plan-pay__update" disabled>${t('update')}</button>`}
            </div>
            ${sub.email ? html`<div class="s-plan-pay__rule"></div><div class="s-plan-pay__email"><div class="s-plan-pay__sub">${t('billingEmail')}</div><div class="s-plan-pay__mail">${sub.email}</div></div>` : ''}
          </section>
          <section class="${cls('s-plan-card s-plan-invoices', items.length && 's-plan-invoices--list')}">
            <h2 class="s-plan-card__title">${t('invoices')}</h2>
            ${items.length ? items.map(invoiceRow) : html`<p class="s-plan-empty">${t('noInvoices')}</p>`}
          </section>
        </div>
      </div>
    </div>
  </div>`;
}

const wait = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

/* PR-MON-9 §3.4: an invoice is GET first; while Polar prepares it the row says so and asks again, bounded. */
async function downloadInvoice(element, orderId) {
  const note = element.querySelector(`[data-invoice-row="${CSS.escape(orderId)}"] [data-invoice-note]`);
  const before = note ? note.textContent : '';
  const end = Date.now() + 30000;
  try {
    while (Date.now() < end) {
      const answer = await api.billingInvoice(orderId);
      if (answer?.state === 'ready' && answer.url) {
        if (note) note.textContent = before;
        window.open(answer.url, '_blank', 'noopener');
        return;
      }
      if (note) note.textContent = t('preparingInvoice');
      await wait(2000);
    }
    toast(t('invoiceLater'), { iconName: 'clock' });
  } catch {
    toast(t('genericError'), { iconName: 'circle-alert' });
  }
  if (note) note.textContent = before;
}

export default async function plan(element, ctx) {
  await useStyles('screens/plan/plan.css');
  // One folder serves both frames: Plans is its own route and its own module.
  if (ctx.route?.id === 'pricing') return pricing(element, ctx);
  const [commerce, offers, plansAnswer, subscription, sale] = await Promise.all([
    api.productCommerce().catch(() => null), loadOffers(api), api.productPlans().catch(() => null),
    api.billingSubscription().catch(() => null), api.billingOffers().catch(() => null),
  ]);
  if (!ctx.isCurrent()) return undefined;
  if (!commerce) throw new Error('plan_unavailable');
  if (offers.available) {
    await useStyles('screens/credits/credits.css');
    ensureSpark();
  }
  const catalogue = pricingPlans({ plans: plansAnswer?.plans, commerce });
  const invoices = subscription?.provider === 'polar' ? await api.billingInvoices().catch(() => null) : null;
  if (!ctx.isCurrent()) return undefined;

  mount(element, billingMarkup(commerce, { credits: offers.available, subscription, catalogue, invoices }));
  const reload = () => { if (ctx.isCurrent()) plan(element, ctx); };
  element.querySelectorAll('[data-open-credits]').forEach((button) => button.addEventListener('click', () => ctx.go(ctx.href('credits'))));
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  element.querySelectorAll('[data-open-plans]').forEach((button) => button.addEventListener('click', () => ctx.go(ctx.href('pricing'))));
  const current = catalogue.find((item) => item.isCurrent) || null;
  element.querySelector('[data-open-cancel]')?.addEventListener('click', () => openBillingSheet({
    kind: 'cancel', target: current, current, subscription: subscriptionView(subscription),
    free: catalogue.find((item) => item.isFree) || null, offers: sale?.offers || [],
    onFinish: (changed) => { if (changed) reload(); },
  }));
  element.querySelector('[data-resume]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    const operation = globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : null;
    try {
      let answer = await api.billingResume({ operation_id: operation });
      for (let tries = 0; ['pending', 'sent', 'provider_unknown'].includes(answer?.state) && tries < 30; tries += 1) {
        await wait(2000);
        answer = await api.billingOperation(operation);
      }
      if (answer?.state !== 'done') throw new Error('resume_not_done');
      let confirmed = false;
      for (let tries = 0; tries < 30 && !confirmed; tries += 1) {
        const view = await api.billingSubscription().catch(() => null);
        confirmed = Boolean(view && view.cancel_at_period_end === false);
        if (!confirmed) await wait(2000);
      }
      // Review P2: "resumed" only once the record shows it; otherwise the neutral sentence.
      toast(confirmed ? t('resumedToast', { plan: current ? planName(current) : '' }) : t('resumePendingToast'),
        { iconName: confirmed ? 'check' : 'clock' });
      reload();
    } catch {
      button.disabled = false;
      toast(t('genericError'), { iconName: 'circle-alert' });
    }
  });
  element.querySelector('[data-update-card]')?.addEventListener('click', async () => {
    // Polar's customer portal: the only place a card is changed (Orena never takes card data). A new tab.
    const tab = window.open('about:blank', '_blank');
    try {
      const answer = await api.billingPortal();
      if (tab) { tab.opener = null; tab.location.href = answer.url; } else window.open(answer.url, '_blank', 'noopener');
    } catch {
      tab?.close();
      toast(t('portalError'), { iconName: 'circle-alert' });
    }
  });
  element.querySelectorAll('[data-invoice]').forEach((button) => button.addEventListener('click', () => downloadInvoice(element, button.dataset.invoice)));
  return undefined;
}

export const __internal = { billingMarkup, usageRowMarkup, usageNote, resetLabel };
