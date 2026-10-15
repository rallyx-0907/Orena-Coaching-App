/* Gate for Credits, Credits Payment and the Plan & usage Credits card (static/orena/screens/credits, screens/plan,
   the Profile row). Rule 40: only what the backend offers is drawn; the design's sample packs, bonuses and prices are
   never shipped; no "I have paid" control; the sheet follows the backend's order state; credits are never a plan. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const model = await import('../static/orena/screens/credits/model.js');
const { creditsMarkup } = (await import('../static/orena/screens/credits/screen.js')).__internal;
const { sheetMarkup, qrMatrix } = await import('../static/orena/screens/credits/sheet.js');
const { billingMarkup } = (await import('../static/orena/screens/plan/screen.js')).__internal;
const { profileActions } = await import('../static/orena/screens/profile/model.js');
const { parseOffers } = await import('../static/orena/product/credit-topup.js');
const copy = await import('../static/orena/copy/index.js');
const { ROUTES, byId } = await import('../static/orena/shell/routes.js');
const { SCREENS } = await import('../static/orena/shell/screens.js');

let checks = 0;
const ok = (value, message) => { assert.ok(value, message); checks += 1; };
const eq = (a, b, message) => { assert.deepEqual(a, b, message); checks += 1; };

const PACKS = parseOffers({ enabled: true, ready: true, offers: [], credit_packs: [
  { key: 'credits:aa:payos', pack_id: 'aa', credit_units: 1111, currency: 'VND', amount_minor: 22222, gateway: 'payos' },
  { key: 'credits:bb:payos', pack_id: 'bb', credit_units: 3333, currency: 'VND', amount_minor: 44444, gateway: 'payos' },
] }).packs;
const SAMPLE = /49[.,]000|119[.,]000|279[.,]000|649[.,]000|\b300\b|\b800\b|2[.,]000 Credits|5[.,]000 Credits|Most chosen|Chọn nhiều nhất|bonus|thưởng|calis@orena/;
const base = (extra = {}) => ({ packs: PACKS, selectedKey: '', strip: { id: 'plus', name: 'Plus' }, pending: null, filter: 'all', rows: [], ...extra });

/* --- model ----------------------------------------------------------------------------------------------- */
{
  eq(model.formatPrice(22222, 'VND', 'en'), '22.222 ₫', 'the design writes a dong price with dots and the dong sign');
  eq(model.formatPrice(22222, 'VND', 'zh'), '22.222 ₫');
  ok(/1,234/.test(model.formatPrice(1234, 'USD', 'en')), 'another currency is formatted by the browser');
  eq(model.packCards(PACKS, 'credits:bb:payos', 'en').map((c) => [c.total, c.price, c.selected]), [['1,111', '22.222 ₫', false], ['3,333', '44.444 ₫', true]]);
  eq(model.packCards(PACKS, 'gone', 'vi').map((c) => c.selected), [true, false], 'an unknown pick falls back to the first pack');
  eq(model.packCards(PACKS, '', 'vi')[0].total, '1.111', 'vi groups with dots');
  eq(model.packCards([], '', 'en'), []);
  eq(model.selectedPack([], 'x'), null);
  eq(model.planStrip({ available: true, plan: { id: 'plus', name: 'Plus' } }), { id: 'plus', name: 'Plus' });
  eq(model.planStrip({ available: false }), null);
  eq(model.planStrip(null), null);
  eq(model.filterHistory([{ change: 5 }, { change: -2 }], 'in'), [{ change: 5 }]);
  eq(model.filterHistory([{ change: 5 }, { change: -2 }], 'out'), [{ change: -2 }]);
  eq(model.filterHistory([{ change: 5 }, { change: -2 }], 'all').length, 2);
  eq(model.sheetStep({ order: null, orderState: 'waiting' }), 'confirm');
  eq(model.sheetStep({ order: {}, orderState: 'waiting' }), 'qr');
  eq(model.sheetStep({ order: {}, orderState: 'received' }), 'received');
  eq(model.sheetStep({ order: {}, orderState: 'confirmed' }), 'done');
  for (const s of ['expired', 'cancelled', 'failed', 'refunded']) eq(model.sheetStep({ order: {}, orderState: s }), 'expired');
  /* roving radio group (WAI-ARIA): arrows move and wrap, Home/End jump */
  const keys = PACKS.map((p) => p.key);
  eq(model.nextPackKey(PACKS, keys[0], 'ArrowRight'), keys[1]);
  eq(model.nextPackKey(PACKS, keys[0], 'ArrowDown'), keys[1]);
  eq(model.nextPackKey(PACKS, keys[1], 'ArrowRight'), keys[0], 'wraps forward');
  eq(model.nextPackKey(PACKS, keys[0], 'ArrowLeft'), keys[1], 'wraps back');
  eq(model.nextPackKey(PACKS, keys[1], 'ArrowUp'), keys[0]);
  eq(model.nextPackKey(PACKS, keys[1], 'Home'), keys[0]);
  eq(model.nextPackKey(PACKS, keys[0], 'End'), keys[1]);
  eq(model.nextPackKey(PACKS, keys[0], 'Tab'), null, 'other keys are not handled');
  eq(model.nextPackKey([], '', 'ArrowRight'), null);
  /* the watcher ends on a still-waiting line, never silently */
  eq(model.watchEndsStillWaiting({ state: 'still_waiting', stopped: false }), true, 'cap reached');
  eq(model.watchEndsStillWaiting({ state: 'waiting', stopped: true, reason: 'missing' }), true, '404 from the order route');
  eq(model.watchEndsStillWaiting({ state: 'confirmed', stopped: false }), false, 'terminal');
  eq(model.watchEndsStillWaiting({ state: 'expired', stopped: false }), false, 'terminal');
  eq(model.watchEndsStillWaiting({ state: 'waiting', stopped: true }), false, 'retired by the screen');
  eq(model.watchEndsStillWaiting({ state: 'waiting', stopped: true, reason: 'auth' }), false, 'signed out');
  /* focus returns to the control that opened the sheet, after the screen re-mounted */
  const root = (have) => ({ querySelector: (sel) => (have.includes(sel) ? { sel } : null) });
  eq(model.sheetReturnTarget(root(['[data-cr-show]', '[data-cr-continue]'])).sel, '[data-cr-show]', 'banner up: Show QR');
  eq(model.sheetReturnTarget(root(['[data-cr-continue]'])).sel, '[data-cr-continue]');
  eq(model.sheetReturnTarget(root([])), null);
  eq(model.qrPath(3, (r, c) => r === c), 'M0 0h1v1h-1zM1 1h1v1h-1zM2 2h1v1h-1z');
  eq(model.qrPath(2, () => true), 'M0 0h2v1h-2zM0 1h2v1h-2z', 'runs are merged');
}

/* --- routes, entry points --------------------------------------------------------------------------------- */
{
  const route = byId('credits');
  ok(route && route.focus === true && route.screen === 'credits' && route.design === 'credits', 'Credits is a focus route of the design');
  ok(typeof SCREENS.credits === 'function', 'the screen is registered');
  eq(profileActions({}).some((a) => a.id === 'credits'), false, 'no Credits row while nothing is on sale');
  eq(profileActions({ credits: true }).map((a) => a.id).slice(3, 5), ['plan', 'credits'], 'the row follows Plan & usage');
  ok(ROUTES.every((r) => r.id !== 'credits' || r.path === 'credits'));
}

/* --- Credits ---------------------------------------------------------------------------------------------- */
for (const locale of ['en', 'vi', 'zh']) {
  copy.setLanguages({ ui: locale, support: locale });
  const markup = String(creditsMarkup(base()));
  eq((markup.match(/data-cr-pack="/g) || []).length, 2, 'one card per backend pack, no more');
  ok(markup.includes('data-cr-pack="credits:aa:payos"') && markup.includes('data-cr-pack="credits:bb:payos"'));
  ok(!SAMPLE.test(markup), `${locale}: no sample content of the design`);
  ok(markup.includes('role="radiogroup"') && (markup.match(/aria-checked="true"/g) || []).length === 1, 'exactly one pack is selected');
  ok(markup.includes('s-cr-hero__num">—<'), 'the balance is unavailable, never a made-up zero');
  ok(!/paid|đã trả|我已付款|I.ve paid|đã thanh toán xong/i.test(markup.replace(/s-cr-[a-z_-]+/g, '')), 'no "I have paid" control');
  ok(!/crown|plan-pill|Pro\b/.test(markup), 'Credits are not styled as a plan');
  ok(!/<[^>]*s-cr-pack__benefit|s-cr-pack__tag/.test(markup), 'no bonus line or tag the backend cannot supply');
  ok(markup.includes('data-cr-continue') && markup.includes('data-cr-add'));
  ok(markup.includes('data-cr-filter="all"'), 'history filters are drawn');
  ok(markup.includes('s-cr-empty'), 'the drawn empty history');
}
copy.setLanguages({ ui: 'en', support: 'en' });
{
  const markup = String(creditsMarkup(base({ strip: null })));
  ok(!markup.includes('s-cr-strip__mark'), 'no plan cell when the plan is unknown');
  const pending = String(creditsMarkup(base({ pending: { price: '22.222 ₫', total: '1,111' } })));
  ok(pending.includes('data-cr-show') && pending.includes('22.222 ₫') && pending.includes('Waiting for payment confirmation') && !pending.includes('Waiting for your transfer'), 'pending banner from the order in hand, in the owner wording');
  ok(String(creditsMarkup(base({ pending: { price: '22.222 ₫', total: '1,111', stillWaiting: true } }))).includes('Still waiting.'), 'pending banner after the cap');
  copy.setLanguages({ ui: 'vi', support: 'vi' });
  ok(String(creditsMarkup(base({ pending: { price: '22.222 ₫', total: '1,111' } }))).includes('Đang chờ xác nhận thanh toán'), 'vi pending wording is the owner-mandated one');
  copy.setLanguages({ ui: 'en', support: 'en' });
  ok(!String(creditsMarkup(base())).includes('data-cr-show'));
  const rows = String(creditsMarkup(base({ rows: [{ labelKey: 'historyBuy', change: 5, at: '' }], filter: 'out' })));
  ok(rows.includes('s-cr-empty'), 'a filter with no rows shows the empty state');
}
/* --- history rows, per language ------------------------------------------------------------------------------ */
{
  const fixture = [
    { labelKey: 'historyBuy', change: 1111, at: '2026-10-14T08:30:00Z' },
    { labelKey: 'historyUse', change: -25, at: '2026-10-13T08:30:00Z' },
    { labelKey: 'historyRefund', change: 25, at: '' },
    { labelKey: 'historyAdjust', change: -5, at: 'not a date' },
  ];
  const words = { en: ['Buy credits', 'Use credits', 'Refund credits', 'Adjust credits'], zh: ['购买 Credits', '使用 Credits', '退还 Credits', '调整 Credits'], vi: ['Mua Credits', 'Dùng Credits', 'Hoàn Credits', 'Điều chỉnh Credits'] };
  for (const locale of ['en', 'vi', 'zh']) {
    copy.setLanguages({ ui: locale, support: locale });
    const all = String(creditsMarkup(base({ rows: fixture })));
    eq((all.match(/class="s-cr-hrow"/g) || []).length, 4, `${locale}: one row per entry`);
    ok(!all.includes('s-cr-empty'), `${locale}: rows replace the empty state`);
    for (const word of words[locale] || []) ok(all.includes(word), `${locale}: ${word}`);
    ok(all.includes('+1') && all.includes('−25') && all.includes('−5'), `${locale}: signed amounts`);
    ok(all.includes('s-cr-hrow__amt--pos'), 'credits in are marked');
    const out = String(creditsMarkup(base({ rows: fixture, filter: 'out' })));
    eq((out.match(/class="s-cr-hrow"/g) || []).length, 2, `${locale}: the Used filter keeps outgoing rows`);
    ok(!/undefined|NaN|Invalid/.test(all), `${locale}: no raw value for a missing or bad time`);
  }
  copy.setLanguages({ ui: 'en', support: 'en' });
  ok(String(creditsMarkup(base({ rows: fixture }))).includes('+1,111'), 'amount grouped for the language');
}
/* --- pack radio group: roving tabindex -------------------------------------------------------------------------- */
{
  const markup = String(creditsMarkup(base({ selectedKey: 'credits:bb:payos' })));
  const tabs = [...markup.matchAll(/data-cr-pack="([^"]+)"/g)].map((m) => {
    const tag = markup.slice(markup.lastIndexOf('<button', m.index), m.index);
    return [m[1], /tabindex="(-?\d)"/.exec(tag)?.[1]];
  });
  eq(tabs, [['credits:aa:payos', '-1'], ['credits:bb:payos', '0']], 'only the selected pack is a tab stop');
}

/* --- Credits Payment --------------------------------------------------------------------------------------- */
{
  const model0 = { total: '1,111', price: '22.222 ₫', planName: 'Plus', qr: '' };
  const confirm = String(sheetMarkup({ ...model0, step: 'confirm' }));
  ok(confirm.includes('data-cr-pay') && confirm.includes('Pay 22.222 ₫') && confirm.includes('Plus · unchanged') && confirm.includes('Pay today'));
  ok(!confirm.includes('Balance after'), 'the balance-after row needs a balance the backend does not serve yet');
  ok(String(sheetMarkup({ ...model0, step: 'confirm', busy: true })).includes('data-cr-pay disabled aria-busy="true"'), 'double submit is disabled while the request is in flight');
  ok(!String(sheetMarkup({ ...model0, step: 'confirm', planName: '' })).includes('unchanged'), 'no plan row without a plan');

  const payos = '00020101021238570010A000000727012700069704220113VQRQ000abc1234520400005303704540510000580270';
  const m = qrMatrix(payos);
  ok(m.size >= 21 && m.size % 4 === 1 && m.path.startsWith('M'), 'a real QR matrix of the payment string');
  eq(qrMatrix(payos).path, m.path, 'deterministic');
  ok(qrMatrix('another payment').path !== m.path, 'different strings give different codes');
  const qr = String(sheetMarkup({ ...model0, step: 'qr', qr: payos }));
  ok(qr.includes(`viewBox="0 0 ${m.size} ${m.size}"`) && qr.includes('Waiting for payment confirmation') && qr.includes('data-cr-cancel'));
  ok(!qr.includes('Waiting for your transfer'), 'owner wording: the pending state reads "waiting for payment confirmation", not "waiting for your transfer"');
  ok(String(sheetMarkup({ ...model0, step: 'qr', qr: payos, stillWaiting: true })).includes('Still waiting. Credits are added once the payment is confirmed.'), 'after the cap the sheet says still waiting');
  ok(!/Transfer note|Copy|15:00|Let this QR expire|Prototype|simulated/i.test(qr), 'no timer, transfer note or prototype affordance');
  ok(!/data-cr-(paid|confirm|done)/.test(qr) && !/I.ve paid|I have paid/i.test(qr), 'the QR step offers no way to say "paid"');
  ok(qr.includes('data-cr-anim="1"'), 'animations are tagged so reduced motion stops them');

  const received = String(sheetMarkup({ ...model0, step: 'received' }));
  ok(received.includes('Payment received') && received.includes('Adding 1,111 Credits') && !received.includes('s-cr-sheet__foot'), 'received: no controls');
  const done = String(sheetMarkup({ ...model0, step: 'done' }));
  ok(done.includes('+1,111 Credits') && done.includes('22.222 ₫ · VietQR') && done.includes('data-cr-done'));
  ok(!/New balance|Receipt|@/.test(done), 'no balance or receipt the backend does not serve');
  const expired = String(sheetMarkup({ ...model0, step: 'expired' }));
  ok(expired.includes('This QR has expired') && expired.includes('Nothing was charged') && expired.includes('data-cr-again'));
  for (const [state, line] of [['cancelled', 'The payment was cancelled'], ['failed', 'The payment did not go through'], ['refunded', 'This payment was refunded']]) {
    const closed = String(sheetMarkup({ ...model0, step: 'expired', orderState: state }));
    ok(closed.includes(line) && !closed.includes('Nothing was charged') && !closed.includes('This QR has expired'), `${state}: its own status line, no "nothing was charged"`);
  }
  /* each closed state has a head and a body of its own (the frame: head "QR expired", body "This QR has expired") */
  for (const locale of ['en', 'vi', 'zh']) {
    copy.setLanguages({ ui: locale, support: locale });
    for (const state of ['expired', 'cancelled', 'failed', 'refunded']) {
      const closed = String(sheetMarkup({ ...model0, step: 'expired', orderState: state }));
      const head = /s-cr-sheet__title[^>]*>([^<]*)</.exec(closed) || /o-sheet__title">([^<]*)</.exec(closed);
      const body = /s-cr-sheet__h s-cr-sheet__h--big">([^<]*)</.exec(closed);
      ok(head && body && head[1] && body[1] && head[1] !== body[1], `${locale} ${state}: head and body differ (${head && head[1]} / ${body && body[1]})`);
      eq(closed.includes('data-cr-again'), state !== 'refunded', `${locale} ${state}: "Make a new QR" is not offered after a refund`);
      ok(closed.includes('data-sheet-close'), `${locale} ${state}: Close stays`);
    }
  }
  copy.setLanguages({ ui: 'en', support: 'en' });
  ok(String(sheetMarkup({ ...model0, step: 'expired' })).includes('QR expired'), 'the frame head for an expired QR');
  eq(qrMatrix('x'.repeat(5000)), null, 'a payment string over QR capacity gives no matrix instead of throwing');
  const unreadable = String(sheetMarkup({ ...model0, step: 'qr', qr: 'x'.repeat(5000) }));
  ok(unreadable.includes('The payment page could not be opened') && unreadable.includes('data-cr-cancel') && !unreadable.includes('shape-rendering'), 'an unreadable QR shows the gateway message in the existing wait line');
  for (const locale of ['vi', 'zh']) {
    copy.setLanguages({ ui: locale, support: locale });
    for (const step of ['confirm', 'qr', 'received', 'done', 'expired']) {
      const text = String(sheetMarkup({ ...model0, step, qr: payos }));
      ok(!/Pay today|Waiting for your transfer|Waiting for payment confirmation|Payment received|Credits added|This QR has expired/.test(text), `${locale} ${step}: translated`);
    }
  }
  copy.setLanguages({ ui: 'en', support: 'en' });
}

/* --- Plan & usage: the Credits card, Profile ------------------------------------------------------------- */
{
  const commerce = { available: true, billing_ready: false, plan: { id: 'free', name: 'Free', description: '' }, subscription: { state: 'none' }, features: {} };
  const without = String(billingMarkup(commerce));
  ok(!without.includes('s-plan-credits') && !without.includes('data-open-credits'), 'no Credits card while nothing is on sale');
  const withCard = String(billingMarkup(commerce, { credits: true }));
  ok(withCard.includes('s-plan-credits') && (withCard.match(/data-open-credits/g) || []).length === 2 && withCard.includes('View history'));
  ok(withCard.indexOf('s-plan-credits') < withCard.indexOf('s-plan-pay'), 'the card sits before the payment method card');
  ok(!withCard.includes('s-plan-pill--accent'), 'Credits carry no plan tag');
}

/* --- the screen's lifecycle (source-level: the route cannot be mounted here) ------------------------------ */
{
  const src = readFileSync(new URL('../static/orena/screens/credits/screen.js', import.meta.url), 'utf8');
  ok(/shouldStop:[^\n]*ctx\.isCurrent\(\)/.test(src), 'the order watcher stops when the route is no longer current');
  ok(/return \(\) => \{ stopped = true;/.test(src) && /shouldStop:[^\n]*stopped/.test(src), 'leaving the route retires the watcher');
  ok(/purchase\.order && !purchase\.cancelled[^\n]*\n?\s*[^\n]*watch\(\);/.test(src), 'returning to the route re-watches an open order');
  ok(/function clearPurchase/.test(src) && /refusal\.action === 'sign_in'\) clearPurchase\(\)/.test(src) && /reason === 'auth'\) \{ clearPurchase/.test(src), 'a purchase does not outlive the signed-in session');
  ok(new RegExp('onClose: \\(\\) => \\{[^}]*paint\\(\\);[^}]*sheetReturnTarget\\(element\\)\\?\\.focus').test(src), 'closing the sheet returns focus to the opener after the re-mount');
  ok(/watchEndsStillWaiting\(result\)/.test(src), 'every non-terminal end of the watcher shows the still-waiting line');
  ok(/keydown/.test(src) && /nextPackKey/.test(src), 'the pack group answers the arrow keys');
  ok(/refusal\.action === 'resume'/.test(src), 'checkout_already_started is handled without looping on the pay button');
  ok(!/t\('waitingTitle'\)|t\('pendingText'/.test(src + readFileSync(new URL('../static/orena/screens/credits/sheet.js', import.meta.url), 'utf8')), 'the design sample waiting lines are not rendered');
}

console.log(`Orena credits screens: ${checks} checks: PASS`);
