/* Coming back to what you were actually doing.

   The continuation shelf is the product's promise that leaving a thing does
   not lose it. A thread that names the wrong work, opens something else, or
   offers work that is no longer there breaks that promise more completely
   than having no shelf at all - the learner trusted it and it was wrong.

   Everything here is device-scoped by design. This file also holds the line
   that it must never say otherwise. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { learnerMemory } from '../static/orena/product/memory.js';
import { conversation } from '../static/orena/product/conversation.js';
import {
  continuationExperience,
  continuationLink,
  practiceIntentions,
} from '../static/orena/product/intent.js';
import {
  continuationEntries,
  continuationShelf,
  resumable,
} from '../static/orena/ui/patterns.js';
import { copy } from '../static/orena/ui/copy.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const store = () => {
  const data = {};
  return {
    data,
    getItem: (k) => data[k] ?? null,
    setItem: (k, v) => {
      data[k] = v;
    },
  };
};
const ctxFor = (memory, ui = 'en', language = 'en') => ({ memory, c: copy[ui], language });

/* --- A destination only receives its own work --- */

const mixedMemory = {
  value: {
    continuation: [
      { id: 'media:night-market', title: 'Night market voices', intent: 'follow' },
      { id: 'story:last-train', title: 'The last train home', intent: 'reading' },
      { id: 'voice:coffee', title: 'Order a coffee', intent: 'speaking' },
      { id: 'expression:note', title: 'A note', intent: 'writing' },
    ],
    conversations: {},
    expressions: {},
  },
};
assert.equal(continuationExperience(mixedMemory.value.continuation[0]), 'listening');
assert.equal(continuationExperience(mixedMemory.value.continuation[1]), 'reading');
assert.equal(continuationExperience(mixedMemory.value.continuation[2]), 'speaking');
assert.equal(continuationExperience(mixedMemory.value.continuation[3]), 'writing');
assert.deepEqual(
  continuationEntries(mixedMemory, { experience: 'listening' }).map((item) => item.id),
  ['media:night-market'],
  'Listening must not borrow Reading or Speaking continuation',
);
assert.deepEqual(
  continuationEntries(mixedMemory, { experience: 'reading' }).map((item) => item.id),
  ['story:last-train'],
  'Reading receives the reading thread that previously appeared under Listening',
);
const rail = continuationShelf(ctxFor(mixedMemory), 20, {
  compact: true,
  rail: true,
});
assert.match(rail, /thread-list--rail/, 'compact continuation uses the shared swipe rail');
assert.equal((rail.match(/class="thread thread--rail"/g) || []).length, 4);
assert.doesNotMatch(rail, /<p>/, 'compact continuation cards do not repeat state prose');

/* --- An intention survives a visit that does not name one --- */

const box = store();
const memory = learnerMemory(box, 'owner-a', 'en');
const STORY = 'story:last-train';

// The learner opens a passage, then begins writing about it.
memory.enter({ id: STORY, title: 'The last train home', excerpt: 'Outside, the last shops...' });
memory.enter({ id: STORY, title: 'The last train home', intent: 'writing', excerpt: 'Outside, the last shops...' });
memory.write(STORY, 'What I remember most is the quiet.');
assert.equal(memory.value.continuation[0].intent, 'writing');

// They reopen the passage itself. Reading it again is not abandoning the draft.
memory.enter({ id: STORY, title: 'The last train home', excerpt: 'Outside, the last shops...' });
assert.equal(
  memory.value.continuation[0].intent,
  'writing',
  'a visit that says nothing about intention must not erase one',
);
assert.equal(
  continuationLink(memory.value.continuation[0]),
  '#/expression?id=story%3Alast-train',
  'the thread must open the draft it is showing, not the source it came from',
);
const shelf = continuationShelf(ctxFor(memory));
assert.ok(shelf.includes(copy.en.draftLabel), 'a draft is named as a draft');
assert.ok(
  shelf.includes('What I remember most is the quiet.'),
  'the shelf shows the work it is offering to reopen',
);

/* --- A stated intention is still honoured, including none ---

   Closing a practice panel passes `intent: null` deliberately: the learner is
   back to the encounter itself and the thread must say so. */
memory.enter({ id: STORY, title: 'The last train home', intent: null });
assert.equal(memory.value.continuation[0].intent, null, 'a stated intention wins');
assert.equal(
  continuationLink(memory.value.continuation[0]),
  '#/encounter?id=story%3Alast-train',
);
memory.enter({ id: STORY, title: 'The last train home', intent: 'dictation' });
assert.equal(memory.value.continuation[0].intent, 'dictation');
// And it survives a reload, still routing where the learner left off.
assert.equal(learnerMemory(box, 'owner-a', 'en').value.continuation[0].intent, 'dictation');

// The moment inside a recording is carried the same way, and reopening the
// encounter without one does not lose the line the learner stopped on.
memory.enter({ id: 'media:x', title: 'A recording', intent: 'follow', segment: 's4' });
memory.enter({ id: 'media:x', title: 'A recording' });
assert.equal(memory.value.continuation[0].segment, 's4');
assert.equal(memory.value.continuation[0].intent, 'follow');

/* --- An intention the product no longer has routes nowhere --- */

const tampered = store();
tampered.setItem(
  'orena.encounters.v1:owner-a:en',
  JSON.stringify({
    continuation: [{ id: STORY, title: 'The last train home', intent: 'telepathy' }],
  }),
);
const restored = learnerMemory(tampered, 'owner-a', 'en').value.continuation[0];
assert.equal(restored.intent, null, 'an unknown intention is dropped, the thread is kept');
assert.ok(!practiceIntentions.includes('telepathy'));
assert.equal(continuationLink(restored), '#/encounter?id=story%3Alast-train');

/* --- A thread is only offered while its work still exists ---

   Conversations are kept to the last twelve and continuation to the last
   twenty. The four oldest conversations used to sit on the shelf saying
   "there is more to come back to" and then fail to open. */

const talkBox = store();
const talks = learnerMemory(talkBox, 'owner-a', 'en');
for (let i = 0; i < 14; i++) {
  const state = conversation({
    id: `conversation:c${i}`,
    language: 'en',
    title: `Situation ${i}`,
    situation: `You are ordering coffee, attempt ${i}.`,
  });
  talks.conversation(state);
  talks.enter({ id: state.id, title: state.title, intent: 'speaking', excerpt: state.situation });
}
assert.equal(talks.value.continuation.length, 14, 'every thread was entered');
assert.equal(Object.keys(talks.value.conversations).length, 12, 'only twelve conversations survive');
const oldest = talks.value.continuation.find((x) => x.id === 'conversation:c0');
assert.ok(oldest, 'the entry is still in memory');
assert.equal(resumable(oldest, talks), false, 'its conversation is gone, so it cannot be resumed');
const talkShelf = continuationShelf(ctxFor(talks), 20);
const offered = [...talkShelf.matchAll(/<strong lang="en">([^<]+)<\/strong>/g)].map((m) => m[1]);
assert.deepEqual(
  offered,
  Array.from({ length: 12 }, (_, i) => `Situation ${13 - i}`),
  'the shelf offers exactly the work that is still there, most recent first',
);
assert.ok(!offered.includes('Situation 0'), 'a thread that cannot open is not offered');
assert.ok(!offered.includes('Situation 1'));

/* The room whose whole subject is coming back must ask the shelf what can be
   resumed rather than counting rows, or it renders an empty page under a
   heading promising otherwise - and it must say when the device has lost the
   ability to remember, which every other memory-backed room already does. */
const reference = read('static/orena/ui/reference.js');
const continueRoom = reference.slice(reference.indexOf('export function renderContinue'));
assert.ok(
  /const threads = continuationShelf\(/.test(continueRoom),
  'Continue must render what the shelf will actually offer',
);
assert.ok(
  /\$\{threads \|\|/.test(continueRoom),
  'an empty shelf must reach the empty state, not a blank room',
);
assert.ok(
  /memory\.available \? '' :/.test(continueRoom) && /memoryUnavailable/.test(continueRoom),
  'a device that cannot remember must say so here',
);

/* --- Language scope --- */

const shared = store();
const english = learnerMemory(shared, 'owner-a', 'en');
english.enter({ id: STORY, title: 'The last train home', intent: 'reading' });
const chinese = learnerMemory(shared, 'owner-a', 'zh');
assert.equal(chinese.value.continuation.length, 0, 'a thread does not cross into another language');
chinese.enter({ id: 'story:beijing', title: '北京的早晨', intent: 'reading' });
assert.equal(learnerMemory(shared, 'owner-a', 'en').value.continuation.length, 1);
assert.equal(learnerMemory(shared, 'owner-a', 'en').value.continuation[0].id, STORY);
// And not into another learner's.
assert.equal(learnerMemory(shared, 'owner-b', 'en').value.continuation.length, 0);
// A language switch rebuilds memory for the new language and leaves the route
// behind, so a thread from the previous language is never reopened.
const app = read('static/orena/app.js');
assert.ok(
  /learningChanged\) history\.replaceState\(null, '', link\(\)\)/.test(app),
  'a language switch must not stay on an encounter from the previous language',
);

/* --- No new durability claim ---

   Continuation is localStorage. It may say where it lives; it may never
   borrow the account's word for it. */
const patterns = read('static/orena/ui/patterns.js');
assert.ok(
  continuationShelf(ctxFor(memory)).includes(copy.en.deviceThreads),
  'the shelf says where these threads live',
);
for (const ui of ['en', 'zh']) {
  assert.ok(copy[ui].deviceThreads, `${ui}: threads must be able to say where they live`);
  assert.ok(copy[ui].draftSaved && copy[ui].memoryUnavailable);
  assert.notEqual(copy[ui].draftSaved, copy[ui].persisted, `${ui}: a draft is not an account save`);
  assert.notEqual(copy[ui].deviceThreads, copy[ui].persisted);
}
assert.ok(
  !/persisted/.test(
    patterns.slice(
      patterns.indexOf('export function continuationShelf'),
      patterns.indexOf('export function progressReporter'),
    ),
  ),
  'the shelf must not claim an account save',
);
// `persisted` is the account's word, and only the reporter that follows an
// acknowledged write is allowed to say it.
const memorySource = read('static/orena/product/memory.js');
assert.ok(
  !/\bapi\b|fetch\(/.test(memorySource),
  'device memory must not reach an API, and so cannot promise one',
);
assert.ok(
  /draftStatus[\s\S]{0,200}memoryUnavailable/.test(patterns),
  'a draft that could not be written says so where it was typed',
);

console.log(
  'Continuation: intention survives, work reopens, dead threads are not offered, scope holds, no borrowed durability: PASS',
);
