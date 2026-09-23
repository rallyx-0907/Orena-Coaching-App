/* One learner flow per capability (D-078). The addresses of retired screens still work - they
   arrive in the flow that replaced them - and nothing in the app links to them any more, so the old
   screens are never drawn. */
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { legacyRedirect } from '../static/orena/product/legacy-routes.js';
import { route, link } from '../static/orena/product/intent.js';

const to = (hash) => {
  const target = legacyRedirect(route(hash));
  return target ? link(...target) : null;
};

// The Practice hub goes Home; its ways in live there now.
assert.equal(to('#/practice'), link());
// Shadowing without a lesson was a list of moments; Speaking has its own library.
assert.equal(to('#/practice?intent=shadowing'), link('practice', { intent: 'speaking' }));
// Dictation is a way to work on a Listening lesson.
assert.equal(to('#/practice?intent=dictation'), link('practice', { intent: 'follow' }));
assert.equal(to('#/practice?intent=dictation&id=media:x'), link('encounter', { id: 'media:x', intent: 'dictation' }));
// Writing's way in is its own library.
assert.equal(to('#/practice?intent=writing'), link('writing'));
// Current addresses are left alone.
for (const hash of [
  '#/',
  '#/practice?intent=reading',
  '#/practice?intent=follow',
  '#/practice?intent=speaking',
  '#/practice?intent=speaking&id=voice:invitation',
  '#/practice?intent=shadowing&id=media:zh-culture-where-are-you-from',
  '#/practice?intent=grammar',
  '#/practice?intent=recall',
  '#/writing',
  '#/encounter?id=media:x&intent=follow',
])
  assert.equal(to(hash), null, `${hash} is current`);

// The router applies it before anything renders.
const app = readFileSync(new URL('../static/orena/app.js', import.meta.url), 'utf8');
assert.match(app, /const replaced = legacyRedirect\(ctx\.location\);\s*if \(replaced\) \{\s*window\.location\.replace\(link\(\.\.\.replaced\)\);\s*return;/);

// No learner surface links to a retired address, and the retired screens are gone from the code.
const ui = new URL('../static/orena/ui/', import.meta.url);
for (const file of readdirSync(ui).filter((name) => name.endsWith('.js'))) {
  const src = readFileSync(new URL(file, ui), 'utf8');
  assert.equal(/link\('practice'\)/.test(src), false, `${file} links to the retired Practice hub`);
  assert.equal(/link\('practice', \{ intent: '(dictation|writing)' \}\)/.test(src), false, `${file} links to a retired practice list`);
  assert.equal(/link\('practice', \{ intent: 'shadowing' \}\)/.test(src), false, `${file} links to shadowing without a lesson`);
}
const world = readFileSync(new URL('world.js', ui), 'utf8');
assert.equal(/practiceOverview|chooseMoment|class="voices"/.test(world), false, 'the Practice map and its list of moments are deleted');
assert.equal(/export function practiceOverview/.test(readFileSync(new URL('discovery.js', ui), 'utf8')), false);

console.log('Legacy learner routes arrive in the current flows; nothing links to a retired screen: PASS');
