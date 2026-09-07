import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { route, link, continuationLink } from '../static/orena/product/intent.js';

assert.equal(route(link('continue')).page, 'continue', 'Continue must have its own reachable experience');
const { experienceFor, entryPoints, referenceCopy } = await import('../static/orena/ui/reference.js');
for (const ui of ['en', 'zh']) {
  const entries = entryPoints(ui);
  assert.equal(new Set(entries.map(x => x.id)).size, entries.length);
  for (const entry of entries) {
    assert.ok(entry.label && entry.href);
    assert.equal(experienceFor(route(entry.href)), entry.id, `entry ${entry.id} must orient the learner correctly`);
  }
  assert.ok(referenceCopy[ui].continueEmpty);
}
assert.equal(experienceFor(route('#/encounter?id=story:test')), 'reading');
assert.equal(experienceFor(route('#/encounter?id=media:test')), 'listening');
assert.equal(experienceFor(route('#/encounter?id=media:test&intent=dictation')), 'practice');
assert.equal(route(continuationLink({id:'conversation:test',intent:'speaking'})).page, 'conversation');
assert.equal(experienceFor(route('#/conversation?id=conversation:test')), 'speaking');
/* --- A row does not reserve space for content it does not have ---

   The pattern list lays each row out on a fixed four-track grid: level, name,
   example, arrow. Only a minority of patterns carry a separate example - the
   rest are named by the sentence itself - so the example track sat empty
   across most of the list while the names wrapped in half the width beside it.
   The rule below gives that space back to the name when there is no example,
   and this holds it. */
const worldCss = readFileSync(new URL('../static/orena/world.css', import.meta.url), 'utf8');
assert.match(
  worldCss,
  /\.pattern-list > a:not\(:has\(> p\)\) > h2 \{\s*grid-column: 2 \/ span 2;/,
  'a pattern with no example must give the reserved track back to its name',
);
// The shared four-track row itself stays: a pattern that does have an example
// still aligns with every other row that does.
assert.match(worldCss, /\.pattern-list > a \{\s*grid-template-columns: 65px/);
/* Narrow, the row already stacks and keeps no reserved track, so the span must
   be given back - otherwise the name spreads under the arrow. The reset has to
   live inside the narrow block, after the rule it undoes. */
const narrow = worldCss.slice(worldCss.indexOf('@media (max-width: 800px)'));
assert.match(
  narrow,
  /\.pattern-list > a:not\(:has\(> p\)\) > h2 \{\s*grid-column: 2;/,
  'the stacked row must not let a name without an example reach the arrow',
);

console.log('Golden Star entry routes, experience orientation, EN/ZH parity and row composition: PASS');
