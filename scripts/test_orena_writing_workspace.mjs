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
import { writingReview, writingReviewFailure, orderedIssues } from '../static/orena/ui/writing-review.js';

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

/* --- Feedback leads with what is worth doing now ------------------------ */
const text = 'I go to the shop yesterday and buyed some bread and I dont finished it.';
const result = {
  overall: 55,
  app_cefr: 'B1',
  summary: { interpretation: 'Your meaning comes through.' },
  corrected_text: 'I went to the shop yesterday and bought some bread.',
  dimensions: { grammar: 50 },
  strengths: [{ quote: 'some bread', why: 'clear', category: 'vocabulary' }],
  next_actions: ['Practise the past tense.'],
  issues: [
    { quote: 'dont finished it', priority: 'low', category: 'tense', suggestion: "didn't finish it" },
    { quote: 'I go to', priority: 'high', category: 'tense', suggestion: 'I went to', why: 'Past.' },
    { quote: 'buyed', priority: 'medium', category: 'word_form', suggestion: 'bought' },
    { quote: 'the shop yesterday', priority: 'medium', category: 'other', suggestion: 'the shop' },
  ],
};
const ordered = orderedIssues(result, text);
assert.deepEqual(
  ordered.map((entry) => entry.item.quote),
  ['I go to', 'buyed', 'the shop yesterday', 'dont finished it'],
  'the most useful come first, and equal ones keep the order they arrived in',
);
assert.deepEqual(
  ordered.map((entry) => entry.index),
  [1, 2, 3, 0],
  'an issue keeps the position the room binds its handlers to',
);
const html = writingReview(c, result, { language: 'en', text });
const focus = html.slice(html.indexOf('review-issues'), html.indexOf('</section>', html.indexOf('review-issues')));
assert.equal((focus.match(/class="correction"/g) || []).length, 3, 'three lead, no more');
assert.ok(html.includes(`<h3>${c.reviewFocus}</h3>`), 'and they are named as the place to start');
/* Where to begin is never folded away: a review that is a score and some
   accordions is a report, not coaching. */
assert.ok(
  !/<details[^>]*>(?:(?!<\/details>)[\s\S])*?review-issues/.test(html),
  'the place to start is not inside a fold',
);
assert.ok(html.indexOf('review-issues') < html.indexOf(c.reviewStrengths), 'corrections come before praise');
for (const folded of [c.reviewStrengths, c.reviewNext, c.reviewDeeper, c.reviewWholePiece])
  assert.ok(html.includes(`<summary>${folded}</summary>`), `${folded} is kept, as its own step`);
/* Everything the evaluator found stays reachable: the rest of the corrections
   are a step of their own rather than a fold inside the first three. */
const deep = html.slice(html.indexOf('review-deeper'), html.indexOf('</section>', html.indexOf('review-deeper')));
assert.equal((deep.match(/class="correction"/g) || []).length, 1, 'the remaining findings are all kept');
assert.ok(
  html.indexOf(c.reviewNext) < html.indexOf('review-deeper'),
  'and they come after what to practise next',
);

/* --- One rubric dimension is one row ------------------------------------ */
/* Label, bar, score, change. They were four items in a three-column grid, so
   the change wrapped under every dimension and each row doubled in height. */
const experiences = read('static/orena/experiences.css');
assert.match(experiences, /\.review-dimension \{[^}]*grid-template-columns: minmax\(6rem, 8\.5rem\) 1fr auto auto/,
  'four columns for four things');
assert.doesNotMatch(experiences, /\.review-dimension dd \{[^}]*display: contents/,
  'the cells are cells, not a contents passthrough that loses the count');
/* The bar shows where the learner was and where they are now. The previous
   score is arithmetic on the change the evaluator returned, never a guess. */
const improved = writingReview(c, { ...result, dimensions: { grammar: 45 }, delta: { grammar: 7 } }, { language: 'en', text });
assert.match(improved, /review-dimension" data-direction="up"/, 'a gain says so');
assert.match(improved, /review-bar__held" style="inline-size:38%"/, 'the ground held is where they were');
assert.match(improved, /review-bar__shift" style="inline-size:7%"/, 'and the stretch is what they added');
const slipped = writingReview(c, { ...result, dimensions: { grammar: 45 }, delta: { grammar: -10 } }, { language: 'en', text });
assert.match(slipped, /review-dimension" data-direction="down"/, 'a loss says so too');
assert.match(slipped, /review-bar__held" style="inline-size:45%"/, 'held is where they are now');
assert.match(slipped, /review-bar__shift" style="inline-size:10%"/, 'and the shift is the ground given up');
assert.match(experiences, /\[data-direction='down'\] \.review-bar__shift \{[^}]*repeating-linear-gradient/,
  'so a drop cannot read as progress');
const flat = writingReview(c, { ...result, dimensions: { grammar: 45 }, delta: {} }, { language: 'en', text });
assert.match(flat, /data-direction="none"/, 'no previous review means no direction');
assert.doesNotMatch(flat, /class="dimension-move"/, 'and no change is invented');
assert.match(flat, /review-bar__held" style="inline-size:45%"/, 'just the score');

/* --- Where am I, before what do I fix ----------------------------------- */
/* The corrections were moved to the front of the review, which left the
   measurement several folds down - so a learner met "fix this" before "how am
   I doing". The overview leads now: the score, the level, the movement since
   the last version, and the dimensions the evaluator actually scored. */
assert.ok(html.includes('class="review-overview"'), 'the review opens on an overview');
assert.ok(
  html.indexOf('review-overview') < html.indexOf('review-issues'),
  'and it comes before the corrections',
);
assert.ok(
  html.indexOf('review-dimensions') < html.indexOf('review-issues'),
  'the dimensions are part of that overview, not a fold below the corrections',
);
assert.ok(
  html.indexOf('review-headline') < html.indexOf('review-dimensions'),
  'the score leads the overview',
);
assert.doesNotMatch(html, new RegExp(`<summary>${c.reviewDimensions}</summary>`),
  'and they are no longer folded away');
/* Only what the evaluator returned. No average, no invented confidence. */
const scoreless = writingReview(c, { ...result, overall: null, dimensions: {} }, { language: 'en', text });
assert.doesNotMatch(scoreless, /review-headline|review-dimensions/,
  'no score and no dimensions means none are drawn');
assert.doesNotMatch(scoreless, /(100|50|0)\s*%/, 'and nothing is computed to fill the gap');
const partial = writingReview(c, { ...result, dimensions: { grammar: 50 } }, { language: 'en', text });
assert.equal((partial.match(/class="review-dimension"/g) || []).length, 1,
  'one scored dimension draws one row, not a full rubric of blanks');

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
/* Nothing is dropped: a folded section is still whole. */
assert.ok(html.includes('Practise the past tense.'), 'the priorities survive the fold');
assert.ok(html.includes(result.corrected_text), 'and so does the whole-piece rewrite');
/* A section behind a fold is named once, by its summary. */
assert.equal((html.match(new RegExp(c.reviewStrengths, 'g')) || []).length, 1, 'named once');

/* --- The learner's own text is where a quote is found ------------------- */
assert.match(html, /data-locate="\d+"/, 'every correction can be found in the text');
const locate = read('static/orena/ui/writing-locate.js');
assert.match(locate, /export function locateInText/, 'finding it is a shared thing, not a page trick');
assert.match(locate, /setSelectionRange/, "it uses the browser's own selection");
assert.doesNotMatch(locate, /innerHTML|value\s*=/, 'and never rewrites what the learner wrote');
assert.match(expression, /locateInText\(box, issue\.quote\)/, 'the room asks it for the quoted phrase');
assert.match(expression, /showActivity\(\);\n\s+if \(!locateInText/, 'on a phone that means coming back to the page');

/* --- Nothing replaces the learner's writing ----------------------------- */
const submit = expression.slice(expression.indexOf("root.querySelector('form').onsubmit"));
assert.doesNotMatch(submit, /box\.value = |textarea'\)\.value = /, 'a review never writes into the box');
assert.match(expression, /data-revise/, 'revising is offered');
assert.match(contract, /27\. \*\*The writing revision loop\.\*\*/, 'the durable rule is recorded');
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
assert.match(contract, /does not replay it\./, 'the durable rule is recorded');

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
