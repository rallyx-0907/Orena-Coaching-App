import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { route, link } from '../static/orena/product/intent.js';

/* A learner never opens #/admin, and must not pay for the console to exist.
   The check is on the *static* graph: everything the browser fetches before
   any route is entered. The console is reached by a dynamic import inside the
   admin branch (shell/screens.js), so it is absent here and present the moment an
   admin needs it. Written as a source walk rather than a bundler assertion because Orena
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

const learnerGraph = staticGraph(path.join(orenaRoot, 'main.js'));
const adminModules = [...learnerGraph]
  .filter((file) => /[\/]screens[\/]admin[\/]|[\/]capabilities[\/]admin-[\w-]+\.js$/.test(file))
  .map((file) => path.relative(orenaRoot, file));
assert.deepEqual(adminModules, [], 'the learner initial module graph contains no admin module');
assert.ok(learnerGraph.size > 20, 'the graph walk actually followed the learner imports');
assert.match(
  fs.readFileSync(path.join(orenaRoot, 'shell', 'screens.js'), 'utf8'),
  /admin: \(\) => import\(['"]\.\.\/screens\/admin\/screen\.js['"]\)/,
  'the admin route reaches its console through a dynamic import',
);
import { api } from '../static/orena/infrastructure/api.js';

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

/* The retired console's own views - the Operations readiness section, the no-access page and the
   operator entry on the rail - are the learner UI's now, and are asserted by
   scripts/test_orena_screen_admin.mjs (adminAccess, No access in each language, the Profile entry for an
   administrator only) and scripts/test_orena_screen_admin_areas.mjs (Operations and its readiness). */
console.log('orena admin entry checks passed');
