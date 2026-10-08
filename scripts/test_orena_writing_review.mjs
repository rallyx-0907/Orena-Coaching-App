// Writing review contracts the learner UI stands on. The evaluator has always returned a full review;
// these assertions hold the parts that make it trustworthy: the dimensions the Writing screen draws
// are dimensions the evaluator scores, every finding category it can return is readable, a fix is
// applied to the learner's own words or not at all, and a finding is marked in the draft only where
// its words are found exactly once. The screen's own mapping is scripts/test_orena_screen_writing.mjs.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { CATEGORY_IDS, dimensionRows } from '../static/orena/screens/writing/model.js';
import { applyFix } from '../static/orena/product/revision.js';
import { issueMarks, marksIn, markedHtml } from '../static/orena/product/draft-marks.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

// The dimensions the UI draws are a subset of the rubric the evaluator scores.
const benchmark = read('writing_coach/writing_evaluation_benchmark.py');
const declared = [
  ...benchmark
    .split('RUBRIC_DIMENSIONS = (')[1]
    .split(')')[0]
    .matchAll(/"([a-z_]+)"/g),
].map((m) => m[1]);
const drawn = dimensionRows({ grammar: 50, vocabulary: 50, coherence: 50, naturalness: 50 }, [], '').map((row) => row.key);
assert.equal(drawn.length, 4, 'the screen draws the four dimensions');
for (const key of drawn) assert.ok(declared.includes(key), `${key} is a scored dimension`);

// Every finding category either language's evaluator can return is one the screen labels.
const profileCategories = (path) => [
  ...read(path)
    .split('ERROR_CATEGORIES = (')[1]
    .split(')')[0]
    .matchAll(/"([a-z_]+)"/g),
].map((match) => match[1]);
for (const key of new Set([
  ...profileCategories('writing_coach/languages/english/profile.py'),
  ...profileCategories('writing_coach/languages/chinese/profile.py'),
])) {
  if (key === 'other') continue; // names nothing
  assert.ok(CATEGORY_IDS.includes(key), `the Writing screen has no label for feedback category "${key}"`);
}

// Applying replaces the first occurrence of the learner's own words, or nothing.
const issues = [
  { id: 'a', fragment: 'ønsker å informere deg om', correction: 'må bare fortelle deg', kind: 'register' },
  { id: 'b', fragment: 'et kafé', correction: 'en kafé', kind: 'grammar' },
];
const draft = 'Jeg ønsker å informere deg om noe. På et kafé.';
const fixed = applyFix(draft, issues[0]);
assert.equal(fixed.text, 'Jeg må bare fortelle deg noe. På et kafé.');
assert.equal(fixed.text.slice(fixed.start, fixed.end), 'må bare fortelle deg');
assert.equal(applyFix('nothing to see', issues[0]), null, 'words that are not in the draft are not replaced');
assert.equal(applyFix('et kafé og et kafé', issues[1]), null, 'a repeated quotation leaves the learner to choose');
assert.equal(applyFix('et kafé', { ...issues[1], correction: 'x'.repeat(12001) }), null, 'the writing limit still holds');

// Register exploration is a comparison, not a rewrite button: the server route is mounted on the
// router the app includes, invents no authority and names no version the correct one.
const server = read('writing_coach/media_interaction.py');
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

// The review, the revision and a finding's sentence are read from their contracts.
const api = read('static/orena/infrastructure/api.js');
for (const contract of ['essayReview', 'essayRevision', 'sentenceSheet']) assert.match(api, new RegExp(`${contract}:`), `${contract} is a client contract`);

/* --- The findings marked in the draft are earned ---------------------------------------------------- */
const draftText = 'Jeg jobber på et kafé nå. Sjefen min er hyggelig, han hjelper meg. Jeg jobber på et kafé.';
const finding = (id, fragment, kind = 'grammar') => ({ id, fragment, correction: 'x', kind });
{
  const found = marksIn(draftText, issueMarks([finding('a', 'hyggelig, han', 'punctuation'), finding('b', 'ikke der'), finding('c', 'på et kafé')]));
  assert.deepEqual(found.map((mark) => mark.id), ['a'], 'a finding whose words are absent, or occur twice, marks nothing');
  assert.equal(found[0].tone, 'info', 'punctuation is marked in blue, everything else in amber');
  const overlapping = marksIn('one two three', issueMarks([finding('a', 'one two'), finding('b', 'two three')]));
  assert.deepEqual(overlapping.map((mark) => mark.id), ['a'], 'marks never overlap: the earlier finding keeps its words');
  const html = markedHtml('a <b> & c', issueMarks([finding('a', '<b>')]));
  assert.equal(html, 'a <mark data-tone="warm">&lt;b&gt;</mark> &amp; c', "the learner's words are escaped, never taken for markup");
}

console.log('Orena writing review: rubric and category parity, fixes on the learner own words, earned marks: PASS');
