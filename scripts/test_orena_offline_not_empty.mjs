/* Gate: a failed read is never an empty result (offline #/review, offline #/discover).
   Review's queue loaders and Discover's catalogue loader must throw to the router's load-error card
   (Back / Retry, which reloads itself on 'online') when the fetch rejects; an answered empty queue still
   shows the empty state. Minimal DOM stub, the screens' own modules, the api singleton patched. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const listeners = {};
const link = () => ({ addEventListener(type, fn) { if (type === 'load') queueMicrotask(fn); } });
globalThis.document = { createElement: link, head: { append() {} }, documentElement: { lang: 'vi', dataset: {} }, querySelector: () => null };
globalThis.window = {
  addEventListener(t, fn) { (listeners[t] ||= []).push(fn); },
  removeEventListener(t, fn) { listeners[t] = (listeners[t] || []).filter((f) => f !== fn); },
  location: { hash: '' },
  matchMedia: () => ({ matches: false }),
};
Object.defineProperty(globalThis, 'navigator', { value: { onLine: false }, configurable: true });
globalThis.localStorage = { getItem: () => null, setItem() {} };

const { api } = await import('../static/orena/infrastructure/api.js');
const { default: mountReview } = await import('../static/orena/screens/review/screen.js');
const { t } = await import('../static/orena/screens/review/copy.js');

const makeElement = () => ({ innerHTML: '', classList: { add() {} }, querySelector: () => ({ addEventListener() {} }), querySelectorAll: () => [], replaceChildren() { this.innerHTML = ''; } });
const ctx = (query = '') => ({ query: new URLSearchParams(query), isCurrent: () => true, context: { language: 'en', memory: null }, go() {}, back() {}, href: () => '#/', route: { id: 'review' } });
const offline = () => new TypeError('Failed to fetch');
const original = api.libraryVocabulary;

for (const query of ['', 'word=buffer']) {
  api.libraryVocabulary = async () => { throw offline(); };
  const el = makeElement();
  await assert.rejects(() => mountReview(el, ctx(query)), /Failed to fetch/, `review ${query || 'due'}: a failed fetch throws to the error card`);
  assert.ok(!el.innerHTML.includes(t('emptyTitle')), 'no empty state painted on failure');
}

// An answered, genuinely empty queue still shows the empty state.
api.libraryVocabulary = async () => ({ items: [] });
const el = makeElement();
await mountReview(el, ctx());
assert.ok(el.innerHTML.includes(t('emptyTitle')), 'an answered empty queue shows the empty state');

// A failure is not remembered as empty: every mount asks again.
let calls = 0;
api.libraryVocabulary = async () => { calls += 1; throw offline(); };
await assert.rejects(() => mountReview(makeElement(), ctx()));
await assert.rejects(() => mountReview(makeElement(), ctx()));
assert.equal(calls, 2, 'a failure is not cached; every mount fetches again');
api.libraryVocabulary = original;

// The error card recovers when the connection returns: the router hooks 'online' to retry.
const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8');
assert.match(read('../static/orena/shell/router.js'), /if \(offline\) \{\s*window\.addEventListener\('online'/, 'router retries a failed page on online');

// Source guards.
const review = read('../static/orena/screens/review/screen.js');
const loaders = review.slice(review.indexOf('let queue;'), review.indexOf('const state = {'));
assert.ok(!/\.catch\(/.test(loaders), 'review queue loaders do not swallow a failure');
const discover = read('../static/orena/screens/discover/screen.js');
assert.match(discover, /failed\.size >= 4 && !state\.entries\.length/, 'discover throws when every catalogue source failed');
assert.match(discover, /new Error\('Discover catalogue unavailable'\)/);
const progress = read('../static/orena/screens/progress/screen.js');
assert.match(progress, /cache\.rank = api\.libraryVocabularySummary\(\)\.catch/, 'progress does not cache a rejected summary');
console.log('offline-not-empty OK');
