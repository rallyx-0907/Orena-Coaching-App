/* The latest lookup wins (bug 7): a Quick Sheet that has been replaced or closed is cancelled, and the
   answer its requests bring back later is ignored instead of being painted over the word that replaced it.
   A follow-up carries the conversation, and the answer is the tutor's. */
import assert from 'node:assert/strict';
import { copy } from '../static/orena/ui/copy.js';
import { createQuickSheet } from '../static/orena/ui/quick-sheet.js';

const c = copy.en;
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => (resolve = done));
  return { promise, resolve };
};
const wait = () => new Promise((resolve) => setTimeout(resolve, 0));

const slow = deferred();
const asked = [];
const api = {
  readingLookup: async () => ({ pronunciation: '/a/' }),
  wordDetail: async (payload) => {
    asked.push(payload);
    if (payload.text === 'Anna') return slow.promise;
    return { available: true, contextMeaning: `meaning of ${payload.text}`, answer: payload.question ? 'a tutor answer' : '' };
  },
  sentenceSheet: async () => ({ available: false }),
};
const ctx = { api, language: 'en', support: 'vi', c };
const painted = [];
const make = (text) =>
  createQuickSheet({
    ctx,
    target: { kind: 'word', text, context: `${text} is here.` },
    title: 'lesson',
    alive: () => true,
    paint: (html) => painted.push([text, html]),
    close: () => {},
    speak: () => {},
    remember: () => {},
    statusEl: () => null,
  });

const a = make('Anna');
const loadingA = a.load();
await wait();
// The learner taps another word while A's answer is still on its way.
a.cancel();
const b = make('pen');
await b.load();
const before = painted.length;
slow.resolve({ available: true, contextMeaning: 'A late answer that must not be shown' });
await loadingA;
await wait();
assert.equal(painted.length, before, 'a cancelled sheet paints nothing when its answer arrives');
assert.ok(painted.every(([text, html]) => text !== 'Anna' || !/late answer/.test(html)), 'A never shows its late answer');
assert.match(painted.at(-1)[1], /meaning of pen/, 'the panel shows the word that was tapped last');
assert.equal(await a.act('close'), undefined, 'a cancelled sheet takes no more actions');

// A follow-up carries what was asked before it, and the answer shown is the tutor's.
const c1 = make('pen');
await c1.load();
await c1.ask('các dạng từ buy ở các thì là gì');
await c1.ask('phát âm bought như thế nào?');
const second = asked.filter((payload) => payload.question).at(-1);
assert.deepEqual(second.history, [{ question: 'các dạng từ buy ở các thì là gì', answer: 'a tutor answer' }], 'the earlier exchange rides along');
assert.match(painted.at(-1)[1], /a tutor answer/, 'the sheet shows the tutor answer');

console.log('Lookup race: the latest word wins, a stale answer is ignored, a follow-up carries the conversation: PASS');
