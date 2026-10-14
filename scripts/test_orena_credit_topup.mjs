/* Gate for the credit top-up client layer (static/orena/product/credit-topup.js, copy/credit-topup.js, api.js
   billingOffers/billingCheckout). Stubbed fetch/api only; no network, no DOM. */
import assert from 'node:assert/strict';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const m = await import('../static/orena/product/credit-topup.js');
const copy = await import('../static/orena/copy/index.js');
const { t } = await import('../static/orena/copy/credit-topup.js');

let checks = 0;
const ok = (value, message) => { assert.ok(value, message); checks += 1; };
const eq = (a, b, message) => { assert.deepEqual(a, b, message); checks += 1; };

const PACK = { key: 'credits:starter:payos', pack_id: 'starter', credit_units: 1234, currency: 'VND', amount_minor: 56789, gateway: 'payos' };
const PACK2 = { key: 'credits:big_1:payos', pack_id: 'big_1', credit_units: 99, currency: 'VND', amount_minor: 4321, gateway: 'payos' };
const READY = (packs) => ({ enabled: true, ready: true, offers: [], credit_packs: packs });
const err = (category, status = 409, extra = {}) => Object.assign(new Error('raw backend words'), { category, status, ...extra });

/* --- offers ---------------------------------------------------------------------------------------------- */
{
  const empty = m.parseOffers(READY([]));
  eq([empty.available, empty.packs], [false, []], 'empty packs is the normal unavailable state');
  eq(m.parseOffers(READY(undefined)).available, false);
  eq(m.parseOffers({ enabled: true, ready: false, offers: [], credit_packs: [PACK] }).packs, [], 'gated off: packs ignored even if present');
  eq(m.parseOffers({ enabled: false, ready: false, offers: [], credit_packs: [] }).available, false);
  for (const bad of [null, undefined, 'x', 5, [], {}]) eq(m.parseOffers(bad).available, false, 'malformed body is unavailable');
  const mixed = m.parseOffers(READY([PACK, null, 'x', { ...PACK2, credit_units: 0 }, { ...PACK2, amount_minor: 1.5 }, { ...PACK2, currency: 'VN' },
    { ...PACK2, key: 'credits:other:payos' }, { ...PACK2, key: 'plus:month:payos' }, PACK, { ...PACK2, extra: 'ignored' }]));
  eq(mixed.packs.map((p) => p.key), [PACK.key, PACK2.key], 'malformed and duplicate packs are dropped, valid ones kept in order');
  eq([mixed.packs[0].creditUnits, mixed.packs[0].amountMinor, mixed.packs[0].currency], [1234, 56789, 'VND']);
  ok(!('extra' in mixed.packs[1]), 'unknown fields are not carried');
  const failing = await m.loadOffers({ billingOffers: async () => { throw err('billing_off', 503); } });
  eq(failing.available, false, 'a failed read is unavailable, not thrown');
  eq((await m.loadOffers({ billingOffers: async () => READY([PACK]) })).packs.length, 1);
}

/* --- checkout payload and idempotency -------------------------------------------------------------------- */
{
  const sent = [];
  const api = { billingCheckout: async (body) => { sent.push(body); return { redirect_url: 'https://pay.example/checkout/1', qr: 'QR', order_code: 77, gateway: 'payos' }; } };
  const ids = ['11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222'];
  const checkout = m.createCheckout({ api, newId: () => ids.shift() });
  const [pack] = m.parseOffers(READY([PACK])).packs;
  const result = await checkout.start(pack);
  eq(sent[0], { price: 'credits:starter:payos', operation_id: '11111111-1111-4111-8111-111111111111', amount_minor: 56789, currency: 'VND', credit_units: 1234 }, 'payload is exactly the offer plus the id');
  eq(Object.keys(sent[0]).sort(), ['amount_minor', 'credit_units', 'currency', 'operation_id', 'price'], 'no extra fields');
  ok(result.ok && result.redirectUrl === 'https://pay.example/checkout/1' && result.orderCode === 77 && result.qr === 'QR');
  await checkout.start(pack);
  eq(sent[1].operation_id, sent[0].operation_id, 'a repeat of the same intent reuses the operation id');
  eq(m.checkoutBody(pack, 'x').credit_units, 1234);

  /* A different pack is a different intent. */
  const [, other] = m.parseOffers(READY([PACK, PACK2])).packs;
  await checkout.start(other);
  ok(sent[2].operation_id !== sent[0].operation_id && sent[2].price === 'credits:big_1:payos');
}
{
  /* Retry after a gateway failure reuses the id; a non-https or incomplete answer is not a link. */
  const sent = []; let calls = 0;
  const api = { billingCheckout: async (body) => { sent.push(body.operation_id); calls += 1; if (calls === 1) throw err('gateway_unavailable', 502, { retryable: true }); return { redirect_url: 'https://pay.example/x', order_code: 5 }; } };
  const checkout = m.createCheckout({ api, newId: () => 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' });
  const [pack] = m.parseOffers(READY([PACK])).packs;
  const first = await checkout.start(pack);
  eq([first.ok, first.refusal.action, first.refusal.message], [false, 'retry_same', 'errGatewayUnavailable']);
  const second = await checkout.start(pack);
  ok(second.ok); eq(sent[0], sent[1], 'retry reuses the operation id');

  for (const bad of [{ redirect_url: 'http://insecure.example', order_code: 1 }, { redirect_url: 'javascript:alert(1)', order_code: 1 }, { order_code: 1 }, { redirect_url: 'https://p.example' }, null]) {
    const c = m.createCheckout({ api: { billingCheckout: async () => bad } });
    const r = await c.start(pack);
    eq([r.ok, r.refusal.code], [false, 'gateway_unavailable'], 'an answer without a safe link and an order is a failed checkout');
  }
}
{
  /* Double submit: one request in flight, the second call shares it. */
  let release; let calls = 0;
  const api = { billingCheckout: () => { calls += 1; return new Promise((resolve) => { release = () => resolve({ redirect_url: 'https://p.example/a', order_code: 9 }); }); } };
  const checkout = m.createCheckout({ api });
  const [pack] = m.parseOffers(READY([PACK])).packs;
  const a = checkout.start(pack); const b = checkout.start(pack); const c = checkout.start(pack);
  eq(checkout.state, 'starting');
  release();
  const results = await Promise.all([a, b, c]);
  eq(calls, 1, 'double submit sends one request'); ok(results.every((r) => r.ok));
  eq(checkout.state, 'redirected');
  eq((await m.createCheckout({ api }).start(null)).refusal.code, 'price_not_offered', 'no pack, no request');
}

/* --- error codes ----------------------------------------------------------------------------------------- */
{
  const EXPECT = {
    billing_off: ['errUnavailable', 'none'], account_backbone_off: ['errUnavailable', 'none'], account_deleted: ['errAccountClosed', 'none'],
    sign_in_required: ['errSignIn', 'sign_in'], billing_not_ready: ['errTryLater', 'retry_later'], credits_not_ready: ['errTryLater', 'retry_later'],
    reconciliation_critical: ['errTryLater', 'retry_later'], catalog_unavailable: ['errTryLater', 'retry_later'],
    price_changed: ['errPriceChanged', 'refetch'], price_unconfirmed: ['errPriceChanged', 'refetch'], price_mismatch: ['errPriceChanged', 'refetch'],
    price_not_offered: ['errNotOffered', 'refetch'], checkout_already_started: ['errAlreadyStarted', 'resume'], order_closed: ['errOrderClosed', 'new_intent'],
    operation_conflict: ['errGeneric', 'new_intent'], operation_id_invalid: ['errGeneric', 'new_intent'], gateway_unavailable: ['errGatewayUnavailable', 'retry_same'],
  };
  for (const [code, [message, action]] of Object.entries(EXPECT)) {
    const refusal = m.checkoutRefusal(err(code));
    eq([refusal.code, refusal.message, refusal.action], [code, message, action], `${code} maps`);
    ok(t.has(message), `${code}: message key ${message} exists in copy`);
    for (const locale of ['en', 'vi', 'zh']) ok(copy.registeredCopy().get('creditTopup').packs[locale][message], `${message} in ${locale}`);
    ok(!/raw backend/.test(JSON.stringify(refusal)), 'the backend sentence never travels');
  }
  /* Unknown code: generic message; retry only when the backend says so. */
  eq(m.checkoutRefusal(err('brand_new_code', 500, { retryable: false })).action, 'none');
  eq(m.checkoutRefusal(err('brand_new_code', 503, { retryable: true })).action, 'retry_later');
  eq(m.checkoutRefusal(err('brand_new_code', 500)).message, 'errGeneric');
  eq(m.checkoutRefusal(new TypeError('network down')).action, 'retry_later', 'a network failure retries later');
  eq(m.checkoutRefusal(Object.assign(new Error('x'), { status: 401 })).action, 'sign_in');
  for (const code of ['price_changed', 'billing_not_ready', 'price_not_offered', 'order_closed']) ok(m.checkoutRefusal(err(code)).refetch, `${code} refetches offers`);
  ok(!m.checkoutRefusal(err('gateway_unavailable')).refetch && !m.checkoutRefusal(err('checkout_already_started')).refetch);

  /* Operation id lifecycle by refusal. */
  const run = async (category) => {
    let n = 0; const sent = [];
    const api = { billingCheckout: async (b) => { sent.push(b.operation_id); if (sent.length === 1) throw err(category); return { redirect_url: 'https://p.example/z', order_code: 1 }; } };
    const c = m.createCheckout({ api, newId: () => `id-${++n}` });
    const [pack] = m.parseOffers(READY([PACK])).packs;
    await c.start(pack); await c.start(pack);
    return sent;
  };
  eq(await run('gateway_unavailable'), ['id-1', 'id-1'], 'retryable gateway failure keeps the id');
  eq(await run('billing_not_ready'), ['id-1', 'id-1'], 'later-retry keeps the id');
  eq(await run('checkout_already_started'), ['id-1', 'id-1'], 'already started keeps the id so the same order is watched');
  eq(await run('price_changed'), ['id-1', 'id-2'], 'price changed needs a fresh intent after re-confirmation');
  eq(await run('order_closed'), ['id-1', 'id-2'], 'a closed order needs a new intent');
}

/* --- return URL never yields success --------------------------------------------------------------------- */
{
  for (const arg of [undefined, '?status=PAID&code=00&cancel=false', { status: 'PAID', code: '00' }, 'https://x.example/#/profile?status=PAID']) {
    const r = m.interpretReturn(arg);
    eq([r.state, r.confirmed], ['waiting', false], 'a return is always waiting');
  }
  eq(m.orderStateFrom({ state: 'pending', status: 'PAID', credited: true }), 'waiting', 'payOS words in the payload mean nothing');
}

/* --- pending -> confirmed only on backend terminal status ------------------------------------------------ */
{
  eq(m.orderStateFrom({ state: 'paid', credited: true }), 'confirmed');
  eq(m.orderStateFrom({ state: 'paid', credited: false }), 'waiting', 'paid but not yet credited is still waiting');
  eq(m.orderStateFrom({ state: 'paid' }), 'waiting');
  for (const s of ['expired', 'cancelled', 'failed', 'refunded']) eq(m.orderStateFrom({ state: s }), s);
  for (const s of [null, undefined, {}, { state: 'created' }, { state: 'pending' }, { state: 'whatever' }]) eq(m.orderStateFrom(s), 'waiting');

  const run = async (answers, options = {}) => {
    const seen = []; const slept = []; let i = 0;
    const result = await m.watchOrder({
      readStatus: async () => { const a = answers[Math.min(i++, answers.length - 1)]; if (a instanceof Error) throw a; return a; },
      onState: (s) => seen.push(s), sleep: async (ms) => { slept.push(ms); }, options,
    });
    return { result, seen, slept, reads: i };
  };
  let r = await run([{ state: 'pending' }, { state: 'pending' }, { state: 'paid', credited: false }, { state: 'paid', credited: true }]);
  eq([r.result.state, r.reads, r.seen], ['confirmed', 4, ['waiting', 'confirmed']], 'confirmed only when the backend says credited; polling stops');
  r = await run([{ state: 'pending' }, { state: 'expired' }]);
  eq([r.result.state, r.reads], ['expired', 2], 'a terminal non-success stops too');
  r = await run([{ state: 'pending' }], { maxAttempts: 5 });
  eq([r.result.state, r.reads], ['still_waiting', 5], 'the cap ends in still_waiting, never success or failure');
  eq(r.slept, [2000, 3200, 5120, 8192, 13107], 'backoff grows');
  r = await run([{ state: 'pending' }], { maxAttempts: 12 });
  ok(Math.max(...r.slept) === 15000, 'backoff is capped');
  r = await run([new TypeError('offline'), new TypeError('offline'), { state: 'paid', credited: true }]);
  eq(r.result.state, 'confirmed', 'a failed read is not a verdict; polling continues');
  r = await run([Object.assign(new Error('x'), { status: 401 })]);
  eq([r.result.stopped, r.reads], [true, 1], 'a 401 stops polling');
  let stop = false; let reads = 0;
  const stopped = await m.watchOrder({ readStatus: async () => { reads += 1; return { state: 'pending' }; }, sleep: async () => { if (reads >= 2) stop = true; }, shouldStop: () => stop });
  ok(stopped.stopped && reads <= 3, 'a screen can stop the watch');
}

/* --- history labels hide backend terms ------------------------------------------------------------------- */
{
  const entries = [
    { kind: 'topup', posted_delta: 500, reserved_delta: 0, reason: 'reconciliation shortfall', source_type: 'billing_order', created_at: '2026-10-01T00:00:00Z' },
    { kind: 'settle', posted_delta: -20, reserved_delta: -20, meter: 'orena.message', created_at: '2026-10-02T00:00:00Z' },
    { kind: 'refund', posted_delta: 5, created_at: '2026-10-03T00:00:00Z' },
    { kind: 'reversal', posted_delta: -500, reversal_request_id: 'r', created_at: '2026-10-04T00:00:00Z' },
    { kind: 'adjustment', posted_delta: 10, actor: 'admin', reason: 'ledger fix', created_at: '2026-10-05T00:00:00Z' },
    { kind: 'reserve', posted_delta: 0, reserved_delta: 20 },
    { kind: 'release', posted_delta: 0, reserved_delta: -20 },
    { kind: 'reserve_expire', posted_delta: 0, reserved_delta: -20 },
    { kind: 'mystery', posted_delta: 3 }, null, 'x',
  ];
  const rows = m.historyRows(entries);
  eq(rows.map((x) => x.labelKey), ['historyBuy', 'historyUse', 'historyRefund', 'historyRefund', 'historyAdjust'], 'four learner labels; internal holds and unknown kinds have no row');
  eq(Object.keys(rows[0]).sort(), ['at', 'change', 'labelKey'], 'only label, change and time are passed on');
  eq(m.historyRows(undefined), []);
  const banned = /ledger|reserve|settle|reversal|reconcil|shortfall|release|topup|adjustment/i;
  ok(!banned.test(JSON.stringify(rows)), 'no backend term in the rows');
  const pack = copy.registeredCopy().get('creditTopup').packs;
  for (const locale of ['en', 'vi', 'zh']) {
    for (const [key, text] of Object.entries(pack[locale])) ok(!banned.test(text), `${locale}.${key} has no backend term`);
  }
  eq([pack.en.historyBuy, pack.en.historyUse, pack.en.historyRefund, pack.en.historyAdjust], ['Buy credits', 'Use credits', 'Refund credits', 'Adjust credits']);
  eq([pack.vi.historyBuy, pack.vi.historyUse, pack.vi.historyRefund, pack.vi.historyAdjust], ['Mua Credits', 'Dùng Credits', 'Hoàn Credits', 'Điều chỉnh Credits']);
}

/* --- the shared client calls the contract's routes ------------------------------------------------------- */
{
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push([url, options.method || 'GET', options.body || null]);
    return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => READY([PACK]) };
  };
  globalThis.location = { href: '' };
  const { api } = await import('../static/orena/infrastructure/api.js');
  await api.billingOffers();
  await api.billingCheckout({ price: PACK.key });
  eq(calls[0].slice(0, 2), ['/api/billing/offers', 'GET']);
  eq(calls[1].slice(0, 2), ['/api/billing/checkout', 'POST']);
  eq(JSON.parse(calls[1][2]), { price: PACK.key });
}

console.log(`Orena credit top-up client: ${checks} checks: PASS`);
