/* Gate for Review Session's pure data mapping (static/orena/screens/review/model.js), D-091.
   Imports only the DOM-free module. Every assertion ties back to the real scheduler contract
   (`writing_coach/becoming_library.py#review_schedule`/`review_library_vocabulary`) and rule 40
   (never fake an interval, never invent a queue row). */
import assert from 'node:assert/strict';
import {
  queueScope,
  buildQueue,
  collectionWordSet,
  filterByWordSet,
  progressCounts,
  progressPercent,
  scheduleLabel,
  GRADES,
  initialStats,
  tally,
  reviewCard,
  MODES,
  clozeFor,
  cardMode,
  hintMask,
  hintFor,
  sourceLabelKey,
  gradeOutcome,
  countsForSession,
} from '../static/orena/screens/review/model.js';

/* --- queueScope: the three #/review entry shapes --- */
assert.deepEqual(queueScope({}), { mode: 'due' });
assert.deepEqual(queueScope({ word: 'buffer' }), { mode: 'word', word: 'buffer' });
assert.deepEqual(queueScope({ collection: 'toeic-core' }), { mode: 'collection', collection: 'toeic-core' });
assert.deepEqual(queueScope({ word: 'buffer', collection: 'x' }), { mode: 'word', word: 'buffer' }, 'word wins when both are somehow present');
assert.deepEqual(queueScope({ word: '  ' }), { mode: 'due' }, 'a blank query param is not a scope');
/* The router gives a room its query as a URLSearchParams (shell/routes.js#match) - reading it as a
   plain object silently ignored ?word= and ?collection= and reviewed the whole due queue instead. */
assert.deepEqual(queueScope(new URLSearchParams('word=buffer')), { mode: 'word', word: 'buffer' });
assert.deepEqual(queueScope(new URLSearchParams('collection=toeic-core')), { mode: 'collection', collection: 'toeic-core' });
assert.deepEqual(queueScope(new URLSearchParams('')), { mode: 'due' });
assert.deepEqual(queueScope(new URLSearchParams('word=%20&collection=x')), { mode: 'collection', collection: 'x' });
assert.deepEqual(queueScope(undefined), { mode: 'due' });

/* --- buildQueue: only real rows with a word --- */
assert.deepEqual(buildQueue(), []);
assert.deepEqual(buildQueue([{ word: 'a' }, null, { word: '' }, { word: 'b' }]), [{ word: 'a' }, { word: 'b' }]);

/* --- collection scoping: only what the learner actually kept, never every catalogue entry --- */
const collectionPayload = { items: [{ word: 'Alpha', saved: true }, { word: 'beta', saved: false }, { headword: 'Gamma', saved: true }] };
const wordSet = collectionWordSet(collectionPayload);
assert.deepEqual([...wordSet].sort(), ['alpha', 'gamma']);
assert.deepEqual(collectionWordSet(null), new Set());
const rows = [{ word: 'alpha' }, { word: 'beta' }, { word: 'Gamma' }, { word: 'delta' }];
assert.deepEqual(filterByWordSet(rows, wordSet).map((r) => r.word), ['alpha', 'Gamma'], 'case-insensitive match, beta (not kept from this collection) excluded');

/* --- progress --- */
assert.equal(progressCounts(0, 0), null, 'no queue, no counter');
assert.deepEqual(progressCounts(0, 5), { n: 1, total: 5 });
assert.deepEqual(progressCounts(4, 5), { n: 5, total: 5 });
assert.deepEqual(progressCounts(5, 5), { n: 5, total: 5 }, 'a finished session reads "5 of 5", never "6 of 5"');
assert.equal(progressPercent(0, 0), 0);
assert.equal(progressPercent(0, 4), 0);
assert.equal(progressPercent(2, 4), 50);
assert.equal(progressPercent(4, 4), 100);

/* --- scheduleLabel: the real interval THIS card's schedule carries, never a fixed table
   (rule 40 - "map honestly... never fake intervals") --- */
const fakeT = { plural: (key, n) => `${n}:${key}` };
assert.equal(scheduleLabel(null, 'again', fakeT), '');
assert.equal(scheduleLabel({ again: { minutes: 10 } }, 'again', fakeT), '10:scheduleMinutes');
assert.equal(scheduleLabel({ unsure: { days: 1 } }, 'unsure', fakeT), '1:scheduleDays');
assert.equal(scheduleLabel({ got_it: { days: 21 } }, 'got_it', fakeT), '21:scheduleDays');
assert.equal(scheduleLabel({ got_it: { days: 21 } }, 'again', fakeT), '', 'no data for the grade asked, no label - not a guess from a different grade');
assert.equal(scheduleLabel({ again: { minutes: 0 } }, 'again', fakeT), '', 'a zero interval is not shown as a real fact');

/* --- exactly three grades: the backend's own VocabularyReviewIn.result pattern
   (again|unsure|got_it) - never the frame's four --- */
assert.deepEqual(GRADES, ['again', 'unsure', 'got_it']);
assert.equal(GRADES.includes('hard'), false);
assert.equal(GRADES.includes('easy'), false);

/* --- stats tally --- */
assert.deepEqual(initialStats(), { again: 0, unsure: 0, got_it: 0 });
let stats = initialStats();
stats = tally(stats, 'got_it');
stats = tally(stats, 'got_it');
stats = tally(stats, 'again');
assert.deepEqual(stats, { again: 1, unsure: 0, got_it: 2 });
assert.deepEqual(tally(initialStats(), 'nonsense'), initialStats(), 'an unknown grade never corrupts the tally');

/* --- reviewCard: backfills a real catalogue meaning/example when the saved item's own
   definition/translation_vi are empty (live sandbox finding: "health", source_kind dictionary,
   definition and translation_vi both blank, support_translations.vi and examples both real) -
   never invents one, only looks in the one other real place the backend already put it. --- */
const bareItem = {
  word: 'health', phonetic: '/helθ/', part_of_speech: '', definition: '', translation_vi: '',
  review_stage: 0, stage_label: 'New', due: true, next_review_at: '2026-09-27T23:40:03+00:00',
  level: 'A1', support_translations: { vi: 'sức khỏe' },
  examples: [{ language: 'en', text: 'Regular sleep is important for your health.' }],
  schedule: { again: { minutes: 10 }, unsure: { days: 1 }, got_it: { days: 1 } },
};
const backfilled = reviewCard('health', bareItem, 'vi');
assert.equal(backfilled.hasMeaning, true, 'a real catalogue translation fills the blank meaning');
assert.equal(backfilled.meaning, 'sức khỏe');
assert.equal(backfilled.hasSupport, false, 'the same localization is not drawn twice, as meaning and support line');
assert.equal(backfilled.hasExample, true);
assert.ok(backfilled.exampleParts.some((part) => part.hit), 'the real catalogue example highlights the headword');
assert.equal(backfilled.saved, true);

const richItem = { word: 'buffer', definition: 'extra time or space kept in reserve', translation_vi: 'khoảng đệm', review_stage: 2, stage_label: 'Reinforcing', support_translations: { vi: 'KHÔNG DÙNG CÁI NÀY' } };
const rich = reviewCard('buffer', richItem, 'vi');
assert.equal(rich.meaning, 'extra time or space kept in reserve', "the learner's own real definition is never overridden by the catalogue fallback");

const unsaved = reviewCard('health', null, 'vi');
assert.equal(unsaved.saved, false, 'a locally-unsaved card (mid-session unsave) has no schedule and is not marked saved');
assert.equal(unsaved.hasMeaning, false, 'nothing to backfill from once the item is gone');

/* --- The two ways a card asks (frame 13's rvMode): only a sentence the learner really met the word
   in makes a source-aware card, and nothing is made up for a word that has none (rule 40) --- */
assert.deepEqual([...MODES], ['typing', 'cloze'], 'the canonical review mode names, one per mode');
const met = { word: 'hectic', source_kind: 'reading', source_fragment: 'My mornings are always hectic before the train leaves.' };
assert.equal(cardMode(met), 'cloze');
assert.equal(clozeFor(met).text, 'My mornings are always ＿＿＿＿＿＿ before the train leaves.', 'the blank is as wide as what it hides');
assert.equal(clozeFor(met).hits, 1);
assert.deepEqual(clozeFor(met).parts.map((part) => part.blank), [false, true, false], 'text, blank, text - so a screen can keep a blank whole');
assert.equal(clozeFor(met).parts.map((part) => part.value).join(''), clozeFor(met).text, 'the parts are the sentence');
assert.equal(cardMode({ word: 'hectic', source_fragment: '' }), 'typing', 'no sentence, no cloze');
assert.equal(cardMode({ word: 'hectic', source_fragment: 'Nothing to see here.' }), 'typing', 'a fragment that does not contain the word is not a cloze');
assert.equal(cardMode({ word: 'hectic' }), 'typing');
assert.equal(clozeFor({ word: 'cat', source_fragment: 'The concatenation of category.' }), null, 'a word inside another word is not an occurrence');
const twice = clozeFor({ word: 'go', source_fragment: 'Go now, then go again.' });
assert.equal(twice.hits, 2, 'every occurrence goes - one left in turns recall into reading');
assert.ok(!/go/i.test(twice.text));
assert.equal(clozeFor({ word: 'figure', source_fragment: 'We figured it out.' }).text, 'We ＿＿＿＿＿＿＿ it out.', 'an inflected form is blanked whole');
const han = clozeFor({ word: '生活', source_fragment: '我喜欢这里的生活，生活很简单。' });
assert.equal(han.hits, 2, 'Chinese has no word boundaries: the word is matched where it stands');
assert.ok(!han.text.includes('生活'));
assert.equal(clozeFor({ word: 'a.b', source_fragment: 'axb and a.b' }).hits, 1, 'the word is matched literally, never as a pattern');
assert.equal(clozeFor({ word: 'Hectic', source_fragment: 'so hectic' }).hits, 1, 'case does not hide an occurrence');
assert.equal(clozeFor({ word: 'x', source_fragment: 'x'.repeat(40) }), null);
assert.ok(clozeFor({ word: 'strengthened', source_fragment: 'It strengthened.' }).text.match(/＿+/)[0].length <= 14, 'a long word never blanks wider than the frame allows');

assert.equal(hintMask('hectic'), 'h_____');
assert.equal(hintMask('look after'), 'l___ a____', 'word by word');
assert.equal(hintMask('生活'), '生_');
assert.equal(hintMask(''), '');
assert.equal(hintFor('cloze', { word: 'hectic', support: 'bận rộn' }), 'h_____');
assert.equal(hintFor('typing', { word: 'hectic', support: 'bận rộn' }), 'bận rộn', "the learner's own-language gloss (the frame's rvG.vi)");
assert.equal(hintFor('typing', { word: 'hectic', support: '' }), '', 'no gloss, no hint - never an invented one');

assert.equal(sourceLabelKey('reading'), 'sourceReading');
assert.equal(sourceLabelKey('feedback'), 'sourceFeedback');
assert.equal(sourceLabelKey('dictionary'), '', 'a kind that names no source draws no source');
assert.equal(sourceLabelKey(undefined), '');

/* --- A grade's fate: kept for the device queue only when there is no network (product/review-
   queue.js's own worthKeeping), never when the server refuses it --- */
assert.equal(gradeOutcome({ result: { found: true } }), 'saved');
assert.equal(gradeOutcome({ result: {} }), 'saved');
assert.equal(gradeOutcome({ result: { found: false } }), 'missing', 'a card unsaved mid-grade has nothing left to schedule');
assert.equal(gradeOutcome({ error: new TypeError('Failed to fetch') }), 'kept', 'no status at all: it never reached a server');
assert.equal(gradeOutcome({ error: Object.assign(new Error('boom'), { status: 503 }) }), 'kept', 'a server error may clear');
assert.equal(gradeOutcome({ error: Object.assign(new Error('bad'), { status: 422 }) }), 'failed', 'a refusal will be refused again');
assert.equal(gradeOutcome({ error: Object.assign(new Error('gone'), { name: 'AbortError' }) }), 'aborted', 'leaving the room is not an offline answer');
assert.equal(countsForSession('saved'), true);
assert.equal(countsForSession('kept'), true, 'an answer waiting on the device is still an answer the learner gave');
assert.equal(countsForSession('failed'), false);
assert.equal(countsForSession('missing'), false);
assert.equal(countsForSession('aborted'), false);

console.log('test_orena_screen_review.mjs: Review Session data mapping - real scheduler contract, rule 40 throughout: PASS');
