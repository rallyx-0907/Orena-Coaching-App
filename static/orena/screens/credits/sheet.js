/* Credits Payment (frame "Credits Payment" of the 2026-10-14 design export): the sheet over Credits. Markup only; the
   screen drives it (./screen.js). Steps: confirm, qr, received, done, expired. What the frame draws and the backend
   cannot yet serve is not drawn (UI_BACKEND_GAPS CT-1..CT-8): the transfer note and Copy, the 15:00 timer, the
   new-balance figure and the receipt line. The prototype's own affordances ("Let this QR expire", the "Prototype:"
   note, "Payments are simulated") are not part of the product. */
import QRCode from '../../vendor/qrcode-generator/qrcode.js';
import { html, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { sheetHead } from '../../kit/overlay.js';
import { shellCopy } from '../../copy/shell.js';
import { t } from '../../copy/credit-topup.js';
import { spark, sparkTile } from './spark.js';
import { qrPath } from './model.js';

/* The QR of the payment string payOS returned. Level Q: the logo sits over the middle (as the design draws it). */
export function qrMatrix(text) {
  const code = QRCode(0, 'Q');
  try {
    code.addData(String(text));
    code.make();
  } catch {
    return null; // over QR capacity or malformed: the sheet shows the gateway message instead (qrBody)
  }
  const size = code.getModuleCount();
  return { size, path: qrPath(size, (row, col) => code.isDark(row, col)) };
}

function rowsMarkup(rows) {
  return rows.map((row) => html`<div class="s-cr-sheet__row"><span>${row.k}</span><b>${row.v}</b></div>`);
}

function confirmBody({ total, price, planName }) {
  const rows = [{ k: t('rowType'), v: t('rowTypeValue') }];
  if (planName) rows.push({ k: t('rowPlan'), v: t('rowPlanValue', { plan: planName }) });
  return html`<div class="s-cr-sheet__lead">${sparkTile(60, 32, { radius: 18 })}<div class="s-cr-sheet__total"><span class="s-cr-sheet__num">${total}</span><span class="s-cr-sheet__unit">${t('credits')}</span></div></div>
    <div class="s-cr-sheet__box">${rowsMarkup(rows)}<div class="s-cr-sheet__row s-cr-sheet__row--due"><span>${t('payToday')}</span><b>${price}</b></div></div>
    <div class="s-cr-sheet__via"><span class="s-cr-sheet__viaicon">${raw(icon('qr-code', { size: 20 }))}</span><div><div class="s-cr-sheet__vialabel">${t('vietqrVia')}</div><div class="s-cr-sheet__viasub">${t('scanWith')}</div></div></div>`;
}

function qrBody({ price, qr, stillWaiting = false }) {
  const matrix = qr ? qrMatrix(qr) : null;
  const unreadable = Boolean(qr) && !matrix;
  const sub = unreadable ? t('errGatewayUnavailable') : t(stillWaiting ? 'statusStillWaiting' : 'waitingText');
  return html`<div class="s-cr-sheet__qrwrap">
      <div class="s-cr-sheet__qr">${matrix ? raw(`<svg width="232" height="232" viewBox="0 0 ${matrix.size} ${matrix.size}" shape-rendering="crispEdges" role="img" aria-label="${t('scanTitle')}"><path d="${matrix.path}" style="fill:var(--qr-ink)"></path></svg>`) : ''}<span class="s-cr-sheet__qrlogo">${sparkTile(38, 20, { radius: 10 })}</span></div>
      <div class="s-cr-sheet__badge">${t('vietqrBadge')}</div>
    </div>
    <div class="s-cr-sheet__box"><div class="s-cr-sheet__row s-cr-sheet__row--amount"><span>${t('amount')}</span><b>${price}</b></div></div>
    <div class="s-cr-wait" role="status"><span class="s-cr-dot"><span></span><span data-cr-anim="1"></span></span><div class="s-cr-wait__text"><div class="s-cr-wait__title">${t('statusWaiting')}</div><div class="s-cr-wait__sub">${sub}</div></div><span class="s-cr-wait__scan"><span data-cr-anim="1"></span></span></div>`;
}

function receivedBody({ total }) {
  return html`<div class="s-cr-sheet__center s-cr-sheet__center--received" role="status"><span class="s-cr-spin"><span></span>${spark(26)}</span><div class="s-cr-sheet__h">${t('receivedTitle')}</div><div class="s-cr-sheet__p">${t('receivedText', { n: total })}</div></div>`;
}

const FLY = [[-46, -38, 0.12], [44, -42, 0.16], [-58, 6, 0.2], [58, 0, 0.24], [-28, 44, 0.28], [30, 46, 0.32], [0, -58, 0.36]];

function doneBody({ total, price }) {
  const sparks = FLY.map(([dx, dy, delay]) => `<span data-cr-anim="1" class="s-cr-burst__dot" style="--dx:${dx}px;--dy:${dy}px;animation-delay:${delay}s"></span>`).join('');
  return html`<div class="s-cr-sheet__center s-cr-sheet__center--done" role="status">
      <div class="s-cr-burst"><span data-cr-anim="1" class="s-cr-burst__ring"></span><span data-cr-anim="1" class="s-cr-burst__ring s-cr-burst__ring--2"></span>${raw(sparks)}<span data-cr-anim="1" class="s-cr-burst__pop">${sparkTile(72, 38, { radius: 22 })}</span></div>
      <div class="s-cr-sheet__added">${t('doneAdded', { n: total })}</div>
      <div class="s-cr-sheet__box s-cr-sheet__box--left">${rowsMarkup([{ k: t('paid'), v: `${price} · VietQR` }])}</div>
    </div>`;
}

/* The closed-order states and the copy key that names each. Only a lapsed QR says nothing was charged: a refunded,
   failed or cancelled order uses its own status line and makes no claim about a charge. */
export const CLOSED_TITLE = Object.freeze({ expired: 'expiredTitle', cancelled: 'statusCancelled', failed: 'statusFailed', refunded: 'statusRefunded' });

function expiredBody(orderState) {
  const key = CLOSED_TITLE[orderState] || CLOSED_TITLE.expired;
  const text = key === 'expiredTitle' ? html`<div class="s-cr-sheet__p s-cr-sheet__p--wide">${t('expiredText')}</div>` : '';
  return html`<div class="s-cr-sheet__center s-cr-sheet__center--expired"><span class="s-cr-sheet__clock">${raw(icon('clock', { size: 26 }))}</span><div class="s-cr-sheet__h s-cr-sheet__h--big">${t(key)}</div>${text}</div>`;
}

/* The sheet for a step. `busy` disables the pay button while a checkout request is in flight (one request per
   intent, product/credit-topup.js createCheckout). */
export function sheetMarkup({ step, total, price, planName = '', qr = '', busy = false, orderState = 'expired', stillWaiting = false }) {
  const titles = { confirm: t('sheetAdd'), qr: t('scanTitle'), received: t('receivedAdding'), done: t('doneTitle'), expired: t(CLOSED_TITLE[orderState] || CLOSED_TITLE.expired) };
  const body = {
    confirm: () => confirmBody({ total, price, planName }),
    qr: () => qrBody({ price, qr, stillWaiting }),
    received: () => receivedBody({ total }),
    done: () => doneBody({ total, price }),
    expired: () => expiredBody(orderState),
  }[step]();
  const busyAttr = raw(busy ? ' disabled aria-busy="true"' : '');
  const foot = {
    confirm: html`<button type="button" class="s-cr-btn s-cr-btn--sec" data-sheet-close>${t('back')}</button><button type="button" class="s-cr-btn s-cr-btn--pri" data-cr-pay${busyAttr}>${t('pay', { price })}</button>`,
    qr: html`<button type="button" class="s-cr-btn s-cr-btn--sec" data-cr-cancel>${t('cancelPayment')}</button>`,
    received: '',
    done: html`<button type="button" class="s-cr-btn s-cr-btn--pri" data-cr-done>${t('done')}</button>`,
    expired: html`<button type="button" class="s-cr-btn s-cr-btn--sec" data-sheet-close>${t('close')}</button><button type="button" class="s-cr-btn s-cr-btn--pri" data-cr-again${busyAttr}>${t('makeNewQr')}</button>`,
  }[step];
  return html`${sheetHead({ title: titles[step], closeLabel: shellCopy('close') })}
    <div class="o-sheet__body s-cr-sheet__body">${body}</div>
    ${foot ? html`<div class="o-sheet__foot s-cr-sheet__foot">${foot}</div>` : ''}`;
}
