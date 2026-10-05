/* Gate for the Reading Transfer screen's DOM-free logic (design route `rtransfer`, frame 39,
   static/orena/screens/reading-transfer/model.js).

   Two kinds of evidence, so a field the screen reads that the backend does not carry fails here:
   - the real captured payloads (scripts/fixtures/api/reading_article_detail{,.zh}.json,
     reading_library_book_chapter.json for the text; spoken_response.json for the coaching answer)
     feed the model;
   - the request and response shapes are also read out of the backend's own source,
     writing_coach/media_interaction.py - the request model's fields and limits, the keys of the
     response dict and of each grounded item - because one capture cannot show every optional
     shape (the captured answer has no "landed differently" points), and compared with what the
     model sends and reads. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const {
  MODES, COACH_LIMITS, SENTENCE_LIMITS, READABLE_KINDS, modeKeys, paragraphsOf, unitsIn, isWorkableSentence,
  workableSentences, nextIndex, canMoveOn, canCheck, coachRequest, mapCoaching,
} = await import('../static/orena/screens/reading-transfer/model.js');
const { t } = await import('../static/orena/screens/reading-transfer/copy.js');

const fixture = (name) => JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url), 'utf8'));
const backend = readFileSync(new URL('../writing_coach/media_interaction.py', import.meta.url), 'utf8');

// 1. The request contract, from the backend's own model.
const requestModel = backend.match(/class SpokenResponseIn\(BaseModel\):[\s\S]*?(?=\nclass |\n@)/)[0];
const requestFields = [...requestModel.matchAll(/^    (\w+): /gm)].map((match) => match[1]);
assert.deepEqual(requestFields.sort(), ['situation', 'source_language', 'source_text', 'target_language', 'transcript']);
assert.equal(Number(requestModel.match(/transcript: str = Field\(min_length=1, max_length=(\d+)\)/)[1]), COACH_LIMITS.transcript, 'the transcript limit is the backend\'s');
assert.equal(Number(requestModel.match(/situation: str = Field\(default="", max_length=(\d+)\)/)[1]), COACH_LIMITS.situation, 'the situation limit is the backend\'s');
assert.ok(requestModel.includes('extra="forbid"'), 'the model forbids extra fields, so a request must carry exactly its own');
assert.ok(
  /def _validated_source_language[\s\S]*?requested != current[\s\S]*?raise HTTPException\(\s*409/.test(backend),
  'source_language must be the learner\'s current learning language (409 otherwise) - the screen passes it from the learner\'s context, never from the text',
);

// 2. The response contract, from the backend's own return statement and grounded-item builder.
const handler = backend.slice(backend.indexOf('def coach_spoken_response'));
const returned = handler.slice(handler.indexOf('    return {'), handler.indexOf('\n    }\n', handler.indexOf('    return {')));
const responseKeys = [...returned.matchAll(/^        "(\w+)":/gm)].map((match) => match[1]);
for (const key of ['available', 'carried', 'landed_differently', 'another_way', 'next_attempt', 'meaning_preserved', 'missing_idea']) {
  assert.ok(responseKeys.includes(key), `the response carries ${key}`);
}
const grounded = handler.slice(handler.indexOf('def _grounded'), handler.indexOf('carried = _grounded'));
for (const key of ['quote', 'why', 'instead']) assert.ok(grounded.includes(`"${key}"`) || grounded.includes(`item.get("${key}")`), `a grounded item carries ${key}`);

// 3. The request the model builds is exactly that model's fields, and carries the task and sentence.
const request = coachRequest({ answer: '  She could not reach them.  ', mode: 'paraphrase', sentence: 'The grapes were out of reach.', language: 'en', support: 'vi' });
assert.deepEqual(Object.keys(request).sort(), requestFields.sort());
assert.equal(request.transcript, 'She could not reach them.', 'the answer is trimmed');
assert.equal(request.source_language, 'en');
assert.equal(request.target_language, 'vi');
assert.equal(request.source_text, 'The grapes were out of reach.', 'the restated sentence itself goes with it, for the two verdicts of frame 39');
assert.ok(request.situation.includes('The grapes were out of reach.'), 'the coach is told which sentence was worked on');
assert.ok(request.situation.startsWith(MODES.find((mode) => mode.key === 'paraphrase').task));
assert.notEqual(coachRequest({ answer: 'x', mode: 'inference', sentence: 's', language: 'en', support: 'en' }).situation, coachRequest({ answer: 'x', mode: 'context_shift', sentence: 's', language: 'en', support: 'en' }).situation, 'each mode gives the coach its own task');
assert.ok(coachRequest({ answer: 'x', mode: 'paraphrase', sentence: 'w '.repeat(2000), language: 'en', support: 'en' }).situation.length <= COACH_LIMITS.situation, 'a request is shaped to fit, never refused');

// 4. Modes: the frame's three, each with the words a learner reads.
assert.deepEqual(modeKeys(), ['paraphrase', 'inference', 'context_shift']);
for (const [key, chip, prompt] of [['paraphrase', 'modeParaphrase', 'promptParaphrase'], ['inference', 'modeInference', 'promptInference'], ['context_shift', 'modeContextShift', 'promptContextShift']]) {
  assert.ok(MODES.some((mode) => mode.key === key));
  assert.ok(t.has(chip) && t.has(prompt), `${key} has a chip and a prompt`);
  assert.notEqual(t(chip), chip);
  assert.notEqual(t(prompt), prompt);
}
assert.deepEqual([...READABLE_KINDS], ['article', 'book', 'text']);

// 5. Sentences: real English article, real Chinese article, real book chapter.
const en = fixture('reading_article_detail.json');
const enParagraphs = paragraphsOf('article', en);
assert.equal(enParagraphs.length, 2, 'the article body reads as its two paragraphs');
const enSentences = workableSentences(enParagraphs, en.language);
assert.ok(enSentences.length >= 4, 'a real article has sentences to work on');
assert.ok(enSentences[0].startsWith('A famished fox saw'), 'reading order, the first real sentence first');
for (const sentence of enSentences) assert.ok(isWorkableSentence(sentence, 'en'), sentence);
assert.ok(enSentences.some((sentence) => sentence.includes('The grapes are sour')), 'a quoted sentence keeps its closing quote and is not cut in two');
assert.ok(!enSentences.some((sentence) => sentence.trim().length === 0));

const zh = fixture('reading_article_detail.zh.json');
const zhSentences = workableSentences(paragraphsOf('article', zh), zh.language);
assert.ok(zhSentences.length >= 3);
assert.ok(zhSentences[0].startsWith('我冒了严寒'));
for (const sentence of zhSentences) assert.ok(unitsIn(sentence, 'zh') >= SENTENCE_LIMITS.minHan, sentence);
assert.equal(unitsIn('我冒了严寒，回到故乡去。', 'zh'), 10, 'Chinese counts Han characters, not words');
assert.equal(unitsIn('The grapes are sour.', 'en'), 4);
assert.equal(unitsIn('— … —', 'en'), 0, 'punctuation is not a word');

const chapter = fixture('reading_library_book_chapter.json');
const chapterParagraphs = paragraphsOf('book', chapter);
assert.ok(chapterParagraphs.length >= 2);
assert.ok(!chapterParagraphs.some((text) => text.startsWith('CHAPTER I.')), 'a heading block is not a sentence to work on');
assert.ok(workableSentences(chapterParagraphs, chapter.language).length >= 2);

assert.deepEqual(paragraphsOf('text', { text: 'One thought here.\n\nAnother thought is here too.' }), ['One thought here.', 'Another thought is here too.']);
assert.deepEqual(paragraphsOf('article', {}), [], 'no body is no paragraphs, never a throw');
assert.deepEqual(paragraphsOf('text', null), []);

// 6. What is not worth working on is dropped, and nothing is invented to fill the gap.
assert.equal(isWorkableSentence('Yes.', 'en'), false, 'a fragment is not a thought to paraphrase');
assert.equal(isWorkableSentence('', 'en'), false);
assert.equal(isWorkableSentence('word '.repeat(SENTENCE_LIMITS.maxChars), 'en'), false, 'too long to travel inside the coaching request');
assert.equal(isWorkableSentence('是的。', 'zh'), false);
assert.deepEqual(workableSentences(['Yes. No.'], 'en'), []);
assert.deepEqual(workableSentences([], 'en'), []);
assert.deepEqual(workableSentences(null, 'en'), []);

// 7. "Another sentence" moves on in reading order and wraps; it is not offered with nothing to move to.
assert.equal(nextIndex(0, 3), 1);
assert.equal(nextIndex(2, 3), 0);
assert.equal(nextIndex(0, 1), 0);
assert.equal(canMoveOn(1), false);
assert.equal(canMoveOn(2), true);
assert.equal(canMoveOn(0), false);

// 8. Check is offered for a real answer that fits, and not while another step is in flight.
assert.equal(canCheck('', false), false);
assert.equal(canCheck('   ', false), false);
assert.equal(canCheck('She could not reach them.', false), true);
assert.equal(canCheck('She could not reach them.', true), false);
assert.equal(canCheck('x'.repeat(COACH_LIMITS.transcript), false), true);
assert.equal(canCheck('x'.repeat(COACH_LIMITS.transcript + 1), false), false);

// 9. The coaching answer: the two real lists and the one thing to try, each item a real quotation.
const coached = mapCoaching({
  source_language: 'en', target_language: 'vi', transcript: 'x', situation: 'y',
  carried: [{ quote: 'she could not reach them', why: 'It keeps the reason for the fox\'s disappointment.' }],
  landed_differently: [{ quote: 'the grapes were bad', why: 'The text says sour, not bad.', instead: 'the grapes were sour', judgement: 'unnatural' }],
  another_way: 'She gave up because the grapes were out of reach.',
  next_attempt: 'Keep the fox\'s reason in your version.',
  say_again: 'z', available: true, claim: 'spoken_response_coaching_from_transcript',
});
assert.equal(coached.available, true);
assert.deepEqual(coached.carried, [{ quote: 'she could not reach them', why: 'It keeps the reason for the fox\'s disappointment.' }]);
assert.deepEqual(coached.landed, [{ quote: 'the grapes were bad', why: 'The text says sour, not bad.', instead: 'the grapes were sour' }]);
assert.equal(coached.improvement, 'Keep the fox\'s reason in your version.', 'the one thing to try is the frame\'s "one useful improvement"');
// The real captured answer (isolated stack, local model): every key the model reads is in it, its
// request echo matches what coachRequest sends, and the common "only carried points" shape maps to
// a single tile plus the one thing to try.
const real = fixture('spoken_response.json');
for (const key of ['available', 'carried', 'landed_differently', 'another_way', 'next_attempt']) assert.ok(key in real, `the real answer carries ${key}`);
// source_text is the one request field the answer does not echo (the verdicts are its answer to it).
for (const key of Object.keys(request).filter((key) => key !== 'source_text')) assert.ok(key in real, `the real answer echoes ${key}`);
const mappedReal = mapCoaching(real);
assert.equal(mappedReal.available, true);
assert.equal(mappedReal.carried.length, real.carried.length);
assert.ok(mappedReal.carried.every((point) => point.quote && point.why));
assert.deepEqual(mappedReal.landed, [], 'no "landed differently" points is a real, common answer');
assert.equal(mappedReal.improvement, real.next_attempt);
for (const point of mappedReal.carried) assert.ok(real.transcript.includes(point.quote), "every quotation is a real quotation of the learner's own words (the backend drops any that is not)");

// The real captured answer with both lists populated (another room's capture of the same endpoint):
// two tiles, each landed point with its own alternative.
const realBoth = fixture('spoken_response_landed.json');
const mappedBoth = mapCoaching(realBoth);
assert.ok(mappedBoth.carried.length >= 1 && mappedBoth.landed.length >= 1, 'both lists are populated in this capture');
for (const point of mappedBoth.landed) {
  assert.ok(point.quote && point.why && typeof point.instead === 'string', 'a landed point carries quote, why and instead');
  assert.ok(realBoth.transcript.includes(point.quote), 'a landed quotation is the learner\'s own words');
}
assert.equal(mappedBoth.improvement, realBoth.next_attempt);

assert.equal(mapCoaching({ carried: [], landed_differently: [], another_way: 'An alternative.', next_attempt: '' }).improvement, 'An alternative.', 'falls back to the alternative, never to invented text');
assert.equal(mapCoaching({ carried: [{ quote: 'q', why: 'w' }], landed_differently: [], next_attempt: '', another_way: '', available: true }).improvement, '', 'nothing to try is nothing drawn');
const nothing = mapCoaching({ available: false, carried: [], landed_differently: [], another_way: '', next_attempt: '', say_again: '' });
assert.deepEqual(nothing, { available: false, carried: [], landed: [], improvement: '', meaning: '', missing: '' }, 'the honest "nothing to point out" degrade');
assert.deepEqual(mapCoaching(null), { available: false, carried: [], landed: [], improvement: '', meaning: '', missing: '' }, 'no answer never throws');
// Frame 39's verdicts: one of the three, else nothing drawn; the missing idea as given.
assert.deepEqual([mapCoaching({ meaning_preserved: 'partly', missing_idea: '“sour”' }).meaning, mapCoaching({ meaning_preserved: 'partly', missing_idea: '“sour”' }).missing], ['partly', '“sour”']);
assert.equal(mapCoaching({ meaning_preserved: 'great' }).meaning, '');
assert.equal(mapCoaching({ meaning_preserved: 'lost' }).available, true, 'a verdict alone is a result');
assert.deepEqual(mapCoaching({ carried: [{ quote: '', why: 'w' }, { why: 'no quote' }, { quote: 'q' }], landed_differently: 'not a list' }).carried, [], 'an item without both a quotation and a reason is not shown');

// 10. Every string is in all three languages with its layer, and the language-neutral request has no words of a language in it.
for (const key of ['sourceLabel', 'placeholder', 'speak', 'listening', 'transcribing', 'checkLabel', 'checking', 'carriedLabel', 'landedLabel', 'improvementLabel', 'insteadLabel', 'anotherSentence', 'finishLabel', 'backToReading', 'notPrepared', 'coachingError', 'noSentence', 'answerLabel']) {
  assert.ok(t.has(key), key);
}

console.log('test_orena_screen_reading-transfer.mjs: Reading Transfer - real article/chapter sentences (en, zh), the backend\'s own coaching request and response contract, states and limits: PASS');
