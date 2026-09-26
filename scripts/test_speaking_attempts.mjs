/* D-076 retention: session only by default; five per line on this device only when the learner
   opts in; turning it off deletes what was kept. Nothing is sent anywhere. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createAttemptStore, bestOf, MAX_PER_LINE } from '../static/orena/capabilities/speaking-attempts.js';

const memoryStorage = () => {
  const map = new Map();
  return { getItem: (k) => map.get(k) ?? null, setItem: (k, v) => map.set(k, String(v)) };
};
const memoryLocal = () => {
  const map = new Map();
  return { map, load: async (k) => map.get(k) || [], save: async (k, list) => map.set(k, list), clear: async () => map.clear() };
};
const urls = { n: 0, revoked: [], createObjectURL() { return `blob:${++this.n}`; }, revokeObjectURL(u) { this.revoked.push(u); } };
const attempt = (i, overall) => ({ id: `a${i}`, at: i, ms: 1200, blob: { size: 10 }, overall, flagged: overall < 90 ? 1 : 0, words: [] });

// Default: session only. Nothing goes to the device store.
{
  const local = memoryLocal();
  const store = createAttemptStore({ storage: memoryStorage(), local, urls });
  assert.equal(store.keepRecent, false);
  await store.add('line-1', attempt(1, 80));
  assert.equal(local.map.size, 0, 'nothing is kept on the device unless the learner opts in');
  assert.equal((await store.list('line-1')).length, 1);
}

// At most five per line, newest first; the oldest's object URL is released.
{
  const store = createAttemptStore({ storage: memoryStorage(), local: memoryLocal(), urls });
  for (let i = 1; i <= 7; i++) await store.add('line', attempt(i, 70 + i));
  const list = await store.list('line');
  assert.equal(list.length, MAX_PER_LINE);
  assert.equal(list[0].id, 'a7');
  assert.ok(urls.revoked.length >= 2);
  assert.equal(bestOf(list).id, 'a7', 'best is the highest measured overall');
}

// Opting in keeps the last five on the device (without the provider's full answer); opting out deletes them.
{
  const storage = memoryStorage();
  const local = memoryLocal();
  const store = createAttemptStore({ storage, local, urls });
  await store.setKeepRecent(true);
  for (let i = 1; i <= 6; i++) await store.add('line', { ...attempt(i, 60 + i), providerAnswer: { secret: 'never kept' } });
  assert.equal(local.map.get('line').length, MAX_PER_LINE);
  assert.equal(JSON.stringify(local.map.get('line')).includes('never kept'), false);
  assert.equal(storage.getItem('orena.speaking.keepRecent'), 'on');
  // A new session on the same device sees what was kept.
  const later = createAttemptStore({ storage, local, urls });
  assert.equal(later.keepRecent, true);
  assert.equal((await later.list('line')).length, MAX_PER_LINE);
  await later.setKeepRecent(false);
  assert.equal(local.map.size, 0, 'turning it off deletes the kept recordings');
}

assert.equal(bestOf([{ overall: null }, { overall: 0 }]).overall, 0, 'an unmeasured attempt is never the best');

const source = readFileSync(new URL('../static/orena/capabilities/speaking-attempts.js', import.meta.url), 'utf8');
assert.equal(/fetch\(|XMLHttpRequest|api\./.test(source), false, 'the attempt store never talks to a server');

console.log('Speaking attempts retention (session default, 5 per line on device when opted in): PASS');
