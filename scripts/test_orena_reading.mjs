import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

/* Reading's source truth, as the learner UI (D-143) holds it. The pre-cutover
   encounter/comprehension/history renderers and the old readable-contract
   module went with the retired UI; the Check screen
   (screens/check) is the successor and is gated by test_orena_screen_check.mjs,
   the Reader by test_orena_screen_reader.mjs. What stays here is what does not
   depend on a retired module. */

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

/* A published article's check is the approved set served for it, and its
   answers are saved as canonical Reading evidence under one operation id that
   every retry reuses. */
const check = read('static/orena/screens/check/screen.js');
const api = read('static/orena/infrastructure/api.js');
assert.match(check, /api\.readingPracticeSet\(/, 'the article reads its approved set');
assert.match(check, /submit_enabled/, 'questions are offered only while submit is open');
assert.match(check, /api\.submitReadingPractice\(setId, operationId,/, 'answers go to canonical evidence under one operation id');
assert.doesNotMatch(api + check, /selection_policy_version|selectionPolicyVersion/,
  'whether the selection policy chose a set is the server\'s to record, never the client\'s to claim');
assert.doesNotMatch(check, /readingSession|'reading:'/, 'no generated session is opened');

{
  const { route, link } = await import('../static/orena/product/intent.js');
  assert.equal(route(link('encounter', { id: 'article:a1', intent: 'reading', rec: 'rr1.p.s' }).slice(1)).rec, 'rr1.p.s',
    'a recommendation survives the address it rides in');
  assert.equal(route(link('encounter', { id: 'article:a1', intent: 'reading' }).slice(1)).rec, '',
    'and an address without one carries none');
}

/* Nothing reads the retired generated-reading sessions. */
assert.doesNotMatch(api, /readingSessions/, 'the client never reads the retired sessions');

// The generated-passage studio is retired (D-082): no internal AI writes a
// source passage, so neither its service nor its routes may come back.
assert.ok(
  !existsSync(new URL('../writing_coach/becoming_reading.py', import.meta.url)),
  'the AI passage generator is removed, not kept beside the corpus',
);
const appSource = read('app.py');
assert.ok(
  !appSource.includes('"/api/reading/session'),
  'no route serves or creates a generated reading session',
);

console.log('Reading: canonical evidence, no generated sessions, retired generator stays retired PASS');
