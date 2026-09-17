/* The reading room: a passage read in its own scrolling frame, one numbered
   block per paragraph, each paragraph's meaning on demand, and any word a tap
   away from what it means in its sentence.

   Pure rendering and request-shaping contracts for static/orena/ui/reading-room.js
   and the word card in static/orena/ui/understanding.js. The DOM wiring lives in
   encounter.js and is checked in the browser; what can be checked without one is
   checked here - escaping, offsets, request limits and EN/ZH copy. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import {
  ANNOTATE_LIMITS,
  EXPLAIN_LIMITS,
  GLOSS_LIMITS,
  TRANSLATE_BATCH,
  annotationChunks,
  explainBounds,
  paragraphHtml,
  readingFrame,
  readingBlock,
  sentenceAround,
  tokensFromAnnotation,
  translationRequests,
} from '../static/orena/ui/reading-room.js';
import { glossKeepPayload, wordCardBody } from '../static/orena/ui/understanding.js';

const c = copy.en;

/* --- A paragraph's text is always escaped, and keeps the line breaks it wrote --- */
assert.equal(paragraphHtml('a <b>bold</b>\nline'), 'a &lt;b&gt;bold&lt;/b&gt;<br>line');

/* --- Words become tap targets at exactly their offsets --- */
{
  const text = 'I like books.';
  const html = paragraphHtml(text, [
    { start: 2, end: 6, pos: 'verb' },
    { start: 7, end: 12, pos: 'noun' },
  ]);
  assert.equal(
    html,
    'I <span class="reading-word" data-start="2" data-end="6" data-pos="verb">like</span> <span class="reading-word" data-start="7" data-end="12" data-pos="noun">books</span>.',
  );
}

/* --- Evidence from a question is marked without losing the words around it,
       even when the mark starts inside a word --- */
{
  const text = 'I like books.';
  const html = paragraphHtml(text, [{ start: 7, end: 12, pos: 'noun' }], { start: 9, end: 13 });
  assert.match(html, /^I like <span class="reading-word" data-start="7" data-end="12" data-pos="noun">bo<\/span><mark>/);
  assert.match(html, /<mark><span class="reading-word" data-start="7" data-end="12" data-pos="noun">oks<\/span>\.<\/mark>$/);
  assert.equal(paragraphHtml('A b c', [], { start: 2, end: 3 }), 'A <mark>b</mark> c');
}

/* --- Annotation offsets are Python code points; the page indexes JS strings --- */
{
  const chunk = '😀 like it';
  const result = {
    text: chunk,
    annotations: [
      { fragment: 'like', start: 2, end: 6, pos: 'verb' },
      { fragment: 'it', start: 7, end: 9, pos: 'pronoun' },
    ],
  };
  const tokens = tokensFromAnnotation(chunk, 10, result);
  assert.deepEqual(tokens, [
    { start: 13, end: 17, pos: 'verb' },
    { start: 18, end: 20, pos: 'pronoun' },
  ]);
  // An answer about different text is not an answer about this chunk.
  assert.deepEqual(tokensFromAnnotation(chunk, 0, { ...result, text: 'other' }), []);
  // A fragment the text does not contain at its offsets is dropped, not trusted.
  assert.deepEqual(
    tokensFromAnnotation(chunk, 0, { text: chunk, annotations: [{ fragment: 'nope', start: 2, end: 6, pos: 'verb' }] }),
    [],
  );
}

/* --- Annotation requests stay inside what the endpoint accepts, and their
       offsets still point into the paragraph --- */
{
  const sentence = 'This sentence is long enough to matter. ';
  const long = sentence.repeat(60);
  const chunks = annotationChunks(long, 'en');
  assert.ok(chunks.length > 1);
  for (const chunk of chunks) {
    assert.ok(chunk.text.length <= ANNOTATE_LIMITS.en, 'an English chunk fits one annotate call');
    assert.equal(long.slice(chunk.start, chunk.start + chunk.text.length), chunk.text);
    assert.equal(chunk.text, chunk.text.trim());
  }
  const zh = '我今天在学校学习中文，也读了一本很有意思的书。'.repeat(30);
  for (const chunk of annotationChunks(zh, 'zh')) {
    assert.ok(chunk.text.length <= ANNOTATE_LIMITS.zh, 'a Chinese chunk stays under the token cap');
    assert.equal(zh.slice(chunk.start, chunk.start + chunk.text.length), chunk.text);
  }
  assert.deepEqual(annotationChunks('   ', 'en'), []);
}

/* --- A word's meaning is asked about in its own sentence --- */
{
  const text = 'The wind blew. The traveler held his cloak tighter! Then the sun shone.';
  const start = text.indexOf('cloak');
  const context = sentenceAround(text, start, start + 5);
  assert.equal(context, 'The traveler held his cloak tighter!');
  const zh = '北风吹得很猛。旅人把斗篷裹得更紧了！后来太阳出来了。';
  const at = zh.indexOf('斗篷');
  assert.equal(sentenceAround(zh, at, at + 2), '旅人把斗篷裹得更紧了！');
  const huge = `${'word '.repeat(400)}target ${'word '.repeat(400)}`;
  const t = huge.indexOf('target');
  const bounded = sentenceAround(huge, t, t + 6);
  assert.ok(bounded.length <= GLOSS_LIMITS.context);
  assert.ok(bounded.includes('target'), 'the selection is always inside its context');
}

/* --- Explaining a paragraph never sends more than the explanation accepts --- */
{
  assert.deepEqual(explainBounds('Short.'), { selection: 'Short.', context: 'Short.' });
  const long = 'A sentence that goes on for a while. '.repeat(120);
  const bounds = explainBounds(long);
  assert.ok(bounds.selection.length <= EXPLAIN_LIMITS.selection);
  assert.ok(bounds.context.length <= EXPLAIN_LIMITS.context);
  assert.ok(bounds.context.includes(bounds.selection));
}

/* --- Meaning is requested in turns a provider batch can hold --- */
{
  const paragraphs = Array.from({ length: 60 }, (_, i) => `Paragraph ${i}.`);
  const requests = translationRequests(paragraphs, paragraphs.map((_, i) => i));
  assert.ok(requests.every((r) => r.segments.length <= TRANSLATE_BATCH.segments));
  assert.deepEqual(requests.flatMap((r) => r.indices), paragraphs.map((_, i) => i));
  assert.deepEqual(requests[0].segments[3], { segment_id: 'p3', text: 'Paragraph 3.' });
  const big = ['x'.repeat(3000), 'y'.repeat(3000), 'z'.repeat(10)];
  const split = translationRequests(big, [0, 1, 2]);
  assert.ok(split.every((r) => r.segments.reduce((n, s) => n + s.text.length, 0) <= TRANSLATE_BATCH.chars || r.segments.length === 1));
}

/* --- One block per paragraph, numbered, with its own tools --- */
const baseBlock = {
  paragraph: 'The <wind> blew.',
  tokens: [],
  mark: null,
  language: 'en',
  support: 'vi',
  translatable: true,
  open: false,
  translation: undefined,
};
{
  const html = readingBlock(c, 2, baseBlock);
  assert.match(html, /data-block="2"/);
  assert.match(html, /class="reading-block__number" aria-hidden="true">3</);
  assert.match(html, /<p class="reading-block__text" data-text="2" lang="en">The &lt;wind&gt; blew\.<\/p>/);
  assert.match(html, /data-translate="2" aria-pressed="false"/);
  assert.match(html, /data-explain="2"/);
  assert.doesNotMatch(html, /data-meaning=/, 'a closed paragraph shows no meaning');
  // Reading in the support language: no translation offered at all.
  assert.doesNotMatch(readingBlock(c, 0, { ...baseBlock, translatable: false }), /data-translate=/);
}
{
  const loading = readingBlock(c, 0, { ...baseBlock, open: true, translation: { state: 'loading' } });
  assert.match(loading, /data-meaning="0"[^>]*data-state="loading"/);
  assert.match(loading, new RegExp(c.readingTranslating));
  assert.match(loading, /aria-pressed="true"/);

  const ready = readingBlock(c, 0, {
    ...baseBlock,
    open: true,
    translation: { state: 'ready', text: 'Gió <thổi>.' },
  });
  assert.match(ready, /<p class="reading-block__meaning" data-meaning="0" lang="vi">/);
  assert.match(ready, /Gió &lt;thổi&gt;\./);
  assert.match(ready, new RegExp(`<span class="sr-only">${c.readingTranslationLabel}: </span>`));

  const failed = readingBlock(c, 0, { ...baseBlock, open: true, translation: { state: 'unavailable' } });
  assert.match(failed, /data-state="unavailable"/);
  assert.match(failed, /data-retry-translate="0"/);
  // Original text is never shown where a translation should be.
  assert.doesNotMatch(failed, /lang="vi">The/);

  const tooLarge = readingBlock(c, 0, { ...baseBlock, open: true, translation: { state: 'too_large' } });
  assert.match(tooLarge, new RegExp(c.readingTranslationTooLarge));
  assert.doesNotMatch(tooLarge, /data-retry-translate/, 'retrying cannot make a paragraph shorter');
}

/* --- The frame: its own scrolling region, a position, and the room's own controls --- */
{
  const html = readingFrame(c, {
    title: 'Chapter <1>',
    blocks: '<div class="reading-block"></div>',
    after: '',
    total: 12,
    tools: '<label data-reading-all-meaning></label>',
    dialogue: false,
  });
  assert.match(html, /class="reading-frame"/);
  assert.match(html, /data-reading-scroll tabindex="0" role="region" aria-label="Chapter &lt;1&gt;"/);
  assert.match(html, /data-reading-position[^>]*>1 \/ 12</);
  assert.match(html, /class="reading-frame__bar"[\s\S]*data-reading-all-meaning[\s\S]*data-reading-scroll/);
  assert.match(html, /<article class="passage">/);
  const plain = readingFrame(c, { title: 'T', blocks: '', after: '', total: 1, tools: '', dialogue: true });
  assert.match(plain, /<article class="passage dialogue">/);
}

/* --- The word card says what it knows, and never invents the rest --- */
{
  const loading = wordCardBody(c, { selection: 'cloak', language: 'en', support: 'vi', state: 'loading' });
  assert.match(loading, /lang="en">cloak</);
  assert.match(loading, new RegExp(c.wordCardLoading));
  assert.match(loading, /data-word-keep/);
  assert.match(loading, /data-word-more/);

  const ready = wordCardBody(c, {
    selection: 'cloaks',
    language: 'en',
    support: 'vi',
    state: 'ready',
    result: { meaning: 'áo <choàng>', base_form: 'cloak', part_of_speech: 'noun', pronunciation: '/kləʊk/' },
  });
  assert.match(ready, /lang="vi">áo &lt;choàng&gt;</);
  assert.match(ready, /\/kləʊk\//);
  assert.match(ready, new RegExp(c.pos_noun));
  assert.match(ready, />cloak</, 'the dictionary form is shown when it differs');

  const unavailable = wordCardBody(c, {
    selection: '学校',
    language: 'zh',
    support: 'vi',
    state: 'unavailable',
    result: { meaning: '', base_form: '学校', part_of_speech: 'noun', pronunciation: 'xué xiào' },
  });
  assert.match(unavailable, new RegExp(c.wordCardUnavailable));
  assert.match(unavailable, /xué xiào/, 'what is known locally still helps');
  assert.doesNotMatch(unavailable, /lang="vi">学校/, 'the word itself is never passed off as its meaning');
  assert.doesNotMatch(unavailable, /data-word-retry/, 'a provider that is not there is not worth retrying');

  // A request that failed on the way is different news from one that has no answer.
  const failed = wordCardBody(c, { selection: 'cloak', language: 'en', support: 'vi', state: 'failed' });
  assert.match(failed, new RegExp(c.wordCardFailed));
  assert.match(failed, /data-word-retry/);
  assert.match(failed, /data-word-keep/, 'the word can still be kept without its meaning');
}

/* --- Keeping a word keeps where it was met --- */
assert.deepEqual(
  glossKeepPayload({
    selection: 'cloaks',
    result: { meaning: 'áo choàng', base_form: 'cloak', part_of_speech: 'noun', pronunciation: '/kləʊk/' },
    context: 'He held his cloaks.',
    title: 'Chapter 1',
  }),
  {
    word: 'cloaks',
    phonetic: '/kləʊk/',
    part_of_speech: 'noun',
    definition: 'áo choàng',
    source_kind: 'reading',
    source_fragment: 'He held his cloaks.',
    focus_note: 'Chapter 1',
  },
);

/* --- EN and ZH both carry every word the room says --- */
const keys = [
  'readingTranslate',
  'readingHideTranslation',
  'readingExplain',
  'readingShowAllMeaning',
  'readingTranslating',
  'readingTranslationUnavailable',
  'readingTranslationTooLarge',
  'readingTranslationLabel',
  'readingParagraph',
  'readingPosition',
  'readingWordHint',
  'wordCardLoading',
  'wordCardUnavailable',
  'wordCardFailed',
  'wordCardMore',
  'wordCardKeep',
  'wordCardBaseForm',
];
const partsOfSpeech = ['noun', 'verb', 'adjective', 'adverb', 'pronoun', 'determiner', 'preposition', 'conjunction', 'numeral', 'particle', 'auxiliary', 'interjection', 'classifier', 'proper_noun', 'other'];
for (const ui of ['en', 'zh']) {
  for (const key of [...keys, ...partsOfSpeech.map((pos) => `pos_${pos}`)])
    assert.ok(copy[ui][key], `${ui}: missing ${key}`);
}
assert.notEqual(copy.en.readingTranslate, copy.zh.readingTranslate);

/* --- The encounter uses the room and the shared surfaces, not a copy of them --- */
const encounter = readFileSync('static/orena/ui/encounter.js', 'utf8');
assert.match(encounter, /from '\.\/reading-room\.js'/);
assert.match(encounter, /openWordCard\(/, 'a word opens the shared word card');
assert.match(encounter, /openUnderstanding\(ctx, \{/, 'explaining a paragraph opens the one understanding surface');
assert.match(encounter, /api\.readingTranslate\(/);
assert.match(encounter, /api\.annotateMediaText\(/, 'words are found by the one shared tagger');
assert.match(
  encounter,
  /followToggle\('meaning-toggle', 'data-reading-all-meaning'/,
  'reading shows every meaning with the same switch Listening uses',
);
const api = readFileSync('static/orena/infrastructure/api.js', 'utf8');
assert.match(api, /readingTranslate:\(payload\)=>request\('\/api\/reading\/translate'/);
assert.match(api, /contextualGloss:\(payload\)=>request\('\/api\/dictionary\/gloss'/);

console.log('Reading room: frame, paragraph blocks, meaning on demand, word card, EN/ZH PASS');
