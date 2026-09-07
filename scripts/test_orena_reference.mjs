import assert from 'node:assert/strict';
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
console.log('Golden Star entry routes, experience orientation and EN/ZH parity: PASS');
