/* Gate for provider health in Admin (PR BZ, P0 2026-10-20): GET /api/admin/ai/health drawn into the design's existing
   elements - the provider-down banner on Overview and AI & Models (the design's BN / ovBanner), the provider row's
   status pill and a mute "last error" pill (the design's pills), the capability row's "Primary failing" pill, and the
   switch history on Operations (a row list) - in English, Vietnamese and Chinese.

     a. a provider that is down shows who, why in plain words, since when, and which capabilities run on a backup;
     b. a provider's pill says it is failing and why, in place of its tested status; the capability it serves as
        primary reads "Primary failing" (with or without a standby), as the design draws it;
     c. the switch history lists from -> to and why;
     d. no report (unreadable) draws nothing and claims nothing; nothing from the report beyond ids and closed words
        is drawn; every key exists in all three languages with the same placeholders;
     e. the policies page draws the new "health" group.

   No browser: the pages are pure builders over a fixture. */
import assert from 'node:assert/strict';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = {
  documentElement: { lang: 'en', dataset: {} },
  activeElement: null,
  head: { append() {} },
  getElementById: () => null,
  createElement: () => ({ addEventListener(type, fn) { if (type === 'load') queueMicrotask(fn); }, dataset: {}, append() {}, querySelector: () => null }),
  addEventListener() {},
  removeEventListener() {},
};
globalThis.fetch = async () => { throw new Error('no request is made by a pure builder'); };

const copyIndex = await import('../static/orena/copy/index.js');
await import('../static/orena/copy/shell.js');
const { t } = await import('../static/orena/screens/admin/copy.js');
const shared = await import('../static/orena/capabilities/admin-ai.js');
const health = await import('../static/orena/screens/admin/provider-health.js');
const pages = await import('../static/orena/screens/admin/ai-pages.js');
const control = await import('../static/orena/screens/admin/control-pages.js');
const policiesPage = await import('../static/orena/screens/admin/policies.js');
const healthCopy = await import('../static/orena/screens/admin/copy-health.js');
const { href } = await import('../static/orena/shell/routes.js');

const NOW = Date.parse('2026-10-19T23:40:00Z');
const PROMPT = 'my private essay about my landlord';
const report = {
  version: 1, available: true, status: 'alert', severity: 'high', window_minutes: 10,
  alerts: [{ provider: 'gemini', severity: 'high', failure_class: 'spend_cap', failed: 6, consecutive_failures: 6, last_error_at: '2026-10-19T23:38:00Z', failing_since: '2026-10-19T23:17:00Z', capabilities: ['agent_turn_fast', 'learner_dictionary'] }],
  providers: [
    { provider: 'gemini', status: 'alert', severity: 'high', ok: 0, failed: 6, consecutive_failures: 6, failure_class: 'spend_cap', last_error_at: '2026-10-19T23:38:00Z', failing_since: '2026-10-19T23:17:00Z',
      capabilities: [
        { capability: 'learner_dictionary', status: 'alert', severity: 'high', ok: 0, failed: 4, failure_class: 'spend_cap', last_error_at: '2026-10-19T23:38:00Z' },
        { capability: 'agent_turn_fast', status: 'alert', severity: 'high', ok: 0, failed: 2, failure_class: 'spend_cap', last_error_at: '2026-10-19T23:36:00Z' },
      ] },
    { provider: 'deepseek', status: 'ok', severity: null, ok: 3, failed: 0, consecutive_failures: 0, failure_class: null, last_error_at: null, capabilities: [] },
  ],
  down: [{ provider: 'gemini', reason: 'spend_cap', since: '2026-10-19T23:17:00Z', severity: 'high', on_backup: ['learner_dictionary'], without_backup: ['agent_turn_fast'], breaker_open: true, seconds_remaining: 1500 }],
  switches: [
    { at: '2026-10-19T23:39:00Z', capability: 'learner_dictionary', from: 'gemini', to: 'deepseek', reason: 'spend_cap', trigger: 'down', answered: true },
    { at: '2026-10-19T23:38:00Z', capability: 'writing_evaluator', from: 'gemini', to: null, reason: 'privacy', trigger: 'refused', answered: false },
  ],
  breaker: [],
  prompt: PROMPT,
};

const capabilities = [
  { key: 'learner_dictionary', operation: 'structured_text_generation', implemented: true, provider_backed: true, configurable: true, allowed_fallback_policies: ['none'], explicit_config_exists: true,
    config: { enabled: true, provider: 'gemini', model: 'gemini-3.5-flash-lite', backup_provider: 'deepseek', backup_model: 'deepseek-chat' } },
  { key: 'writing_evaluator', operation: 'structured_text_generation', implemented: true, provider_backed: true, configurable: true, allowed_fallback_policies: ['none'], explicit_config_exists: true,
    config: { enabled: true, provider: 'gemini', model: 'gemini-3.5-flash-lite' } },
  { key: 'text_discussion', operation: 'structured_text_generation', implemented: true, provider_backed: true, configurable: true, allowed_fallback_policies: ['none'], explicit_config_exists: true,
    config: { enabled: true, provider: 'deepseek', model: 'deepseek-chat' } },
];
const config = {
  learner_runtime: { mode: 'capability' },
  capabilities,
  providers: [
    { id: 'gemini', name: 'Google Gemini', kind: 'cloud', secret_mode: 'server-managed', supported_operations: ['structured_text_generation'], server_configured: true },
    { id: 'deepseek', name: 'DeepSeek', kind: 'cloud', secret_mode: 'server-managed', supported_operations: ['structured_text_generation'], server_configured: true },
  ],
};
const snapshot = (id, name) => ({ id, name, kind: 'cloud', configured: true, models: ['m'], default_model: 'm', secret_mode: 'server-managed',
  configuration: { endpoint_url: `https://${id}.example/v1`, credential_env: `${id.toUpperCase()}_API_KEY`, credential_source: 'encrypted_server_store' } });
const providers = shared.mergeProviders(config, { providers: [snapshot('gemini', 'Google Gemini'), snapshot('deepseek', 'DeepSeek')] });
const state = (healthReport) => ({ config, operations: { available: true, recent: [], by_capability: [] }, catalogState: 'ready', providers,
  providerTests: new Map(), routeTests: new Map(), health: healthReport, dataClasses: { doc: null, state: 'loading' } });

const esc = (text) => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');

/* ---- a-c, every language ------------------------------------------------------------------------ */
for (const ui of ['en', 'vi', 'zh']) {
  copyIndex.setLanguages({ ui, support: 'en' });
  const words = copyIndex.registeredCopy().get('admin').packs[ui];
  const reason = words.phReason_spend_cap;
  const common = { state: state(report), t, ui, href, now: NOW };

  const prov = pages.listPage({ ...common, view: { tab: 'prov', query: '' } }).markup.toString();
  const title = words.phDownTitle.replace('{provider}', 'Google Gemini').replace('{reason}', reason);
  assert.ok(prov.includes(esc(title)), `${ui}: the banner says who is down and why`);
  assert.ok(prov.includes(esc(words.phOnBackup.split('{list}')[0])), `${ui}: the banner says which capabilities run on a backup`);
  assert.ok(prov.includes(esc(words.phNoBackup.split('{list}')[0])), `${ui}: and which have no backup answering`);
  assert.ok(prov.includes(esc(words.phDownSince.split('{when}')[0])), `${ui}: since when`);
  assert.ok(prov.includes(esc(words.phFailingPill.replace('{reason}', reason))), `${ui}: the provider pill says failing and why`);
  assert.ok(prov.includes(esc(words.phLastError.split('{when}')[0])), `${ui}: the last error pill`);
  assert.ok(!prov.includes(PROMPT), 'nothing beyond ids and closed words is drawn');

  const route = pages.listPage({ ...common, view: { tab: 'route', query: '' } }).markup.toString();
  assert.ok(route.includes(esc(words.routeStateFailingStandby)), `${ui}: a capability with a standby reads "Primary failing · standby ready"`);
  assert.ok(route.includes(esc(words.routeStateFailingNoStandby)), `${ui}: one without reads "Primary failing · no standby"`);

  const rows = shared.capabilityRows(config, null, providers, report);
  assert.deepEqual(rows.map((row) => row.state), ['failing_standby', 'failing_no_standby', 'routed']);

  const overview = control.controlPage('adminOverview', { overview: {}, spend: null, health: report }, { href }).markup.toString();
  assert.ok(overview.includes(esc(words.phDownTitle.replace('{provider}', 'gemini').replace('{reason}', reason))), `${ui}: the Overview banner`);

  const ops = control.controlPage('adminOperations', { runtime: {}, telemetry: {}, overview: {}, reading: {}, health: report }, { href }).markup.toString();
  assert.ok(ops.includes(esc(words.phSwitches)), `${ui}: the switch history block`);
  assert.ok(ops.includes(esc(words.phSwitchMeta.replace('{from}', 'gemini').replace('{to}', 'deepseek').replace('{reason}', reason))), `${ui}: from -> to and why`);
  assert.ok(ops.includes(esc(words.phSwitchMeta.replace('{from}', 'gemini').replace('{to}', words.phSwitchNobody).replace('{reason}', words.phReason_privacy))), `${ui}: a refused switch`);
  assert.ok(ops.includes(esc(words.phTrigger_down)) && ops.includes(esc(words.phTrigger_refused)));
}

/* ---- d. nothing claimed without a report; the pieces on their own --------------------------------- */
copyIndex.setLanguages({ ui: 'en', support: 'en' });
const quiet = pages.listPage({ state: state(null), view: { tab: 'prov', query: '' }, t, ui: 'en', href, now: NOW }).markup.toString();
assert.ok(!quiet.includes('is down:') && !quiet.includes('Failing ·'), 'no report draws no banner and no failing pill');
assert.deepEqual(health.downBanners(t, null, { ui: 'en', now: NOW }), []);
assert.deepEqual(health.switchRows(t, { switches: [] }, { ui: 'en', now: NOW }), []);
assert.equal(health.downPill(t, report, 'deepseek'), null, 'a healthy provider keeps its own status');
assert.equal(health.reasonText(t, 'not-a-class'), t('phReason_other'));
assert.equal(health.downPill(t, { down: [{ provider: 'x', reason: 'rate_limit', severity: 'medium' }] }, 'x').tone, 'warn');
assert.equal(control.providerDownBanners(null, href).length, 0);
assert.equal(shared.capabilityRows(config, null, providers, null)[0].state, 'routed', 'no report, no failing route');

/* The controller asks for the report with the rest, and an unreadable one is null (not healthy, not failing). */
const calls = [];
const api = {
  aiConfig: async () => config, aiOperations: async () => ({ available: true, recent: [] }),
  aiHealth: async () => { calls.push('health'); throw new Error('503'); },
};
const controller = shared.createAiAdmin({ api });
await controller.loadCore();
assert.deepEqual(calls, ['health']);
assert.equal(controller.state.health, null);
const older = shared.createAiAdmin({ api: { aiConfig: async () => config, aiOperations: async () => ({}) } });
await older.loadCore();
assert.equal(older.state.health, null, 'a client without the route still loads');

/* Copy: the same keys and placeholders in every language, Vietnamese with its diacritics, Chinese in Chinese. */
const placeholders = (text) => [...String(text).matchAll(/\{([a-z]+)\}/g)].map((m) => m[1]).sort().join(',');
assert.deepEqual(Object.keys(healthCopy.vi).sort(), Object.keys(healthCopy.en).sort());
assert.deepEqual(Object.keys(healthCopy.zh).sort(), Object.keys(healthCopy.en).sort());
for (const key of Object.keys(healthCopy.en)) {
  for (const locale of ['vi', 'zh']) assert.equal(placeholders(healthCopy[locale][key]), placeholders(healthCopy.en[key]), `${locale}.${key}`);
}
for (const cls of ['spend_cap', 'rate_limit', 'auth', 'unconfigured', 'server', 'timeout', 'schema', 'other']) {
  assert.ok(healthCopy.en[`phReason_${cls}`] && healthCopy.vi[`phReason_${cls}`] && healthCopy.zh[`phReason_${cls}`], `${cls} is worded`);
}
assert.ok(/[ạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữự]/i.test(healthCopy.vi.phReason_spend_cap));
assert.ok(/[一-鿿]/.test(healthCopy.zh.phReason_spend_cap));

/* ---- e. the policies page carries the health group --------------------------------------------------- */
assert.ok(policiesPage.GROUP_ORDER.includes('health') && policiesPage.GROUP_COLUMN.health === 'right');

console.log('admin provider health: banner, pills, routing, switch history and policies OK in en/vi/zh');
