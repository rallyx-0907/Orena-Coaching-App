/* Gate for the new learner UI's shell (D-088, D-091; Design Contract rules 38, 47, 49).

   The shell's routing rules are read from the pinned design's own state script, so they cannot
   drift from it: the focus list (applyBody), the six primary places (navFor), the rail's and the
   phone bar's items and order (the frame's markup). Routes round-trip; every agent intent a route
   answers is an AGENT_CONTRACT §6.1 id; every registered screen exists. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const PIN = fs.readFileSync('docs/design/canonical-ui/screens/Orena.dc.html', 'utf8');
const script = PIN.slice(PIN.lastIndexOf('</x-dc>'));

const { ROUTES, PRIMARY, entryRoute, match, href, byId } = await import('../static/orena/shell/routes.js');

// 1. Focus routes are exactly the design's focus list (applyBody).
const focusList = JSON.parse(script.match(/b\.dataset\.focus=(\[[^\]]+\])\.includes/)[1]);
// The design's "grammar" (one fixed concept) and "gconcept" (any concept) are one screen here.
const ALIASES = { grammar: 'gconcept' };
/* The 2026-10-08 export adds Plan & usage (billing) and Pricing to the design's focus list; until the export is re-pinned
   (its own PR) they are named here from that export's applyBody list. Remove when the pin lands. */
const EXPORT_ADDED_FOCUS = ['billing', 'pricing'];
const designFocus = new Set([...focusList, ...EXPORT_ADDED_FOCUS].map((key) => ALIASES[key] || key));
// Onboarding (bare) comes from Onboarding.dc.html, not from Orena.dc.html's focus list.
const ourFocus = new Set(ROUTES.filter((route) => route.focus && !route.bare).map((route) => route.design));
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
assert.ok(
  ROUTES.every((route) => !route.bare || route.design === 'onboarding' || route.admin === true),
  'only onboarding and Platform Admin (which draws its own shell, Orena-Admin.dc.html) are drawn without the learner shell',
);
assert.ok(ROUTES.filter((route) => route.admin).every((route) => route.bare && !route.focus), 'an admin place is bare and not a learning workspace');
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
/* The entry (D-098): Welcome only when the server says there is no profile, or no learning language. */
assert.equal(entryRoute({ profile: { exists: false }, activeLanguage: 'en' }), 'welcome', 'no profile: Welcome');
assert.equal(entryRoute({ profile: { exists: true, language: '' }, activeLanguage: '' }), 'welcome', 'no learning language: Welcome');
assert.equal(entryRoute({ profile: { exists: true, language: 'zh', declared_level: '' }, activeLanguage: 'zh' }), 'today', 'a level the backend cannot store is not asked for');
assert.equal(entryRoute({ profile: { exists: true, language: '' }, activeLanguage: 'en' }), 'today', 'the session names the learning language');
assert.equal(entryRoute({ profile: null, activeLanguage: 'en' }), 'today', 'an unreadable profile is not a missing one');
assert.equal(entryRoute(), 'today');
assert.equal(byId(entryRoute({ profile: { exists: false } })).bare, true, 'Welcome is the bare onboarding route');
assert.equal(byId('reader').focus, true);
/* D-101 H9: exactly the eight Coming-soon routes are deferred, and no screen links to one. */
{
  const { isDeferred } = await import('../static/orena/shell/routes.js');
  const deferred = ROUTES.filter((route) => isDeferred(route.id)).map((route) => route.id).sort();
  assert.deepEqual(deferred, ['mock', 'retell', 'rewrite', 'sound', 'timed', 'timedreact', 'timedwr', 'transfer']);
}

/* The implementation map names each screen's route; it must name the one the router serves, or a
   later design revision is applied to the wrong address (a drift found 2026-09-29). */
{
  const map = fs.readFileSync('docs/design/canonical-ui/IMPLEMENTATION_MAP.md', 'utf8');
  const screens = map.slice(map.indexOf('## Screens'), map.indexOf('## Retired by the cutover'));
  const paths = new Set(ROUTES.map((route) => `#/${route.path}`));
  const named = [...screens.matchAll(/^\|[^|]*\|[^|]*\|\s*(`#\/[^|]*)\|/gm)].flatMap((m) => [...m[1].matchAll(/`(#\/[^`?]+)[^`]*`/g)].map((x) => x[1]));
  assert.ok(named.length >= 45, `the map's screen table names its routes (${named.length})`);
  for (const address of named) assert.ok(paths.has(address), `IMPLEMENTATION_MAP names ${address}, which shell/routes.js does not serve`);
}

/* D-101 D2: nothing the new UI loads comes from the old UI's `ui/`. Walked from main.js through
   every static and dynamic relative import; a shared helper moves to kit/ or capabilities/ and the
   old UI points at it, never the other way round. */
{
  const path = await import('node:path');
  const root = path.resolve('static/orena');
  const pattern = /(?:import|export)\s[^'"]*?from\s*['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)|import\s*['"]([^'"]+)['"]/g;
  const seen = new Map();
  const queue = [[path.join(root, 'main.js'), 'entry']];
  while (queue.length) {
    const [file, from] = queue.shift();
    if (seen.has(file) || !fs.existsSync(file)) continue;
    seen.set(file, from);
    for (const m of fs.readFileSync(file, 'utf8').matchAll(pattern)) {
      const spec = m[1] || m[2] || m[3];
      if (spec && spec.startsWith('.')) queue.push([path.resolve(path.dirname(file), spec), file]);
    }
  }
  assert.ok(seen.size > 150, `the new UI's module graph was walked (${seen.size})`);
  const fromOld = [...seen].filter(([file]) => path.relative(root, file).split(path.sep).join('/').startsWith('ui/'));
  assert.deepEqual(
    fromOld.map(([file, from]) => `${path.relative(root, file)} <- ${path.relative(root, from)}`),
    [],
    'a module the new UI loads imports the old ui/ presentation layer',
  );
}

// 6. Agent intents are the contract's (AGENT_CONTRACT §6.1), each used once.
const contract = fs.readFileSync('docs/project/AGENT_CONTRACT.md', 'utf8');
const sixOne = contract.slice(contract.indexOf('### 6.1'), contract.indexOf('## 7.'));
const section = sixOne.slice(sixOne.indexOf('```text') + 7, sixOne.indexOf('```', sixOne.indexOf('```text') + 7));
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
