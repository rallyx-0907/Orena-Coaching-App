import assert from 'node:assert/strict';
import { route, link } from '../static/orena/product/intent.js';
import { api } from '../static/orena/infrastructure/api.js';
import { referenceNavigation, operatorEntry } from '../static/orena/ui/reference.js';

const memory = { value: { continuation: [] } };

assert.equal(route('#/admin').page, 'admin', 'admin is a recognised Orena route');
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

const { renderAdmin } = await import('../static/orena/ui/admin.js');
const root = {
  innerHTML: '',
  querySelector: () => null,
};
let renderCalls = 0;
await renderAdmin(root, {
  c: {
    adminTitle: 'Platform readiness',
    adminNote: 'Authorised view',
    adminLoading: 'Loading',
    adminUnavailable: 'Unavailable',
    adminEmpty: 'Empty',
    adminState: 'Evidence state',
    adminApproval: 'Approval state',
    adminIndicators: 'Indicators',
    adminSource: 'Source',
    adminDetail: 'Detail',
    adminRedaction: 'Data boundary',
    adminRetry: 'Read again',
  },
  alive: () => true,
  api: {
    adminReadinessSummary: async () => {
      renderCalls += 1;
      return {
        available: true,
        state: 'deferred',
        evidence_state: 'ready',
        approval_state: 'not_granted',
        indicators: [{ name: 'runtime_activation', state: 'deferred', source: 'Human activation policy' }],
        redaction: 'aggregate-only',
      };
    },
  },
});
assert.equal(renderCalls, 1, 'the screen reads its data through the API method');
assert.match(root.innerHTML, /runtime_activation/, 'the screen renders returned readiness evidence');

console.log('orena admin entry checks passed');
