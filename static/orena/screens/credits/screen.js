/* Credits (frame "Credits" of the 2026-10-14 design export), reached from Profile's "Credits" row and the Plan & usage
   Credits card. A focus route (shell/routes.js `credits`): the header stays, the cards scroll in their own region.

   Credits are a one-time purchase, separate from the plan (billing lane contract): nothing here touches Plus/Pro.
   Real data only (Design Contract rule 40): the packs come from GET /api/billing/offers `credit_packs`; the price and
   units are the pack's own and travel back unchanged with the checkout (product/credit-topup.js). The screen exists only
   while the backend offers at least one pack; otherwise the route returns to Plan & usage and the entry points are not
   drawn (the design draws no "unavailable" state - decision recorded in UI_BACKEND_GAPS "Credits").

   Payment: payOS/VietQR. The QR is the payment string the checkout returned. The sheet moves on only when the backend
   says so (the order watcher): never from the return URL, never from a button. The balance, the bonus and "most chosen"
   tags, the history and the transfer note have no learner endpoint yet (CT-2, CT-3, CT-5, CT-8): they are not drawn. */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { brandChip } from '../../kit/brand.js';
import { pageHeader } from '../../kit/components.js';
import { openSheet, closeSheet, fillSheet } from '../../kit/overlay.js';
import { toast } from '../../kit/toast.js';
import { useStyles } from '../../kit/styles.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy, planName } from '../../copy/shell.js';
import { t } from '../../copy/credit-topup.js';
import { createCheckout, loadOffers, historyRows, watchOrder } from '../../product/credit-topup.js';
import { packCards, selectedPack, planStrip, formatNumber, formatPrice, HOW_ROWS, FILTERS, filterHistory, sheetStep } from './model.js';
import { sheetMarkup } from './sheet.js';
import { ensureSpark, spark } from './spark.js';

const checkout = createCheckout({ api });

/* The purchase in hand lives for the session, so a learner who closes the sheet finds "Show QR" again. `state` is only
   ever what the backend's order status said. */
const purchase = { order: null, state: 'waiting', watching: false, cancelled: false, stillWaiting: false, watcher: null };

function clearPurchase() {
  purchase.order = null; purchase.state = 'waiting'; purchase.stillWaiting = false; purchase.watcher = null; checkout.reset();
}

const lang = () => languages().ui;

export function creditsMarkup({ packs, selectedKey, strip, pending, filter, rows }) {
  const cards = packCards(packs, selectedKey, lang());
  const pick = selectedPack(packs, selectedKey);
  const shown = filterHistory(rows, filter);
  return html`<div class="s-cr">
    ${pageHeader({
      back: { label: shellCopy('back'), dataset: { back: '1' } },
      title: t('title'),
      actions: [html`<button type="button" class="o-btn o-btn--secondary s-plan__all" data-open-plan>${t('planButton')}</button>`],
    })}
    <div class="s-cr__scroll" data-scroll-region>
      <section class="s-cr-hero">
        <div class="s-cr-hero__top">
          <span class="s-cr-tile s-cr-tile--hero" aria-hidden="true"><span class="s-cr-glint" data-cr-anim="1">${spark(42)}</span></span>
          <div class="s-cr-hero__id">
            <div class="s-cr-hero__eyebrow">${t('creditBalance')}</div>
            <div class="s-cr-hero__bal"><span class="s-cr-hero__num">—</span><span class="s-cr-hero__unit">${t('credits')}</span></div>
            <div class="s-cr-hero__sub">${t('heroSub')}</div>
          </div>
          <button type="button" class="s-cr-add" data-cr-add>${raw(icon('plus', { size: 18, stroke: 2.4 }))}${t('addCredits')}</button>
        </div>
        <div class="s-cr-strip">
          ${strip ? html`<div class="s-cr-strip__cell">${brandChip({ size: 30, mark: 20, className: 's-cr-strip__mark' })}<div class="s-cr-strip__text"><b>${planName({ id: strip.id, name: strip.name })}</b></div></div>` : ''}
          <div class="${cls('s-cr-strip__cell', strip && 's-cr-strip__cell--sep')}">${spark(16)}<span>${t('planStripSep')}</span></div>
        </div>
      </section>
      ${pending ? html`<div class="s-cr-pending" role="status"><span class="s-cr-dot"><span></span><span data-cr-anim="1"></span></span><span class="s-cr-pending__text">${t(pending.stillWaiting ? 'statusStillWaiting' : 'statusWaiting')} · ${pending.price}</span><button type="button" class="s-cr-pending__show" data-cr-show>${t('showQr')}</button></div>` : ''}
      <div class="s-cr__grid">
        <section class="s-cr-card s-cr-packs" data-cr-packs>
          <div class="s-cr-card__head"><h2 class="s-cr-card__title">${t('addCredits')}</h2><div class="s-cr-card__sub">${t('packsSub')}</div></div>
          <div class="s-cr-packs__list" role="radiogroup" aria-label="${t('packsLabel')}">
            ${cards.map((card) => html`<button type="button" role="radio" class="${cls('s-cr-pack', card.selected && 's-cr-pack--on')}" aria-checked="${card.selected ? 'true' : 'false'}" data-cr-pack="${card.key}">
              <div class="s-cr-pack__top">${spark(18)}<span class="s-cr-pack__flex"></span><span class="s-cr-pack__check">${raw(icon('check', { size: 13, stroke: 3.4 }))}</span></div>
              <div class="s-cr-pack__total"><span class="s-cr-pack__num">${card.total}</span><span class="s-cr-pack__unit">${t('credits')}</span></div>
              <div class="s-cr-pack__rule"></div>
              <div class="s-cr-pack__price">${card.price}</div>
            </button>`)}
          </div>
          <div class="s-cr-summary">
            <div class="s-cr-summary__text"><div class="s-cr-summary__main">${pick ? `${formatNumber(pick.creditUnits, lang())} ${t('credits')} · ${formatPrice(pick.amountMinor, pick.currency, lang())}` : ''}</div></div>
            <button type="button" class="s-cr-btn s-cr-btn--pri s-cr-summary__go" data-cr-continue>${t('continue')}</button>
          </div>
          <div class="s-cr-note"><span class="s-cr-note__badge">VietQR</span><span>${t('vietqrNote')}</span></div>
        </section>
        <div class="s-cr__col">
          <section class="s-cr-card s-cr-history">
            <div class="s-cr-history__head"><h2 class="s-cr-card__title">${t('history')}</h2>
              <div class="s-cr-filter" role="group">${FILTERS.map((item) => html`<button type="button" class="${cls('s-cr-filter__btn', filter === item.id && 's-cr-filter__btn--on')}" aria-pressed="${filter === item.id ? 'true' : 'false'}" data-cr-filter="${item.id}">${t(item.label)}</button>`)}</div>
            </div>
            ${shown.length ? '' : html`<div class="s-cr-empty">${spark(26)}<div class="s-cr-empty__title">${filter === 'in' ? t('emptyInTitle') : t('emptyTitle')}</div><div class="s-cr-empty__text">${t('emptyText')}</div></div>`}
          </section>
          <section class="s-cr-card s-cr-how">
            <h2 class="s-cr-how__title">${t('howTitle')}</h2>
            ${HOW_ROWS.map((row) => html`<div class="s-cr-how__row"><span class="s-cr-how__icon">${raw(icon(row.icon, { size: 16 }))}</span><div class="s-cr-how__body"><div class="s-cr-how__t">${t(row.title)}</div><div class="s-cr-how__d">${t(row.text)}</div></div></div>`)}
          </section>
        </div>
      </div>
    </div>
  </div>`;
}

export default async function credits(element, ctx) {
  await useStyles('screens/credits/credits.css');
  ensureSpark();
  let [offers, commerce] = await Promise.all([loadOffers(api), api.productCommerce().catch(() => null)]);
  if (!ctx.isCurrent()) return undefined;
  /* Nothing on sale (gated off, no packs, or the read failed): the backend is the source of truth; return to Plan & usage. */
  if (!offers.available) {
    clearPurchase(); // nothing on sale (or signed out): an earlier session's purchase must not linger
    ctx.replace(ctx.href('billing'));
    return undefined;
  }

  const view = { selectedKey: offers.packs[0].key, filter: 'all', rows: historyRows([]) };
  let sheet = null; // { element, handle }
  let stopped = false; // set when the route is left: retires this screen's watcher

  const currentPack = () => selectedPack(offers.packs, view.selectedKey);
  const orderPack = () => (purchase.order ? offers.packs.find((pack) => pack.key === purchase.order.packKey) || purchase.order.pack : null);
  const pendingNow = () => {
    const pack = orderPack();
    return pack && !sheet && ['waiting', 'received'].includes(purchase.state)
      ? { price: formatPrice(pack.amountMinor, pack.currency, lang()), total: formatNumber(pack.creditUnits, lang()), stillWaiting: purchase.stillWaiting }
      : null;
  };

  function paint() {
    const scroll = element.querySelector('[data-scroll-region]');
    const top = scroll ? scroll.scrollTop : 0;
    mount(element, creditsMarkup({ packs: offers.packs, selectedKey: view.selectedKey, strip: planStrip(commerce), pending: pendingNow(), filter: view.filter, rows: view.rows }));
    const next = element.querySelector('[data-scroll-region]');
    if (next) next.scrollTop = top;
    wire();
  }

  function sheetModel(step, busy = false) {
    const pack = purchase.order ? orderPack() : currentPack();
    return {
      step, busy, qr: purchase.order ? purchase.order.qr : '', orderState: purchase.state, stillWaiting: purchase.stillWaiting,
      total: formatNumber(pack.creditUnits, lang()), price: formatPrice(pack.amountMinor, pack.currency, lang()),
      planName: commerce?.plan ? planName({ id: String(commerce.plan.id), name: String(commerce.plan.name || '') }) : '',
    };
  }

  function paintSheet(step, busy = false) {
    if (!sheet) return;
    fillSheet(sheet.element, sheet.handle, sheetMarkup(sheetModel(step, busy)));
    wireSheet();
    /* The step's markup replaced the focused control: keep focus inside the dialog so Escape and Tab still work. */
    if (!sheet.element.contains(document.activeElement)) (sheet.element.querySelector('button:not([disabled])') || sheet.element).focus({ preventScroll: true });
  }

  function stepNow() {
    return sheetStep({ order: purchase.order, orderState: purchase.state });
  }

  function openPayment(step) {
    openSheet({
      label: t('sheetAdd'),
      className: 's-cr-sheet',
      onClose: () => { sheet = null; if (ctx.isCurrent()) paint(); },
      render: (el, handle) => {
        sheet = { element: el, handle };
        fillSheet(el, handle, sheetMarkup(sheetModel(step)));
        wireSheet();
        return null;
      },
    });
  }

  /* Follow the order with the backend's own status; the sheet changes step only when it says so. One watcher at a
     time (the token): a newer watch, leaving the route or cancelling retires the older one. */
  function watch() {
    if (!purchase.order) return;
    const token = Symbol('watch');
    purchase.watcher = token;
    purchase.watching = true;
    purchase.stillWaiting = false;
    const code = purchase.order.orderCode;
    const refresh = () => {
      if (!ctx.isCurrent()) return;
      if (sheet) paintSheet(stepNow());
      else paint();
    };
    watchOrder({
      readStatus: () => api.billingOrder(code),
      onState: (state) => {
        if (purchase.watcher !== token || !purchase.order || purchase.order.orderCode !== code) return;
        purchase.state = state;
        refresh();
      },
      shouldStop: () => stopped || !ctx.isCurrent() || purchase.watcher !== token || purchase.cancelled || !purchase.order || purchase.order.orderCode !== code,
    }).then((result) => {
      if (purchase.watcher !== token) return;
      if (result.reason === 'auth') { clearPurchase(); return; }
      if (result.state === 'still_waiting') { purchase.stillWaiting = true; refresh(); }
    }).finally(() => { if (purchase.watcher === token) purchase.watching = false; });
  }

  async function reloadOffers() {
    offers = await loadOffers(api);
    if (!ctx.isCurrent()) return;
    if (!offers.available) { closeSheet(); ctx.replace(ctx.href('billing')); return; }
    if (!offers.packs.some((pack) => pack.key === view.selectedKey)) view.selectedKey = offers.packs[0].key;
    paint();
  }

  async function pay() {
    const pack = currentPack();
    paintSheet('confirm', true);
    const result = await checkout.start(pack);
    if (!ctx.isCurrent()) return;
    if (result.ok && result.qr) {
      purchase.cancelled = false;
      purchase.order = { orderCode: result.orderCode, qr: result.qr, packKey: pack.key, pack };
      purchase.state = 'waiting';
      paintSheet('qr');
      watch();
      return;
    }
    const refusal = result.ok ? { message: 'errGatewayUnavailable', action: 'retry_same', refetch: false } : result.refusal;
    toast(t(refusal.message), { iconName: 'circle-alert' });
    if (refusal.action === 'sign_in') clearPurchase();
    /* An order for this intent already exists but the backend gives no link to resume it (CT-4): follow the one in hand,
       otherwise close the sheet rather than loop on a button that cannot succeed. */
    if (refusal.action === 'resume') {
      if (purchase.order && purchase.order.packKey === pack.key && ['waiting', 'received'].includes(purchase.state)) { paintSheet('qr'); watch(); return; }
      closeSheet();
      return;
    }
    if (refusal.action === 'sign_in' || refusal.action === 'none') { closeSheet(); return; }
    if (refusal.refetch || refusal.action === 'new_intent' || refusal.action === 'refetch') { closeSheet(); await reloadOffers(); return; }
    paintSheet('confirm', false);
  }

  function startAgain() {
    purchase.order = null;
    purchase.state = 'waiting';
    checkout.reset();
    pay();
  }

  function wireSheet() {
    const el = sheet?.element;
    if (!el) return;
    el.querySelector('[data-cr-pay]')?.addEventListener('click', pay);
    el.querySelector('[data-cr-again]')?.addEventListener('click', startAgain);
    el.querySelector('[data-cr-done]')?.addEventListener('click', () => { purchase.order = null; purchase.state = 'waiting'; checkout.reset(); closeSheet(); });
    el.querySelector('[data-cr-cancel]')?.addEventListener('click', () => {
      /* The backend closes an unpaid order itself; there is no cancel call (CT-1). We only stop watching it here. */
      purchase.cancelled = true; purchase.order = null; purchase.state = 'waiting'; checkout.reset(); closeSheet();
    });
  }

  function wire() {
    element.querySelector('[data-back]')?.addEventListener('click', () => ctx.back());
    element.querySelector('[data-open-plan]')?.addEventListener('click', () => ctx.go(ctx.href('billing')));
    const scrollToPacks = () => element.querySelector('[data-cr-packs]')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    element.querySelector('[data-cr-add]')?.addEventListener('click', scrollToPacks);
    element.querySelectorAll('[data-cr-pack]').forEach((button) => button.addEventListener('click', () => { view.selectedKey = button.dataset.crPack; paint(); element.querySelector(`[data-cr-pack="${view.selectedKey}"]`)?.focus({ preventScroll: true }); }));
    element.querySelectorAll('[data-cr-filter]').forEach((button) => button.addEventListener('click', () => { view.filter = button.dataset.crFilter; paint(); }));
    element.querySelector('[data-cr-continue]')?.addEventListener('click', () => {
      const resumable = purchase.order && purchase.order.packKey === view.selectedKey && ['waiting', 'received'].includes(purchase.state);
      if (resumable) { openPayment('qr'); return; }
      purchase.order = null; purchase.state = 'waiting'; checkout.reset();
      openPayment('confirm');
    });
    element.querySelector('[data-cr-show]')?.addEventListener('click', () => openPayment(stepNow()));
  }

  paint();
  /* Back on the route with an order still open: follow it again (the earlier watcher stopped when the route was left). */
  if (purchase.order && !purchase.cancelled && ['waiting', 'received'].includes(purchase.state)) watch();
  return () => { stopped = true; closeSheet(); };
}

export const __internal = { creditsMarkup, purchase };
