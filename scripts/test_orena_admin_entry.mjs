import assert from 'node:assert/strict';
import { route, link } from '../static/orena/product/intent.js';
import { api } from '../static/orena/infrastructure/api.js';
import { referenceNavigation } from '../static/orena/ui/reference.js';

const memory = { value: { continuation: [] } };

assert.equal(route('#/admin').page, 'admin', 'admin is a recognised Orena route');
assert.equal(route('#/admin?id=operations').page, 'admin', 'an admin section stays on the admin route');
assert.equal(route('#/admin?id=operations').id, 'operations', 'the section is carried by the route');
assert.equal(link('admin'), '#/admin', 'admin links stay inside the Orena hash router');
assert.equal(typeof api.adminReadinessSummary, 'function', 'the admin screen has a named API boundary');

const navigation = (isAdmin) =>
  referenceNavigation({
    ui: 'en',
    location: route(isAdmin ? '#/admin' : '#/'),
    memory,
    user: { is_admin: isAdmin },
  });

assert.doesNotMatch(navigation(false), /#\/admin/, 'non-admin navigation has no admin entry point');
assert.match(navigation(true), /#\/admin/, 'admin navigation includes the admin entry point');

let requestedPath = '';
globalThis.fetch = async (url) => {
  requestedPath = String(url);
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: async () => ({ available: true, indicators: [] }),
  };
};
await api.adminReadinessSummary();
assert.equal(requestedPath, '/api/admin/readiness-summary', 'admin data crosses the server API boundary');

/* The console renders into the room; its sections read through the admin API
   boundary. Readiness now lives in Operations rather than being the landing
   page, and it renders the server's evidence and approval state unchanged. */
function element() {
  const children = {};
  return {
    innerHTML: '',
    querySelector(selector) {
      children[selector] ||= element();
      return children[selector];
    },
    querySelectorAll: () => [],
    addEventListener() {},
    removeEventListener() {},
  };
}

const { renderAdmin } = await import('../static/orena/ui/admin.js');
const calls = [];
const adminApi = {
  runtime: async () => {
    calls.push('runtime');
    return { persistence_backend: 'postgresql', ai: { learner_runtime_mode: 'legacy' }, app_version: 'test' };
  },
  readiness: async () => {
    calls.push('readiness');
    return {
      available: true,
      state: 'deferred',
      evidence_state: 'ready',
      approval_state: 'not_granted',
      indicators: [{ name: 'runtime_activation', state: 'deferred', source: 'Human activation policy' }],
      redaction: 'aggregate-only',
    };
  },
  aiOperations: async () => ({ available: true, has_data: false }),
  productActivity: async () => ({ available: true, learner_impact_failures: { available: true, by_capability: [] } }),
};
const root = element();
const cleanup = await renderAdmin(root, {
  ui: 'en',
  location: route('#/admin?id=operations'),
  alive: () => true,
  adminApi,
});
assert.equal(typeof cleanup, 'function', 'the console hands the router a cleanup');
assert.match(root.innerHTML, /<h1>Platform Admin<\/h1>/, 'the console names itself');
assert.match(root.innerHTML, /aria-current="page">Operations/, 'the requested section is the current one');
const section = root.querySelector('[data-ac-section]').innerHTML;
assert.ok(calls.includes('readiness'), 'Operations reads readiness through the API');
assert.match(section, /Runtime activation/, 'the section renders returned readiness evidence');
assert.match(section, /Not granted/, 'approval is the server’s, and it is not granted');

console.log('orena admin entry checks passed');
