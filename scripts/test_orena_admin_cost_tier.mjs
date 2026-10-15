/* Gate for the free-tier cost display on Admin > AI & Models > AI cost (D-219, owner decision 2026-10-16).

     a. the words: every new key exists in English, Vietnamese and Chinese with the same placeholders, and the three
        provider flags are named and explained (the policies gate covers every other policy);
     b. the rule: real spend is drawn as every amount is; free-tier value is drawn apart (the muted "Free tier" pill and
        a secondary "Free tier · ~$ at list price" phrase) and is never added to real spend; an amount recorded before
        the tier was stamped is drawn as its own phrase, in neither;
     c. the page in the three languages: the metrics, the by-feature, by-day, media-processing and by-account blocks;
     d. the server keeps the shape this page reads (writing_coach/ai/platform.py cost_report, media_spend.totals).

   No browser: the page is a pure function of the report. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = {
  documentElement: { lang: 'en', dataset: {} }, activeElement: null, head: { append() {} }, getElementById: () => null,
  createElement: () => ({ addEventListener() {}, dataset: {}, append() {}, querySelector: () => null }),
  addEventListener() {}, removeEventListener() {},
};

const copyIndex = await import('../static/orena/copy/index.js');
await import('../static/orena/copy/shell.js');
await import('../static/orena/screens/admin/copy.js');
const { costsPage } = await import('../static/orena/screens/admin/costs.js');
const { tierRow, tierParts } = await import('../static/orena/screens/admin/cost-tier.js');
const packs = copyIndex.registeredCopy().get('admin').packs;
const href = (name) => `#/${name}`;
const escape = (text) => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');

/* ---- a. the words -------------------------------------------------------------------------------------------- */
const NEW_KEYS = ['costReal', 'costFreeValue', 'costFreeValueNote', 'costFreeTier', 'costFreeShort', 'costFreeAt', 'costUnknownTier',
  'costMedia', 'costMediaSub', 'costMediaEvents', 'costMediaRequests', 'costGap_free_tier_tier', 'costGap_account_tier',
  'pol_cost_free_tier_groq', 'polHelp_cost_free_tier_groq', 'pol_cost_free_tier_supadata', 'polHelp_cost_free_tier_supadata',
  'pol_cost_free_tier_gemini', 'polHelp_cost_free_tier_gemini'];
const placeholders = (text) => [...String(text).matchAll(/\{([a-zA-Z]+)\}/g)].map((m) => m[1]).sort().join(',');
for (const key of NEW_KEYS) {
  assert.ok(packs.en[key], `en has ${key}`);
  for (const locale of ['vi', 'zh']) {
    assert.ok(packs[locale][key], `${locale} has ${key}`);
    assert.equal(placeholders(packs[locale][key]), placeholders(packs.en[key]), `${locale}.${key} keeps the placeholders of English`);
  }
}
assert.equal(placeholders(packs.en.costFreeAt), 'amount');
assert.match(packs.en.costFreeAt, /Free tier/);
assert.ok(/[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữự]/i.test(packs.vi.costFreeTier + packs.vi.costFreeValueNote), 'Vietnamese keeps its diacritics');
assert.ok(/[一-鿿]/.test(packs.zh.costFreeTier), 'Chinese is written in Chinese');

/* ---- b. the rule ---------------------------------------------------------------------------------------------- */
{
  copyIndex.setLanguages({ ui: 'en', support: 'en' });
  const { t } = await import('../static/orena/screens/admin/copy.js');
  const money = (value) => `$${value.toFixed(2)}`;
  const only = (row) => tierRow(row, { money, t });
  const free = only({ usd: 0.12, usd_real: 0, usd_free: 0.12, usd_unknown: 0 });
  assert.equal(free.right, 'Free', 'a free-tier-only row says Free, not $0.00');
  assert.deepEqual(free.meta, ['Free tier · ~$0.12 at list price']);
  assert.deepEqual(free.pills, [{ label: 'Free tier', tone: 'mute' }]);
  const paid = only({ usd: 0.5, usd_real: 0.5, usd_free: 0, usd_unknown: 0 });
  assert.equal(paid.right, '$0.50');
  assert.deepEqual(paid.meta, []);
  assert.deepEqual(paid.pills, [], 'a paid amount carries no free-tier label');
  const mixed = only({ usd: 0.62, usd_real: 0.5, usd_free: 0.12, usd_unknown: 0 });
  assert.equal(mixed.right, '$0.50', 'the amount on the right is real spend only; the free value is not added');
  assert.equal(mixed.meta.length, 1);
  const legacy = only({ usd: 0.7, usd_real: 0, usd_free: 0, usd_unknown: 0.7 });
  assert.equal(legacy.right, '$0.70');
  assert.deepEqual(legacy.meta, ['Before the tier was recorded · $0.70']);
  assert.deepEqual(legacy.pills, [], 'an unstamped amount is not called free');
  assert.deepEqual(tierParts({ real_usd: 1, free_tier_usd: 2, unknown_tier_usd: 3 }), { real: 1, free: 2, unknown: 3 }, 'the media ledger shape reads the same');
}

/* ---- c. the page ---------------------------------------------------------------------------------------------- */
const report = {
  days: 30, currency: 'USD',
  totals: { usd: 1.75, usd_real: 0.5, usd_free: 1.0, usd_unknown: 0.25 },
  by_day: [{ day: '2026-10-16', calls: 4, unpriced_calls: 1, usd: 1.5, usd_real: 0.5, usd_free: 1.0, usd_unknown: 0 },
    { day: '2026-10-15', calls: 2, unpriced_calls: 0, usd: 0.25, usd_real: 0, usd_free: 0, usd_unknown: 0.25 }],
  by_feature: [
    { capability: 'word_translation', provider: 'groq', model: 'qwen/qwen3.8-27b', usd: 1.0, usd_real: 0, usd_free: 1.0, usd_unknown: 0, usd_per_unit: 0.1, unit: 'call' },
    { capability: 'writing_evaluator', provider: 'gemini', model: 'gemini-3.5-flash-lite', usd: 0.5, usd_real: 0.5, usd_free: 0, usd_unknown: 0, usd_per_unit: 0.05, unit: 'call' },
  ],
  media: { days: 30, real_usd: 0.25, free_tier_usd: 0.4, unknown_tier_usd: 0, by_provider: [
    { provider: 'groq', real_usd: 0.25, free_tier_usd: 0.4, unknown_tier_usd: 0, events: 7, requests: 0 },
    { provider: 'supadata', real_usd: 0, free_tier_usd: 0, unknown_tier_usd: 0, events: 3, requests: 3 },
  ] },
  gaps: [{ code: 'free_tier_tier' }, { code: 'account_tier' }],
};
const accounts = { available: true, truncated: false, accounts: [{ name: 'Ada', email: 'ada@x.io', calls: 3, usd: 0.3, usd_real: 0.1, usd_free: 0.2 }] };
for (const ui of ['en', 'vi', 'zh']) {
  copyIndex.setLanguages({ ui, support: 'en' });
  const words = packs[ui];
  const money = (value) => new Intl.NumberFormat(ui, { style: 'currency', currency: 'USD', minimumFractionDigits: value < 1 ? 4 : 2, maximumFractionDigits: value < 1 ? 4 : 2 }).format(value);
  const markup = String(costsPage({ report, accounts, days: 30, failed: false, ui, href }));
  assert.ok(markup.includes(escape(words.costReal)) && markup.includes(escape(money(0.5))), `${ui}: real spend is a metric`);
  assert.ok(markup.includes(escape(words.costFreeValue)) && markup.includes(escape(money(1))), `${ui}: free-tier value is its own metric`);
  assert.ok(markup.includes(escape(words.costUnknownTier.replace('{amount}', money(0.25)))), `${ui}: the unstamped total is told apart`);
  assert.ok(markup.includes(escape(words.costFreeAt.replace('{amount}', money(1)))), `${ui}: a feature row says Free tier at list price`);
  assert.ok(markup.includes(escape(words.costFreeAt.replace('{amount}', money(0.4)))), `${ui}: the media block says it too`);
  assert.ok(markup.includes(escape(words.costFreeAt.replace('{amount}', money(0.2)))), `${ui}: and the account row`);
  assert.ok((markup.match(new RegExp(`>${escape(words.costFreeTier)}<`, 'g')) || []).length >= 4, `${ui}: the Free tier pill on every row with free value`);
  assert.ok(markup.includes(`>${escape(words.costFreeShort)}<`), `${ui}: a free-only row says Free`);
  assert.ok(markup.includes(escape(words.costMedia)) && markup.includes(escape(words.costMediaRequests.replace('{n}', '3'))), `${ui}: media processing, with the credit-priced requests`);
  assert.ok(markup.includes(escape(words.costGap_free_tier_tier)) && markup.includes(escape(words.costGap_account_tier)), `${ui}: the report's own gaps are stated`);
  assert.doesNotMatch(markup, /\{[a-zA-Z]+\}|undefined|\[object|NaN/, `${ui}: nothing unfilled`);
  assert.ok(!markup.includes(escape(money(1.75))), `${ui}: the grand list-price total is never presented as spend`);

  const paidOnly = String(costsPage({ report: { ...report, media: null, totals: { usd: 0.5, usd_real: 0.5, usd_free: 0, usd_unknown: 0 },
    by_feature: [report.by_feature[1]], by_day: [report.by_day[0]].map((d) => ({ ...d, usd_free: 0, usd: 0.5 })) }, accounts: null, days: 30, failed: false, ui, href }));
  assert.ok(!paidOnly.includes(`>${escape(words.costFreeTier)}<`), `${ui}: nothing is labelled free when nothing was`);
}

/* ---- d. the server keeps the shape this page reads ------------------------------------------------------------- */
const platform = fs.readFileSync('writing_coach/ai/platform.py', 'utf8');
for (const name of ['usd_real', 'usd_free', 'usd_unknown']) assert.ok(platform.includes(`"${name}"`), `cost_report carries ${name}`);
assert.ok(platform.includes('report["media"]'), 'the cost report carries the media ledger');
const spend = fs.readFileSync('writing_coach/media_spend.py', 'utf8');
for (const name of ['real_usd', 'free_tier_usd', 'unknown_tier_usd', 'by_provider']) assert.ok(spend.includes(`"${name}"`), `media totals carry ${name}`);
const policies = fs.readFileSync('writing_coach/policies.py', 'utf8');
for (const provider of ['groq', 'supadata', 'gemini']) assert.ok(policies.includes(`"cost.free_tier.${provider}"`), `the ${provider} flag is a policy`);

console.log('admin cost tier gate: ok');
