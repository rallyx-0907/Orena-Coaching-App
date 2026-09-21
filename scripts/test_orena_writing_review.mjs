// Writing review and register exploration. The evaluator has always returned a
// full review; the surface used to show two lines of it. These assertions hold
// the parts that make the review trustworthy: it says only what the payload
// carried, it never strikes through words the learner did not write, and it
// never presents one rewrite as the answer.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import {
  DIMENSIONS,
  KINDS,
  applyFix,
  dimensionsHtml,
  feedbackHtml,
  issueSheetHtml,
  revisionHtml,
  writingReviewFailure,
} from '../static/orena/ui/writing-feedback.js';
import { REGISTERS, registerLabel } from '../static/orena/ui/registers.js';

const c = copy.en;
const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

// The dimensions the UI draws are a subset of the rubric the evaluator scores,
// in the baseline's order; the fifth (task achievement) is scored and kept.
const benchmark = read('writing_coach/writing_evaluation_benchmark.py');
const declared = [
  ...benchmark
    .split('RUBRIC_DIMENSIONS = (')[1]
    .split(')')[0]
    .matchAll(/"([a-z_]+)"/g),
].map((m) => m[1]);
for (const key of DIMENSIONS) assert.ok(declared.includes(key), `${key} is a scored dimension`);
const RUBRIC = declared;

// Every dimension and register a learner can be shown has to be readable in
// both languages. A missing label degrades to a raw key like task_achievement.
for (const ui of ['en', 'zh']) {
  for (const key of RUBRIC) {
    assert.ok(copy[ui][`rubric_${key}`], `${ui}: no label for dimension "${key}"`);
  }
  for (const key of REGISTERS) {
    const label = registerLabel(copy[ui], key);
    assert.ok(label && label.length > 1, `${ui}: no label for register "${key}"`);
  }
}

const profileCategories = (path) => [
  ...read(path)
    .split('ERROR_CATEGORIES = (')[1]
    .split(')')[0]
    .matchAll(/"([a-z_]+)"/g),
].map((match) => match[1]);
for (const ui of ['en', 'zh']) {
  for (const key of new Set([
    ...profileCategories('writing_coach/languages/english/profile.py'),
    ...profileCategories('writing_coach/languages/chinese/profile.py'),
  ])) {
    assert.ok(copy[ui][`rubric_${key}`], `${ui}: no readable label for feedback category "${key}"`);
  }
}
assert.equal(registerLabel(c, 'not_a_register'), '', 'unknown stays silent');

/* --- The review, the finding and the revision, from the two contracts (D-066) --- */
const review = {
  draftId: '1', version: 1, wordCount: 142, summary: 'Thư đủ ý <và> dễ đọc.', strengths: 'Mở thư đúng kiểu.',
  issues: [
    { id: 'a', fragment: 'ønsker å informere deg om', correction: 'må bare fortelle deg', why: 'Giọng công văn.', rule: 'Chọn động từ thường.',
      grammarRef: null, examples: ['Jeg må bare fortelle deg at jeg har ny jobb.'], kind: 'register', anchored: true },
    { id: 'b', fragment: 'et kafé', correction: 'en kafé', why: 'kafé là en-ord.', rule: 'Từ mượn -é là en-ord.',
      grammarRef: 'no-gender', examples: [], kind: 'grammar', anchored: true },
    { id: 'c', fragment: ', han hjelper meg', correction: ', og han hjelper meg', why: 'Cần liên từ.', rule: '', grammarRef: null, examples: [], kind: 'punctuation', anchored: false },
  ],
  dimensions: [
    { name: 'naturalness', value: 72 }, { name: 'grammar', value: 84 }, { name: 'vocabulary', value: 80 }, { name: 'coherence', value: 88 },
  ],
};
for (const ui of ['en', 'zh']) {
  for (const key of ['writingKindRegister', 'writingKindGrammar', 'writingKindPunctuation', 'writingKindVocabulary', 'writingKindNaturalness', 'writingDimensions',
    'writingOverview', 'writingStrengths', 'writingIssuesCount', 'writingRuleChip', 'writingGrammarChip', 'writingSaveConcept', 'writingApply', 'writingRuleLabel',
    'writingAllApplied', 'writingVsPrevious', 'writingFixedCount', 'writingRemainingCount', 'writingNewCount', 'writingVersion', 'writingWords', 'writingChanges',
    'writingFixedOf', 'writingNoChanges'])
    assert.ok(copy[ui][key], `${ui}: missing copy for "${key}"`);
}
assert.deepEqual([...KINDS], ['register', 'grammar', 'punctuation', 'vocabulary', 'naturalness'], "the kinds are the baseline's");

const html = feedbackHtml(c, review, { language: 'no' });
assert.match(html, /Thư đủ ý &lt;và&gt; dễ đọc\./, 'the evaluator\'s words are escaped');
assert.equal((html.match(/class="wf-issue"/g) || []).length, 3, 'every finding is kept, anchored or not');
assert.match(html, new RegExp(c.writingIssuesCount.replace('{n}', '3')));
assert.match(html, /wf-was wf-was--warm[^>]*>ønsker å informere deg om</, 'a register finding is struck in the warm colour');
assert.match(html, /wf-was wf-was--info[^>]*>, han hjelper meg</, 'a punctuation one in blue');
assert.match(html, /href="#\/grammar\?id=no-gender"/, 'related grammar links to its lesson');
assert.equal((html.match(/data-wf="rule"/g) || []).length, 2, 'a finding without a rule offers no rule chip');
assert.equal((html.match(/data-wf="ask"/g) || []).length, 3);
assert.equal((html.match(/class="wf-dimension"/g) || []).length, 4, 'four dimensions, no fifth');
assert.match(html, /inline-size:72%/, 'a dimension is drawn at the value it was given');
assert.doesNotMatch(html, /review-headline|task_achievement/, 'no invented headline score');

// A finding applied leaves the list; when none is left the review says so.
const oneApplied = feedbackHtml(c, review, { language: 'no', applied: new Set(['a']) });
assert.equal((oneApplied.match(/class="wf-issue"/g) || []).length, 2);
assert.match(oneApplied, new RegExp(c.writingIssuesCount.replace('{n}', '2')));
const allApplied = feedbackHtml(c, review, { language: 'no', applied: new Set(['a', 'b', 'c']) });
assert.match(allApplied, new RegExp(c.writingAllApplied));
assert.doesNotMatch(allApplied, /class="wf-issue"/);

// Nothing to fix says so; nothing to score draws no dimensions.
const clean = feedbackHtml(c, { ...review, issues: [], dimensions: [], strengths: '' }, { language: 'en' });
assert.match(clean, new RegExp(c.noCorrections));
assert.equal(dimensionsHtml(c, []), '');
assert.doesNotMatch(dimensionsHtml(c, [{ name: 'grammar', value: null }]), /wf-dimension"/, 'a missing score is not drawn as 0');

// The finding, opened.
const sheet = issueSheetHtml(c, review.issues[0], { language: 'no', support: 'vi', thread: [{ id: 1, question: 'Why?', state: 'ready', answer: 'Because.' }] });
assert.match(sheet, /wf-sheet-fragment[^>]*>ønsker å informere deg om</);
assert.match(sheet, new RegExp(c.writingKindRegister));
assert.match(sheet, /Chọn động từ thường\./);
assert.match(sheet, /Jeg må bare fortelle deg at jeg har ny jobb\./, 'the evaluator\'s example is shown');
assert.match(sheet, /data-wf="apply"/);
assert.match(sheet, /data-wf="save-concept"[^>]*aria-disabled="true"/, 'saving a concept keeps its place and says it is not available yet');
assert.doesNotMatch(issueSheetHtml(c, review.issues[1], { language: 'no', support: 'vi' }), /wf-example/, 'no example is invented');
assert.doesNotMatch(issueSheetHtml(c, review.issues[2], { language: 'no', support: 'vi', canApply: false }), /data-wf="apply"/, 'an unanchored finding cannot be applied');

// Applying replaces the first occurrence of the learner\'s own words, or nothing.
const draft = 'Jeg ønsker å informere deg om noe. På et kafé.';
const fixed = applyFix(draft, review.issues[0]);
assert.equal(fixed.text, 'Jeg må bare fortelle deg noe. På et kafé.');
assert.equal(fixed.text.slice(fixed.start, fixed.end), 'må bare fortelle deg');
assert.equal(applyFix('nothing to see', review.issues[0]), null, 'words that are not in the draft are not replaced');
assert.equal(applyFix('et kafé og et kafé', review.issues[1]), null, 'a repeated quotation leaves the learner to choose');
assert.equal(applyFix('et kafé', { ...review.issues[1], correction: 'x'.repeat(12001) }), null, 'the writing limit still holds');

const compare = {
  previous: { version: 1, wordCount: 142, text: 'Jeg ønsker å informere deg om at jeg bor her.' },
  current: { version: 2, wordCount: 151, text: 'Jeg må bare fortelle deg at jeg bor her.' },
  fixed: [{ title: 'ønsker å informere', kind: 'register', detail: 'ønsker å informere → må bare fortelle' }],
  remaining: [{ title: ', han hjelper meg', kind: 'punctuation', detail: ', og han hjelper meg - Cần liên từ.' }],
  added: [{ title: 'veldig masse', kind: 'vocabulary', detail: 'veldig mye - masse không đi với veldig' }],
  dimensionDeltas: [{ name: 'naturalness', from: 72, to: 88 }, { name: 'vocabulary', from: 80, to: 78 }],
};
const revised = revisionHtml(c, compare, { language: 'no' });
assert.match(revised, new RegExp(c.writingFixedOf.replace('{a}', '1').replace('{b}', '2')), 'fixed one of the two that were there');
assert.match(revised, new RegExp(c.writingFixedCount.replace('{n}', '1')));
assert.match(revised, new RegExp(c.writingRemainingCount.replace('{n}', '1')));
assert.match(revised, new RegExp(c.writingNewCount.replace('{n}', '1')));
assert.match(revised, new RegExp(c.writingVersion.replace('{n}', '1')));
assert.match(revised, new RegExp(c.writingVersion.replace('{n}', '2')));
assert.match(revised, /72 → 88/, 'a dimension shows where it was and where it is');
assert.match(revised, /80 → 78[\s\S]*?data-move="down"|data-move="down"[\s\S]*?80 → 78/, 'a drop is a drop');
assert.match(revised, /veldig masse/);
assert.match(revised, /data-state="added"/);
// The comparison has nothing to say about a first version, and says nothing.
assert.match(revisionHtml(c, { ...compare, fixed: [], remaining: [], added: [], dimensionDeltas: [] }, { language: 'no' }), new RegExp(c.writingNoChanges));

// A transient provider failure is actionable; a permanent/unconfigured state
// must not invite a retry that cannot help. Both keep the learner's draft.
const retryableFailure = writingReviewFailure(c, new Error('x'));
assert.ok(retryableFailure.includes(c.reviewFailed));
assert.ok(retryableFailure.includes('data-retry-review'));
const unavailableFailure = writingReviewFailure(c, Object.assign(new Error('x'), { retryable: false }));
assert.ok(unavailableFailure.includes(c.reviewUnavailable));
assert.ok(!unavailableFailure.includes('data-retry-review'));

/* What the learner is writing reaches the evaluator. A lab report and a
   friendly email are not the same task, and the evaluator has always accepted
   one - nothing asked the learner for it. */
const expressionSource = read('static/orena/ui/expression.js');
assert.ok(
  expressionSource.includes("root.querySelector('[name=task]').value.trim()"),
  'the surface must ask what the learner is writing',
);
assert.ok(
  /task && `\$\{c\.writingTask\} \$\{task\}`/.test(expressionSource),
  'the stated task must travel with the text as the writing task',
);
/* Proficiency is guidance the frame gives no control for (D-067): the request carries no target and the
   evaluator infers the demonstrated band, so the target travels as null, never as an empty string. */
assert.ok(!/name="target"/.test(expressionSource), 'no level control is drawn');
assert.match(expressionSource, /target_cefr:\s*null/, 'the target travels as null so the evaluator infers the level');
for (const ui of ['en', 'zh']) {
  for (const key of ['writingTask', 'writingTaskNote', 'chooseTarget', 'reviewReworked'])
    assert.ok(copy[ui][key], `${ui}: missing copy for "${key}"`);
}

// Register exploration is a comparison, not a rewrite button. Each version has
// to arrive with what puts it in that register and when it is the wrong choice.
const registers = read('static/orena/ui/registers.js');
assert.match(registers, /registerSignals/, 'a version shows the signals that place it');
assert.match(registers, /registerAvoidWhen/, 'a version shows when it is wrong');
assert.match(registers, /registerUnavailable/, 'an answer that did not arrive is not filled in');

const server = read('writing_coach/media_interaction.py');
const serverRegisters = [
  ...server.split('REGISTERS = (')[1].split(')')[0].matchAll(/"([a-z_]+)"/g),
].map((m) => m[1]);
assert.deepEqual([...REGISTERS], serverRegisters, 'the register vocabulary must match on both sides');
// Only `contextual_router` is mounted by the app; `router` in this module is
// not. A route added to the wrong one answers 404 in the browser and passes
// every unit test.
assert.match(
  server,
  /@contextual_router\.post\("\/registers"\)/,
  'the register route must hang off the router the app actually includes',
);
assert.match(
  server,
  /Never cite a style guide, standard or corpus you were not/,
  'no invented authority',
);
assert.match(
  server,
  /one version as correct and the others as mistakes/,
  'no version is the correct one',
);

// Going deeper from a finding asks about the learner's own wording, with the
// sentence it sat in, through the same sentence contract the Quick Sheet uses.
const expression = read('static/orena/ui/expression.js');
const feedbackSource = read('static/orena/ui/writing-feedback.js');
assert.match(feedbackSource, /api\.sentenceSheet\(\{\s*text: issue\.fragment/, 'the question is about the quoted words');
assert.match(feedbackSource, /find\(\(part\) => part\.includes\(issue\.fragment\)\)/, 'the sentence travels with it');
assert.match(expression, /api\.essayReview\(/, 'the review is read from its contract');
assert.match(expression, /api\.essayRevision\(/, 'and so is the revision');
/* Register exploration has no place in the "Writing workspace" frame (D-067), so the room no longer
   opens it; the module stays, tested above, until the human gives it a place or removes it
   (UI_BACKEND_GAPS.md, Writing decisions). */
assert.doesNotMatch(expression, /openRegisters\(ctx/, 'the room offers no entry the frame does not draw');
assert.match(
  expression,
  /data-retry-review/,
  'a retryable evaluation failure is wired back to the same writing submission',
);
assert.match(
  expression,
  /const form = event\.currentTarget/,
  'the form reference is captured before the asynchronous evaluation begins',
);
assert.match(
  expression,
  /form\.requestSubmit\(\)/,
  'retry submits the captured form after the original submit event has finished',
);

console.log('Orena writing review, rubric parity and register comparison: PASS');
