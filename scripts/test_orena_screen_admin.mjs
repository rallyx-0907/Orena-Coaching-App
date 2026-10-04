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

/* ---- 1. routes: Admin is bare, admin-only, and on the pinned design's own keys ---------------- */
const pin = fs.readFileSync('docs/design/canonical-ui/screens/Orena-Admin.dc.html', 'utf8');
const adminRoutes = ROUTES.filter((route) => route.admin);
assert.deepEqual(adminRoutes.map((route) => route.id).sort(), [...model.ADMIN_ROUTE_IDS].sort(), 'every admin route the shell serves is one the Admin model knows');
for (const route of adminRoutes) {
  assert.ok(route.bare && !route.focus, `${route.id} draws no learner frame and is not a learning workspace`);
  assert.equal(route.screen, 'admin');
  /* The design's own page keys: a frame it draws through its `isReading`-style flags (queue, detail, add,
     cset) is named by the state script's go("...") calls; every other page by its route branch. */
  if (route.id !== 'admin') assert.ok(pin.includes(`r==="${route.design}"`) || pin.includes(`"${route.design}"`), `${route.id}: "${route.design}" is a page of the pinned Admin design`);
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
for (const ui of ['en', 'vi', 'zh']) {
  copyIndex.setLanguages({ ui, support: 'en' });
  const common = { state: live, t, ui, href, now: Date.now() };
  const drawn = [
    pages.listPage({ ...common, view: { tab: 'prov', query: '' } }),
    pages.listPage({ ...common, view: { tab: 'route', query: '' } }),
    pages.listPage({ ...common, view: { tab: 'prov', query: 'zzz-nothing' } }),
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
  /* Listing: the provider rows say what the control plane knows, no more. */
  const list = String(drawn[0].markup);
  assert.ok(list.includes('OpenAI') && list.includes('Google Gemini'));
  assert.ok(list.includes('data-go="#/admin/ai/provider/openai"'), 'a provider row opens its detail');
  assert.doesNotMatch(list, /P95|updated .* ago/, 'no figure the control plane cannot answer');
  /* The key form is write-only: the stored key is not in the field, and a stored provider says so. */
  const keyForm = String(drawn[6].markup);
  assert.match(keyForm, /type="password"[^>]*value=""/, 'the key field never carries a stored key');
  assert.doesNotMatch(keyForm, /value="sk-/);
  /* The remove dialog names the consequence and arms only on the typed name. */
  assert.ok(String(drawn[10].markup).includes('data-a="dialog-confirm" disabled'), 'removal is armed by typing the provider name');
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

/* ---- 6. the old console still reads the same shared code ---------------------------------------- */
const oldAi = await import('../static/orena/admin/ai.js');
assert.equal(oldAi.capabilityKind, shared.capabilityKind, 'one capabilityKind');
assert.equal(oldAi.credentialState, shared.credentialState, 'one credentialState');
assert.equal(oldAi.mergeProviders, shared.mergeProviders, 'one mergeProviders');
const oldApi = await import('../static/orena/admin/api.js');
assert.equal(oldApi.adminApi, (await import('../static/orena/capabilities/admin-api.js')).adminApi, 'one admin client');
const oldFormat = await import('../static/orena/admin/format.js');
assert.equal(oldFormat.latency, (await import('../static/orena/capabilities/admin-format.js')).latency, 'one formatter set');

/* ---- 7. nothing here borrows the old UI, and every colour is a token ------------------------------ */
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
