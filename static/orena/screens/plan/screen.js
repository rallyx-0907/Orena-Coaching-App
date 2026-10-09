/* Plan & usage (frame "Plan & usage" of the 2026-10-09 design export), reached from Profile's
   "Plan & usage" row; "See all plans" and the plan card's button open Plans (./pricing.js).
   A focus route (shell/routes.js `billing`): the header stays, the cards scroll in their own region.

   Real data only (Design Contract rule 40): GET /api/product/commerce gives the plan, the
   subscription state and, for each meter enforcement counts, its use in the current window against the
   plan's limit and when it resets (the quota buckets - D-160). A meter nothing counts on this
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
import { t } from './copy.js';
import { planView, usageRows, featureCopyKey, formatNumber } from './model.js';
import pricing from './pricing.js';

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
   the 1st - D-160): a day counts down ("Resets in 5h 12m"), a month names its date ("Resets Nov 1"). */
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

export function billingMarkup(commerce) {
  const view = planView(commerce);
  const rows = usageRows(commerce);
  const tone = STATUS_TONE[view.statusKey] || 'neutral';
  const name = view.plan ? planName(view.plan) : '';
  const description = view.plan ? planDescription(view.plan) : '';
  return html`<div class="s-plan">
    ${pageHeader({
      back: { label: shellCopy('back'), dataset: { back: '1' } },
      title: t('title'),
      actions: [html`<button type="button" class="o-btn o-btn--secondary s-plan__all" data-open-plans>${t('seePlans')}</button>`],
    })}
    <div class="s-plan__scroll" data-scroll-region>
      <div class="s-plan__grid">
        <div class="s-plan__col">
          <section class="s-plan-card s-plan-current">
            <div class="s-plan-current__top">
              ${intelChip({ size: 56, mark: 40 })}
              <div class="s-plan-current__id">
                <div class="s-plan-current__eyebrow">${t('currentPlan')}</div>
                <div class="s-plan-current__name">${name}</div>
                ${view.isFree ? html`<div class="s-plan-current__sub">${t('noCharge')}</div>` : ''}
              </div>
              <span class="s-plan-pill s-plan-pill--${tone}">${t(view.statusKey)}</span>
            </div>
            ${description ? html`<p class="s-plan-note">${description}</p>` : ''}
            <div class="s-plan-actions"><button type="button" class="o-btn o-btn--primary s-plan__change" data-open-plans>${view.isFree ? t('upgrade') : t('changePlan')}</button></div>
          </section>
          <section class="s-plan-card s-plan-usage">
            <h2 class="s-plan-card__title">${t('usage')}</h2>
            ${rows.length ? rows.map(usageRowMarkup) : html`<p class="s-plan-empty">${t('usageUnavailable')}</p>`}
          </section>
        </div>
        <div class="s-plan__col">
          <section class="s-plan-card s-plan-pay">
            <h2 class="s-plan-card__title">${t('paymentMethod')}</h2>
            <div class="s-plan-pay__row">
              <span class="s-plan-pay__tile">${raw(icon('credit-card', { size: 22 }))}</span>
              <div class="s-plan-pay__text"><div class="s-plan-pay__label">${t('noPaymentMethod')}</div><div class="s-plan-pay__sub">${t('paymentMethodSub')}</div></div>
              <button type="button" class="o-btn o-btn--secondary s-plan-pay__update" disabled>${t('update')}</button>
            </div>
          </section>
          <section class="s-plan-card s-plan-invoices">
            <h2 class="s-plan-card__title">${t('invoices')}</h2>
            <p class="s-plan-empty">${t('noInvoices')}</p>
          </section>
        </div>
      </div>
    </div>
  </div>`;
}

export default async function plan(element, ctx) {
  await useStyles('screens/plan/plan.css');
  // One folder serves both frames: Plans is its own route and its own module.
  if (ctx.route?.id === 'pricing') return pricing(element, ctx);
  const commerce = await api.productCommerce().catch(() => null);
  if (!ctx.isCurrent()) return undefined;
  if (!commerce) throw new Error('plan_unavailable');

  mount(element, billingMarkup(commerce));
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  element.querySelectorAll('[data-open-plans]').forEach((button) => button.addEventListener('click', () => ctx.go(ctx.href('pricing'))));
  return undefined;
}

export const __internal = { billingMarkup, usageRowMarkup, usageNote, resetLabel };
