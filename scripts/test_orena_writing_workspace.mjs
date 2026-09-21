/* Writing as a workspace, not a form.

   What this replaced: a page-wide heading, one very tall box, and then - under
   the box, where a learner only arrives after writing - the draft status, a
   character count, a selector labelled "feedback target", the Review button,
   and finally the field asking what the piece was for. The thing most needed
   before starting was the last thing reachable, the primary action sat at the
   bottom of a form, and an empty bordered pane stood beside it taking half the
   room until a review arrived.

   These are the contracts that keep that from growing back: the learner's text
   and the feedback stay in one working context, the feedback leads with what
   is worth doing now, a quoted phrase is findable in the learner's own text,
   and nothing replaces what the learner wrote (DESIGN_CONTRACT rule 27). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { writingReviewFailure } from '../static/orena/ui/writing-feedback.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const expression = read('static/orena/ui/expression.js');
const rooms = read('static/orena/rooms.css');
const contract = read('docs/project/DESIGN_CONTRACT.md');

/* --- What the piece is for, before and while writing -------------------- */
const head = expression.slice(
  expression.indexOf('<header class="writing-head">'),
  expression.indexOf('<section class="learning-workspace writing-workspace"'),
);
assert.ok(head.includes('writing-intention'), 'the intention has a place in the heading');
assert.ok(head.includes('id="writingTask"'), 'and it is the same field the evaluator is told about');
assert.ok(
  expression.indexOf('class="writing-intention"') < expression.indexOf('id="expressionText"'),
  'the learner meets it before the box, not under it',
);
assert.doesNotMatch(expression, /class="writing-task"/, 'the form row below the editor is gone');
assert.doesNotMatch(expression, /class="expression-tools"/, 'and so is the settings row it sat in');

/* --- One primary action, named in one word ------------------------------ */
assert.match(expression, /data-review-action/, 'Review is a named control');
assert.match(expression, /\$\{esc\(c\.reviewAction\)\}<\/button>/, 'it carries the short name');
for (const ui of ['en', 'zh', 'vi']) {
  assert.ok(copy[ui].reviewAction?.trim(), `${ui} names the action`);
  assert.ok(
    copy[ui].reviewAction.length < copy[ui].review.length,
    `${ui}: the action is shorter than the room's own title for the review`,
  );
}
/* The level the review aims at is a setting, not the headline of the task. */
const bar = expression.slice(
  expression.indexOf('<div class="writing-bar">'),
  expression.indexOf('data-writing-trouble'),
);
assert.ok(bar.includes("name=\"target\""), 'the level still exists');
assert.ok(bar.includes('class="sr-only">${esc(c.reviewTarget)}'), 'named for assistive technology');
assert.ok(!bar.includes(`>\${c.reviewTarget}<`), 'but not as a visible form label beside the action');
assert.ok(bar.includes('learningToolbar('), 'the secondary actions use the shared bar');
assert.equal((bar.match(/class="primary"/g) || []).length, 1, 'one primary action in the row');

/* --- The margin is a margin until there is something to hold ------------ */
assert.match(expression, /data-review="waiting"/, 'the workspace says whether a review exists');
assert.match(expression, /workspace\.dataset\.review = 'ready'/, 'and says so when one arrives');
assert.match(expression, /workspace\.dataset\.review = 'working'/, 'and while one is being made');
assert.match(
  rooms,
  /\.writing-workspace\[data-review='ready'\] \.writing-result \{[^}]*border:/,
  'the margin becomes a surface only once it holds a review',
);
assert.match(
  rooms,
  /\.writing-workspace\[data-review='waiting'\],[\s\S]{0,120}?grid-template-columns: minmax\(0, 2\.1fr\)/,
  'and the page takes the width until then',
);
assert.match(
  rooms,
  /\.writing-workspace\[data-review='ready'\] \{[\s\S]{0,80}?grid-template-columns: minmax\(0, 1\.15fr\)/,
  'then the two settle into a working balance',
);
/* Chrome does not interpolate `minmax(0, <n>fr)`, so a transition on the
   columns held the starting width and the rebalance never arrived. */
assert.doesNotMatch(rooms, /transition:[^;]*grid-template-columns/, 'the columns change at once');

/* --- A review that cannot be made is a line, not a pane ----------------- */
const c = copy.en;
const failure = writingReviewFailure(c, { retryable: false });
assert.match(failure, /class="notice review-trouble"/, 'the failure is one compact notice');
assert.doesNotMatch(failure, /<section|<h2|<h3/, 'with no structure of its own');
assert.ok(failure.length < 400, 'and it is short');
assert.match(expression, /sayTrouble\(writingReviewFailure\(c, error\)\)/,
  'it is said beside the action that asked for the review');
assert.match(expression, /showActivity\(\);\n\s+const retry/, 'and the learner is put back on their page');
assert.match(rooms, /\.writing-trouble,\n\.review-trouble \{/, 'it is styled as a row, not a panel');

/* --- A review belongs to the words it was written about ----------------- */
assert.match(expression, /let reviewedText = null/, 'the room remembers which words were reviewed');
assert.match(expression, /function markReviewFreshness\(\)/, 'and says whether that is still current');
assert.match(expression, /reviewedText !== null && reviewedText !== box\.value/,
  'by comparing them, not by guessing from a timer');
assert.match(expression, /data-review-stale-note/, 'the learner is told, in the result frame');
/* The workspace's flag and the note are different names on purpose: one
   selector matching both hid the whole workspace, and only the grid's own
   `display` kept that from being visible. */
assert.ok(
  !/querySelector\('\[data-review-stale\]'\)/.test(expression),
  'the note is addressed by its own name',
);
assert.doesNotMatch(
  expression.slice(expression.indexOf('function markReviewFreshness(')),
  /feedback\.innerHTML = ''|\.remove\(\)/,
  'and the review is not taken away from somebody who is acting on it',
);
for (const ui of ['en', 'zh', 'vi'])
  for (const key of ['reviewStale', 'reviewStaleAction', 'writingTooLong', 'writingTooLongPaste'])
    assert.ok(copy[ui][key]?.trim(), `${ui}.${key} is said in the support language`);

/* --- What never reaches the network ------------------------------------- */
const limits = read('static/orena/capabilities/writing-limits.js');
assert.match(limits, /export function measureWriting/, 'the browser can measure a piece of writing');
assert.match(limits, /export function editWouldFit/, 'and an edit before it happens');
assert.match(expression, /box\.addEventListener\('paste'/, 'a paste is judged before it is inserted');
assert.ok(
  new RegExp('event\\.preventDefault\\(\\);\\s*sayTrouble').test(expression),
  'and refused whole',
);
assert.doesNotMatch(limits, /\.slice\(0, MAX|substring/, 'nothing here truncates a learner');
assert.match(expression, /const measured = measureWriting\(event\.target\.value\)/,
  'and any other way text arrives is measured too');
/* The browser and the server share one contract, and a gate fails on drift. */
const python = read('writing_coach/writing_limits.py');
for (const name of ['MAX_CHARACTERS', 'MAX_BYTES', 'MAX_LINES']) {
  const inJs = limits.match(new RegExp('export const ' + name + ' = (\\d+)'))?.[1];
  const inPy = python
    .match(new RegExp('^' + name + ' = ([\\d_]+)', 'm'))?.[1]
    ?.replace(/_/g, '');
  assert.ok(inJs && inPy, `${name} is stated on both sides`);
  assert.equal(inJs, inPy, `${name} must be the same number in the browser and on the server`);
}
/* --- Nothing replaces the learner's writing ----------------------------- */
const submit = expression.slice(expression.indexOf("root.querySelector('form').onsubmit"));
assert.doesNotMatch(submit, /box\.value = |textarea'\)\.value = /, 'a review never writes into the box');
assert.match(expression, /data-revise/, 'revising is offered');
assert.match(contract, /27\. \*\*The writing revision loop\.\*\*/, 'the durable rule is recorded');
assert.match(contract, /never substitutes generated text for the learner's\s+writing/, "and says a review never replaces the learner's writing");
assert.match(contract, /28\. \*\*Bounded before it is spent on\.\*\*/, 'and so is the resource bound');
assert.match(contract, /29\. \*\*A valid evaluation is reused, never recomputed\.\*\*/, 'and the reuse rule');

/* --- A stale device record never blocks a learner from being read ------- */
assert.match(expression, /error\?\.category !== 'parent_essay_not_found'/,
  'a parent the server does not know is dropped, not reported to the learner');
assert.match(expression, /parentId = null;\n\s+result = await ask\(null\)/, 'and the review is asked for again');

/* --- Generated guidance speaks the support language --------------------- */
/* And it is the evaluation that says so, not the device that happened to ask
   for it: a review earned on one device is recognised on another, and a
   Vietnamese one is never replayed to a learner now reading Chinese. */
const backend = read('app.py');
assert.match(backend, /support_language_name=support_name/, 'the evaluator is told which language to answer in');
assert.match(backend, /def _resolved_writing_support_language/, "from the learner's own profile");
const identity = read('writing_coach/writing_review_identity.py');
assert.match(identity, /"support_language": normalized_support/, 'the support language is part of a review identity');
assert.match(identity, /EVALUATOR_CONTRACT_VERSION/, 'and so is the evaluator agreement it was produced under');
assert.match(expression, /const reviewSpeaksTo = /, 'the room asks the stored identity, not a device record');
assert.match(expression, /identity\.support_language/, 'about the support language');
assert.doesNotMatch(expression, /entry\.support === ctx\.support/, 'the device-only guess is retired');
assert.match(contract, /Generated guidance is \*\*requested\*\* in the support language, not translated\s+afterwards, and a stored one carries the language it was written in\./, 'the durable rule is recorded');

/* --- EN, ZH and VI all say it ------------------------------------------- */
for (const ui of ['en', 'zh', 'vi'])
  for (const key of ['reviewAction', 'reviewFocus', 'reviewDeeper', 'reviewLocate',
    'reviewWorking', 'reviewAgain', 'writingIntentionNone', 'writingKeepWriting']) {
    assert.equal(typeof copy[ui][key], 'string', `${ui}.${key} exists`);
    assert.ok(copy[ui][key].trim(), `${ui}.${key} is not empty`);
  }
for (const key of ['reviewAction', 'reviewFocus', 'writingKeepWriting'])
  assert.equal(
    new Set([copy.en[key], copy.zh[key], copy.vi[key]]).size,
    3,
    `${key} reads differently in each supported language`,
  );

/* --- A phone recomposes rather than stacking the desktop ---------------- */
assert.match(rooms, /\.writing-bar \{[\s\S]{0,160}?display: flex/, 'the actions are one row');
assert.doesNotMatch(expression, /class="writing-sheet"[\s\S]{0,400}?<h2/, 'the page carries no heading of its own');

console.log('Writing workspace: intention first, one action, feedback that leads, text that stays: PASS');
