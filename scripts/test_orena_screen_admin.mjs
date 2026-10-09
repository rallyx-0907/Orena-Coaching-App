/* Gate for Platform Admin in the new UI (D-101 E; Orena-Admin.dc.html): the pure model, the shared
   AI-control-plane logic the old console and this UI both use, every AI & Models page rendered from a
   fixture in all three languages, and - the part that matters most - access:

     a. the Profile entry to Admin exists only for an admin and opens the Admin inside this UI;
     b. an account that is not an admin, at an admin address, gets the design's No access frame and
        the client makes NO request at all (fetch is stubbed and counted);
     c. every admin endpoint the new screens call is one tests/test_admin_authorization_matrix.py
        already calls as nobody, as a learner and as an administrator (the server refuses non-admins).

   No browser: the screen is driven through a small stand-in for the DOM it touches. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

/* ---- a browser, just enough of one ------------------------------------------------------------ */
const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });

class Fake {
  constructor(selector = '') {
    this.selector = selector;
    this.innerHTML = '';
    this.textContent = '';
    this.value = '';
    this.disabled = false;
    this.dataset = {};
    this.children = new Map();
  }
  querySelector(selector) {
    if (!this.children.has(selector)) this.children.set(selector, new Fake(selector));
    return this.children.get(selector);
  }
  querySelectorAll() { return []; }
  addEventListener() {}
  removeEventListener() {}
  contains() { return false; }
  focus() {}
  remove() {}
  append() {}
  setAttribute() {}
}
globalThis.document = {
  documentElement: { lang: 'en', dataset: {} },
  activeElement: null,
  head: { append() {} },
  getElementById: () => null,
  createElement: () => Object.assign(new Fake(), { addEventListener(type, fn) { if (type === 'load') queueMicrotask(fn); } }),
  addEventListener() {},
  removeEventListener() {},
};

/* fetch: every request is recorded; the answer is the fixture for its path. */
const requests = [];
let fixtureFor = () => ({ status: 404, body: { detail: 'not found' } });
globalThis.fetch = async (url, options = {}) => {
  const method = String(options.method || 'GET').toUpperCase();
  requests.push({ method, path: String(url).split('?')[0] });
  const { status = 200, body = {} } = fixtureFor(method, String(url).split('?')[0], options) || {};
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => 'application/json' },
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
};

/* ---- copy modules register before anything reads them ---------------------------------------- */
const copyIndex = await import('../static/orena/copy/index.js');
await import('../static/orena/copy/shell.js');
const { t } = await import('../static/orena/screens/admin/copy.js');
const model = await import('../static/orena/screens/admin/model.js');
const shared = await import('../static/orena/capabilities/admin-ai.js');
const { ROUTES, match, href, isAdminHash } = await import('../static/orena/shell/routes.js');

/* Pages the design does not draw, built from existing kit blocks only by the human's decision (D-128): the
   reason is required, and every key here must still not be a design page (the list cannot hide one). */
const KIT_PAGES = Object.freeze({
  adminPlans: 'Plans & pricing: the learner Pricing card flipped to an edit form, kit blocks only (human request 2026-10-09)',
  adminTraffic: 'Traffic & engagement: sign-ups and learning activity per day from the overview and product-activity reads, kit blocks only (human request 2026-10-09)',
  adminFeedback: 'Feedback: the reviews learners sent, with a summary, filters and paging, kit blocks only (D-156; human request 2026-10-09)',
  impPack: 'D-128: content pack export/import, kit blocks only (human decision 2026-10-04, item 2 of the completion plan)',
  aiCosts: 'D-128: AI cost page, kit blocks only (human decision 2026-10-04, decision 2)',
  impGrammar: 'Grammar package import, composed from the Content packs page (proposals/ADMIN_GRAMMAR_UI.md G2; layout approved by the human 2026-10-08)',
  grammar: 'Grammar review queue, composed from the Reading queue (proposals/ADMIN_GRAMMAR_UI.md G3; approved 2026-10-08)',
  grammarPoint: 'Grammar point review, composed from the Reading review detail with the learner Concept page as preview (G4; approved 2026-10-08)',
});
/* ---- 1. routes: Admin is bare, admin-only, and on the pinned design's own keys ---------------- */
const pin = fs.readFileSync('docs/design/canonical-ui/screens/Orena-Admin.dc.html', 'utf8');
const adminRoutes = ROUTES.filter((route) => route.admin);
assert.deepEqual(adminRoutes.map((route) => route.id).sort(), [...model.ADMIN_ROUTE_IDS].sort(), 'every admin route the shell serves is one the Admin model knows');
for (const route of adminRoutes) {
  assert.ok(route.bare && !route.focus, `${route.id} draws no learner frame and is not a learning workspace`);
  assert.equal(route.screen, 'admin');
  /* The design's own page keys: a frame it draws through its `isReading`-style flags (queue, detail, add,
     cset) is named by the state script's go("...") calls; every other page by its route branch. */
  if (route.id !== 'admin' && !KIT_PAGES[route.design]) assert.ok(pin.includes(`r==="${route.design}"`) || pin.includes(`"${route.design}"`), `${route.id}: "${route.design}" is a page of the pinned Admin design`);
}
assert.equal(match('#/admin/ai/provider/openai').params.id, 'openai');
assert.equal(match('#/admin/ai/provider/openai/key').route.id, 'adminProviderKey');
assert.equal(match('#/admin/ai/capability/learner_dictionary').route.id, 'adminCapability');
assert.equal(href('adminAi', {}, { tab: 'route' }), '#/admin/ai?tab=route');
for (const hash of ['#/admin', '#/admin/ai', '#/admin?x=1', '#admin/ai']) assert.ok(isAdminHash(hash), `${hash} is an admin address`);
for (const hash of ['#/today', '#/administrator', '#/', '']) assert.ok(!isAdminHash(hash), `${hash} is not`);
/* Basic Product Completion includes all six approved operator areas. */
assert.deepEqual(model.AREAS.map((area) => area.id), ['overview', 'ai', 'users', 'content', 'imports', 'operations']);
assert.equal(model.areaOf('adminCapability'), 'ai');
assert.equal(model.areaOf('adminQueue'), 'content');
assert.equal(model.areaOf('adminJob'), 'imports');
assert.equal(model.areaOf('today'), '');

/* ---- 2. model ---------------------------------------------------------------------------------- */
assert.equal(model.adminAccess({ isAdmin: true, user: { email: 'a@x.io' }, name: 'A' }).allowed, true);
assert.equal(model.adminAccess({ isAdmin: false, user: { email: 'a@x.io' } }).allowed, false);
assert.equal(model.adminAccess({ isAdmin: 'true' }).allowed, false, 'only a real true opens Admin');
assert.equal(model.adminAccess({}).allowed, false);
assert.equal(model.adminAccess(undefined).allowed, false);
assert.equal(model.providerMono('Google Gemini'), 'GG');
assert.equal(model.providerMono('Groq'), 'GR');
assert.equal(model.humanKey('agent_turn_fast'), 'Agent turn fast');
assert.ok(model.matchesFilter('', 'x') && model.matchesFilter('gem', 'Google Gemini') && !model.matchesFilter('zzz', 'Groq'));
assert.equal(model.validateKey(''), 'errKeyRequired');
assert.equal(model.validateKey('short'), 'errKeyShort');
assert.equal(model.validateKey('sk-0123456789abcdef'), '');
assert.equal(model.validateKey('', { required: false }), '', 'a provider with no key asks for none');
assert.equal(model.providerPill('healthy').tone, 'ok');
assert.equal(model.providerPill('untested').tone, 'warn', 'configured is not healthy');
assert.equal(model.routePill('failing_no_standby').tone, 'err');
assert.equal(model.routePill('reserved').tone, 'fut');

/* ---- 3. the shared control-plane logic ---------------------------------------------------------- */
const capabilities = [
  { key: 'learner_dictionary', operation: 'structured_text_generation', implemented: true, provider_backed: true, configurable: true, allowed_fallback_policies: ['none', 'provider'], explicit_config_exists: true,
    config: { enabled: true, provider: 'openai', model: 'gpt-x', backup_provider: 'groq', backup_model: 'llama-x', timeout_seconds: 30, temperature: 0.2, fallback_policy: 'provider' } },
  { key: 'writing_evaluator', operation: 'structured_text_generation', implemented: true, provider_backed: true, configurable: true, allowed_fallback_policies: ['none'], explicit_config_exists: true,
    config: { enabled: true, provider: 'groq', model: 'llama-x' } },
  { key: 'reading_evaluator', operation: 'deterministic', implemented: true, provider_backed: false, configurable: false, allowed_fallback_policies: ['none'], explicit_config_exists: false, config: null },
  { key: 'text_to_speech', operation: 'speech_synthesis', implemented: false, provider_backed: true, configurable: false, allowed_fallback_policies: ['none'], explicit_config_exists: false, config: null },
  { key: 'writing_improver', operation: 'structured_text_generation', implemented: true, provider_backed: true, configurable: true, allowed_fallback_policies: ['none'], explicit_config_exists: false, config: null },
  { key: 'text_discussion', operation: 'structured_text_generation', implemented: true, provider_backed: true, configurable: true, allowed_fallback_policies: ['none'], explicit_config_exists: true,
    config: { enabled: false, provider: 'openai', model: 'gpt-x' } },
];
const configFixture = {
  learner_runtime: { mode: 'legacy' },
  capabilities,
  providers: [
    { id: 'ollama', name: 'Ollama', kind: 'local', secret_mode: 'none', supported_operations: ['structured_text_generation'], server_configured: true },
    { id: 'openai', name: 'OpenAI', kind: 'cloud', secret_mode: 'server-managed', supported_operations: ['structured_text_generation'], server_configured: true },
    { id: 'groq', name: 'Groq', kind: 'cloud', secret_mode: 'server-managed', supported_operations: ['structured_text_generation'], server_configured: true },
    { id: 'gemini', name: 'Google Gemini', kind: 'cloud', secret_mode: 'server-managed', supported_operations: ['structured_text_generation'], server_configured: false },
  ],
};
const snapshot = (id, name, configured, source, models, extra = {}) => ({
  id, name, kind: id === 'ollama' ? 'local' : 'cloud', configured, models, default_model: models[0] || '',
  secret_mode: id === 'ollama' ? 'none' : 'server-managed',
  configuration: { endpoint_url: `https://${id}.example/v1`, credential_env: id === 'ollama' ? null : `${id.toUpperCase()}_API_KEY`, credential_source: source },
  ...extra,
});
const catalogFixture = {
  providers: [
    snapshot('ollama', 'Ollama', true, 'not_configured', ['qwen3']),
    snapshot('openai', 'OpenAI', true, 'encrypted_server_store', ['gpt-x', 'gpt-y']),
    snapshot('groq', 'Groq', true, 'server_environment', ['llama-x']),
    snapshot('gemini', 'Google Gemini', false, 'not_configured', []),
  ],
};
const operationsFixture = {
  available: true, sample_limit: 200, sample_truncated: false,
  recent: [
    { capability: 'learner_dictionary', provider: 'openai', outcome: 'success', latency_ms: 800 },
    { capability: 'learner_dictionary', provider: 'openai', outcome: 'failure', latency_ms: 1200 },
    { capability: 'writing_evaluator', provider: 'groq', outcome: 'failure', latency_ms: null },
  ],
  by_capability: [
    { capability: 'learner_dictionary', health_state: 'healthy', evidence_count: 2 },
    { capability: 'writing_evaluator', health_state: 'provider_failure', evidence_count: 1 },
  ],
};

assert.equal(shared.capabilityKind(capabilities[0]), 'configurable');
assert.equal(shared.capabilityKind(capabilities[2]), 'deterministic');
assert.equal(shared.capabilityKind(capabilities[3]), 'reserved');
const providers = shared.mergeProviders(configFixture, catalogFixture);
assert.equal(providers.length, 4);
assert.equal(shared.credentialState(providers[0]), 'not_required');
assert.equal(shared.credentialState(providers[1]), 'encrypted_server_store');
assert.equal(shared.credentialState(providers[2]), 'server_environment');
assert.equal(shared.credentialState(providers[3]), 'not_configured');
/* Before the live catalog answers, only the registry's `configured` is known: say configured, not a
   "not configured" nobody has checked. */
const early = shared.mergeProviders(configFixture, null);
assert.deepEqual(early.map((provider) => shared.credentialState(provider)), ['not_required', 'configured', 'configured', 'not_configured']);
assert.equal(shared.providerStatus(providers[1], undefined), 'untested', 'configured is not healthy');
assert.equal(shared.providerStatus(providers[1], { state: 'ok' }), 'healthy');
assert.equal(shared.providerStatus(providers[1], { state: 'failed' }), 'failed');
assert.equal(shared.providerStatus(providers[3], { state: 'ok' }), 'not_configured', 'no key, no health');

const body = shared.routeBody(capabilities[0], { enabled: true, provider: 'groq', model: 'llama-x', backup_provider: '', backup_model: '' });
assert.equal(body.backup_provider, null);
assert.equal(body.timeout_seconds, 30, 'a route edit keeps the tuning it does not edit');
assert.equal(body.temperature, 0.2);
assert.equal(body.fallback_policy, 'provider');
assert.equal(shared.routeBody({ allowed_fallback_policies: ['none'] }, { provider: 'a', model: 'b' }).fallback_policy, 'none');
assert.deepEqual(shared.routeDraft(capabilities[0], providers), { provider: 'openai', model: 'gpt-x', backup_provider: 'groq', backup_model: 'llama-x', enabled: true });
assert.equal(shared.routeDraft({}, providers).provider, 'ollama', 'nothing saved: the first configured provider');
assert.equal(shared.routeDraft({ config: { model: 'm', model_redacted: true } }, providers).model, '', 'a redacted model is never put back in a field');
assert.equal(shared.routeChanged(capabilities[0].config, shared.routeDraft(capabilities[0], providers)), false);
assert.equal(shared.routeChanged(capabilities[0].config, { ...shared.routeDraft(capabilities[0], providers), model: 'other' }), true);
assert.ok(!('api_key' in shared.providerBody({ baseUrl: ' https://x/ ', apiKey: '   ', defaultModel: 'm', models: ['m'] })), 'an empty key is not sent');
assert.equal(shared.providerBody({ apiKey: ' k ' }).api_key, 'k');
assert.deepEqual(shared.removalConsequences('openai', capabilities, providers).map((row) => [row.key, row.fallback]), [['learner_dictionary', 'Groq']], 'a disabled route (text_discussion) loses nothing');
assert.deepEqual(shared.providerUsedBy(capabilities, 'groq').map((row) => `${row.key}:${row.role}`), ['learner_dictionary:standby', 'writing_evaluator:primary']);
const usage = shared.providerUsage(operationsFixture, 'openai');
assert.deepEqual([usage.requests, usage.failures, usage.meanLatency], [2, 1, 1000]);
assert.equal(shared.providerUsage(operationsFixture, 'gemini'), null, 'no events, no invented figures');
assert.equal(shared.providerUsage(operationsFixture, 'groq').meanLatency, null, 'a latency nobody recorded is not zero');
assert.deepEqual(shared.modelChoices(providers[1], 'gone', 'ready').models[0], { id: 'gone', unavailable: true }, 'a saved model the catalog dropped stays visible, flagged');
assert.equal(shared.modelChoices(providers[1], 'gpt-x', 'loading').loading, true);
assert.equal(shared.standbySameProvider({ provider: 'a', backup_provider: 'a' }), true);
assert.equal(shared.healthErrorClass({ body: { detail: { error_class: 'provider_unavailable' } } }), 'provider_unavailable');
assert.equal(shared.healthErrorClass({ body: { detail: { error_class: 'made_up' } } }), '');

/* D-104: the legacy-routing status shows only while it is true, and never claims a Save went live. */
assert.equal(shared.routingIsLive({ learner_runtime: { mode: 'legacy' }, policy: { learner_runtime_uses_capability_config: false } }), false);
assert.equal(shared.routingIsLive({ learner_runtime: { mode: 'capability' }, policy: { learner_runtime_uses_capability_config: false } }), false, 'a mode alone is not proof');
assert.equal(shared.routingIsLive({ learner_runtime: { mode: 'capability' }, policy: { learner_runtime_uses_capability_config: true } }), true);
const stamped = shared.providerUsage({ recent: [
  { provider: 'openai', outcome: 'success', latency_ms: 100, created_at: '2026-09-29T10:00:00Z' },
  { provider: 'openai', outcome: 'failure', latency_ms: 200, error_class: 'provider_unavailable', created_at: '2026-09-29T11:00:00Z' },
  { provider: 'openai', outcome: 'success', latency_ms: 300, created_at: '2026-09-29T12:00:00Z' },
] }, 'openai');
assert.deepEqual([stamped.lastSuccessAt, stamped.lastFailureAt, stamped.lastError], ['2026-09-29T12:00:00Z', '2026-09-29T11:00:00Z', 'provider_unavailable']);

const rows = shared.capabilityRows(configFixture, operationsFixture, providers);
const state = Object.fromEntries(rows.map((row) => [row.key, row.state]));
assert.deepEqual(state, {
  learner_dictionary: 'routed',
  writing_evaluator: 'failing_no_standby',
  reading_evaluator: 'local',
  text_to_speech: 'reserved',
  writing_improver: 'not_configured',
  text_discussion: 'disabled',
});

/* Every registry capability is named, and hinted, in every language. */
const registry = fs.readFileSync('writing_coach/ai/capabilities.py', 'utf8');
const keys = [...registry.matchAll(/_definition\(\s*"([a-z_]+)"/g)].map((match) => match[1]);
assert.ok(keys.length >= 10, 'capability keys were read from the registry');
const packs = copyIndex.registeredCopy().get('admin').packs;
for (const key of keys) for (const locale of copyIndex.LOCALES) {
  assert.ok(packs[locale][`cap_${key}`], `${locale}: capability "${key}" is named`);
  assert.ok(packs[locale][`capHint_${key}`], `${locale}: capability "${key}" is explained`);
}

/* ---- 4. every page, every language: no missing key, no unfilled placeholder, no secret ---------- */
const pages = await import('../static/orena/screens/admin/ai-pages.js');
const dialogs = await import('../static/orena/screens/admin/blocks.js');
const problems = [];
const realError = console.error;
console.error = (...args) => problems.push(args.join(' '));
const SECRET = 'sk-THIS-MUST-NEVER-BE-DRAWN';
const live = {
  config: configFixture,
  operations: operationsFixture,
  catalogState: 'ready',
  providers,
  providerTests: new Map([['groq', { state: 'failed', reason: 'boom', at: Date.now() - 60000 }], ['openai', { state: 'ok', count: 2, time: 320, models: ['gpt-x'], at: Date.now() - 5000 }]]),
  routeTests: new Map([['learner_dictionary', { state: 'ok', latency: 700 }]]),
};
const draft = shared.routeDraft(capabilities[0], providers);
const usageReport = { by_feature: [
  { capability: 'writing_evaluator', provider: 'openai', model: 'gpt-x', calls: 5, failures: 1, priced_calls: 4, unpriced_calls: 0, usd: 1.5, prompt_tokens: 3000, completion_tokens: 1000, audio_seconds: 0 },
  { capability: 'speech_asr', provider: 'groq', model: 'whisper-x', calls: 2, failures: 0, priced_calls: 2, unpriced_calls: 0, usd: 0.02, prompt_tokens: 0, completion_tokens: 0, audio_seconds: 120 },
], by_day: [] };
for (const ui of ['en', 'vi', 'zh']) {
  copyIndex.setLanguages({ ui, support: 'en' });
  const common = { state: live, t, ui, href, now: Date.now() };
  const drawn = [
    pages.listPage({ ...common, view: { tab: 'prov', query: '' } }),
    pages.listPage({ ...common, view: { tab: 'route', query: '' } }),
    pages.listPage({ ...common, view: { tab: 'prov', query: 'zzz-nothing' } }),
    pages.listPage({ ...common, view: { tab: 'tok', query: '', usage: { days: 7, report: usageReport, failed: false } } }),
    pages.listPage({ ...common, view: { tab: 'tok', query: '', usage: { days: 1, report: { by_feature: [], by_day: [] }, failed: false } } }),
    pages.listPage({ ...common, view: { tab: 'tok', query: '', usage: { days: 30, report: null, failed: true } } }),
    pages.providerPage({ ...common, view: { id: 'openai' } }),
    pages.providerPage({ ...common, view: { id: 'groq' } }),
    pages.providerPage({ ...common, view: { id: 'gemini' } }),
    pages.keyPage({ ...common, view: { id: 'openai', form: { key: '', endpoint: null, model: '', busy: '', error: 'errKeyRequired' } } }),
    pages.keyPage({ ...common, view: { id: 'gemini', form: { busy: 'saving' } } }),
    pages.capabilityPage({ ...common, view: { id: 'learner_dictionary', draft, error: '', busy: false } }),
    pages.capabilityPage({ ...common, view: { id: 'learner_dictionary', draft: { ...draft, backup_provider: 'openai', model: 'gpt-y' }, error: '', busy: false } }),
  ];
  const dialog = pages.removeDialog({ state: live, providerId: 'openai', typed: 'Open', t });
  drawn.push({ markup: dialogs.dialog(dialog) });
  for (const [index, page] of drawn.entries()) {
    const text = String(page.markup);
    assert.ok(text.length > 200, `${ui} page ${index} drew something`);
    assert.doesNotMatch(text, /\{[a-z]+\}/i, `${ui} page ${index} left a placeholder unfilled`);
    assert.doesNotMatch(text, /undefined|\[object/, `${ui} page ${index} printed a JS value`);
    assert.ok(!text.includes(SECRET), 'no secret is ever drawn');
    assert.doesNotMatch(text, /<script|onerror=/i);
  }
  assert.deepEqual(problems, [], `${ui}: no copy key is missing`);
  const routeTab = String(drawn[1].markup);
  assert.ok(routeTab.includes('a-opstatus') && routeTab.includes(packs[ui].runtimeLegacyStatus), `${ui}: the legacy-routing status is drawn while learners use legacy routing`);
  assert.ok(routeTab.includes(`a-opstatus__dot" aria-hidden="true"></span>${packs[ui].runtimeLegacyStatus}`), `${ui}: and it is a status line, not a banner`);
  const liveConfig = { ...live, config: { ...configFixture, learner_runtime: { mode: 'capability' }, policy: { learner_runtime_uses_capability_config: true } } };
  assert.ok(!String(pages.listPage({ ...common, state: liveConfig, view: { tab: 'route', query: '' } }).markup).includes('a-opstatus'), `${ui}: it disappears once learners consume the configured route`);
  /* Token usage: only what the ledger answers - no budget, no per-day chart, nothing estimated. */
  const tokenTab = String(drawn[3].markup);
  assert.ok(tokenTab.includes(packs[ui].tabTokens) && tokenTab.includes('data-tab="tok"'), `${ui}: the Token usage tab is drawn`);
  assert.ok(tokenTab.includes('a-bar__fill') && tokenTab.includes('a-metric__value'), `${ui}: metrics and capability bars come from the report`);
  assert.ok(tokenTab.includes('data-a="tk-period"'), `${ui}: the period is chosen in the tab`);
  assert.doesNotMatch(tokenTab, /of budget|a-banner/, `${ui}: no budget or alert the backend cannot answer`);
  assert.ok(String(drawn[4].markup).includes('a-state'), `${ui}: an empty ledger says so`);
  /* Listing: the provider rows say what the control plane knows, no more. */
  const list = String(drawn[0].markup);
  assert.ok(list.includes('OpenAI') && list.includes('Google Gemini'));
  assert.ok(list.includes('data-go="#/admin/ai/provider/openai"'), 'a provider row opens its detail');
  assert.doesNotMatch(list, /P95|updated .* ago/, 'no figure the control plane cannot answer');
  /* The key form is write-only: the stored key is not in the field, and a stored provider says so. */
  const keyForm = String(drawn[9].markup);
  assert.match(keyForm, /type="password"[^>]*value=""/, 'the key field never carries a stored key');
  assert.doesNotMatch(keyForm, /value="sk-/);
  /* The remove dialog names the consequence and arms only on the typed name. */
  assert.ok(String(drawn[13].markup).includes('data-a="dialog-confirm" disabled'), 'removal is armed by typing the provider name');
}
copyIndex.setLanguages({ ui: 'en', support: 'en' });
const removal = pages.removeDialog({ state: live, providerId: 'openai', typed: 'OpenAI', t });
assert.equal(removal.ready, true);
assert.match(removal.list[0], /falls back to Groq/);
console.error = realError;

/* ---- 5a. the Profile entry -------------------------------------------------------------------- */
{
  const { profileActions } = await import('../static/orena/screens/profile/model.js');
  const { __internal } = await import('../static/orena/screens/profile/screen.js');
  const admin = profileActions({ isAdmin: true });
  const learner = profileActions({ isAdmin: false });
  assert.equal(admin.filter((a) => a.id === 'admin').length, 1, 'an admin sees Platform admin once');
  assert.equal(learner.filter((a) => a.id === 'admin').length, 0, 'anyone else does not see it at all');
  const ctx = { href };
  const target = __internal.actionHref('admin', ctx);
  assert.equal(target, '#/admin/ai', 'the entry opens Admin inside the new UI');
  assert.equal(match(target).route.id, 'adminAi');
  assert.doesNotMatch(target, /^\/#\/admin/, 'not the old console');
  assert.ok(String(__internal.actionRow(admin[0], ctx)).includes('data-go="#/admin/ai"'), 'the row is an in-app link');
}

/* ---- 5b. a non-admin at an admin address: No access, and no request at all ---------------------- */
const screen = (await import('../static/orena/screens/admin/screen.js')).default;
const ctxFor = (context, routeId = 'adminAi', extra = {}) => ({
  route: ROUTES.find((route) => route.id === routeId),
  params: {}, query: new URLSearchParams(), context,
  href, go() {}, replace() {}, setCrumb() {}, isCurrent: () => true, ...extra,
});
for (const [label, context] of [
  ['a learner', { isAdmin: false, name: 'Linh', user: { email: 'linh@example.com', is_admin: false } }],
  ['an unknown account', {}],
  ['a truthy non-boolean', { isAdmin: 'yes', user: {} }],
]) {
  for (const routeId of model.ADMIN_ROUTE_IDS) {
    requests.length = 0;
    const element = new Fake();
    const result = await screen(element, ctxFor(context, routeId, { params: { id: 'openai' } }));
    await new Promise((resolve) => setTimeout(resolve, 15));
    assert.equal(result, undefined, `${label}: nothing to clean up`);
    assert.deepEqual(requests, [], `${label} at ${routeId}: the client made no request at all`);
    assert.ok(element.innerHTML.includes('data-screen-label="No access"'), `${label}: the No access frame is drawn`);
    assert.ok(element.innerHTML.includes(t('noAccessTitle')));
    assert.ok(!element.innerHTML.includes('a-shell'), `${label}: no part of the Admin shell is drawn`);
  }
}
{
  const element = new Fake();
  await screen(element, ctxFor({ isAdmin: false, user: { email: 'linh@example.com' } }));
  assert.match(element.innerHTML, /<b>linh@example\.com<\/b>/, 'the frame quotes the signed-in account');
  assert.match(element.innerHTML, /href="#\/today"/, 'and offers the way back');
  const anonymous = new Fake();
  await screen(anonymous, ctxFor({ isAdmin: false }));
  assert.ok(!anonymous.innerHTML.includes('<b>'), 'an account with no email is not quoted');
  for (const ui of ['vi', 'zh']) {
    copyIndex.setLanguages({ ui, support: 'en' });
    const localized = new Fake();
    await screen(localized, ctxFor({ isAdmin: false, user: { email: 'linh@example.com' } }));
    assert.ok(localized.innerHTML.includes(packs[ui].noAccessTitle), `${ui}: No access speaks the interface language`);
  }
  copyIndex.setLanguages({ ui: 'en', support: 'en' });
}

/* ---- 5c. an admin: the Admin draws, and asks only for endpoints the server already guards -------- */
fixtureFor = (method, url) => {
  if (url === '/api/admin/ai/config' && method === 'GET') return { body: configFixture };
  if (url === '/api/admin/ai/catalog') return { body: catalogFixture };
  if (url === '/api/admin/ai/operations') return { body: operationsFixture };
  return { status: 404, body: { detail: 'nope' } };
};
requests.length = 0;
{
  const element = new Fake();
  const cleanup = await screen(element, ctxFor({ isAdmin: true, name: 'Calis', user: { email: 'admin@example.com' } }));
  await new Promise((resolve) => setTimeout(resolve, 60));
  assert.equal(typeof cleanup, 'function', 'an admin gets a page with its own cleanup');
  assert.ok(element.innerHTML.includes('class="a-shell"'), 'the Admin shell is drawn');
  assert.ok(!element.innerHTML.includes('No access'));
  const page = element.querySelector('[data-part="page"]').innerHTML;
  assert.ok(page.includes('OpenAI') && page.includes('data-screen-label="A2 AI &amp; Models"'), 'the providers list is painted from the control plane');
  assert.ok(requests.length >= 3 && requests.every((r) => r.path.startsWith('/api/admin/ai/')), `only AI control-plane reads: ${JSON.stringify(requests)}`);
  cleanup();
}
{
  /* The legacy Admin address opens the first staged area. */
  requests.length = 0;
  let went = '';
  await screen(new Fake(), ctxFor({ isAdmin: true }, 'admin', { replace: (address) => { went = address; } }));
  assert.equal(went, '#/admin/overview');
  assert.deepEqual(requests, [], 'redirecting is not a request');
}

/* ---- 5d. the writes the new screens make are the server's guarded ones -------------------------- */
const matrix = fs.readFileSync('tests/test_admin_authorization_matrix.py', 'utf8');
const guarded = [...matrix.matchAll(/\("(GET|POST|PUT|DELETE)", "(\/api\/[^"]+)"\)/g)].map(([, method, route]) => ({
  method,
  pattern: new RegExp(`^${route.replace(/\{[^}]+\}/g, '[^/]+')}$`),
}));
assert.ok(guarded.length > 40, `the authorization matrix was read (${guarded.length} routes)`);
requests.length = 0;
fixtureFor = (method, url) => {
  if (url === '/api/admin/ai/config' && method === 'GET') return { body: configFixture };
  if (url === '/api/admin/ai/catalog') return { body: catalogFixture };
  if (url === '/api/admin/ai/operations') return { body: operationsFixture };
  if (url.endsWith('/test') || url.includes('/ai/test/')) return { body: { ok: true, models: ['gpt-x'], latency_ms: 12 } };
  return { body: { ok: true } };
};
{
  const { createAiAdmin } = shared;
  const controller = createAiAdmin({ api: (await import('../static/orena/capabilities/admin-api.js')).adminApi });
  await controller.loadCore();
  await controller.loadCatalog();
  await controller.testRoute('learner_dictionary', false);
  await controller.testRoute('learner_dictionary', true);
  assert.equal((await controller.saveRoute('learner_dictionary', { ...draft, model: 'gpt-y' })).ok, true);
  await controller.testProvider('openai');
  await controller.testProvider('openai', { api_key: SECRET });
  assert.equal((await controller.saveProvider('openai', { baseUrl: 'https://x.example/v1', apiKey: SECRET, defaultModel: 'gpt-x' })).ok, true);
  assert.equal((await controller.removeProvider('openai')).ok, true);
  const used = new Set(requests.map((r) => `${r.method} ${r.path.replace(/\/(learner_dictionary|openai)(?=\/|$)/g, '/{id}')}`));
  assert.ok(used.size >= 8, `the controller exercised the AI endpoints (${[...used].join(', ')})`);
  for (const request of requests) {
    assert.ok(request.path.startsWith('/api/admin/ai/'), `${request.method} ${request.path}: an AI control-plane route`);
    assert.ok(guarded.some((g) => g.method === request.method && g.pattern.test(request.path)), `${request.method} ${request.path} is in tests/test_admin_authorization_matrix.py (anonymous 401, learner 403)`);
  }
  /* The key travels once, in the body of the request that stores or tries it - never in a URL. */
  assert.ok(requests.every((r) => !r.path.includes(SECRET)));
  assert.equal(controller.state.providerTests.has('openai'), false, 'a removed credential leaves no test result behind');
}
{
  /* A failed verify stores nothing. */
  requests.length = 0;
  fixtureFor = (method, url) => {
    if (url === '/api/admin/ai/config') return { body: configFixture };
    if (url.endsWith('/credentials/openai/test')) return { status: 502, body: { detail: 'Provider connection validation failed: 401' } };
    return { body: { ok: true } };
  };
  const controller = shared.createAiAdmin({ api: (await import('../static/orena/capabilities/admin-api.js')).adminApi });
  await controller.loadCore();
  const outcome = await controller.saveProvider('openai', { apiKey: 'sk-bad', defaultModel: 'm' });
  assert.deepEqual([outcome.ok, outcome.stage], [false, 'verify']);
  assert.ok(!requests.some((r) => r.method === 'PUT'), 'a key that cannot connect is never stored');
  assert.equal(controller.state.providerTests.get('openai').state, 'failed');
}

/* ---- 6. nothing here borrows the old UI, and every colour is a token ------------------------------ */
const root = path.resolve('static/orena/screens/admin');
for (const file of fs.readdirSync(root)) {
  const source = fs.readFileSync(path.join(root, file), 'utf8');
  if (file.endsWith('.js')) assert.doesNotMatch(source, /from\s+['"][^'"]*\/ui\/|from\s+['"][^'"]*\/admin\//, `${file} imports nothing from ui/ or the old admin/`);
  if (file.endsWith('.css')) {
    const hardcoded = source.replace(/\/\*[\s\S]*?\*\//g, '').match(/#[0-9a-fA-F]{3,8}\b|rgba?\(/g) || [];
    assert.deepEqual(hardcoded, [], `${file}: every colour is a semantic token`);
  }
}

console.log(`Orena admin screen: routes, access (Profile entry, No access with zero requests, ${guarded.length} guarded routes cross-checked), shared control-plane logic, ${3} languages x 11 pages: PASS`);

/* ---- 5f. Feedback: metrics, bars, filters, the review list, paging, empty and failed ------------------ */
{
  const page = await import('../static/orena/screens/admin/feedback.js');
  assert.equal(model.areaOf('adminFeedback'), 'users');
  assert.equal(match('#/admin/feedback').route.id, 'adminFeedback');
  assert.equal(page.starsText(3), '★★★☆☆');
  const data = {
    available: true,
    summary: { total: 4, average: 3.75, by_stars: { 1: 0, 2: 1, 3: 0, 4: 1, 5: 2 }, by_area: { writing: 3, bugs: 1 }, last_7_days: 2 },
    areas: page.AREAS, total: 60, limit: 25, offset: 0,
    items: [
      { id: 'f1', created_at: '2026-10-09T10:30:00Z', stars: 5, areas: ['writing', 'bugs'], text: 'Great <b>app</b>', account_id: 'acc-1', name: 'Linh', email: 'linh@example.com', language: 'en', interface: 'vi' },
      { id: 'f2', created_at: '2026-10-08T10:30:00Z', stars: 2, areas: [], text: '', account_id: null, name: '', email: '', language: 'zh', interface: 'zh' },
    ],
  };
  for (const ui of ['en', 'vi', 'zh']) {
    copyIndex.setLanguages({ ui, support: 'en' });
    const markup = String(page.feedbackPage({ data, filters: { stars: '5', area: 'writing' }, offset: 0, ui, href }));
    const words = packs[ui];
    for (const key of ['fbTitle', 'fbTotal', 'fbAverage', 'fbLast7', 'fbByStars', 'fbByArea', 'fbArea_writing']) assert.ok(markup.includes(words[key].replace('&', '&amp;')), `${ui}: ${key}`);
    assert.ok(markup.includes('3.75'.replace('.', ui === 'vi' ? ',' : '.')) === false, `${ui}: the average is one decimal`);
    assert.match(markup, new RegExp(`a-metric__value[^>]*>${ui === 'vi' ? '3,8' : '3.8'}<`), `${ui}: average to one decimal`);
    assert.equal((markup.match(/class="a-bar"/g) || []).length, 5 + 7, `${ui}: five star bars and seven area bars`);
    assert.match(markup, /width:50%/, `${ui}: the 5-star bar is half`);
    assert.equal((markup.match(/class="a-chipbtn"/g) || []).length, 6 + 8, `${ui}: stars and area chips`);
    assert.equal((markup.match(/aria-pressed="true"/g) || []).length, 2, `${ui}: the chosen filters are pressed`);
    assert.ok(markup.includes('★★★★★') && markup.includes('★★☆☆☆'), `${ui}: stars as text`);
    assert.ok(markup.includes('data-go="#/admin/users/acc-1"') && markup.includes('linh@example.com'), `${ui}: the review links to the account`);
    assert.equal((markup.match(/a-row--open/g) || []).length, 1, `${ui}: a review with no account does not link`);
    assert.ok(markup.includes('Great &lt;b&gt;app&lt;/b&gt;') && !markup.includes('<b>app'), `${ui}: the text is escaped`);
    assert.ok(markup.includes(words.fbAnonymous === undefined ? '' : words.fbAnonymous), `${ui}: a review without an account says so`);
    assert.match(markup, /data-a="previous"[^>]*disabled/, `${ui}: no previous on the first page`);
    assert.doesNotMatch(markup, /data-a="next"[^>]*disabled/, `${ui}: more pages remain`);
    assert.doesNotMatch(markup, /\{[a-z]+\}|undefined|\[object|NaN/i, `${ui}: nothing unfilled`);
    const last = String(page.feedbackPage({ data: { ...data, total: 2 }, offset: 0, ui, href }));
    assert.match(last, /data-a="next"[^>]*disabled/, `${ui}: no next on the last page`);
    const empty = String(page.feedbackPage({ data: { available: true, summary: { total: 0, average: null, by_stars: {}, by_area: {}, last_7_days: 0 }, areas: page.AREAS, total: 0, items: [] }, ui, href }));
    assert.ok(empty.includes(words.opNone), `${ui}: empty says there is nothing`);
    assert.ok(empty.includes('—'), `${ui}: no average when there is no review`);
    const failed = String(page.feedbackPage({ data: null, failed: true, ui, href }));
    assert.ok(failed.includes(words.opUnavailable), `${ui}: failed says unavailable`);
    assert.ok(String(page.feedbackPage({ data: { available: false }, ui, href })).includes(words.opUnavailable), `${ui}: not stored here says unavailable`);
    assert.ok(String(page.feedbackPage({ data: null, ui, href })).includes('a-skeleton'), `${ui}: loading is the skeleton`);
  }
  copyIndex.setLanguages({ ui: 'en', support: 'en' });
  const usersPage = String((await import('../static/orena/screens/admin/control-pages.js')).controlPage('adminUsers', { summary: { activity: {} }, list: { items: [], total: 0 } }, { href }).markup);
  assert.ok(usersPage.includes('data-to="#/admin/feedback"'), 'Users offers Feedback');
}

/* ---- 5g. Traffic & engagement: metrics, per-day bars, skills, funnel, honest note, empty and failed ---- */
{
  const page = await import('../static/orena/screens/admin/traffic.js');
  assert.equal(model.areaOf('adminTraffic'), 'overview');
  assert.equal(match('#/admin/traffic').route.id, 'adminTraffic');
  const dates = Array.from({ length: 30 }, (_, i) => `2026-09-${String(10 + i).padStart(2, '0')}`.replace(/^2026-09-(3[1-9]|[4-9]\d)$/, '2026-10-01'));
  const overview = {
    accounts: { available: true, total: 12, admins: 1, new_7d: 3, new_30d: 9, window_days: 30, registrations: dates.map((date, i) => ({ date, count: i % 3 })) },
    activity: { available: true, active_7d: 5, active_30d: 8, new_7d: 3, returning_7d: 2, events: 400, daily: dates.map((date, i) => ({ date, learners: i % 5, events: 10 })), domains: [], languages: [] },
  };
  const stages = (a, c) => ({ stages: [{ stage: 'started', available: false, count: null, rate_percent: null }, { stage: 'attempted', available: true, count: a, rate_percent: null }, { stage: 'completed', available: true, count: c, rate_percent: 50 }] });
  const activity = {
    available: true, has_data: true, window_days: 30, active_learners: 5, returning_learners: 3, repeat_practice_learners: 2, cross_skill_returning_learners: null,
    return_windows: [{ days: 1, eligible_learners: 4, returned_learners: 2, return_rate_percent: 50 }, { days: 7, eligible_learners: 0, returned_learners: 0, return_rate_percent: null }],
    skills: [{ skill: 'writing', activities: 10, completions: 6, completion_rate_percent: 60, funnel: stages(10, 6) }, { skill: 'speaking', activities: 5, completions: 5, completion_rate_percent: 100, funnel: stages(null, 5) }],
  };
  for (const ui of ['en', 'vi', 'zh']) {
    copyIndex.setLanguages({ ui, support: 'en' });
    const words = packs[ui];
    const markup = String(page.trafficPage({ overview, activity, days: 7, ui, href }));
    for (const key of ['trafTitle', 'trafSub', 'trafNote', 'trafAccounts', 'trafSignups', 'trafEvents', 'trafPerDay', 'trafSignupsPerDay', 'trafSkills', 'trafFunnel', 'trafReturnWindows', 'trafSkill_writing']) assert.ok(markup.includes(words[key].replace('&', '&amp;')), `${ui}: ${key}`);
    assert.equal((markup.match(/class="a-chipbtn"/g) || []).length, 2, `${ui}: two period chips`);
    assert.match(markup, /data-a="pick"[^>]*data-field="days"[^>]*data-value="7"[^>]*aria-pressed="true"/, `${ui}: 7 days is chosen`);
    assert.equal((markup.match(/class="a-bar"/g) || []).length, 7 + 7 + 2, `${ui}: seven days of each series and two skills`);
    assert.match(markup, new RegExp(`a-metric__value[^>]*>${new Intl.NumberFormat(ui).format(70)}<`), `${ui}: seven days of events`);
    assert.match(markup, />—</, `${ui}: a missing number is a dash`);
    assert.doesNotMatch(markup, /\{[a-z]+\}|undefined|\[object|NaN/i, `${ui}: nothing unfilled`);
    const thirty = String(page.trafficPage({ overview, activity, days: 30, ui, href }));
    assert.equal((thirty.match(/class="a-bar"/g) || []).length, 30 + 30 + 2, `${ui}: thirty days of each series`);
    const empty = String(page.trafficPage({ overview: { accounts: { available: false }, activity: { available: false } }, activity: { available: true, has_data: false, skills: [] }, ui, href }));
    assert.ok(empty.includes(words.opUnavailable) && empty.includes(words.opNone) && empty.includes(words.trafNote), `${ui}: empty says so and keeps the note`);
    assert.ok(String(page.trafficPage({ overview: null, activity: null, failed: true, ui, href })).includes(words.opUnavailable), `${ui}: failed says unavailable`);
    assert.ok(String(page.trafficPage({ overview: null, activity: null, ui, href })).includes('a-skeleton'), `${ui}: loading is the skeleton`);
  }
  copyIndex.setLanguages({ ui: 'en', support: 'en' });
  const overviewPage = String((await import('../static/orena/screens/admin/control-pages.js')).controlPage('adminOverview', { overview: {} }, { href }).markup);
  assert.ok(overviewPage.includes('data-to="#/admin/traffic"'), 'Overview offers Traffic & engagement');
}

/* ---- 5e. Plans & pricing: the flip card, both faces, the PUT body, three languages ---------------- */
{
  const plansPage = await import('../static/orena/screens/admin/plans.js');
  /* Catalogue v2 (D-161): the design's meters; minute meters are stored in seconds. */
  const KEYS = ['writing.review', 'pronunciation.audio', 'orena.message'];
  const catalogue = {
    plans: ['free', 'plus', 'pro'].map((id, index) => ({
      id, name: id, description: `${id} plan`, price_label: id, rank: index,
      prices: { monthly: { USD: index * 9.99, VND: index * 249000 }, yearly: { USD: index * 99, VND: index * 2490000 } },
      entitlements: [
        { key: KEYS[0], enabled: true, limit: 10 * (index + 1), monthly_limit: 10 * (index + 1), window: 'month', unit: 'review', display_unit: 'review', scale: 1, params: {} },
        { key: KEYS[1], enabled: index > 0, limit: 300 * (index + 1), monthly_limit: 300 * (index + 1), window: 'month', unit: 'second', display_unit: 'minute', scale: 60, params: {} },
        { key: KEYS[2], enabled: true, limit: 20, monthly_limit: null, window: 'day', unit: 'message', display_unit: 'message', scale: 1, params: { voice_seconds_per_message: 60 } },
      ],
    })),
    features: KEYS, currencies: ['USD', 'VND'], periods: ['monthly', 'yearly'], source: 'stored', updated_at: '2026-10-09T08:30:00Z', updated_by: 'admin@x.io', billing_ready: false,
  };
  const drafts = Object.fromEntries(catalogue.plans.map((plan) => [plan.id, plansPage.draftOf(plan)]));
  const payload = plansPage.plansPayload(catalogue.plans.map((plan) => drafts[plan.id]));
  assert.equal(payload.version, 2);
  assert.deepEqual(payload.plans.map((plan) => plan.id), ['free', 'plus', 'pro'], 'the whole catalogue is sent');
  assert.deepEqual(payload.plans[1].prices, { monthly: { USD: 9.99, VND: 249000 }, yearly: { USD: 99, VND: 2490000 } });
  assert.deepEqual(payload.plans[1].entitlements, [
    { key: KEYS[0], enabled: true, limit: 20, params: {} },
    { key: KEYS[1], enabled: true, limit: 600, params: {} },
    { key: KEYS[2], enabled: true, limit: 20, params: { voice_seconds_per_message: 60 } },
  ], 'every meter carries its limit in the stored unit, and its own parameters');
  assert.equal(drafts.plus.entitlements[1].limit, '10', 'the operator edits minutes');
  drafts.plus.prices.monthly.USD = '12.5';
  drafts.plus.entitlements[0].limit = 'many';
  drafts.plus.entitlements[1].limit = '2.5';
  drafts.plus.entitlements[2].params.voice_seconds_per_message = '30';
  const edited = plansPage.plansPayload(catalogue.plans.map((plan) => drafts[plan.id]));
  assert.equal(edited.plans[1].prices.monthly.USD, 12.5, 'typed prices become numbers');
  assert.equal(edited.plans[1].entitlements[0].limit, 'many', 'what is not a number is sent as typed, for the server to name');
  assert.equal(edited.plans[1].entitlements[1].limit, 150, 'minutes are sent as seconds');
  assert.equal(edited.plans[1].entitlements[2].params.voice_seconds_per_message, 30);
  drafts.free.prices.monthly.USD = '5';
  assert.deepEqual(plansPage.plansPayload([drafts.free]).plans[0].prices.monthly, { USD: 0, VND: 0 }, 'Free is always free');
  for (const ui of ['en', 'vi', 'zh']) {
    copyIndex.setLanguages({ ui, support: 'en' });
    const markup = String(plansPage.plansPage({ doc: catalogue, drafts: Object.fromEntries(catalogue.plans.map((plan) => [plan.id, plansPage.draftOf(plan)])), editing: { plus: true }, error: { plan: 'plus', message: 'USD price must have at most 2 decimals' }, ui, href }));
    assert.equal((markup.match(/data-plan-card="/g) || []).length, 3, `${ui}: three plan cards`);
    assert.equal((markup.match(/class="a-plan__face a-plan__back"/g) || []).length, 3, `${ui}: every card has a back`);
    assert.equal((markup.match(/is-flipped/g) || []).length, 1, `${ui}: only the card being edited is turned`);
    assert.match(markup, /data-a-input="price\|plus\|monthly\|USD"/, `${ui}: Plus has price inputs`);
    assert.doesNotMatch(markup, /data-a-input="price\|free\|/, `${ui}: Free has no price inputs`);
    assert.match(markup, /data-a-input="limit\|plus\|writing\.review"/, `${ui}: a meter has a limit input`);
    assert.match(markup, /data-a-input="param\|plus\|orena\.message\|voice_seconds_per_message"/, `${ui}: the voice conversion is editable`);
    assert.ok(markup.includes(`${packs[ui].plansUnit_minute} ${packs[ui].plansPer_month}`), `${ui}: unit and window beside the number`);
    assert.ok(markup.includes('USD price must have at most 2 decimals'), `${ui}: the server's message is shown on the back`);
    assert.ok(markup.includes(packs[ui].plansTitle.replace('&', '&amp;')) && markup.includes(packs[ui].plansBilling), `${ui}: title and billing line`);
    assert.ok(markup.includes(packs[ui].plansFree), `${ui}: Free is named`);
    assert.ok(markup.includes('admin@x.io') && markup.includes(packs[ui].plansBy.replace('{name}', 'admin@x.io')), `${ui}: the header names who changed it`);
    assert.doesNotMatch(markup, /\{[a-z]+\}|undefined|\[object/i, `${ui}: nothing unfilled`);
  }
  copyIndex.setLanguages({ ui: 'en', support: 'en' });
  assert.ok(String(plansPage.plansPage({ doc: { ...catalogue, source: 'default', updated_at: null }, drafts, ui: 'en', href })).includes(t('plansDefault')), 'built-in values say so');
  assert.equal(model.areaOf('adminPlans'), 'users');
}
