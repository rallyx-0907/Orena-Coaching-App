/* Gate for the Check Understanding screen's DOM-free logic (design route `checku`, frame 20,
   static/orena/screens/check/model.js). Loads the real captured/serializer-built payloads
   (scripts/fixtures/api/reading_practice_article_set_approved.json,
   reading_practice_grade_result.json - see their own "_note" for why one is built, not captured,
   in this sandbox) so a screen field read that does not exist in the real backend shape fails
   here, per the task brief. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const {
  parseContentId,
  QUESTION_TYPES,
  typeLabel,
  letterFor,
  optionStyle,
  markFor,
  progressLabel,
  progressPercent,
  scoreSummary,
  nextLabel,
} = await import('../static/orena/screens/check/model.js');
const { t } = await import('../static/orena/screens/check/copy.js');

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url)));
}

// 1. The shared content-id scheme, trimmed to what this screen needs (kind + id only).
assert.deepEqual(parseContentId('article:abc-1'), { kind: 'article', id: 'abc-1' });
assert.deepEqual(parseContentId('book:b1:c2'), { kind: 'book', id: 'b1:c2' }, 'not this screen\'s id shape to unpack further - only article ever practises');
assert.deepEqual(parseContentId('bogus'), { kind: '', id: '' });
assert.deepEqual(parseContentId(''), { kind: '', id: '' });

// 2. Every real backend question type (reading_evidence_repository.py QUESTION_TYPES) has a
// translated label in all three packs - never the frame's own sample "factual/inference/meaning"
// wording (D-068). An unknown type falls back to its own raw string rather than throwing.
for (const type of QUESTION_TYPES) {
  assert.equal(typeof typeLabel(type, t), 'string');
  assert.notEqual(typeLabel(type, t), '');
}
assert.equal(typeLabel('never_seen_type', t), 'never_seen_type');
assert.equal(letterFor(0), 'A');
assert.equal(letterFor(3), 'D');

// 3. Option style/mark, the design script's own three states (`cuOptions`): unanswered and every
// option that is neither the answer nor the pick look the same (rule 40: no colour before a real
// verdict exists), the correct option is green, a wrong pick is red, and the text colour never
// changes.
const neutral = { border: 'var(--border)', bg: 'var(--surface)', color: 'var(--text)', markBg: 'transparent', markColor: 'var(--muted)' };
assert.deepEqual(optionStyle({ index: 1, graded: false, correctIndex: null, selectedIndex: null }), neutral);
assert.equal(markFor({ index: 1, graded: false }), 'B');

const correctPicked = optionStyle({ index: 2, graded: true, correctIndex: 2, selectedIndex: 2 });
assert.deepEqual(correctPicked, { border: 'var(--green)', bg: 'var(--green-soft)', color: 'var(--text)', markBg: 'var(--green)', markColor: 'var(--badge-ink)' });
assert.equal(markFor({ index: 2, graded: true, correctIndex: 2, selectedIndex: 2 }), '✓');

const wrongPicked = optionStyle({ index: 0, graded: true, correctIndex: 2, selectedIndex: 0 });
assert.deepEqual(wrongPicked, { border: 'var(--red)', bg: 'var(--red-soft)', color: 'var(--text)', markBg: 'var(--red)', markColor: 'var(--badge-ink)' });
assert.equal(markFor({ index: 0, graded: true, correctIndex: 2, selectedIndex: 0 }), '×');

const answerShownAfterWrongPick = optionStyle({ index: 2, graded: true, correctIndex: 2, selectedIndex: 0 });
assert.equal(answerShownAfterWrongPick.border, 'var(--green)', 'the answer is shown on a wrong pick');
const untouchedAfterGrading = optionStyle({ index: 1, graded: true, correctIndex: 2, selectedIndex: 0 });
assert.deepEqual(untouchedAfterGrading, neutral, 'a third option, neither correct nor picked, is unchanged - the text colour included');
assert.equal(markFor({ index: 1, graded: true, correctIndex: 2, selectedIndex: 0 }), 'B');

// A graded option must stay an ordinary button: the kit's global `button:disabled` rule is
// `!important` and would paint every option the same grey, erasing the verdict colours above.
const checkSource = readFileSync(new URL('../static/orena/screens/check/screen.js', import.meta.url), 'utf8');
const optionLine = checkSource.split(/\r?\n/).find((line) => line.includes('data-option="${index}"'));
assert.ok(optionLine, 'the option markup line is found');
assert.ok(!/\sdisabled\b/.test(optionLine.replaceAll('aria-disabled', '')), 'a graded option is aria-disabled, never `disabled`');
assert.ok(optionLine.includes('aria-disabled="true"'));

// 4. Progress line/bar: position, not score - and, like the source, the bar moves with the current
// question's index (it reads 0 on the first question, whether or not it is answered yet) and reads
// 100 on the result.
assert.equal(progressLabel(0, 3, t), 'question 1 of 3');
assert.equal(progressLabel(2, 3, t), 'question 3 of 3');
assert.equal(t('progressDone'), 'done');
assert.equal(progressPercent(0, 3), 0);
assert.equal(progressPercent(1, 3), 33);
assert.equal(progressPercent(3, 3), 100);
assert.equal(progressPercent(7, 3), 100, 'never past the end');
assert.equal(progressPercent(0, 0), 0);

// 5. nextLabel: "Next question" mid-set, "See result" only on the last one.
assert.equal(nextLabel(0, 3, t), 'Next question');
assert.equal(nextLabel(2, 3, t), 'See result');

// 6. scoreSummary against the real (serializer-built) question set + a real grade result shape -
// every field this screen reads (question_type, id, correct) is one the backend actually returns.
const approved = fixture('reading_practice_article_set_approved.json');
const gradeFixture = fixture('reading_practice_grade_result.json');
const questions = approved.set.questions;
assert.equal(questions.length, 3);
for (const question of questions) {
  assert.ok(QUESTION_TYPES.includes(question.question_type), `unknown question_type ${question.question_type}`);
  assert.ok(Array.isArray(question.options) && question.options.length >= 2);
}
assert.equal(gradeFixture.result.question_id, questions[0].id);

const graded = {
  [questions[0].id]: gradeFixture.result, // correct: true
  [questions[1].id]: { ...gradeFixture.result, question_id: questions[1].id, correct: false },
};
const summary = scoreSummary(questions, graded, t);
assert.equal(summary.total, 3);
assert.equal(summary.correctCount, 1);
assert.equal('pct' in summary, false, "the headline is the source's fraction, not a percentage");
assert.equal(t('resultHeadline', { correct: summary.correctCount, total: summary.total }), 'You understood 1 / 3');
// One chip per graded question, in order, "<type> · Correct|Missed" - the third (ungraded) question contributes none.
assert.deepEqual(summary.chips, [
  { label: typeLabel('main_idea', t), result: 'Correct', ok: true },
  { label: typeLabel('inference', t), result: 'Missed', ok: false },
]);

// Two questions of one type are two chips, never a merged tally.
const twins = [{ id: 'a', question_type: 'detail' }, { id: 'b', question_type: 'detail' }];
assert.deepEqual(scoreSummary(twins, { a: { correct: true }, b: { correct: false } }, t).chips.map((chip) => chip.result), ['Correct', 'Missed']);

// A wholly-ungraded summary is an honest 0/total, never a fabricated pass.
assert.deepEqual(scoreSummary(questions, {}, t), { correctCount: 0, total: 3, chips: [] });

// The fixture's evidence is plain words copied from the article (the backend verifies the span), so
// the screen's own quotation marks are the only ones - and a question may have none at all.
assert.ok(!/^["“]|["”]$/.test(gradeFixture.result.evidence_fragment), "the backend's evidence carries no quotation marks of its own");

// 7. Every word this screen adds is in all three languages with its placeholders.
for (const key of ['progress', 'progressDone', 'seeResult', 'resultHeadline', 'missedLabel', 'correctLabel']) assert.ok(t.has(key), key);

console.log('test_orena_screen_check.mjs: Check Understanding model - real question types, option grading states, score summary against the captured/serializer contract: PASS');
