/* Gate for Admin > Operations > Policies & limits (D-17P): the page that edits the server's operational policies.

     a. the model: what a draft is, the change a Save sends (set / reset, never a pinned policy), what needs the
        operator's explicit yes (deleting data, a cap past its sane maximum) - the same rule the server enforces;
     b. the page in English, Vietnamese and Chinese: every group, every field with its label, source tag, unit, range
        and default, a policy pinned by the environment shown locked and read-only, who changed it and when;
     c. the words: every policy the server declares (writing_coach/policies.py) is named and explained in all three
        languages, and the copy has the same keys and placeholders in each;
     d. the flow, driven through the real host: an edit and Save send only the change with the version the page
        loaded; a dangerous change asks first; a stale page (409) shows the server's message and keeps the edits; the
        quota switch saves on its own route;
     e. the route is an operations place, admin-only, on the pinned design's list of kit-only pages.

   No browser: the page is driven through a small stand-in for the DOM it touches. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

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

/* fetch: every request is recorded; the answer is whatever `answer` says for it. */
const requests = [];
let answer = () => ({ status: 404, body: { detail: 'not found' } });
globalThis.fetch = async (url, options = {}) => {
  const method = String(options.method || 'GET').toUpperCase();
  const body = options.body ? JSON.parse(options.body) : undefined;
  requests.push({ method, path: String(url).split('?')[0], body });
  const { status = 200, body: payload = {} } = answer(method, String(url).split('?')[0], body) || {};
  return { ok: status >= 200 && status < 300, status, headers: { get: () => 'application/json' }, json: async () => payload, text: async () => JSON.stringify(payload) };
};

const copyIndex = await import('../static/orena/copy/index.js');
await import('../static/orena/copy/shell.js');
const { t } = await import('../static/orena/screens/admin/copy.js');
const model = await import('../static/orena/screens/admin/model.js');
const page = await import('../static/orena/screens/admin/policies.js');
const { ROUTES, match, href } = await import('../static/orena/shell/routes.js');
const packs = copyIndex.registeredCopy().get('admin').packs;

/* ---- the server's own list of policies, read from its source ------------------------------------------------ */
const source = fs.readFileSync('writing_coach/policies.py', 'utf8');
const declared = [...source.matchAll(/_p\(\s*"([a-z_.0-9]+)",\s*"([a-z]+)"/g)].map(([, key, group]) => ({ key, group }));
assert.ok(declared.length >= 30, `the policies were read from writing_coach/policies.py (${declared.length})`);
const groups = [...new Set(declared.map((item) => item.group))];
assert.deepEqual([...page.GROUP_ORDER].sort(), [...groups, ...(groups.includes('quota') ? [] : ['quota'])].sort(), 'the page draws exactly the server\'s groups');
const keyOf = (prefix, key) => `${prefix}${key.replace(/[.]/g, '_')}`;

/* ---- c. every policy and group is named and explained, in every language -------------------------------------- */
for (const locale of copyIndex.LOCALES) {
  for (const { key } of declared) {
    assert.ok(packs[locale][keyOf('pol_', key)], `${locale}: ${key} is named`);
    assert.ok(packs[locale][keyOf('polHelp_', key)], `${locale}: ${key} is explained`);
  }
  for (const group of page.GROUP_ORDER) {
    assert.ok(packs[locale][`polGroup_${group}`] && packs[locale][`polGroupSub_${group}`], `${locale}: group ${group} is named and explained`);
  }
  for (const choice of ['admitted', 'zero']) assert.ok(packs[locale][`polChoice_quota_abandoned_settles_${choice}`], `${locale}: ${choice}`);
}
const placeholders = (text) => [...String(text).matchAll(/\{([a-z]+)\}/g)].map((m) => m[1]).sort().join(',');
for (const key of Object.keys(packs.en).filter((name) => name.startsWith('pol'))) {
  for (const locale of ['vi', 'zh']) {
    assert.ok(packs[locale][key], `${locale} has ${key}`);
    assert.equal(placeholders(packs[locale][key]), placeholders(packs.en[key]), `${locale}.${key} keeps the placeholders of English`);
    assert.notEqual(packs[locale][key], '', `${locale}.${key} is not empty`);
  }
}
assert.ok(/[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữự]/i.test(packs.vi.polSub), 'Vietnamese keeps its diacritics');
assert.ok(/[一-鿿]/.test(packs.zh.polSub), 'Chinese is written in Chinese');

/* ---- a fixture of the server's answer ------------------------------------------------------------------------- */
const row = (key, group, kind, defaults, extra = {}) => ({
  key, group, kind, unit: '', default: defaults, low: null, high: null, nullable: false, choices: [], danger: '', confirm_above: null,
  env: '', locked: false, source: 'default', value: defaults, admin: null, has_admin: false, ...extra,
});
const fixture = () => ({
  version: 1, groups: [...page.GROUP_ORDER], source: 'stored', state: 'stored', updated_at: '2026-10-11T08:30:00+00:00', updated_by: 'admin@x.io',
  policies: [
    row('quota.abandoned_settles', 'quota', 'enum', 'admitted', { choices: ['admitted', 'zero'] }),
    row('agent.turns_per_window', 'agent', 'int', 12, { unit: 'count', low: 1, high: 600, source: 'admin', has_admin: true, value: 20, admin: 20 }),
    row('voice.enabled', 'voice', 'bool', false, { env: 'AGENT_VOICE_ENABLED', locked: true, source: 'env', value: true }),
    row('speech.take_max_seconds', 'speech', 'int', 300, { unit: 'seconds', low: 10, high: 900 }),
    row('media.model_clips_enabled', 'media', 'bool', true),
    row('rate.writing_ai_per_10min', 'rates', 'int', 30, { unit: 'count', low: 1, high: 5000 }),
    row('feedback.retention_sweep', 'feedback', 'bool', false, { danger: 'delete', env: 'FEEDBACK_RETENTION_SWEEP' }),
    row('feedback.retention_days', 'feedback', 'int', 730, { unit: 'days', low: 30, high: 3650, danger: 'delete' }),
    row('agent.daily_spend_cap_usd', 'spend', 'float', null, { unit: 'usd', low: 0.01, high: 10000, nullable: true, confirm_above: 50, env: 'AGENT_DAILY_SPEND_CAP_USD' }),
    row('media.daily_cap_usd', 'spend', 'float', 25, { unit: 'usd', low: 0, high: 10000, confirm_above: 250 }),
  ],
});
const quotaFixture = (extra = {}) => ({
  enabled: true, meters: ['writing.review'], wired_meters: ['writing.review', 'orena.message', 'pronunciation.audio', 'media.import'], wired_entitlements: ['languages.target'],
  source: 'setting', state: 'enforced', reason: '', store: 'ready', updated_at: '2026-10-11T07:00:00+00:00', updated_by: 'ops@x.io', ...extra,
});
const rowOf = (doc, key) => doc.policies.find((policy) => policy.key === key);

/* ---- a. the model ----------------------------------------------------------------------------------------------- */
{
  const doc = fixture();
  const drafts = page.draftsOf(doc);
  assert.equal(drafts['agent.turns_per_window'], '20', 'a draft is the value in force, as typed');
  assert.equal(drafts['voice.enabled'], true);
  assert.equal(drafts['agent.daily_spend_cap_usd'], '', 'no cap is an empty box');
  assert.deepEqual(page.changeOf(doc, drafts), { set: {}, reset: [], changed: [] }, 'untouched: nothing to send');

  drafts['agent.turns_per_window'] = '30';
  drafts['speech.take_max_seconds'] = ' 120 ';
  drafts['media.model_clips_enabled'] = false;
  drafts['quota.abandoned_settles'] = 'zero';
  drafts['voice.enabled'] = false;          // pinned by the environment: never sent
  drafts['media.daily_cap_usd'] = 'lots';   // not a number: sent as typed, for the server to name
  const change = page.changeOf(doc, drafts);
  assert.deepEqual(change.set, { 'agent.turns_per_window': 30, 'speech.take_max_seconds': 120, 'media.model_clips_enabled': false, 'quota.abandoned_settles': 'zero', 'media.daily_cap_usd': 'lots' });
  assert.deepEqual(change.reset, []);
  assert.ok(!('voice.enabled' in change.set), 'a policy the environment pins is never sent');

  const back = page.draftsOf(doc);
  back['agent.turns_per_window'] = '12';   // the default again: the stored value is removed, so it follows the default
  back['agent.daily_spend_cap_usd'] = '5';
  back['media.daily_cap_usd'] = '25';      // unchanged
  const returned = page.changeOf(doc, back);
  assert.deepEqual(returned.reset, ['agent.turns_per_window']);
  assert.deepEqual(returned.set, { 'agent.daily_spend_cap_usd': 5 });
  const clearing = page.draftsOf({ ...doc, policies: [{ ...rowOf(doc, 'agent.daily_spend_cap_usd'), value: 5, source: 'admin', has_admin: true, locked: false }] });
  clearing['agent.daily_spend_cap_usd'] = '   ';
  assert.deepEqual(page.changeOf({ ...doc, policies: [{ ...rowOf(doc, 'agent.daily_spend_cap_usd'), value: 5, source: 'admin', has_admin: true, locked: false }] }, clearing).reset, ['agent.daily_spend_cap_usd'], 'emptying a cap box returns it to "no cap"');

  /* what needs a yes: the rule the server enforces */
  const need = (key, from, to) => page.needsConfirmation(rowOf(doc, key), from, to);
  assert.equal(need('feedback.retention_sweep', false, true), true, 'switching a deleting job on');
  assert.equal(need('feedback.retention_sweep', true, false), true, 'and off again is confirmed too');
  assert.equal(need('feedback.retention_days', 730, 365), true, 'a shorter retention deletes more');
  assert.equal(need('feedback.retention_days', 730, 730), false);
  assert.equal(need('media.daily_cap_usd', 25, 250), false, 'at the sane maximum');
  assert.equal(need('media.daily_cap_usd', 25, 251), true, 'past the sane maximum');
  assert.equal(need('media.daily_cap_usd', 500, 100), false, 'lowering a cap needs nothing');
  assert.equal(need('agent.daily_spend_cap_usd', 5, null), true, 'removing a cap is past any maximum');
  assert.equal(need('agent.turns_per_window', 12, 400), false, 'an ordinary limit needs nothing');
  const sweep = page.changeOf(doc, { ...page.draftsOf(doc), 'feedback.retention_sweep': true, 'media.daily_cap_usd': '900', 'agent.turns_per_window': '40' });
  assert.deepEqual(page.confirmationsOf(sweep).map(({ policy }) => policy.key), ['feedback.retention_sweep', 'media.daily_cap_usd']);

  /* the quota switch is its own document: the whole switch, with the version it was loaded at */
  const quota = quotaFixture();
  const draft = page.quotaDraftOf(quota);
  assert.deepEqual(draft.meters, { 'writing.review': true, 'orena.message': false, 'pronunciation.audio': false, 'media.import': false, 'languages.target': false });
  draft.meters['orena.message'] = true;
  draft.enabled = false;
  assert.deepEqual(page.quotaPayload(quota, draft), { enabled: false, meters: ['writing.review', 'orena.message'], expected_updated_at: '2026-10-11T07:00:00+00:00' });
  assert.equal(page.quotaPayload({ ...quota, updated_at: null }, draft).expected_updated_at, null, '"nothing stored yet" is a version too');
}

/* ---- b. the page in three languages ------------------------------------------------------------------------------ */
const render = (ui, extra = {}) => {
  copyIndex.setLanguages({ ui, support: 'en' });
  const doc = extra.doc || fixture();
  return String(page.policiesPage({ doc, quota: quotaFixture(), quotaDraft: page.quotaDraftOf(quotaFixture()), drafts: page.draftsOf(doc), view: extra.view || {}, ui, href, ...extra.rest }));
};
for (const ui of ['en', 'vi', 'zh']) {
  const words = packs[ui];
  const markup = render(ui);
  const esc = (text) => String(text).replaceAll('&', '&amp;');
  assert.ok(markup.includes(esc(words.polTitle)), `${ui}: title`);
  assert.ok(markup.includes('data-screen-label="Policies &amp; limits"') || markup.includes('data-screen-label="Policies & limits"'), `${ui}: the screen is labelled`);
  assert.ok(markup.includes(esc(words.polQuotaTitle)) && markup.includes('data-field="quota|enabled"'), `${ui}: the quota switch block`);
  assert.equal((markup.match(/data-field="quota\|meter\|/g) || []).length, 5, `${ui}: a switch for each of the five enforceable features`);
  for (const group of page.GROUP_ORDER) assert.ok(markup.includes(esc(words[`polGroup_${group}`])), `${ui}: group ${group}`);
  for (const policy of fixture().policies) {
    assert.ok(markup.includes(esc(words[keyOf('pol_', policy.key)])), `${ui}: ${policy.key} is labelled`);
    assert.ok(markup.includes(esc(words[keyOf('polHelp_', policy.key)])), `${ui}: ${policy.key} says what it does`);
  }
  /* source, value, unit, range, default */
  assert.ok(markup.includes(esc(words.polSourceAdmin)) && markup.includes(esc(words.polSourceDefault)), `${ui}: a value is Default or Set in Admin`);
  const fmt = new Intl.NumberFormat(ui);
  assert.ok(markup.includes(esc(words.polRange.replace('{low}', fmt.format(10)).replace('{high}', fmt.format(900)).replace('{unit}', ` ${words.polUnit_seconds}`))), `${ui}: the allowed range with its unit`);
  assert.ok(markup.includes(esc(words.polDefaultIs.replace('{value}', `${fmt.format(300)} ${words.polUnit_seconds}`))), `${ui}: the default with its unit`);
  assert.ok(markup.includes(esc(words.polDefaultIs.replace('{value}', words.polNoCap))), `${ui}: a cap's default is "no cap"`);
  assert.ok(markup.includes(esc(words.polDangerHint)), `${ui}: a deleting policy says it is confirmed`);
  assert.match(markup, /name="pol\|agent\.turns_per_window"[^>]*value="20"/, `${ui}: the value in force is in the box`);
  /* a policy pinned by the environment */
  assert.ok(markup.includes(esc(words.polLocked)) && markup.includes(esc(words.polLockedHint.replace('{env}', 'AGENT_VOICE_ENABLED'))), `${ui}: pinned: tagged and told which variable`);
  assert.match(markup, /data-field="pol\|voice\.enabled"[^>]*disabled/, `${ui}: a pinned switch cannot be turned`);
  assert.doesNotMatch(markup, /data-field="pol\|media\.model_clips_enabled"[^>]*disabled/, `${ui}: an unpinned one can`);
  /* who and when */
  assert.ok(markup.includes('admin@x.io') && markup.includes(esc(words.polChangedBy.replace('{name}', 'admin@x.io'))), `${ui}: the header names who changed it`);
  assert.ok(markup.includes('ops@x.io'), `${ui}: and who last changed the quota switch`);
  assert.ok(markup.includes(esc(words.polQuotaState_enforced)), `${ui}: the quota state`);
  assert.equal((markup.match(/data-a="policies-save"/g) || []).length, 2, `${ui}: Save in the head and at the foot`);
  assert.doesNotMatch(markup, /\{[a-z]+\}|undefined|\[object|NaN/i, `${ui}: nothing unfilled`);
  /* the other states */
  assert.ok(render(ui, { rest: { doc: null }, doc: null }).includes('a-skeleton'), `${ui}: loading is the skeleton`);
  assert.ok(render(ui, { rest: { failed: true } }).includes(esc(words.opUnavailable)), `${ui}: failed says unavailable`);
  const stale = render(ui, { doc: { ...fixture(), state: 'stale' } });
  assert.ok(stale.includes(esc(words.polStateStale)), `${ui}: a store that did not answer is said`);
  const defaults = render(ui, { doc: { ...fixture(), source: 'default', updated_at: null, updated_by: null } });
  assert.ok(defaults.includes(esc(words.polDefaultDoc)), `${ui}: built-in values say so`);
  const error = render(ui, { view: { error: 'The policies were changed by someone else since you opened this page. Reload to see them.', status: '' } });
  assert.ok(error.includes('changed by someone else'), `${ui}: the server's refusal is shown`);
  const locked = String(page.policiesPage({ doc: fixture(), quota: quotaFixture({ source: 'environment' }), quotaDraft: page.quotaDraftOf(quotaFixture()), drafts: page.draftsOf(fixture()), view: {}, ui, href }));
  assert.ok(locked.includes(esc(words.polQuotaLockedHint)) && locked.includes(esc(words.polLocked)), `${ui}: the quota switch pinned by the environment is locked`);
  const gone = String(page.policiesPage({ doc: fixture(), quota: null, quotaDraft: null, drafts: page.draftsOf(fixture()), view: {}, ui, href }));
  assert.ok(gone.includes(esc(words.polQuotaUnavailable)), `${ui}: an unreadable quota switch is said`);
}
copyIndex.setLanguages({ ui: 'en', support: 'en' });
assert.ok(page.valueLabel(rowOf(fixture(), 'agent.daily_spend_cap_usd'), null).includes('No cap'));
assert.equal(page.valueLabel(rowOf(fixture(), 'voice.enabled'), true), t('polOn'));
assert.equal(page.policyLabel({ key: 'future.policy_key', kind: 'int' }), 'Future policy key', 'a policy this build has no words for falls back to its key');

/* ---- e. the place -------------------------------------------------------------------------------------------------- */
{
  const route = match('#/admin/operations/policies').route;
  assert.equal(route.id, 'adminPolicies');
  assert.ok(route.admin && route.bare && !route.focus, 'an admin place, drawn without the learner frame');
  assert.equal(model.areaOf('adminPolicies'), 'operations');
  assert.ok(model.ADMIN_ROUTE_IDS.includes('adminPolicies') && ROUTES.some((r) => r.id === 'adminPolicies'));
  const gate = fs.readFileSync('scripts/test_orena_screen_admin.mjs', 'utf8');
  assert.ok(/adminPolicies:\s*'Policies & limits/.test(gate), 'the page is registered as a kit-only page with its reason');
  const operations = String((await import('../static/orena/screens/admin/control-pages.js')).controlPage('adminOperations', { runtime: {}, telemetry: {} }, { href }).markup);
  assert.ok(operations.includes('data-go="#/admin/operations/policies"'), 'Operations offers Policies & limits');
  const guardedRoutes = fs.readFileSync('tests/test_admin_authorization_matrix.py', 'utf8');
  for (const route of ['("GET", "/api/product/admin/policies")', '("PUT", "/api/product/admin/policies")', '("GET", "/api/product/admin/quota")', '("PUT", "/api/product/admin/quota")']) {
    assert.ok(guardedRoutes.includes(route), `${route} is in the authorization matrix (anonymous 401, learner 403)`);
  }
}

/* ---- d. the flow, through the real host ---------------------------------------------------------------------------- */
{
  const listeners = { page: {}, layer: {} };
  /* A node that remembers the nodes asked of it by selector, so the dialog host keeps its markup between paints. */
  const node = () => {
    const children = new Map();
    return {
      innerHTML: '', value: '', disabled: false, scrollTop: 0, textContent: '', dataset: {},
      focus() {}, remove() {}, setAttribute() {}, append() {},
      querySelector(selector) { if (!children.has(selector)) children.set(selector, node()); return children.get(selector); },
    };
  };
  const holder = (name) => Object.assign(node(), {
    addEventListener: (type, fn) => { listeners[name][type] = fn; },
    removeEventListener() {}, contains: () => true,
  });
  const shell = { page: holder('page'), layer: holder('layer'), main: { scrollTop: 0 }, filter: holder('filter'), setTitle() {}, setFilter() {} };
  shell.filter.addEventListener = () => {};
  const server = { doc: fixture(), quota: quotaFixture(), conflict: false, needConfirm: false };
  answer = (method, path, body) => {
    if (path === '/api/product/admin/policies' && method === 'GET') return { body: server.doc };
    if (path === '/api/product/admin/quota' && method === 'GET') return { body: server.quota };
    if (path === '/api/product/admin/policies' && method === 'PUT') {
      if (server.conflict) return { status: 409, body: { detail: 'The policies were changed by someone else since you opened this page. Reload to see them.' } };
      const values = { ...Object.fromEntries(server.doc.policies.filter((p) => p.has_admin).map((p) => [p.key, p.admin])), ...body.set };
      server.doc = { ...server.doc, updated_at: '2026-10-11T09:00:00+00:00', updated_by: 'me@x.io', policies: server.doc.policies.map((p) => (p.key in values ? { ...p, value: values[p.key], admin: values[p.key], has_admin: true, source: 'admin' } : p)) };
      return { body: server.doc };
    }
    if (path === '/api/product/admin/quota' && method === 'PUT') {
      if (server.conflict) return { status: 409, body: { detail: 'The switch was changed by someone else since you opened this page. Reload to see it.' } };
      server.quota = quotaFixture({ enabled: body.enabled, meters: body.meters, updated_at: '2026-10-11T09:30:00+00:00', updated_by: 'me@x.io' });
      return { body: server.quota };
    }
    return { status: 404, body: { detail: 'no' } };
  };
  const ctx = { href, go() {}, isCurrent: () => true, route: { id: 'adminPolicies' }, params: {}, context: {}, setCrumb() {} };
  const cleanup = await page.mountPolicies(shell, ctx);
  assert.equal(typeof cleanup, 'function');
  assert.deepEqual(requests.map((r) => `${r.method} ${r.path}`).sort(), ['GET /api/product/admin/policies', 'GET /api/product/admin/quota']);
  assert.ok(shell.page.innerHTML.includes('name="pol|agent.turns_per_window"'), 'the page is painted from the server\'s answer');

  const control = (data) => ({ dataset: data, tagName: 'BUTTON', disabled: false });
  const click = (data, layer = false) => (layer ? listeners.layer : listeners.page).click({ target: { closest: () => control(data) }, stopPropagation() {}, preventDefault() {} });
  const type = (name, value) => listeners.page.input({ target: { closest: () => ({ dataset: { aInput: name }, value }) } });
  const flush = () => new Promise((resolve) => setTimeout(resolve, 5));
  requests.length = 0;

  /* nothing changed: nothing sent */
  await click({ a: 'policies-save' });
  await flush();
  assert.equal(requests.length, 0, 'an untouched page sends nothing');
  assert.ok(shell.page.innerHTML.includes(packs.en.polNothing));

  /* an edit sends only the change, with the version the page loaded */
  type('pol|agent.turns_per_window', '35');
  await click({ a: 'policies-save' });
  await flush();
  assert.equal(requests.length, 1);
  assert.deepEqual(requests[0].body, { set: { 'agent.turns_per_window': 35 }, reset: [], expected_updated_at: '2026-10-11T08:30:00+00:00' });
  assert.ok(shell.page.innerHTML.includes(packs.en.polSaved) && shell.page.innerHTML.includes('me@x.io'), 'saved: said, and who changed it');
  assert.match(shell.page.innerHTML, /name="pol\|agent\.turns_per_window"[^>]*value="35"/);

  /* a dangerous change asks first; no is no request, yes carries the confirmation */
  requests.length = 0;
  await click({ a: 'toggle', field: 'pol|feedback.retention_sweep' });
  const asking = click({ a: 'policies-save' });
  await flush();
  assert.equal(requests.length, 0, 'nothing is sent before the operator answers');
  const dialog = shell.layer.querySelector('[data-part="dialog"]').innerHTML;
  assert.ok(dialog.includes(packs.en.polConfirmTitle) && dialog.includes(packs.en.polConfirmBodyDelete), 'the dialog says what is at stake');
  assert.ok(dialog.includes(`${packs.en.pol_feedback_retention_sweep}: ${packs.en.polOff} → ${packs.en.polOn}`.replace('→', '→')), 'and lists the change');
  await click({ a: 'dialog-cancel' }, true);
  await asking;
  await flush();
  assert.equal(requests.length, 0, 'cancelling sends nothing');
  const again = click({ a: 'policies-save' });
  await flush();
  await click({ a: 'dialog-confirm' }, true);
  await again;
  await flush();
  assert.equal(requests.length, 1);
  assert.deepEqual(requests[0].body.set, { 'feedback.retention_sweep': true });
  assert.deepEqual(requests[0].body.confirm, { 'feedback.retention_sweep': true }, 'the confirmation travels with the change');
  assert.equal(requests[0].body.expected_updated_at, '2026-10-11T09:00:00+00:00', 'the version the last save returned');

  /* a stale page: the server's message, the edits kept */
  requests.length = 0;
  server.conflict = true;
  type('pol|speech.take_max_seconds', '90');
  await click({ a: 'policies-save' });
  await flush();
  assert.ok(shell.page.innerHTML.includes('changed by someone else'), 'a 409 is shown to the operator');
  assert.match(shell.page.innerHTML, /name="pol\|speech\.take_max_seconds"[^>]*value="90"/, 'and what they typed is still there');
  assert.ok(!shell.page.innerHTML.includes(packs.en.polSaved) || shell.page.innerHTML.includes('changed by someone else'));

  /* the quota switch saves on its own route, with its own version, and also meets a 409 */
  requests.length = 0;
  await click({ a: 'toggle', field: 'quota|meter|orena.message' });
  await click({ a: 'quota-save' });
  await flush();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].path, '/api/product/admin/quota');
  assert.deepEqual(requests[0].body, { enabled: true, meters: ['writing.review', 'orena.message'], expected_updated_at: '2026-10-11T07:00:00+00:00' });
  assert.ok(shell.page.innerHTML.includes('changed by someone else since you opened this page. Reload to see it.'), 'the quota 409 is shown in its own block');
  server.conflict = false;
  await click({ a: 'quota-save' });
  await flush();
  assert.ok(shell.page.innerHTML.includes('me@x.io') && shell.page.innerHTML.includes(packs.en.polSaved));
  cleanup();
}

console.log('Admin policies & limits: model, page (EN/VI/ZH), copy parity, locked state, confirmation, CAS conflict and quota switch checks passed');
