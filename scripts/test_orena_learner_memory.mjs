/* Kept language, and the way back to where it was met.

   The account library owns the word and its review history. It has no column
   for where the learner found it, so that lives beside it in memory - and
   without it a kept phrase is an anonymous card, which is the thing this
   product is trying not to produce. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { learnerMemory, KEEP_REASONS } from '../static/orena/product/memory.js';
import { keptProvenance } from '../static/orena/ui/patterns.js';
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

// Every reason a learner can have is sayable in both interface languages. A
// missing label would leave the card explaining nothing.
for (const ui of ['en', 'zh'])
  for (const why of KEEP_REASONS)
    assert.ok(copy[ui][`kept_${why}`], `${ui}: no label for "${why}"`);
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

/* The card says why and offers the way back, and says neither when it has
   nothing honest to say. */
const line = keptProvenance(copy.en, KEPT);
assert.ok(line.includes(copy.en.kept_from_reading));
assert.ok(line.includes('The last train home'));
assert.ok(line.includes(`href="${sourceLink('story:last-train')}"`));
assert.equal(keptProvenance(copy.en, null), '');
// A phrase whose origin cannot be routed to still says where it came from,
// without offering a link that goes nowhere.
const unrouted = keptProvenance(copy.en, { ...KEPT, origin: '' });
assert.ok(unrouted.includes('The last train home'));
assert.ok(!unrouted.includes('<a '), 'no link without somewhere to go');
assert.ok(
  !keptProvenance(copy.en, { ...KEPT, where: '<img src=x>' }).includes('<img'),
  'provenance is escaped',
);

/* Every capability that can open the shared explanation says where the learner
   was and why, or a phrase kept there loses its origin. */
const understanding = read('static/orena/ui/understanding.js');
assert.ok(
  understanding.includes('ctx.memory.rememberLanguage({'),
  'the shared keep form records provenance',
);
assert.ok(
  understanding.indexOf('api.saveLibraryVocabulary') <
    understanding.indexOf('ctx.memory.rememberLanguage'),
  'a route back is only recorded once the word itself is saved',
);
assert.ok(
  understanding.includes('if (origin?.why)'),
  'provenance is recorded only when the caller supplied a reason',
);

const sites = {
  'static/orena/ui/encounter.js': ['from_reading', 'from_listening'],
  'static/orena/ui/expression.js': ['from_writing', 'from_grammar'],
  'static/orena/ui/conversation.js': ['from_speaking'],
  'static/orena/ui/voice-response.js': ['from_speaking'],
};
for (const [path, reasons] of Object.entries(sites)) {
  const source = read(path);
  for (const why of reasons)
    assert.ok(source.includes(`why: '${why}'`), `${path}: never says "${why}"`);
}

// Asking again about a word already kept must not lose its origin.
assert.ok(
  read('static/orena/ui/expression.js').includes(
    'memory.value.keptLanguage?.[entry.word]',
  ),
  'reopening a kept word carries its own provenance',
);


/* Recall shaped by how the phrase entered the learner's life. A queue of
   identical cards teaches one thing: how to recognise a card. */
const { recallShape, blankContext, gradable, RECALL_SHAPES } = await import(
  '../static/orena/product/recall.js'
);

const inContext = {
  word: 'gave way to',
  source_fragment: 'Outside, the last shops gave way to fields.',
  definition: 'one thing replaced by another',
};

// The origin the learner's own saving recorded decides the question.
assert.equal(recallShape(inContext, { why: 'from_speaking' }), 'say');
assert.equal(recallShape(inContext, { why: 'from_writing' }), 'reuse');
assert.equal(recallShape(inContext, { why: 'from_reading' }), 'in_context');
assert.equal(recallShape(inContext, { why: 'looked_up' }), 'in_context');
assert.equal(recallShape(inContext, null), 'in_context', 'no provenance still recalls in context');
// A sentence that does not contain the phrase cannot hide it, so the shape
// falls back rather than showing a blank that conceals nothing.
assert.equal(
  recallShape({ word: 'x', source_fragment: 'an unrelated sentence' }, { why: 'from_reading' }),
  'meaning',
);
assert.equal(recallShape({ word: 'x' }, { why: 'looked_up' }), 'meaning');
for (const shape of RECALL_SHAPES)
  for (const ui of ['en', 'zh']) {
    assert.ok(copy[ui][`recallAsk_${shape}`], `${ui}: no question for "${shape}"`);
    assert.ok(copy[ui][`recallReveal_${shape}`], `${ui}: no reveal label for "${shape}"`);
  }

// The gap is the real sentence with the real phrase withheld - never invented.
assert.deepEqual(blankContext('Outside, the last shops gave way to fields.', 'gave way to'), {
  before: 'Outside, the last shops ',
  after: ' fields.',
  phrase: 'gave way to',
});
assert.equal(blankContext('a b c', 'zzz'), null);
assert.equal(blankContext('', 'x'), null);
assert.equal(blankContext('a b c', ''), null);

// Seeing a card is not recall. Nothing is graded before the learner has
// committed to an answer.
assert.equal(gradable(false), false);
assert.equal(gradable(undefined), false);
assert.equal(gradable(true), true);

const recallUi = read('static/orena/ui/expression.js');
assert.ok(
  recallUi.includes('recallShape(current, keptNow)'),
  'the moment asks the question its provenance calls for',
);
assert.ok(
  recallUi.includes('keptProvenance(c, keptNow)'),
  'a recalled phrase still says where it came from',
);

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

console.log('Learner memory, provenance, the route back, and recall that fits its origin: PASS');
