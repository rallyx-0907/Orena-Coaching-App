/* Three states a set or a sitting can be in, and the answers that wait.
 *
 * Frames 30 "Deck nothing due mobile", 31 "Review offline mobile" and 32
 * "Deck load error mobile". What these hold is the part that is easy to break
 * without noticing: an answer given with no network must not be lost, must not
 * be reordered, and must not be retried forever.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  MAX_WAITING,
  flushQueue,
  readQueue,
  withWaiting,
  worthKeeping,
} from '../static/orena/product/review-queue.js';

const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');
const room = read('ui/expression.js');
const css = read('rooms.css');
const copy = read('ui/copy.js');
const copyVi = read('ui/copy-vi.js');

/* --- What waits, and in what order -------------------------------------- */

const at = '2026-09-23T10:00:00Z';
let queue = withWaiting([], 'harbour', 'got_it', at);
queue = withWaiting(queue, 'lantern', 'again', at);
assert.deepEqual(
  queue.map((item) => item.word),
  ['harbour', 'lantern'],
  'answers wait in the order they were given',
);

const sent = [];
const left = await flushQueue(queue, (item) => {
  sent.push(item.word);
  return Promise.resolve();
});
assert.deepEqual(sent, ['harbour', 'lantern'], 'and go up in that order');
assert.deepEqual(left, [], 'nothing is left behind');

/* One that will not go blocks the ones behind it: they are later events in
   the same schedule, and sending them first would leave a card wrong. */
const stillLeft = await flushQueue(queue, (item) => {
  if (item.word === 'harbour') return Promise.reject(Object.assign(new Error('down'), { status: 503 }));
  return Promise.resolve();
});
assert.deepEqual(stillLeft.map((i) => i.word), ['harbour', 'lantern'], 'a failure holds the queue');

/* A refusal is not a network problem: it would be refused again forever, so
   it is dropped rather than blocking every answer behind it. */
const afterRefusal = await flushQueue(queue, (item) =>
  item.word === 'harbour'
    ? Promise.reject(Object.assign(new Error('gone'), { status: 404 }))
    : Promise.resolve(),
);
assert.deepEqual(afterRefusal, [], 'a refusal is dropped, not retried forever');

assert.equal(worthKeeping({ status: 503 }), true, 'a server that is down is worth waiting for');
assert.equal(worthKeeping({ status: 422 }), false, 'a refusal is not');
assert.equal(worthKeeping(new Error('failed to fetch')), true, 'and a request that never arrived is');

/* Read back from the device, nothing is believed: a grade the scheduler does
   not take, or a row that is not one, does not come back. */
assert.deepEqual(readQueue([{ word: 'x', grade: 'brilliant', at }]), [], 'an unknown grade is not a grade');
assert.deepEqual(readQueue('not a queue'), []);
assert.equal(readQueue(Array.from({ length: 400 }, () => ({ word: 'x', grade: 'again', at }))).length, MAX_WAITING);

/* --- One route for every grade ------------------------------------------ */

assert.match(room, /const record = async \(word, grade\) => \{/, 'one place every grade goes');
assert.match(room, /memory\.setReviewQueue\(waiting\)/, 'what waits is the device’s memory');
assert.match(room, /window\.addEventListener\('online'/, 'and goes up when there is a connection');

/* --- The three states are drawn, and measured --------------------------- */

assert.match(room, /const deckNothingDue = \(\) =>/, 'a set with nothing due has its own screen');
assert.match(room, /const deckLoadError = \(\) =>/, 'and so does one that would not load');
assert.match(room, /collectionFailed = `VOC-\$\{Number\(error\?\.status \|\| 0\) \|\| 'OFF'\}`/,
  'which carries the code a learner can quote');
assert.match(room, /class="recall-offline"/, 'no network is said once, above the card');
assert.match(room, /class="recall-waiting ds-data"/, 'and counted at the foot');

for (const [what, rule] of [
  ['the mark', /\.deck-state__mark \{\n  inline-size: 72px;/],
  ['the title', /\.deck-state__body h2 \{[^}]*font-size: 22px;/s],
  ['the note', /\.deck-state__body p \{ margin: 0; font-size: 14\.5px; line-height: 1\.55;/],
  ['the offline notice', /\.recall-offline \{\n  flex: none;[^}]*padding: 11px 13px;\n  border-radius: 13px;/s],
])
  assert.match(css, rule, `${what} is the frame’s size`);

/* The set's screen says a real number or says nothing: both come from counts
   the app already has, never from an estimate. */
assert.match(room, /const tomorrow = Number\(summary\(\)\.due_next_day \|\| 0\);/, 'tomorrow is counted');
assert.match(room, /const unlearned = Math\.max\(0, total - learned\);/, 'and so is what is left to learn');

for (const key of ['deckAllDoneToday', 'deckNextUp', 'deckLearnNew', 'deckFreePractice', 'deckLoadFailed', 'deckLoadFailedNote', 'recallOffline', 'recallWaiting']) {
  assert.equal((copy.match(new RegExp(`${key}:`, 'g')) || []).length, 2, `${key} in English and Chinese`);
  assert.ok(copyVi.includes(`${key}:`), `${key} in Vietnamese`);
}

console.log('test_orena_review_states.mjs: nothing due, no network, and a set that would not load');
