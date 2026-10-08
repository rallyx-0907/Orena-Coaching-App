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
import * as browserLimits from '../static/orena/capabilities/writing-limits.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const screen = read('static/orena/screens/writing/screen.js');
const contract = read('docs/project/DESIGN_CONTRACT.md');

/* --- What never reaches the network ------------------------------------- */
const limits = read('static/orena/capabilities/writing-limits.js');
assert.match(limits, /export function measureWriting/, 'the browser can measure a piece of writing');
assert.match(limits, /export function editWouldFit/, 'and an edit before it happens');
assert.match(screen, /root\.addEventListener\('paste', onPaste\)/, 'a paste is judged before it is inserted');
assert.match(screen, /if \(measured\.withinLimits\) return;\s+event\.preventDefault\(\);\s+refuseTooLong\(measured\);/, 'and refused whole');
assert.doesNotMatch(limits, /\.slice\(0, MAX|substring/, 'nothing here truncates a learner');
assert.match(screen, /const measured = measureWriting\(box\.value\);\s+if \(!measured\.withinLimits\)/,
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

/* --- The request minimum: one table, per learning language, on both sides --------
   `tests/fixtures/writing_minimum_cases.json` states it once - the table, the stated
   default, and the counts that follow from it - and `tests/test_writing_minimum.py` holds
   the server to it. This holds the browser to the same file, so a learner is never told
   "write more" by a button the server would have accepted, or let through by one it
   would refuse. It is a floor for "is this writing at all"; whether an attempt is enough
   to grade stays the evaluator's (`band_status: insufficient_evidence`). */
const minimum = JSON.parse(read('tests/fixtures/writing_minimum_cases.json'));
assert.deepEqual(
  JSON.parse(JSON.stringify(browserLimits.MINIMUM_BY_LANGUAGE)),
  minimum.table,
  'the browser and the server have the same row for every learning language',
);
assert.deepEqual(
  JSON.parse(JSON.stringify(browserLimits.DEFAULT_MINIMUM)),
  minimum.default,
  'and the same default for a language with none',
);
assert.ok(minimum.cases.length >= 40, 'the shared cases are the whole of the table, not a sample');
for (const item of minimum.cases) {
  const label = `${item.language} ${JSON.stringify(item.text)} (${item.note})`;
  const measured = browserLimits.measureMinimum(item.text, item.language);
  assert.equal(measured.unit, item.unit, `${label}: counted in ${item.unit}`);
  assert.equal(measured.count, item.count, `${label}: counts to ${item.count}`);
  assert.equal(measured.met, item.meets, `${label}: ${item.meets ? 'is' : 'is not'} an attempt`);
  assert.equal(browserLimits.meetsMinimum(item.text, item.language), item.meets, label);
}
assert.ok(
  !/min_length\s*=\s*10/.test(read('app.py')),
  'no request model carries a flat ten-character floor: what counts as an attempt depends on the language',
);
assert.ok(
  minimum.cases.some((item) => item.language === 'zh' && item.text === '我是学生。' && item.meets),
  'the HSK 1 sentence that was refused is in the shared cases, accepted',
);
/* The box states no floor of its own: a textarea's `minlength` is checked in code points before any
   handler runs, so a five-character HSK 1 sentence would be refused before anything could count it
   in the learner's own unit. The review gate asks the shared table (screens/writing/model.js
   reviewGate -> measureMinimum). */
assert.ok(!/minlength\s*=/i.test(screen), 'the Writing textarea carries no minlength');
assert.match(read('static/orena/screens/writing/model.js'), /measureMinimum\(trimmed, language\)\.met/, 'the review gate asks the language floor');
/* --- Nothing replaces the learner's writing: the durable rules are recorded --------- */
assert.match(contract, /27\. \*\*The writing revision loop\.\*\*/, 'the durable rule is recorded');
assert.match(contract, /never substitutes generated text for the learner's\s+writing/, "and says a review never replaces the learner's writing");
assert.match(contract, /28\. \*\*Bounded before it is spent on\.\*\*/, 'and so is the resource bound');
assert.match(contract, /29\. \*\*A valid evaluation is reused, never recomputed\.\*\*/, 'and the reuse rule');

/* --- A stale device record never blocks a learner from being read ------- */
assert.match(screen, /error\?\.category !== 'parent_essay_not_found'/,
  'a parent the server does not know is dropped, not reported to the learner');


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
assert.match(contract, /Generated guidance is \*\*requested\*\* in the support language, not translated\s+afterwards, and a stored one carries the language it was written in\./, 'the durable rule is recorded');

console.log('Writing workspace: input bounds, the language floor on both sides, support-language reviews, durable rules: PASS');
