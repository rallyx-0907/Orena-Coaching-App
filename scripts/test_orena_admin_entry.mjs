import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { route, link } from '../static/orena/product/intent.js';

/* A learner never opens #/admin, and must not pay for the console to exist.
   The check is on the *static* graph: everything the browser fetches before
   any route is entered. The console is reached by a dynamic import inside the
   admin branch, so it is absent here and present the moment an admin needs
   it. Written as a source walk rather than a bundler assertion because Orena
   ships browser ESM with no bundler - what the browser follows is exactly
   these import statements. */
const orenaRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'static', 'orena');
const STATIC_IMPORT = /(?:^|[\n;])\s*(?:import|export)\s+(?:[^'"]*?\bfrom\s*)?['"]([^'"]+)['"]/g;

const staticGraph = (entry) => {
  const seen = new Set();
  const queue = [path.resolve(entry)];
  while (queue.length) {
    const file = queue.shift();
    if (seen.has(file) || !fs.existsSync(file)) continue;
    seen.add(file);
    const source = fs.readFileSync(file, 'utf8');
    for (const match of source.matchAll(STATIC_IMPORT)) {
      const specifier = match[1];
      if (!specifier.startsWith('.')) continue;
      queue.push(path.resolve(path.dirname(file), specifier.replace(/[?#].*$/, '')));
    }
  }
  return seen;
};

const learnerGraph = staticGraph(path.join(orenaRoot, 'app.js'));
const adminModules = [...learnerGraph]
  .filter((file) => /[\\/]admin[\\/]|[\\/]admin\.js$/.test(file))
  .map((file) => path.relative(orenaRoot, file));
assert.deepEqual(adminModules, [], 'the learner initial module graph contains no admin module');
assert.ok(learnerGraph.size > 20, 'the graph walk actually followed the learner imports');
assert.match(
  fs.readFileSync(path.join(orenaRoot, 'app.js'), 'utf8'),
  /await import\('\.\/ui\/admin\.js'\)/,
  'the admin route reaches its console through a dynamic import',
);
import { api } from '../static/orena/infrastructure/api.js';
import { referenceNavigation, operatorEntry } from '../static/orena/ui/reference.js';

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

/* The rail draws five learner destinations and no operations (D-065), so the
   operator entry lives with the settings - rendered for an administrator, and
   for nobody else. */
assert.doesNotMatch(navigation(false), /#\/admin/, 'the learner rail has no admin entry point');
assert.doesNotMatch(navigation(true), /#\/admin/, 'and neither does the rail of an administrator');
assert.equal(operatorEntry({ ui: 'en', user: { is_admin: false } }), '', 'a learner is offered no operator entry');
assert.match(operatorEntry({ ui: 'en', user: { is_admin: true } }), /#\/admin/, 'an administrator keeps the way in');

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
