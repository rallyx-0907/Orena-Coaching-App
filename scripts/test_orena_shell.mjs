/* Gate for the new learner UI's shell (D-088, D-091; Design Contract rules 38, 47, 49).

   The shell's routing rules are read from the pinned design's own state script, so they cannot
   drift from it: the focus list (applyBody), the six primary places (navFor), the rail's and the
   phone bar's items and order (the frame's markup). Routes round-trip; every agent intent a route
   answers is an AGENT_CONTRACT §6.1 id; every registered screen exists. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const PIN = fs.readFileSync('docs/design/canonical-ui/screens/Orena.dc.html', 'utf8');
const script = PIN.slice(PIN.lastIndexOf('</x-dc>'));

const { ROUTES, PRIMARY, match, href, byId } = await import('../static/orena/shell/routes.js');

// 1. Focus routes are exactly the design's focus list (applyBody).
const focusList = JSON.parse(script.match(/b\.dataset\.focus=(\[[^\]]+\])\.includes/)[1]);
// The design's "grammar" (one fixed concept) and "gconcept" (any concept) are one screen here.
const ALIASES = { grammar: 'gconcept' };
const designFocus = new Set(focusList.map((key) => ALIASES[key] || key));
const ourFocus = new Set(ROUTES.filter((route) => route.focus).map((route) => route.design));
assert.deepEqual([...ourFocus].sort(), [...designFocus].sort(), 'learning workspaces are the design focus list');
for (const route of ROUTES.filter((r) => !r.focus)) assert.ok(!designFocus.has(route.design), `${route.id} keeps the shell, as the design does`);

// 2. The six primary places (navFor's list), in order.
const primary = JSON.parse(script.match(/const on=s\.route===r\|\|\(!(\[[^\]]+\])\.includes/)[1]);
assert.deepEqual([...PRIMARY], primary, 'primary places are the design\'s');

// 3. Every drawn screen has a route.
const designRoutes = new Set([...PIN.matchAll(/<sc-if value="\{\{ is([A-Z]\w*) \}\}"/g)].map((m) => m[1]));
const ROUTE_OF_FLAG = {
  Discover: 'discover', Detail: 'detail', Listening: 'listening', Dictation: 'dictation', Practice: 'practice', SkillHub: 'skillhub',
  Today: 'today', OrenaHome: 'orena', Library: 'library', Review: 'review', Reader: 'reader', Speak: 'speak', Compare: 'compare',
  Progress: 'progress', Writing: 'writing', WrCompare: 'wrcompare', CheckU: 'checku', Collection: 'collection', Word: 'word',
  Grammar: 'gconcept', GConcept: 'gconcept', Profile: 'profile', Settings: 'settings', Search: 'search', Shadow: 'shadow',
  FreeTalk: 'freetalk', Conv: 'conv', Situation: 'situation', Retell: 'retell', React: 'react', Timed: 'timed', Transfer: 'transfer',
  Feed: 'feed', Rewrite: 'rewrite', TimedWr: 'timedwr', RTransfer: 'rtransfer', RComplete: 'rcomplete', Attempts: 'attempts',
  SpSummary: 'spsummary', TimedReact: 'timedreact', GrammarLib: 'grammarlib', Respond: 'respond', Discussion: 'discussion',
  Mock: 'mock', Sound: 'sound', ErrFix: 'errfix', Coming: 'coming',
};
const designKeys = new Set(ROUTES.map((route) => route.design));
for (const flag of designRoutes) {
  assert.ok(flag in ROUTE_OF_FLAG, `design screen flag is${flag} is mapped`);
  assert.ok(designKeys.has(ROUTE_OF_FLAG[flag]), `design screen ${flag} has a route`);
}

// 4. Rail and phone bar: the design's items in the design's order.
const shellHead = PIN.slice(PIN.indexOf('<!-- Desktop rail -->'), PIN.indexOf('<!-- Main column -->'));
const railOrder = [...shellHead.matchAll(/onClick="\{\{ go\.(\w+) \}\}"/g)].map((m) => m[1]);
assert.deepEqual(railOrder, ['today', 'discover', 'practice', 'library', 'orena', 'profile'], 'rail order (items, Ask Orena, account)');
const barHtml = PIN.slice(PIN.indexOf('<!-- Mobile bottom nav -->'), PIN.indexOf('</nav>', PIN.indexOf('<!-- Mobile bottom nav -->')));
const barOrder = [...barHtml.matchAll(/onClick="\{\{ go\.(\w+) \}\}"/g)].map((m) => m[1]);
const frame = fs.readFileSync('static/orena/shell/frame.js', 'utf8');
const ours = (name) => [...frame.slice(frame.indexOf(`const ${name} = [`), frame.indexOf('];', frame.indexOf(`const ${name} = [`))).matchAll(/id: '(\w+)'/g)].map((m) => m[1]);
assert.deepEqual(ours('RAIL'), railOrder.slice(0, 4), 'the rail draws the design\'s four places');
assert.deepEqual(ours('BAR'), barOrder, 'the phone bar draws the design\'s five items');

// 5. Routes round-trip and parameters are required.
for (const route of ROUTES) {
  const params = Object.fromEntries([...route.path.matchAll(/:(\w+)/g)].map((m) => [m[1], `x y/${m[1]}`]));
  const address = href(route.id, params, { tab: 'a b' });
  const found = match(address);
  assert.ok(found, `${route.id} matches its own address ${address}`);
  assert.equal(found.route.id === route.id || found.route.path === route.path, true, `${address} resolves to ${route.id}`);
  assert.deepEqual(found.params, params, `${route.id} params survive`);
  assert.equal(found.query.get('tab'), 'a b');
  if (Object.keys(params).length) assert.throws(() => href(route.id, {}), `${route.id} refuses a missing parameter`);
}
assert.equal(match('#/').route.id, 'today', 'the empty address is Today');
assert.equal(match('#/no-such-place'), null, 'an unknown address is refused');
assert.equal(byId('reader').focus, true);

// 6. Agent intents are the contract's (AGENT_CONTRACT §6.1), each used once.
const contract = fs.readFileSync('docs/project/AGENT_CONTRACT.md', 'utf8');
const section = contract.slice(contract.indexOf('### 6.1'), contract.indexOf('## 7.'));
const ids = new Set([...section.matchAll(/\b([a-z]+(?:\.[a-z_]+)?)(?:\{[^}]*\})?/g)].map((m) => m[1]));
const seen = new Set();
for (const route of ROUTES.filter((r) => r.intent)) {
  assert.ok(ids.has(route.intent), `${route.id}: intent ${route.intent} is a contract surface id`);
  assert.ok(!seen.has(route.intent) || route.intent === 'writing.review', `${route.intent} maps to one route`);
  seen.add(route.intent);
}

// 7. Every registered screen exists, and Coming soon is registered.
const registry = fs.readFileSync('static/orena/shell/screens.js', 'utf8');
const registered = [...registry.matchAll(/(\w[\w-]*|'[\w-]+'):\s*\(\)\s*=>\s*import\('\.\.\/screens\/([\w-]+)\/screen\.js'\)/g)];
assert.ok(registered.some((m) => m[2] === 'coming'), 'Coming soon is registered');
for (const [, , folder] of registered) assert.ok(fs.existsSync(`static/orena/screens/${folder}/screen.js`), `screens/${folder}/screen.js exists`);

// 8. Every route's title is in the shell's copy.
const shellCopy = fs.readFileSync('static/orena/copy/shell.js', 'utf8');
for (const route of ROUTES) assert.ok(new RegExp(`'${route.crumb}'`).test(shellCopy), `${route.id}: title key ${route.crumb} declared`);

console.log(`Orena shell: ${ROUTES.length} routes, focus list and primary places are the design's, rail and phone bar match its order, intents are contract ids, ${registered.length} screens registered: PASS`);
