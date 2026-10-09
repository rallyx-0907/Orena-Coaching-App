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
const { billingMarkup, usageNote, resetLabel } = (await import('../static/orena/screens/plan/screen.js')).__internal;
const { t } = await import('../static/orena/screens/plan/copy.js');
const { pricingMarkup } = (await import('../static/orena/screens/plan/pricing.js')).__internal;
const { sheetMarkup } = await import('../static/orena/screens/plan/sheet.js');
const copy = await import('../static/orena/copy/index.js');
const { ROUTES, byId, match } = await import('../static/orena/shell/routes.js');

const PRICES = (m, mv, y, yv) => ({ monthly: { USD: m, VND: mv }, yearly: { USD: y, VND: yv } });
/* Catalogue v2 (D-161): the design's Pricing meters. Minute meters are stored in seconds (scale 60). */
const METER = {
  'orena.message': { window: 'day', unit: 'message', display_unit: 'message', scale: 1 },
  'writing.review': { window: 'month', unit: 'review', display_unit: 'review', scale: 1 },
  'pronunciation.audio': { window: 'month', unit: 'second', display_unit: 'minute', scale: 60 },
  'media.import': { window: 'month', unit: 'second', display_unit: 'minute', scale: 60 },
  'languages.target': { window: null, unit: 'language', display_unit: 'language', scale: 1 },
};
const ent = (key, limit, enabled = true) => ({ key, enabled, limit, monthly_limit: METER[key].window === 'month' ? limit : null, params: {}, ...METER[key] });
const ents = (msg, wr, pron, imp, lang) => [ent('orena.message', msg), ent('writing.review', wr), ent('pronunciation.audio', pron * 60), ent('media.import', imp * 60), ent('languages.target', lang)];
const FREE = { id: 'free', name: 'Free', description: 'Core writing practice for everyday learning.', price_label: 'Free', rank: 0, prices: PRICES(0, 0, 0, 0), entitlements: ents(20, 2, 5, 15, 1) };
const PLUS = { id: 'plus', name: 'Plus', description: 'Steady learners.', price_label: 'Plus', rank: 1, prices: PRICES(9.99, 199000, 79.99, 1590000), entitlements: ents(200, 10, 30, 120, 2) };
const PRO = { id: 'pro', name: 'Pro', description: 'Heavy practice.', price_label: 'Pro', rank: 2, prices: PRICES(19.99, 399000, 159.99, 3190000), entitlements: ents(1000, 50, 120, 600, 2) };
const feature = (key, limit, used, extra = {}) => ({ key, enabled: true, limit, monthly_limit: METER[key].window === 'month' ? limit : null, used, remaining: Math.max(0, limit - used), usage_state: 'known', entitlement_state: 'enabled', resets_at: '2026-11-01T00:00:00Z', ...METER[key], ...extra });
const COMMERCE = {
  available: true, billing_ready: false,
  plan: { id: 'free', name: 'Free', description: FREE.description, price_label: 'Free' },
  subscription: { state: 'none', status: 'inactive' },
  features: {
    'orena.message': feature('orena.message', 20, 16, { resets_at: '2026-10-10T00:00:00Z' }),
    'writing.review': feature('writing.review', 2, 2),
    'pronunciation.audio': feature('pronunciation.audio', 300, 0),
    'media.import': feature('media.import', 900, 90),
    'languages.target': { ...feature('languages.target', 1, 0), usage_state: 'not_metered', used: null, remaining: null },
  },
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
  assert.deepEqual(rows.map((r) => r.key), ['orena.message', 'writing.review', 'pronunciation.audio', 'media.import'], 'the windowed meters, in the design order; the language cap has no usage row');
  assert.equal(rows[0].percent, 80);
  assert.equal(rows[0].tone, 'amber');
  assert.equal(rows[0].left, 4);
  assert.equal(rows[0].window, 'day');
  assert.equal(rows[1].tone, 'red');
  assert.equal(rows[2].used, 0, 'an unused meter is a real zero');
  assert.deepEqual([rows[3].used, rows[3].limit, rows[3].left, rows[3].unit], [1.5, 15, 13.5, 'minute'], 'seconds are shown as minutes');
  assert.deepEqual(model.usageRows(null), [], 'no read, no rows - never a sample');
  assert.deepEqual(model.usageRows({ features: null }), []);
  const unknown = model.usageRows({ features: { 'writing.review': feature('writing.review', 2, 0, { entitlement_state: 'unknown', usage_state: 'unavailable' }) } });
  assert.equal(unknown[0].unknown, true, 'use the server could not read is unknown, not zero');
  assert.equal(unknown[0].tone, 'ok');
  const notMetered = model.usageRows({ features: { 'writing.review': feature('writing.review', 2, 0, { usage_state: 'not_metered', used: null }) } });
  assert.equal(notMetered[0].unknown, true, 'a meter nothing counts is not "0 used"');
  assert.equal(notMetered[0].resetsAt, null);
  assert.equal(model.displayAmount(90, 60), 1.5);
  assert.equal(model.displayAmount(300, 60), 5);
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
  assert.deepEqual(plans[0].features.map((f) => f.key), ['orena.message', 'writing.review', 'pronunciation.audio', 'media.import', 'languages.target'], 'the design meters');
  assert.equal(plans[0].features[0].limit, 20);
  assert.equal(plans[0].features[2].limit, 5, 'minutes, not seconds');
  assert.equal(model.pricingPlans({ plans: null }).length, 0);
  assert.equal(model.pricingPlans({ plans: [{}, null] }).length, 0);
  const rows = model.compareRows(plans);
  assert.equal(rows.length, 5);
  assert.deepEqual(rows[1].cells, [{ kind: 'limit', value: 2, unit: 'review' }, { kind: 'limit', value: 10, unit: 'review' }, { kind: 'limit', value: 50, unit: 'review' }]);
  assert.deepEqual(rows[3].cells.map((c) => c.value), [15, 120, 600], 'media import in minutes');
  const offPlus = model.compareRows(model.pricingPlans({ plans: [FREE, { ...PLUS, entitlements: PLUS.entitlements.map((e) => (e.key === 'media.import' ? { ...e, enabled: false } : e)) }] }));
  assert.deepEqual(offPlus[3].cells.map((c) => c.kind), ['limit', 'no']);
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
  assert.equal(model.featureCopyKey('writing.review'), 'feature_writing_review');
  assert.equal(model.formatNumber(2000, 'en'), '2,000');
}

/* --- rendered markup, every language ---------------------------------------------------------- */
for (const ui of ['en', 'vi', 'zh']) {
  copy.setLanguages({ ui, support: 'en' });
  const billing = String(billingMarkup(COMMERCE));
  assert.match(billing, /data-open-plans/, `${ui}: the plan card opens Plans`);
  assert.equal((billing.match(/s-plan-usage__row/g) || []).length, 4, `${ui}: four metered rows`);
  assert.match(billing, /width:80%/, `${ui}: the bar is the real share`);
  assert.ok(billing.includes(t('amountMinutes', { n: '15' })), `${ui}: minute meters say minutes`);
  assert.doesNotMatch(billing, /\{[a-z]+\}|undefined|NaN/, `${ui}: nothing unfilled`);
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
  assert.ok(pricing.includes(t('line_orena_message', { n: '20' })) && pricing.includes(t.plural('line_languages_target', 1, { n: '1' })), `${ui}: plan lines worded as the design's`);
  assert.ok(pricing.includes(t('compare_writing_review')), `${ui}: compare rows name the window`);
  assert.doesNotMatch(pricing, /\{[a-z]+\}|undefined|NaN/, `${ui}: nothing unfilled`);
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
assert.equal(usageNote({ unknown: false, tone: 'ok', left: 13.5, unit: 'minute' }).text, '13.5 min left');
assert.equal(resetLabel({ window: 'day', resetsAt: '2026-10-10T00:00:00Z' }, new Date('2026-10-09T18:48:00Z')), 'Resets in 5h 12m');
assert.equal(resetLabel({ window: 'month', resetsAt: '2026-11-01T12:00:00Z' }), 'Resets Nov 1');
assert.equal(resetLabel({ window: 'day', resetsAt: null }), 'Resets every day');

/* --- the in-room exhausted message (D-161) ---------------------------------------------------- */
{
  const notice = await import('../static/orena/screens/plan/quota-notice.js');
  const refusal = { status: 429, category: 'quota_exhausted', context: { feature: 'writing.review', used: 2, limit: 2, scale: 1 } };
  assert.equal(notice.isQuotaExhausted(refusal), true);
  assert.equal(notice.isQuotaExhausted({ status: 429, category: 'rate_limited' }), false, 'the agent rate limit is not a plan limit');
  for (const ui of ['en', 'vi', 'zh']) {
    copy.setLanguages({ ui, support: 'en' });
    const text = notice.quotaMessage(refusal);
    assert.ok(text.includes('2') && !/\{|undefined/.test(text), `${ui}: names used and limit`);
    assert.ok(notice.seePlansLabel().length > 0);
  }
  copy.setLanguages({ ui: 'en', support: 'en' });
  assert.equal(notice.quotaMessage(refusal), 'You have used 2 of 2 writing reviews this month.');
  assert.equal(notice.quotaMessage({ status: 429, category: 'quota_exhausted', context: {} }), 'You have reached the limit of your plan for now.');

  /* Pronunciation minutes (D-16Z): stored in seconds, said in minutes exactly as Plan & usage shows them (whole when
     whole, one decimal otherwise), in the learner's language, from the server's own figures. */
  const pronunciation = (used, limit = 300) => ({ status: 429, category: 'quota_exhausted', context: { feature: 'pronunciation.audio', used, limit, unit: 'second', display_unit: 'minute', scale: 60 } });
  copy.setLanguages({ ui: 'en', support: 'en' });
  assert.equal(notice.quotaMessage(pronunciation(300)), 'You have used 5 of 5 pronunciation minutes this month.');
  assert.equal(notice.quotaMessage(pronunciation(68)), 'You have used 1.1 of 5 pronunciation minutes this month.', '68 s is 1.1 min');
  assert.equal(notice.quotaMessage(pronunciation(1800 - 30, 1800)), 'You have used 29.5 of 30 pronunciation minutes this month.');
  assert.equal(notice.quotaMessage(pronunciation(300)).includes('300'), false, 'never seconds');
  copy.setLanguages({ ui: 'vi', support: 'en' });
  assert.equal(notice.quotaMessage(pronunciation(68)), 'Bạn đã dùng 1,1/5 phút phát âm trong tháng này.');
  copy.setLanguages({ ui: 'zh', support: 'en' });
  assert.equal(notice.quotaMessage(pronunciation(68)), '本月发音分析已用 1.1/5 分钟。');
  /* The same figure Plan & usage draws for the same bucket. */
  const row = model.usageRows({ ...COMMERCE, features: { ...COMMERCE.features, 'pronunciation.audio': feature('pronunciation.audio', 300, 68) } }).find((r) => r.key === 'pronunciation.audio');
  assert.deepEqual([row.used, row.limit], [1.1, 5], 'display == bucket');
  copy.setLanguages({ ui: 'en', support: 'en' });
}

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
