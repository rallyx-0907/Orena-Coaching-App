/* Gate for From Your Errors' pure data mapping (static/orena/screens/errors/model.js), D-091.
   Imports only the DOM-free module. Every assertion ties back to the real
   GET /api/practice-outcomes + GET /api/essays/{id} join (no R5 grammar route anywhere here -
   the 2026-09-28 Grammar Lab retirement) and rule 40 (never invent a correction). */
import assert from 'node:assert/strict';
import {
  outcomesWithIssues,
  essayIdsOf,
  matchIssue,
  buildDrillItems,
  buildEssayDrillItems,
  mergeDrillItems,
  isCorrect,
  initialResults,
  recordCheck,
  recordReveal,
  score,
  summaryRows,
} from '../static/orena/screens/errors/model.js';

/* --- outcomesWithIssues: only real, evidenced attempts --- */
assert.deepEqual(outcomesWithIssues(null), []);
const outcomesPayload = {
  items: [
    { essay_id: 1, focus_label: 'Articles', issue_count: 2, error_evidence: ['a wrong sentence'] },
    { essay_id: 2, focus_label: 'Tense', issue_count: 0, error_evidence: [] },
    { essay_id: 3, focus_label: '', issue_count: 1, error_evidence: ['x'] },
    { essay_id: 4, focus_label: 'Word choice', issue_count: 1, error_evidence: [] },
  ],
};
const kept = outcomesWithIssues(outcomesPayload, 10);
assert.deepEqual(kept.map((o) => o.essay_id), [1], 'no issues, no focus label, or no fragments - none of those become drill candidates');
assert.equal(outcomesWithIssues(outcomesPayload, 0).length, 0, 'limit is respected');

/* --- essayIdsOf: unique, well-formed ids only --- */
assert.deepEqual(essayIdsOf([{ essay_id: 1 }, { essay_id: 1 }, { essay_id: 2 }, { essay_id: 'nope' }]), [1, 2]);

/* --- matchIssue: prefix match against the essay's own untruncated quote (the outcome's
   error_evidence fragment is truncated to 260 chars server-side, the issue's quote is not) --- */
const issues = [
  { quote: 'I go to school yesterday and I seen my friend there for the first time in a long while.', suggestion: 'I went to school yesterday and I saw my friend there.', why: 'Past events need past tense.' },
  { quote: 'She dont like it.', suggestion: 'She doesn’t like it.', why: '' },
];
assert.equal(matchIssue('I go to school yesterday', issues), issues[0], 'a truncated fragment matches by prefix');
assert.equal(matchIssue('She dont like it.', issues), issues[1], 'an exact fragment matches too');
assert.equal(matchIssue('completely unrelated text', issues), null, 'no invented pairing when nothing matches');
assert.equal(matchIssue('', issues), null);

/* --- buildDrillItems: a card only when a real, different correction exists --- */
const outcomes = [
  { essay_id: 10, focus_label: 'Tense', created_at: '2026-09-20T00:00:00', error_evidence: ['She dont like it.', 'no match here'] },
  { essay_id: 11, focus_label: 'Empty fix', created_at: '2026-09-21T00:00:00', error_evidence: ['same both sides'] },
];
const issuesByEssay = {
  10: issues,
  11: [{ quote: 'same both sides', suggestion: 'same both sides', why: 'x' }],
};
const drillItems = buildDrillItems(outcomes, issuesByEssay);
assert.equal(drillItems.length, 1, 'the unmatched fragment and the no-op "correction" are both skipped');
assert.equal(drillItems[0].bad, 'She dont like it.');
assert.equal(drillItems[0].good, 'She doesn’t like it.');
assert.equal(drillItems[0].pattern, 'Tense');

/* --- isCorrect: forgiving of whitespace/punctuation, never of the actual words --- */
assert.equal(isCorrect('She doesn’t like it.', 'She doesn’t like it.'), true);
assert.equal(isCorrect('  she doesnt like it  ', 'She doesn’t like it.'), true, 'case/space/punctuation-insensitive');
assert.equal(isCorrect('She does not like it.', 'She doesn’t like it.'), false, 'a different real answer is not accepted');
assert.equal(isCorrect('', 'She doesn’t like it.'), false, 'an empty answer is never correct');

/* --- isCorrect in any script: Chinese punctuation is punctuation too --- */
assert.equal(isCorrect('我昨天去了学校', '我昨天去了学校。'), true, 'full-width punctuation does not decide it');
assert.equal(isCorrect('我昨天去了学校，然后回家。', '我昨天去了学校, 然后回家'), true);
assert.equal(isCorrect('我昨天去学校', '我昨天去了学校。'), false, 'a missing word is a different answer');

/* --- the drill's state machine, as the frame's own copy says it ("fixed on the first try" /
   "fixed after a retry"): right at the first check is `first`, right after a wrong check is `later`,
   asking for the answer is `shown` and forfeits credit, and a settled sentence is never re-graded --- */
assert.deepEqual(initialResults([{}, {}, {}]), [null, null, null]);
assert.equal(recordCheck(null, { correct: true, wrongBefore: 0 }), 'first');
assert.equal(recordCheck(null, { correct: true, wrongBefore: 2 }), 'later');
assert.equal(recordCheck(null, { correct: false, wrongBefore: 0 }), null, 'a wrong check settles nothing');
assert.equal(recordCheck('first', { correct: false, wrongBefore: 1 }), 'first', 'a settled sentence stays settled');
assert.equal(recordReveal(null), 'shown');
assert.equal(recordReveal('later'), 'later', 'the answer is only ever shown for a sentence not yet cleared');

const items2 = [{ pattern: 'Tense' }, { pattern: 'Tense' }, { pattern: 'Articles' }, { pattern: 'Word choice' }];
const results2 = ['first', 'later', 'shown', null];
assert.deepEqual(score(results2), { firstTry: 1, total: 4 });
assert.deepEqual(score([]), { firstTry: 0, total: 0 });
assert.deepEqual(summaryRows(items2, results2), [
  { pattern: 'Tense', state: 'cleared' },
  { pattern: 'Tense', state: 'later' },
  { pattern: 'Articles', state: 'keep' },
  { pattern: 'Word choice', state: 'keep' },
], 'one row per sentence in the order asked (two of the same pattern stay two rows), asked-for or unanswered is "keep practising"');

/* --- D-110: a review with fixes is a source of drills even when no targeted practice was run on it --- */
{
  const essays = [
    { id: 41, created_at: '2026-10-01T16:16:02+00:00', language_code: 'en', issues: [
      { category: 'word_form', quote: 'many peoples', suggestion: 'many people', why: 'people is already plural' },
      { category: 'tense', quote: 'I make soup', suggestion: 'I made soup', why: 'past story' },
      { category: 'article', quote: 'a cat', suggestion: 'a cat', why: 'nothing to fix' },
      { category: 'article', quote: 'the dog', suggestion: '', why: 'no correction given' },
    ] },
    { id: 40, created_at: '2026-09-29T00:00:00+00:00', language_code: 'en', issues: [] },
  ];
  const items = buildEssayDrillItems(essays, { labelOf: (category) => ({ word_form: 'Word form', tense: 'Verb tense' }[category]) });
  assert.deepEqual(items.map((item) => [item.essayId, item.pattern, item.bad, item.good]), [
    [41, 'Word form', 'many peoples', 'many people'],
    [41, 'Verb tense', 'I make soup', 'I made soup'],
  ], 'only issues with a real, different suggestion become drills');
  assert.equal(items[0].why, 'people is already plural');
  assert.deepEqual(buildEssayDrillItems([], {}), []);
  assert.deepEqual(buildEssayDrillItems(null), []);
  assert.equal(buildEssayDrillItems(essays, { limit: 1 }).length, 1);
  // a category the interface has no words for is shown as the category itself, never blank
  assert.equal(buildEssayDrillItems([{ id: 1, issues: [{ category: 'collocation', quote: 'a', suggestion: 'b' }] }])[0].pattern, 'collocation');
  // the same sentence of the same essay is one drill, whichever source found it
  const practice = [{ essayId: 41, pattern: 'Word form', createdAt: '', bad: 'Many peoples!', good: 'many people', why: '' }];
  const merged = mergeDrillItems(practice, items);
  assert.equal(merged.length, 2);
  assert.equal(merged[0].pattern, 'Word form');
  assert.equal(mergeDrillItems([], items, 1).length, 1);
}

console.log('test_orena_screen_errors.mjs: From Your Errors data mapping - real practice-outcome + essay-issue join, rule 40 throughout: PASS');
