/* Kept language, and the way back to where it was met.

   The account library owns the word and its review history. It has no column
   for where the learner found it, so that lives beside it in memory - and
   without it a kept phrase is an anonymous card, which is the thing this
   product is trying not to produce. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { learnerMemory, KEEP_REASONS } from '../static/orena/product/memory.js';
import { sourceLink } from '../static/orena/product/intent.js';

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

const KEPT = {
  term: 'gave way to',
  origin: 'story:last-train',
  where: 'The last train home',
  why: 'from_reading',
  context: 'Outside, the last shops gave way to fields.',
};

assert.ok(KEEP_REASONS.includes('looked_up'));
assert.ok(!KEEP_REASONS.includes('manual'), '"manual" is how, not why');

const box = store();
const memory = learnerMemory(box, 'owner-a', 'en');

// The five questions a kept item must answer.
assert.equal(memory.rememberLanguage(KEPT), true);
const kept = memory.value.keptLanguage['gave way to'];
assert.equal(kept.term, 'gave way to', 'what was this');
assert.equal(kept.where, 'The last train home', 'where did I encounter it');
assert.equal(kept.context, KEPT.context, 'what did it mean in that context');
assert.equal(kept.why, 'from_reading', 'why did I keep it');
assert.ok(kept.at, 'when');
// And the route back is a real one.
assert.equal(kept.origin, 'story:last-train');
assert.equal(sourceLink(kept.origin), '#/encounter?id=story%3Alast-train');

// It survives a reload, and stays inside its own owner and language.
assert.equal(
  learnerMemory(box, 'owner-a', 'en').value.keptLanguage['gave way to'].where,
  'The last train home',
);
assert.deepEqual(learnerMemory(box, 'owner-b', 'en').value.keptLanguage, {});
assert.deepEqual(learnerMemory(box, 'owner-a', 'zh').value.keptLanguage, {});

// Nothing is stored that cannot be explained: an unknown reason is refused
// rather than rendered as a blank line.
assert.equal(memory.rememberLanguage({ ...KEPT, why: 'because' }), false);
assert.equal(memory.rememberLanguage({ ...KEPT, why: undefined }), false);
assert.equal(memory.rememberLanguage({ ...KEPT, term: '  ' }), false);
assert.equal(memory.rememberLanguage({ ...KEPT, term: '__proto__' }), false);
assert.equal(memory.value.keptLanguage.__proto__?.term, undefined);

// Keeping the same phrase again updates it rather than duplicating it.
memory.rememberLanguage({ ...KEPT, where: 'Read again', why: 'looked_up' });
assert.equal(Object.keys(memory.value.keptLanguage).length, 1);
assert.equal(memory.value.keptLanguage['gave way to'].why, 'looked_up');
assert.equal(memory.forgetLanguage('gave way to'), true);
assert.equal(memory.forgetLanguage('never kept'), false);

/* Repeated attempts must not erase what came before. The library only ever
   accumulates: a lapse steps the interval back without deleting a success. */
const library = read('writing_coach/becoming_library.py');
assert.ok(
  library.includes('next_stage=max(0,stage-1); lapses+=1'),
  'a lapse steps back rather than resetting',
);
assert.ok(
  !/success\s*-=|success\s*=\s*0/.test(library),
  'a forgotten word never loses the successes it already earned',
);
assert.ok(
  !/lapses\s*-=|lapses\s*=\s*0/.test(library),
  'lapses are history and are not cleared by a later success',
);

/* An imported media membership of either kind survives a reload: `url:` and `upload:` (addMedia accepts both). */
{
  const reloadBox = (() => { const d = {}; return { getItem: (k) => d[k] ?? null, setItem: (k, v) => { d[k] = String(v); }, removeItem: (k) => { delete d[k]; } }; })();
  const first = learnerMemory(reloadBox, 'owner-m', 'en');
  assert.ok(first.addMedia({ id: 'url:abc', title: 'A pasted link', kind: 'video' }));
  assert.ok(first.addMedia({ id: 'upload:def', title: 'An uploaded file', kind: 'audio' }));
  const again = learnerMemory(reloadBox, 'owner-m', 'en');
  assert.deepEqual(again.value.mediaImports.map((x) => x.id).sort(), ['upload:def', 'url:abc'], 'an upload: membership is not dropped on reload');
  assert.deepEqual(learnerMemory(reloadBox, 'owner-m', 'zh').value.mediaImports, [], 'still language-isolated');
  /* The account's media imports reach a device that never had them, in the device's own list, and survive a reload. */
  const sent = [];
  const newDevice = (() => { const d = {}; return { getItem: (k) => d[k] ?? null, setItem: (k, v) => { d[k] = String(v); }, removeItem: (k) => { delete d[k]; } }; })();
  const fresh = learnerMemory(newDevice, 'owner-m', 'en');
  assert.equal(fresh.mergeImports([{ id: 'url:https://x.test/v', title: 'v', kind: 'video' }, { id: 'upload:stored-9', title: 'f', kind: 'audio' }, { id: 'text:t1', title: 'T', text: 'b', kind: 'text', language: 'en', origin: 'imported' }]), true);
  assert.deepEqual(learnerMemory(newDevice, 'owner-m', 'en').value.mediaImports.map((x) => x.id), ['url:https://x.test/v', 'upload:stored-9']);
  assert.equal(learnerMemory(newDevice, 'owner-m', 'en').value.imports.length, 1);
  assert.equal(fresh.mergeImports([{ id: 'url:https://x.test/v', title: 'v' }]), false, 'a repeat changes nothing');
  void sent;
}

console.log(
  'Learner memory, kept-language provenance, the route back, the library that only accumulates: PASS',
);
