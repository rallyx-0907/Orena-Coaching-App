/* Gate for Respond to Content's pure data mapping (static/orena/screens/respond/model.js), frame
   45, D-091. Imports only the DOM-free module (plus the shared, non-screen `sentenceSpans` from
   product/reader-text.js, the same import screen.js itself makes).

   `sourceLinesFromSegments` is exercised against the real captured
   `GET /api/listening/library/{lessonId}` payload (scripts/fixtures/api/listening_library_lesson.
   en.json) and `sourceLinesFromText` against the real captured
   `GET /api/reading/articles/{id}` payload (scripts/fixtures/api/reading_article_detail.json), so a
   field this module reads that those captures do not carry fails this gate.

   No fixture exists for `POST /api/evaluate`'s create response (this sandbox has no AI provider
   key, so the route always fails here - see the brief's "build it from the serializer" allowance,
   the same situation scripts/test_orena_screen_react.mjs documents for `spoken-response`).
   `mapFeedback`'s test data below is built field-for-field from `_issue_envelope`/
   `result["issues"]`/`result["next_actions"]` in writing_coach/writing_evaluation.py and
   `_run_review`'s own `return {...}` in app.py, not shipped or invented data. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { sentenceSpans } from '../static/orena/product/reader-text.js';
import {
  parseContentId, respondVariantFor, sourceLinesFromText, sourceLinesFromSegments,
  wordCountOf, canGetFeedback, mapFeedback,
} from '../static/orena/screens/respond/model.js';

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url)));
}

/* --- parseContentId: screens/content/model.js's own "<kind>:<id>" scheme, book's own
   "<bookId>:<chapterId>" tail - byte-identical to screens/discussion/model.js's version, which this
   module intentionally duplicates (surface brief §2: a screen's own model.js is private to it) --- */
{
  assert.deepEqual(parseContentId('article:en-abc'), { kind: 'article', id: 'en-abc' });
  assert.deepEqual(parseContentId('media:en-science-cosmic-calendar'), { kind: 'media', id: 'en-science-cosmic-calendar' });
  assert.deepEqual(parseContentId('book:b1:c2'), { kind: 'book', id: 'b1', chapterId: 'c2' });
  assert.deepEqual(parseContentId('book:b1'), { kind: 'book', id: 'b1', chapterId: '' });
  assert.deepEqual(parseContentId('text:xyz'), { kind: 'text', id: 'xyz' });
  assert.deepEqual(parseContentId(''), { kind: '', id: '' });
  assert.deepEqual(parseContentId(null), { kind: '', id: '' });
}

/* --- respondVariantFor: media/upload get the frame's media prompt copy, everything else (article,
   book, a learner's own text) gets the reading variant --- */
{
  assert.equal(respondVariantFor('media'), 'media');
  assert.equal(respondVariantFor('upload'), 'media');
  assert.equal(respondVariantFor('article'), 'reading');
  assert.equal(respondVariantFor('book'), 'reading');
  assert.equal(respondVariantFor('text'), 'reading');
  assert.equal(respondVariantFor(''), 'reading', 'an unrecognised kind never throws - it degrades to the reading variant');
}

/* --- sourceLinesFromSegments: the real EN transcript's own segments, read as lines directly --- */
{
  const en = fixture('listening_library_lesson.en.json');
  const segs = en.transcript.segments;
  const lines = sourceLinesFromSegments(segs, 4);
  assert.equal(lines.length, Math.min(4, segs.length));
  assert.equal(lines[0], segs[0].original_text);
  assert.deepEqual(sourceLinesFromSegments([], 4), []);
  assert.deepEqual(sourceLinesFromSegments(null, 4), [], 'a missing transcript never throws');
}

/* --- sourceLinesFromText: the real article body, sentence-split, bounded to `max`, never an
   invented excerpt --- */
{
  const article = fixture('reading_article_detail.json');
  const lines = sourceLinesFromText(sentenceSpans, article.body, 4);
  assert.ok(lines.length > 0, 'the real article body really has at least one sentence');
  assert.ok(lines.length <= 4);
  assert.ok(article.body.includes(lines[0]), 'the first line is really lifted from the real body, not invented');
  assert.deepEqual(sourceLinesFromText(sentenceSpans, '', 4), []);
  assert.deepEqual(sourceLinesFromText(sentenceSpans, null, 4), []);
}

/* --- wordCountOf: real English + real Chinese counts (Intl.Segmenter word-like runs) --- */
{
  assert.equal(wordCountOf('I go to the market', 'en'), 5);
  assert.equal(wordCountOf('', 'en'), 0);
  assert.equal(wordCountOf('   ', 'en'), 0);
  assert.ok(wordCountOf('我今天去市场买水果', 'zh') > 0, 'Chinese text segments into a real positive count, never a fallback whitespace split of 1');
}

/* --- canGetFeedback: the server's own real floor (the learning language's own minimum,
   writing_coach/writing_limits.py MINIMUM_BY_LANGUAGE) and, when a measurer is given, its real
   ceiling too (the same measureWriting() screen.js passes in) --- */
{
  assert.equal(canGetFeedback('short'), false);
  assert.equal(canGetFeedback('this is definitely long enough'), true);
  assert.equal(canGetFeedback('   '), false);
  assert.equal(canGetFeedback(''), false);
  const withinLimits = (v) => ({ withinLimits: v.length <= 20 });
  assert.equal(canGetFeedback('this is definitely long enough', withinLimits), false, 'over the given measurer\'s ceiling: disabled, never silently ignored');
  assert.equal(canGetFeedback('short but fits', withinLimits), true);

  // The floor is per learning language, not ten code points.
  assert.equal(canGetFeedback('我是学生。', undefined, 'zh'), true, 'an HSK 1 sentence of five characters is an attempt');
  assert.equal(canGetFeedback('你好。', undefined, 'zh'), true);
  assert.equal(canGetFeedback('好', undefined, 'zh'), false, 'one Han character is not');
  assert.equal(canGetFeedback('。。。。。。。。。。', undefined, 'zh'), false, 'punctuation is not writing');
  assert.equal(canGetFeedback('Hi Bob.', undefined, 'en'), true, 'seven characters, two words');
  assert.equal(canGetFeedback('Hello', undefined, 'en'), false);
  assert.equal(canGetFeedback('          ', undefined, 'en'), false, 'ten spaces are not writing');
  assert.equal(canGetFeedback('Hi Bob.', undefined, ''), true, 'a request with no known language uses the stated default');
  assert.equal(canGetFeedback('我是学生。', undefined, 'en'), false, 'the floor follows the language the request is made in, not the script typed');
  assert.equal(canGetFeedback('我是学生。', withinLimits, 'zh'), true, 'and the ceiling is asked as well');
  assert.equal(canGetFeedback('我是学生。'.repeat(5), withinLimits, 'zh'), false);
}

/* --- mapFeedback on the REAL captured create response: every field the Result state draws is
   really there --- */
{
  const real = fixture('essay_evaluate.json');
  const mapped = mapFeedback(real);
  assert.equal(mapped.id, real.id);
  assert.equal(mapped.overall, Math.round(real.overall));
  assert.ok(mapped.issues.length >= 1, 'the real evaluation found something to fix');
  assert.equal(mapped.issues.length, real.issues.filter((item) => item.quote).length);
  for (const issue of mapped.issues) assert.ok(issue.quote && issue.suggestion && issue.why, 'each fix has the line, its correction and the reason');
  assert.equal(mapped.nextStep, real.next_actions[0]);
}

/* --- mapFeedback: the real POST /api/evaluate create-response shape, per
   writing_coach/writing_evaluation.py's own `_issue_envelope`/`result["issues"]`/
   `result["next_actions"]` and app.py `_run_review`'s own return --- */
{
  const raw = {
    id: 4821,
    series_id: 4821,
    revision_no: 1,
    overall: 71.4,
    app_cefr: 'B1',
    evaluator: 'gemini-3.5-flash-lite',
    issues: [
      { id: 'e1', category: 'grammar', priority: 'high', span: { start: 0, end: 5 }, quote: 'I go', why: 'Past time needs past tense.', how: 'Use the -ed form or the irregular past.', suggestion: 'I went', examples: [] },
      { id: 'e2', category: 'vocabulary', priority: 'medium', span: { start: 10, end: 15 }, quote: 'a lot of', why: 'A more specific quantity reads more naturally here.', how: 'Name the amount when you know it.', suggestion: 'several', examples: [] },
    ],
    next_actions: ['Mark every past action with "-ed" or its irregular form before your next attempt.'],
  };
  const mapped = mapFeedback(raw);
  assert.equal(mapped.id, 4821);
  assert.equal(mapped.overall, 71);
  assert.equal(mapped.issues.length, 2);
  assert.deepEqual(mapped.issues[0], { quote: 'I go', suggestion: 'I went', why: 'Past time needs past tense.' });
  assert.equal(mapped.nextStep, raw.next_actions[0]);
}

/* --- mapFeedback: the honest degrade - no issues, no next step, never fabricated (rule 40) --- */
{
  const mapped = mapFeedback({ id: 5, overall: 88, issues: [], next_actions: [] });
  assert.deepEqual(mapped.issues, []);
  assert.equal(mapped.nextStep, '');
  assert.equal(mapped.overall, 88);
}

/* --- mapFeedback: a null/undefined response (network error) never throws --- */
{
  const mapped = mapFeedback(null);
  assert.equal(mapped.id, null);
  assert.equal(mapped.overall, null);
  assert.deepEqual(mapped.issues, []);
  assert.equal(mapped.nextStep, '');
}

console.log('test_orena_screen_respond.mjs: Respond to Content data mapping - real GET /api/listening/library/{id} + GET /api/reading/articles/{id} captures, POST /api/evaluate serializer shape, rule 40 throughout: PASS');
