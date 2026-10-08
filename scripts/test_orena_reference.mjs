/* The routing contract of product/intent.js: every practice intent still routes, because saved
   continuations and kept-language provenance hold these hrefs. (The learner shell, its rail, tab
   bar and measures are the test_orena_shell*.mjs and test_orena_kit*.mjs gates.) */
import assert from 'node:assert/strict';
import { route, link, continuationLink, practiceIntentions } from '../static/orena/product/intent.js';

assert.equal(route(link('continue')).page, 'continue', 'Continue must have its own reachable address');
assert.equal(route(continuationLink({ id: 'conversation:test', intent: 'speaking' })).page, 'conversation');

/* The engine contract is untouched. */
assert.deepEqual(
  practiceIntentions,
  ['follow', 'reading', 'dictation', 'shadowing', 'speaking', 'writing', 'grammar', 'recall'],
  'the practice-intent contract must survive any navigation change',
);
for (const intent of practiceIntentions)
  assert.equal(route(link('practice', { intent })).intent, intent, `${intent} must still resolve`);
for (const page of ['content', 'language', 'continue', 'expression', 'encounter', 'conversation', 'collection'])
  assert.equal(route(`#/${page}`).page, page, `${page} must still resolve`);

console.log('Reference routing: the intent contract and every saved address still resolve: PASS');
