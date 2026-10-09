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

/* In-app Back (GLB-3): the index of a history entry is stamped in its state, so Back, Forward, reload and a hash typed
   by hand cannot put a counter out of step. */
{
  const { canStepBack, entryIndex, readIndex, withIndex } = await import('../static/orena/shell/history-index.js');
  assert.equal(readIndex(null), null);
  assert.equal(readIndex({}), null);
  assert.equal(readIndex({ orenaIdx: -1 }), null);
  assert.equal(readIndex({ orenaIdx: '2' }), null);
  assert.equal(readIndex({ orenaIdx: 3 }), 3);
  assert.deepEqual(withIndex({ orenaGrammarSearch: 'x' }, 2), { orenaGrammarSearch: 'x', orenaIdx: 2 }, 'the stamp keeps the entry\'s other state');
  assert.deepEqual(withIndex(null, 0), { orenaIdx: 0 });

  // Replay a session against a model of the browser's history: entries with their state, a cursor.
  const entries = [];
  let cursor = -1;
  let previous = null;
  const render = (replaced = false) => {
    const stamped = readIndex(entries[cursor].state);
    previous = entryIndex({ stamped, replaced, previous });
    entries[cursor].state = withIndex(entries[cursor].state, previous);
    return previous;
  };
  const push = () => { entries.length = cursor + 1; entries.push({ state: null }); cursor += 1; return render(); };
  const replace = () => { entries[cursor] = { state: null }; return render(true); };
  const traverse = (to) => { cursor = to; return render(); };

  entries.push({ state: null });
  cursor = 0;
  assert.equal(render(), 0, 'the first entry of a tab is 0');
  assert.equal(canStepBack(0), false, 'no app entry before it: in-app Back goes to the place\'s parent route');
  assert.equal(push(), 1);
  assert.equal(push(), 2);
  assert.equal(canStepBack(2), true);
  assert.equal(replace(), 2, 'the app\'s own replace keeps the index of the entry it replaces');

  // The browser's Back button twice, then in-app navigation: the old counter would still say 2.
  assert.equal(traverse(1), 1);
  assert.equal(traverse(0), 0);
  assert.equal(canStepBack(previous), false, 'after the browser\'s own Back reached the first entry, in-app Back must not leave the app');
  assert.equal(push(), 1, 'a push from the first entry drops the forward entries and numbers on from it');
  assert.equal(entries.length, 2);

  // Forward and reload read the stamp back.
  assert.equal(traverse(0), 0);
  assert.equal(traverse(1), 1);
  previous = null;
  assert.equal(render(), 1, 'a reload keeps the stamp, so Back still works after it');

  // A hash typed by hand is an unstamped entry the browser pushed: one past the entry before it.
  previous = 1;
  entries.push({ state: null });
  cursor += 1;
  assert.equal(render(), 2);
}

{
  const router = fs.readFileSync('static/orena/shell/router.js', 'utf8');
  assert.doesNotMatch(router, /orena\.next\.depth|\bdepth\b/, 'no counter kept in step with go()');
  assert.match(router, /if \(canStepBack\(position\)\) history\.back\(\);\s*else go\(href\(origin\), \{ replace: true \}\);/, 'in-app Back steps through history only when an app entry precedes this one');
  assert.match(router, /hasHistory: \(\) => canStepBack\(position\)/);
  assert.match(router, /history\.replaceState\(withIndex\(history\.state, position\), ''\)/, 'every rendered entry is stamped');
  console.log('history index: PASS');
}
