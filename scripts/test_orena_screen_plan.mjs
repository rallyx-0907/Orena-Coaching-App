/* Gate for Plan & usage, Plans and the Billing sheet (static/orena/screens/plan): the pure mapping
   (model.js) and the rendered markup (the screens' `__internal`, plain string templating). Checks
   rule 40: only what GET /api/product/commerce and /api/product/plans answer is drawn, a missing
   read is the honest unavailable state (never a sample figure), the payment controls are inert,
   and every word exists in English, Vietnamese and Chinese. */
import assert from 'node:assert/strict';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const model = await import('../static/orena/screens/plan/model.js');
const { billingMarkup, usageNote } = (await import('../static/orena/screens/plan/screen.js')).__internal;
const { pricingMarkup } = (await import('../static/orena/screens/plan/pricing.js')).__internal;
const { sheetMarkup } = await import('../static/orena/screens/plan/sheet.js');
const copy = await import('../static/orena/copy/index.js');
const { ROUTES, byId, match } = await import('../static/orena/shell/routes.js');

const PRICES = (m, mv, y, yv) => ({ monthly: { USD: m, VND: mv }, yearly: { USD: y, VND: yv } });
const FREE = { id: 'free', name: 'Free', description: 'Core writing practice for everyday learning.', price_label: 'Free', rank: 0, prices: PRICES(0, 0, 0, 0), entitlements: [
  { key: 'writing.evaluate', enabled: true, monthly_limit: 30 }, { key: 'writing.improve', enabled: true, monthly_limit: 10 },
  { key: 'library.grammar', enabled: true, monthly_limit: null }, { key: 'dictionary.lookup', enabled: true, monthly_limit: 120 },
  { key: 'vocabulary.save', enabled: true, monthly_limit: 100 }, { key: 'analytics.basic', enabled: true, monthly_limit: null },
  { key: 'analytics.advanced', enabled: false, monthly_limit: null }, { key: 'practice.personalized', enabled: false, monthly_limit: null },
  { key: 'export.report', enabled: false, monthly_limit: null },
] };
const PLUS = { id: 'plus', name: 'Plus', description: 'Steady learners.', price_label: 'Plus', rank: 1, prices: PRICES(9.99, 199000, 79.99, 1590000), entitlements: [
  { key: 'writing.evaluate', enabled: true, monthly_limit: 150 }, { key: 'writing.improve', enabled: true, monthly_limit: 60 },
  { key: 'library.grammar', enabled: true, monthly_limit: null }, { key: 'dictionary.lookup', enabled: true, monthly_limit: 800 },
  { key: 'vocabulary.save', enabled: true, monthly_limit: 1000 }, { key: 'analytics.basic', enabled: true, monthly_limit: null },
  { key: 'analytics.advanced', enabled: true, monthly_limit: null }, { key: 'practice.personalized', enabled: true, monthly_limit: null },
  { key: 'export.report', enabled: false, monthly_limit: null },
] };
const PRO = { id: 'pro', name: 'Pro', description: 'Heavy practice.', price_label: 'Pro', rank: 2, prices: PRICES(19.99, 399000, 159.99, 3190000), entitlements: [
  { key: 'writing.evaluate', enabled: true, monthly_limit: 500 }, { key: 'writing.improve', enabled: true, monthly_limit: 250 },
  { key: 'library.grammar', enabled: true, monthly_limit: null }, { key: 'dictionary.lookup', enabled: true, monthly_limit: 2000 },
  { key: 'vocabulary.save', enabled: true, monthly_limit: 3000 }, { key: 'analytics.basic', enabled: true, monthly_limit: null },
  { key: 'analytics.advanced', enabled: true, monthly_limit: null }, { key: 'practice.personalized', enabled: true, monthly_limit: null },
  { key: 'export.report', enabled: true, monthly_limit: null },
] };
const feature = (key, limit, used, extra = {}) => ({ key, enabled: true, monthly_limit: limit, used, remaining: Math.max(0, limit - used), usage_state: 'known', entitlement_state: 'enabled', ...extra });
const COMMERCE = {
  available: true, billing_ready: false,
  plan: { id: 'free', name: 'Free', description: FREE.description, price_label: 'Free' },
  subscription: { state: 'none', status: 'inactive' },
  features: { 'writing.evaluate': feature('writing.evaluate', 30, 24), 'writing.improve': feature('writing.improve', 10, 10), 'dictionary.lookup': feature('dictionary.lookup', 120, 0), 'vocabulary.save': feature('vocabulary.save', 100, 3), 'library.grammar': { key: 'library.grammar', enabled: true, monthly_limit: null, used: 0 } },
};

/* --- usage ---------------------------------------------------------------------------------- */
{
  assert.equal(model.usagePercent(0, 30), 0);
  assert.equal(model.usagePercent(15, 30), 50);
  assert.equal(model.usagePercent(99, 30), 100, 'a bar never runs past its track');
  assert.equal(model.usagePercent(5, 0), 0, 'no limit fills nothing');
  assert.equal(model.usagePercent('x', 30), 0);
  assert.equal(model.usageTone(79), 'ok');
  assert.equal(model.usageTone(80), 'amber');
  assert.equal(model.usageTone(100), 'red');

  const rows = model.usageRows(COMMERCE);
  assert.deepEqual(rows.map((r) => r.key), ['writing.evaluate', 'writing.improve', 'dictionary.lookup', 'vocabulary.save'], 'only metered features, in catalogue order');
  assert.equal(rows[0].percent, 80);
  assert.equal(rows[0].tone, 'amber');
  assert.equal(rows[0].left, 6);
  assert.equal(rows[1].tone, 'red');
  assert.equal(rows[2].used, 0, 'an unused feature is a real zero');
  assert.deepEqual(model.usageRows(null), [], 'no read, no rows - never a sample');
  assert.deepEqual(model.usageRows({ features: null }), []);
  const unknown = model.usageRows({ features: { 'writing.evaluate': feature('writing.evaluate', 30, 0, { entitlement_state: 'unknown', usage_state: 'unavailable' }) } });
  assert.equal(unknown[0].unknown, true, 'use the server could not read is unknown, not zero');
  assert.equal(unknown[0].tone, 'ok');
}

/* --- plan card and status --------------------------------------------------------------------- */
{
  assert.equal(model.statusCopyKey(COMMERCE), 'status_free');
  assert.equal(model.statusCopyKey({ ...COMMERCE, subscription: { state: 'active' } }), 'status_active');
  assert.equal(model.statusCopyKey({ ...COMMERCE, subscription: { state: 'past_due' } }), 'status_past_due');
  assert.equal(model.statusCopyKey({ ...COMMERCE, subscription: { state: 'weird' } }), 'status_unknown');
  assert.equal(model.statusCopyKey({ available: false }), 'status_unknown');
  const view = model.planView(COMMERCE);
  assert.equal(view.known, true);
  assert.equal(view.isFree, true);
  assert.equal(model.planView(null).known, false);
  assert.equal(model.planView({ available: false, plan: null }).plan, null);
  assert.equal(model.billingReady(COMMERCE), false, 'payments are not ready');
  assert.equal(model.billingReady(null), false);
}

/* --- plans, compare, change kind -------------------------------------------------------------- */
{
  const plans = model.pricingPlans({ plans: [FREE, PLUS, PRO], commerce: COMMERCE });
  assert.deepEqual(plans.map((p) => [p.id, p.isCurrent, p.isFree, p.rank]), [['free', true, true, 0], ['plus', false, false, 1], ['pro', false, false, 2]], 'three tiers (D-153)');
  assert.deepEqual(plans[0].features.map((f) => f.key), ['writing.evaluate', 'writing.improve', 'dictionary.lookup', 'vocabulary.save', 'library.grammar', 'analytics.basic'], 'only enabled features');
  assert.equal(plans[0].features[0].limit, 30);
  assert.equal(plans[0].features.at(-1).limit, null);
  assert.equal(model.pricingPlans({ plans: null }).length, 0);
  assert.equal(model.pricingPlans({ plans: [{}, null] }).length, 0);
  const rows = model.compareRows(plans);
  assert.equal(rows.length, 9);
  assert.deepEqual(rows[0].cells, [{ kind: 'limit', value: 30 }, { kind: 'limit', value: 150 }, { kind: 'limit', value: 500 }]);
  assert.deepEqual(rows.find((r) => r.key === 'analytics.advanced').cells.map((c) => c.kind), ['no', 'yes', 'yes']);
  assert.equal(model.changeKind(plans[0], plans[0]), 'current');
  assert.equal(model.changeKind(plans[1], plans[0]), 'upgrade');
  assert.equal(model.changeKind(plans[2], plans[1]), 'upgrade', 'a higher rank is an upgrade');
  const onPro = model.pricingPlans({ plans: [FREE, PLUS, PRO], commerce: { ...COMMERCE, plan: { id: 'pro' } } });
  assert.equal(model.changeKind(onPro[1], onPro[2]), 'switch', 'a lower rank is a switch, not an upgrade');
  assert.equal(model.changeKind(onPro[0], onPro[2]), 'switch');
  // Prices: dong to a Vietnamese interface, dollars otherwise; a yearly plan shows its monthly share.
  assert.equal(model.currencyFor('vi'), 'VND');
  assert.equal(model.currencyFor('zh'), 'USD');
  assert.equal(model.priceView(plans[1], 'monthly', 'en').price, '$9.99');
  assert.equal(model.priceView(plans[1], 'monthly', 'en').billedKey, 'billedMonthly');
  const yearly = model.priceView(plans[1], 'yearly', 'en');
  assert.equal(yearly.price, '$6.67');
  assert.equal(yearly.billedAmount, '$79.99');
  assert.match(model.priceView(plans[1], 'monthly', 'vi').price, /199\.000/);
  assert.match(model.priceView(plans[1], 'yearly', 'vi').price, /133\.000/, 'the dong share rounds to a thousand');
  assert.equal(model.priceView(plans[0], 'yearly', 'en').free, true);
  assert.equal(model.priceView({ ...plans[1], prices: {} }, 'monthly', 'en').price, '—', 'a missing price is a dash, never invented');
  assert.equal(model.yearlySaving(plans, 'en'), 33);
  assert.equal(model.yearlySaving([plans[0]], 'en'), 0);
  assert.equal(model.featureCopyKey('writing.evaluate'), 'feature_writing_evaluate');
  assert.equal(model.formatNumber(2000, 'en'), '2,000');
}

/* --- rendered markup, every language ---------------------------------------------------------- */
for (const ui of ['en', 'vi', 'zh']) {
  copy.setLanguages({ ui, support: 'en' });
  const billing = String(billingMarkup(COMMERCE));
  assert.match(billing, /data-open-plans/, `${ui}: the plan card opens Plans`);
  assert.equal((billing.match(/s-plan-usage__row/g) || []).length, 4, `${ui}: four metered rows`);
  assert.match(billing, /width:80%/, `${ui}: the bar is the real share`);
  assert.match(billing, /s-plan-pay__update" disabled/, `${ui}: the card update is inert`);
  assert.doesNotMatch(billing, /\$\d|calis@|14 days|Plus|Pro\b/, `${ui}: no sample price, email, chart or tier`);
  const none = String(billingMarkup({ ...COMMERCE, features: {} }));
  assert.match(none, /s-plan-empty/, `${ui}: no usage read is an honest line`);
  assert.doesNotMatch(none, /s-plan-usage__row/);

  const plans = model.pricingPlans({ plans: [FREE, PLUS, PRO], commerce: COMMERCE });
  const pricing = String(pricingMarkup({ plans: [FREE, PLUS, PRO], commerce: COMMERCE }));
  assert.equal((pricing.match(/class="s-plan-card s-pricing-card"/g) || []).length, 3, `${ui}: three plan cards`);
  assert.match(pricing, /s-pricing-card__cta" disabled/, `${ui}: the current plan's button is disabled`);
  assert.match(pricing, /data-choose="plus"/, `${ui}: Plus opens the sheet`);
  assert.match(pricing, /data-choose="pro"/, `${ui}: Pro opens the sheet`);
  assert.doesNotMatch(pricing, /data-choose="free"/);
  assert.equal((pricing.match(/data-cycle=/g) || []).length, 2, `${ui}: Monthly and Yearly`);
  assert.match(pricing, /−33%/, `${ui}: the yearly saving is computed from the prices`);
  assert.match(pricing, ui === 'vi' ? /199\.000/ : /\$9\.99/, `${ui}: the monthly price in the interface's currency`);
  assert.doesNotMatch(pricing, /Most popular|Phổ biến nhất/, `${ui}: no invented popularity tag`);
  assert.match(pricing, /style="--cols:3"/);
  const yearlyPricing = String(pricingMarkup({ plans: [FREE, PLUS, PRO], commerce: COMMERCE, cycle: 'yearly' }));
  assert.match(yearlyPricing, /data-cycle="yearly" aria-pressed="true"|aria-pressed="true" data-cycle="yearly"/);
  assert.match(yearlyPricing, ui === 'vi' ? /1\.590\.000/ : /\$79\.99/, `${ui}: yearly states the yearly total`);

  const sheet = String(sheetMarkup({ target: plans[1], current: plans[0] }));
  assert.match(sheet, ui === 'vi' ? /199\.000/ : /\$9\.99/, `${ui}: the sheet states the plan's price`);
  assert.match(String(sheetMarkup({ target: plans[2], current: plans[0], cycle: 'yearly' })), ui === 'vi' ? /3\.190\.000/ : /\$159\.99/);
  assert.match(sheet, /o-btn--primary" disabled/, `${ui}: the sheet's confirm is inert`);
  assert.match(sheet, /data-sheet-close/);
  assert.doesNotMatch(sheet, /4242|processing/i);
}
copy.setLanguages({ ui: 'en', support: 'en' });
assert.equal(usageNote({ unknown: true, tone: 'ok', left: 0 }).text, 'Not available');
assert.equal(usageNote({ unknown: false, tone: 'red', left: 0 }).text, 'Limit reached');
assert.equal(usageNote({ unknown: false, tone: 'ok', left: 6 }).text, '6 left');

/* --- routes ---------------------------------------------------------------------------------- */
{
  for (const id of ['billing', 'pricing']) {
    const route = byId(id);
    assert.equal(route.focus, true, `${id} is a learning workspace (the design's focus list)`);
    assert.equal(route.screen, 'plan');
  }
  assert.equal(match('#/plan').route.id, 'billing');
  assert.equal(match('#/plan/pricing').route.id, 'pricing');
  assert.ok(ROUTES.every((r) => r.id !== 'pricing' || r.path === 'plan/pricing'));
}

console.log('Orena plan screens: real usage and plans only, honest unavailable states, inert payment controls, EN/VI/ZH markup, routes: PASS');
