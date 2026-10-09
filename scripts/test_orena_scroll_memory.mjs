/* Gate for shell/scroll-memory.js: Back returns a browsing page to where the learner left it (learner report
   2026-10-09: Grammar Library -> a point -> Back landed at the top). DOM-free except for restoreScrollWhenReady,
   which is driven with a stand-in scroller. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { SCROLL_LIMIT, addressOf, createScrollMemory, restoreScrollWhenReady } from '../static/orena/shell/scroll-memory.js';

const storage = () => {
  const map = new Map();
  return { getItem: (k) => map.get(k) ?? null, setItem: (k, v) => map.set(k, String(v)), map };
};

// The place is the hash with its query; a full URL and a bare hash are the same place.
assert.equal(addressOf('http://localhost:8021/#/grammar?cat=fn.time'), '#/grammar?cat=fn.time');
assert.equal(addressOf('#/grammar'), '#/grammar');
assert.equal(addressOf('http://localhost:8021/'), '');
assert.equal(addressOf(undefined), '');

{
  const store = storage();
  const memory = createScrollMemory(store);
  assert.equal(memory.recall('#/grammar'), 0, 'nothing remembered: the top');
  memory.remember('http://h/#/grammar?level=B1&cat=fn.time', 1234.6);
  assert.equal(memory.recall('#/grammar?level=B1&cat=fn.time'), 1235, 'the position is kept by address, rounded');
  assert.equal(memory.recall('#/grammar'), 0, 'the same page filtered another way is another place');
  assert.equal(memory.recall('#/grammar?level=B1&cat=fn.link'), 0);

  // It survives a reload of the page (new memory over the same session storage).
  assert.equal(createScrollMemory(store).recall('#/grammar?level=B1&cat=fn.time'), 1235);

  // The top forgets an older, deeper position (an arrival from a link starts at the top).
  memory.remember('#/grammar?level=B1&cat=fn.time', 0);
  assert.equal(memory.recall('#/grammar?level=B1&cat=fn.time'), 0);
  assert.equal(createScrollMemory(store).size(), 0);

  // Nonsense is not remembered.
  for (const bad of [NaN, -5, Infinity, 'x', undefined]) memory.remember('#/x', bad);
  memory.remember('', 50);
  assert.equal(memory.size(), 0);
}

// Capped, oldest first; touching an address makes it the newest.
{
  const memory = createScrollMemory(storage(), 3);
  for (const n of [1, 2, 3]) memory.remember(`#/p${n}`, 100 * n);
  memory.remember('#/p1', 111);
  memory.remember('#/p4', 400);
  assert.deepEqual([1, 2, 3, 4].map((n) => memory.recall(`#/p${n}`)), [111, 0, 300, 400], 'the least recently used place goes');
  assert.ok(SCROLL_LIMIT >= 10);
}

// Blocked, full or corrupt storage never breaks the page.
{
  const broken = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('full'); } };
  const memory = createScrollMemory(broken);
  memory.remember('#/a', 10);
  assert.equal(memory.recall('#/a'), 10, 'it still serves this page');
  assert.equal(createScrollMemory({ getItem: () => 'not json', setItem() {} }).size(), 0);
  assert.equal(createScrollMemory({ getItem: () => '[["#/a",5],["#/b","x"],[1,2],"y"]', setItem() {} }).size(), 1, 'only well-formed pairs are read');
  assert.equal(createScrollMemory(null).size(), 0);
}

// restoreScrollWhenReady: applied at once when the content is there, as the content grows when it is not, never
// past what can be reached, and stopped by the learner's own input.
{
  const handlers = new Map();
  const make = (height) => ({
    scrollHeight: height,
    clientHeight: 500,
    scrolls: [],
    scrollTo(options) { this.scrolls.push(options.top); },
    addEventListener(name, fn) { handlers.set(name, fn); },
    removeEventListener(name) { handlers.delete(name); },
  });
  let observed = null;
  globalThis.ResizeObserver = class {
    constructor(fn) { this.fn = fn; observed = this; }
    observe() {}
    disconnect() { this.gone = true; }
  };

  const ready = make(3000);
  restoreScrollWhenReady(ready, 1200, {});
  assert.deepEqual(ready.scrolls, [1200], 'content already there: restored at once');
  assert.equal(handlers.size, 0, 'and done: no listeners left behind');
  assert.equal(observed.gone, true);

  const growing = make(600);
  const stop = restoreScrollWhenReady(growing, 1200, {});
  assert.deepEqual(growing.scrolls, [100], 'content short: as far as it reaches, no further');
  growing.scrollHeight = 900;
  observed.fn();
  growing.scrollHeight = 2000;
  observed.fn();
  assert.deepEqual(growing.scrolls, [100, 400, 1200], 'follows the content until the target is reached');
  observed.fn();
  assert.equal(growing.scrolls.length, 3, 'then stops');
  stop();

  const touched = make(600);
  restoreScrollWhenReady(touched, 1200, {});
  assert.ok(['wheel', 'touchstart', 'pointerdown', 'keydown'].every((name) => handlers.has(name)), "the learner's own input is watched");
  handlers.get('wheel')();
  touched.scrollHeight = 5000;
  observed.fn();
  assert.deepEqual(touched.scrolls, [100], 'after the learner scrolls, the page is left alone');
  assert.equal(handlers.size, 0);
  delete globalThis.ResizeObserver;
}

// The router wires it: saves the page being left under its own (possibly rewritten) address, restores only on a
// browser traversal of a browsing page, and treats the app's own go() as a fresh arrival.
{
  const router = fs.readFileSync('static/orena/shell/router.js', 'utf8');
  assert.match(router, /memory\.remember\(addressOf\(event\.oldURL\), frame\.main\.scrollTop\)/, 'leaving saves under the old address');
  assert.match(router, /reached === 'traverse' && !route\.focus \? memory\.recall\(address\) : 0/, 'only a traversal of a browsing page restores');
  assert.match(router, /arrival = replace \? 'replace' : 'push';/, "go() marks the arrival as the app's own");
  assert.match(router, /if \(reached !== 'traverse'\) memory\.remember\(address, 0\);/, 'a fresh arrival drops a stale position');
}
console.log('scroll memory: PASS');
