/* Credit top-up, learner side: the integration layer only (PR-MON-5 contract). No DOM, no markup, no copy drawn.
   The design draws no top-up frame yet (docs/project/UI_BACKEND_GAPS.md "Credit top-up client"), so nothing here
   reaches a screen; a surface will import these functions when the human supplies the frames.

   Rules this file keeps (the billing lane's binding contract):
   - Credits are a one-time purchase, never a plan, add-on or subscription. Nothing here touches Plus/Pro access.
   - Packs come only from GET /api/billing/offers `credit_packs[]`. No pack, price or unit is written here.
   - A checkout copies price/amount/currency/units from the offer it was given; nothing is computed client-side.
   - The backend decides what is on sale and what succeeded. A return URL, a redirect, a 200 from checkout is never
     "paid". Only the backend's own order status, read by the watcher below, confirms. There is no "I have paid".
   - One purchase intent has one operation id (UUID), reused on every retry, so a retry is idempotent. */

import { newIdempotencyKey } from '../infrastructure/quota-headers.js';

const CREDIT_KEY = /^credits:[a-z0-9][a-z0-9_-]{0,39}:payos$/;

/* ---- offers -------------------------------------------------------------------------------------------------- */

function positiveInt(value) {
  return typeof value === 'number' && Number.isInteger(value) && value > 0;
}

/* One credit pack as the backend serves it, or null when it is not a well-formed pack. Unknown extra fields are kept
   out; a missing one drops the pack rather than inventing it (never a broken card). */
export function parsePack(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const key = typeof raw.key === 'string' ? raw.key : '';
  const currency = typeof raw.currency === 'string' ? raw.currency.trim().toUpperCase() : '';
  if (!CREDIT_KEY.test(key) || key.split(':')[1] !== String(raw.pack_id)) return null;
  if (!positiveInt(raw.credit_units) || !positiveInt(raw.amount_minor) || currency.length !== 3) return null;
  return Object.freeze({
    key, packId: String(raw.pack_id), creditUnits: raw.credit_units, amountMinor: raw.amount_minor, currency,
    gateway: typeof raw.gateway === 'string' ? raw.gateway : 'payos',
  });
}

/* GET /api/billing/offers -> { available, packs }. `available` is the backend's word: true only when the answer says
   billing is ready and at least one well-formed pack came back. An empty list, a gated-off answer, a failed read or a
   malformed body is the normal "unavailable" state, never an error to draw. */
export function parseOffers(payload) {
  const empty = { available: false, enabled: false, ready: false, packs: [] };
  if (!payload || typeof payload !== 'object') return empty;
  const ready = payload.ready === true;
  const seen = new Set();
  const packs = ready && Array.isArray(payload.credit_packs)
    ? payload.credit_packs.map(parsePack).filter((pack) => pack && !seen.has(pack.key) && seen.add(pack.key))
    : [];
  return { available: packs.length > 0, enabled: payload.enabled === true, ready, packs };
}

export async function loadOffers(api) {
  try {
    return parseOffers(await api.billingOffers());
  } catch {
    return parseOffers(null);
  }
}

/* ---- checkout errors ----------------------------------------------------------------------------------------- */

/* What a screen does about a refusal. The code is the backend's `category` (billing_api.py / CheckoutRefused).
   `message` is a key in copy/credit-topup.js, never the backend's sentence.
     retry_same     the same intent may be sent again (same operation id)
     retry_later    nothing the learner can fix now; try again later (same operation id kept)
     refetch        read the offers again and require a fresh confirmation (a new intent)
     resume         an order for this intent already exists: watch it, do not start another
     new_intent     this intent is spent; a new purchase needs a new operation id
     sign_in        the learner is not signed in
     none           final: nothing to retry */
export const CHECKOUT_ERRORS = Object.freeze({
  billing_off: { message: 'errUnavailable', action: 'none' },
  account_backbone_off: { message: 'errUnavailable', action: 'none' },
  account_deleted: { message: 'errAccountClosed', action: 'none' },
  sign_in_required: { message: 'errSignIn', action: 'sign_in' },
  billing_not_ready: { message: 'errTryLater', action: 'retry_later', refetch: true },
  credits_not_ready: { message: 'errTryLater', action: 'retry_later', refetch: true },
  reconciliation_critical: { message: 'errTryLater', action: 'retry_later', refetch: true },
  catalog_unavailable: { message: 'errTryLater', action: 'retry_later', refetch: true },
  price_changed: { message: 'errPriceChanged', action: 'refetch', refetch: true },
  price_unconfirmed: { message: 'errPriceChanged', action: 'refetch', refetch: true },
  price_mismatch: { message: 'errPriceChanged', action: 'refetch', refetch: true },
  price_not_offered: { message: 'errNotOffered', action: 'refetch', refetch: true },
  checkout_already_started: { message: 'errAlreadyStarted', action: 'resume' },
  order_closed: { message: 'errOrderClosed', action: 'new_intent', refetch: true },
  operation_conflict: { message: 'errGeneric', action: 'new_intent', refetch: true },
  operation_id_invalid: { message: 'errGeneric', action: 'new_intent' },
  gateway_unavailable: { message: 'errGatewayUnavailable', action: 'retry_same' },
});

/* The refusal for any thrown request error. An unknown code never leaks its text: it maps to the generic message and
   retries only when the backend said it is retryable. */
export function checkoutRefusal(error) {
  const code = String(error?.category || '');
  const known = CHECKOUT_ERRORS[code];
  if (known) return { code, ...known, refetch: known.refetch === true };
  if (error && typeof error.status === 'number' && error.status === 401) {
    return { code: 'sign_in_required', ...CHECKOUT_ERRORS.sign_in_required, refetch: false };
  }
  const retryable = error?.retryable === true || error?.status === undefined;
  return { code: code || 'unknown', message: 'errGeneric', action: retryable ? 'retry_later' : 'none', refetch: false };
}

/* ---- checkout ------------------------------------------------------------------------------------------------ */

/* The body of POST /api/billing/checkout, every value copied from the offer. */
export function checkoutBody(pack, operationId) {
  return {
    price: pack.key, operation_id: operationId, amount_minor: pack.amountMinor, currency: pack.currency,
    credit_units: pack.creditUnits,
  };
}

function safeRedirect(url) {
  try {
    const parsed = new URL(String(url));
    return parsed.protocol === 'https:' ? parsed.href : '';
  } catch {
    return '';
  }
}

/* One purchase at a time. `start(pack)` is safe to call twice: while a request is in flight the second call returns
   the first one's promise (no double submit), and an intent keeps its operation id across retries until the backend
   says it is spent (new_intent / refetch) or the checkout opened. `newId` is injectable for tests. */
export function createCheckout({ api, newId = newIdempotencyKey } = {}) {
  let intent = null; // { key, operationId }
  let inFlight = null;
  let state = 'idle'; // idle | starting | redirected | refused

  function intentFor(pack) {
    if (!intent || intent.key !== pack.key) intent = { key: pack.key, operationId: newId() };
    return intent;
  }

  async function run(pack) {
    const current = intentFor(pack);
    state = 'starting';
    try {
      const answer = await api.billingCheckout(checkoutBody(pack, current.operationId));
      const redirectUrl = safeRedirect(answer?.redirect_url);
      const orderCode = Number(answer?.order_code);
      if (!redirectUrl || !Number.isSafeInteger(orderCode)) {
        state = 'refused';
        return { ok: false, refusal: { code: 'gateway_unavailable', ...CHECKOUT_ERRORS.gateway_unavailable, refetch: false } };
      }
      state = 'redirected';
      /* Opened: the operation id stays with the intent so the order can still be watched; a new purchase calls reset(). */
      return { ok: true, redirectUrl, qr: typeof answer.qr === 'string' ? answer.qr : '', orderCode, operationId: current.operationId };
    } catch (error) {
      const refusal = checkoutRefusal(error);
      state = 'refused';
      if (refusal.action === 'new_intent' || refusal.action === 'refetch') intent = null;
      return { ok: false, refusal, operationId: current.operationId };
    }
  }

  return {
    get state() { return state; },
    get operationId() { return intent ? intent.operationId : null; },
    start(pack) {
      if (!pack || !pack.key) return Promise.resolve({ ok: false, refusal: checkoutRefusal({ category: 'price_not_offered' }) });
      if (inFlight) return inFlight;
      inFlight = run(pack).finally(() => { inFlight = null; });
      return inFlight;
    },
    reset() { intent = null; state = 'idle'; },
  };
}

/* ---- the return from the payment page ------------------------------------------------------------------------ */

/* payOS sends the learner back with query parameters (`status=PAID`, `code=00`, ...). They are the learner's browser
   talking: they prove nothing. Whatever they say, the answer is "waiting for the backend". */
export function interpretReturn() {
  return Object.freeze({ state: 'waiting', confirmed: false });
}

/* ---- order status -> state ----------------------------------------------------------------------------------- */

/* The learner-visible states of a purchase. `confirmed` only from the backend: an order that is `paid` AND whose
   credit has been applied. `paid` alone is still waiting (the webhook marks the order; the credit is applied after).
   The status payload's shape is not served yet (UI_BACKEND_GAPS CT-1); this reads the shape that gap proposes:
   { state: <order state>, credited: boolean }. */
export const ORDER_TERMINAL = Object.freeze(['confirmed', 'expired', 'cancelled', 'failed', 'refunded']);

export function orderStateFrom(status) {
  const state = String(status?.state || '');
  if (state === 'paid') return status.credited === true ? 'confirmed' : 'received'; // money seen, credits not yet added
  if (state === 'refunded') return 'refunded';
  if (state === 'expired' || state === 'cancelled' || state === 'failed') return state;
  return 'waiting'; // created, pending, unknown, missing: the backend has not said otherwise
}

export const WATCH_DEFAULTS = Object.freeze({ firstDelayMs: 2000, factor: 1.6, maxDelayMs: 15000, maxAttempts: 40 });

/* Polls `readStatus()` (a function the screen supplies once a status endpoint exists) with backoff and a cap, and
   stops on a terminal state. Reaching the cap is `still_waiting`, never a failure and never a success: the backend
   still credits exactly once when payment is confirmed. `sleep` and `onState` are injectable. */
export async function watchOrder({ readStatus, onState = () => {}, sleep = (ms) => new Promise((r) => setTimeout(r, ms)),
  options = {}, shouldStop = () => false } = {}) {
  const { firstDelayMs, factor, maxDelayMs, maxAttempts } = { ...WATCH_DEFAULTS, ...options };
  let delay = firstDelayMs;
  let last = 'waiting';
  onState(last);
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    if (shouldStop()) return { state: last, stopped: true, attempts: attempt - 1 };
    await sleep(delay);
    delay = Math.min(maxDelayMs, Math.round(delay * factor));
    if (shouldStop()) return { state: last, stopped: true, attempts: attempt - 1 };
    let next = last;
    try {
      next = orderStateFrom(await readStatus());
    } catch (error) {
      if (error?.status === 401 || error?.status === 403) return { state: last, stopped: true, reason: 'auth', attempts: attempt };
      if (error?.status === 404) return { state: last, stopped: true, reason: 'missing', attempts: attempt };
      /* A failed read tells nothing about the payment: keep waiting. */
    }
    if (next !== last) { last = next; onState(last); }
    if (ORDER_TERMINAL.includes(last)) return { state: last, stopped: false, attempts: attempt };
  }
  return { state: 'still_waiting', stopped: false, attempts: maxAttempts };
}

/* ---- history ------------------------------------------------------------------------------------------------- */

/* The four learner words for a ledger entry's kind (copy keys). Holds that the learner never made a decision about
   (reserve, release, reserve_expire) have no row; `reversal` (a top-up taken back) reads as a refund. */
const HISTORY_LABELS = Object.freeze({
  topup: 'historyBuy', settle: 'historyUse', refund: 'historyRefund', reversal: 'historyRefund', adjustment: 'historyAdjust',
});

export function historyLabelKey(kind) {
  return Object.prototype.hasOwnProperty.call(HISTORY_LABELS, kind) ? HISTORY_LABELS[kind] : null;
}

/* Rows for a learner: a label key, the signed change in credits and the time. Nothing else of the entry (kind, source,
   reason, actor, reserved amount, references) is passed on. */
export function historyRows(entries) {
  return (Array.isArray(entries) ? entries : []).flatMap((entry) => {
    const labelKey = historyLabelKey(entry?.kind);
    const change = Number(entry?.posted_delta);
    if (!labelKey || !Number.isFinite(change) || change === 0) return [];
    return [{ labelKey, change, at: typeof entry.created_at === 'string' ? entry.created_at : '' }];
  });
}
