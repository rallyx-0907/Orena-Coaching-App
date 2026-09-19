// Writing review and register exploration. The evaluator has always returned a
// full review; the surface used to show two lines of it. These assertions hold
// the parts that make the review trustworthy: it says only what the payload
// carried, it never strikes through words the learner did not write, and it
// never presents one rewrite as the answer.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import {
  RUBRIC,
  anchored,
  shownIssues,
  shownStrengths,
  writingReviewFailure,
  writingReview,
} from '../static/orena/ui/writing-review.js';
import { REGISTERS, registerLabel } from '../static/orena/ui/registers.js';

const c = copy.en;
const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

// The rubric the UI renders must be the rubric the evaluator scores, or a
// dimension the learner is judged on stops being visible to them.
const benchmark = read('writing_coach/writing_evaluation_benchmark.py');
const declared = [
  ...benchmark
    .split('RUBRIC_DIMENSIONS = (')[1]
    .split(')')[0]
    .matchAll(/"([a-z_]+)"/g),
].map((m) => m[1]);
assert.deepEqual([...RUBRIC], declared, 'the rubric must match on both sides of the API');

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

const text = 'I go to the shop yesterday and buyed some bread for my family.';
const full = {
  overall: 68,
  app_cefr: 'B1',
  delta: { overall: 6 },
  summary: { interpretation: 'Your meaning comes through clearly.' },
  corrected_text: 'I went to the shop yesterday and bought some bread for my family.',
  dimensions: {
    grammar: 58,
    vocabulary: 72,
    coherence: 80,
    task_achievement: 74,
    naturalness: 66,
  },
  strengths: [
    {
      quote: 'for my family',
      why: 'A natural way to say who it was for.',
      category: 'vocabulary',
    },
    {
      quote: 'not in the learner text',
      why: 'This evidence was invented.',
      category: 'grammar',
    },
  ],
  issues: [
    {
      quote: 'go to the shop yesterday',
      suggestion: 'went to the shop yesterday',
      why: 'Yesterday puts this in the past.',
      how: 'Past simple',
      priority: 'high',
      category: 'grammar',
    },
    { quote: 'not in the learner text', suggestion: 'x', why: 'y', category: 'grammar' },
  ],
  next_actions: ['Past tense of irregular verbs'],
};

/* A finding is kept; a highlight is earned.

   An evaluator that quotes text back inaccurately cannot be allowed to point
   at the learner's words - a struck-through phrase must always be one they
   actually wrote. But dropping the whole finding for it meant a real mistake
   went unmentioned because the quote lost an apostrophe, which is the bug
   this pair of assertions now guards from both sides: every trustworthy
   finding survives, and only the ones that can be located are offered a span. */
const shown = shownIssues(full, text);
assert.equal(shown.length, 2, 'every trustworthy finding is kept');
assert.equal(
  shown.filter((issue) => anchored(issue, text)).length,
  1,
  'but only the one the learner actually wrote can be pointed at',
);
assert.equal(anchored({ quote: 'not in the learner text' }, text), false);
assert.equal(anchored({ quote: 'buyed some bread' }, text), true);
assert.equal(shown[0].quote, 'go to the shop yesterday');
assert.deepEqual(shownIssues({}, text), [], 'no issues is not an error');
const visibleStrengths = shownStrengths(full, text);
assert.equal(visibleStrengths.length, 1, 'a strength must quote words the learner actually wrote');
assert.equal(visibleStrengths[0].quote, 'for my family');
assert.deepEqual(shownStrengths({}, text), [], 'no strengths is not an error');

const html = writingReview(c, full, { language: 'en', text });
for (const fragment of [
  '68',
  'B1',
  'Your meaning comes through clearly.',
  'Yesterday puts this in the past.',
  'for my family',
  'Past tense of irregular verbs',
  c.rubric_task_achievement,
  c.reviewNotOneAnswer,
]) {
  assert.ok(html.includes(fragment), `the review dropped "${fragment}"`);
}
/* The unanchored finding is kept as guidance - it is a real mistake and the
   learner should hear about it - but it is never offered a span to jump to.
   A strength is different: praising words the learner did not write is not
   guidance about anything, so an invented one is still dropped. */
assert.ok(html.includes('not in the learner text'), 'a finding that cannot be located is still said');
assert.equal(
  (html.match(/data-locate=/g) || []).length,
  1,
  'but only the located one offers to be found in the text',
);
assert.ok(!html.includes('This evidence was invented.'), 'invented strength evidence must not reach the page');
assert.equal(
  (html.match(/data-why=/g) || []).length,
  shown.length,
  'every shown issue, and only a shown issue, can be taken further',
);
assert.ok(html.includes('data-registers'), 'register exploration is reachable from the review');
assert.match(html, /inline-size:58%/, 'a dimension is drawn at the value it was given');

// Nothing is inferred. No score means no headline; an unchanged score is not
// movement; a demo evaluator says so.
const bare = writingReview(c, { issues: [] }, { language: 'en', text });
assert.ok(!bare.includes('review-headline'), 'no score is shown when none was returned');
assert.ok(bare.includes(c.noCorrections), 'a review that found nothing has to say so');
assert.ok(
  !writingReview(c, { overall: 68, delta: { overall: 0 }, issues: [] }, {
    language: 'en',
    text,
  }).includes('review-delta'),
  'an unchanged score is not progress',
);
assert.ok(
  !writingReview(c, { overall: 68, delta: {}, issues: [] }, {
    language: 'en',
    text,
  }).includes('review-delta'),
  'a first draft has nothing to be better than',
);
assert.ok(
  writingReview(c, { evaluator: 'fallback-demo', issues: [] }, {
    language: 'en',
    text,
  }).includes(c.demoMeasurement),
  'a demo review is labelled as one',
);
assert.ok(
  !writingReview(c, { dimensions: { grammar: null }, issues: [] }, {
    language: 'en',
    text,
  }).includes('review-bar'),
  'unmeasured stays unmeasured rather than becoming zero',
);
const injected = writingReview(
  c,
  { corrected_text: '<img src=x onerror=alert(1)>', issues: [] },
  { language: 'en', text },
);
assert.ok(!injected.includes('<img'), 'evaluator text is escaped');

// A transient provider failure is actionable; a permanent/unconfigured state
// must not invite a retry that cannot help. Both keep the learner's draft.
const retryableFailure = writingReviewFailure(c, { retryable: true });
assert.ok(retryableFailure.includes(c.reviewFailed));
assert.ok(retryableFailure.includes('data-retry-review'));
const unavailableFailure = writingReviewFailure(c, { retryable: false });
assert.ok(unavailableFailure.includes(c.reviewUnavailable));
assert.ok(!unavailableFailure.includes('data-retry-review'));
for (const ui of ['en', 'zh']) {
  assert.ok(copy[ui].reviewFailed, `${ui}: missing retryable review failure copy`);
  assert.ok(copy[ui].reviewUnavailable, `${ui}: missing unavailable review copy`);
}

/* Revising is where writing is actually learned. `revision_delta()` has always
   worked out which problems went, which stayed, which arrived and which were
   reworked; the surface showed one number. These hold the rendering of it. */
const revised = {
  ...full,
  delta: {
    overall: 6,
    grammar: 8,
    naturalness: -2,
    coherence: 0,
    issues: {
      removed: [{ fragment: 'buyed', mini_rule_vi: 'Irregular past' }],
      persistent: [{ fragment: 'go to the shop yesterday', mini_rule_vi: 'Past simple' }],
      new: [{ fragment: 'for my family' }],
      changed: [{ before: { fragment: 'some bread' }, after: { fragment: 'a loaf of bread' } }],
    },
  },
};
const revisedHtml = writingReview(c, revised, { language: 'en', text });
for (const fragment of [
  c.reviewSinceLast,
  c.reviewFixed,
  c.reviewStill,
  c.reviewArrived,
  c.reviewReworked,
  'buyed',
  'a loaf of bread',
]) {
  assert.ok(revisedHtml.includes(fragment), `the comparison dropped "${fragment}"`);
}
// A score that rose while the same problem persists is a different result from
// one where the problem is gone, so both must be visible, not just the total.
assert.ok(
  revisedHtml.includes("data-tone=\"good\"") && revisedHtml.includes("data-tone=\"watch\""),
  'fixed and persisting problems must be told apart',
);
// Movement is shown where it happened. A dimension that did not move says
// nothing rather than "0".
assert.ok(revisedHtml.includes('+8'), 'a dimension that improved says so');
assert.ok(revisedHtml.includes('-2'), 'a dimension that slipped says so');
assert.equal(
  (revisedHtml.match(/dimension-move/g) || []).length,
  2,
  'only dimensions that actually moved carry a movement',
);
// A first draft has nothing to compare against, and must not imply it does.
assert.ok(
  !html.includes('review-comparison'),
  'a first version shows no comparison',
);
assert.ok(
  !writingReview(c, { ...full, delta: { overall: 6 } }, { language: 'en', text }).includes(
    'review-comparison',
  ),
  'a delta carrying no issue movement renders no comparison shell',
);
assert.ok(
  !writingReview(c, { ...revised, delta: { ...revised.delta, issues: { removed: [], persistent: [], new: [], changed: [] } } }, {
    language: 'en',
    text,
  }).includes('review-comparison'),
  'an empty comparison is not shown as an empty section',
);

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
/* Proficiency is optional guidance, not a prerequisite. `c778005` made the
   request target optional, so the surface must let a learner write and press
   Review with nothing chosen and let the evaluator infer the demonstrated
   band; an unchosen target has to travel as null, never as an empty string. */
assert.ok(
  !/name="target"\s+required/.test(expressionSource),
  'the feedback target must not be a required field',
);
assert.match(
  expressionSource,
  /\[name=target\]'\)\.value\s*\|\|\s*null/,
  'an unchosen target must travel as null so the evaluator infers the level',
);
for (const ui of ['en', 'zh']) {
  for (const key of ['writingTask', 'writingTaskNote', 'chooseTarget', 'reviewSinceLast', 'reviewFixed', 'reviewStill', 'reviewArrived', 'reviewReworked'])
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

// Going deeper from an issue reaches the one shared explanation surface, with
// the learner's own wording and the sentence it sat in.
const expression = read('static/orena/ui/expression.js');
assert.match(
  expression,
  /openUnderstanding\(ctx, \{\s*selection: issue\.quote/,
  'why? asks about the quoted words',
);
assert.match(
  expression,
  /find\(\(part\) => part\.includes\(issue\.quote\)\)/,
  'the sentence travels with it',
);
assert.match(
  expression,
  /openRegisters\(ctx, \{ text, title \}\)/,
  'registers are asked about what the learner wrote',
);
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
