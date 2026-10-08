/* Gate for React / Reuse's pure data mapping (static/orena/screens/react/model.js), frame 33,
   D-091. Imports only the DOM-free module.

   `usefulPhrase` and `buildUnderstandCheck` are exercised against the real captured
   `GET /api/listening/library/{lessonId}` payload (scripts/fixtures/api/listening_library_lesson.
   {en,zh}.json), so a field this module reads that those captures do not carry fails this gate.

   `mapCoaching` is exercised against the REAL captured answer of
   `POST /api/dictionary/spoken-response` (scripts/fixtures/api/spoken_response.en.json, a live call
   against the isolated app), plus one block built field-for-field from `coach_spoken_response`'s own
   `return {...}` (writing_coach/media_interaction.py) for the shapes a live call cannot be made to
   produce on demand (an empty answer). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { usefulPhrase, buildUnderstandCheck, mapCoaching, phraseReused, resultTiles, waveBars, promptKey } from '../static/orena/screens/react/model.js';

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url)));
}

const en = fixture('listening_library_lesson.en.json');
const zh = fixture('listening_library_lesson.zh.json');

/* --- usefulPhrase: the real EN catalogue vocabulary matched into a real segment --- */
{
  const segs = en.transcript.segments;
  const galaxySeg = segs.find((s) => s.original_text.toLowerCase().includes('galax'));
  if (galaxySeg) {
    assert.equal(usefulPhrase(en.catalog.vocabulary, galaxySeg.original_text), 'galaxy');
  }
  assert.equal(usefulPhrase(['extinct'], 'nothing relevant here'), null, 'no catalogue word present: no invented phrase (rule 40)');
  assert.equal(usefulPhrase([], en.transcript.segments[0].original_text), null, 'an empty catalogue never throws');
}

/* --- usefulPhrase: the real ZH catalogue, character substrings need no stemming --- */
{
  const [term] = zh.catalog.vocabulary;
  const seg = zh.transcript.segments.find((s) => s.original_text.includes(term));
  if (seg) assert.equal(usefulPhrase(zh.catalog.vocabulary, seg.original_text), term);
}

/* --- buildUnderstandCheck: real segments, no real translations in this capture -> null,
   never a generated wrong answer (rule 40) --- */
{
  const segs = en.transcript.segments;
  assert.equal(en.translations.length, 0, 'this capture really has no translations - the check below is the honest degrade, not a stale assumption');
  const noMeaning = () => '';
  assert.equal(buildUnderstandCheck(segs, segs[0].segment_id, noMeaning, 0), null);
}

/* --- buildUnderstandCheck: with enough real distinct meanings, a real 3-option check --- */
{
  const segs = [
    { segment_id: 'a' }, { segment_id: 'b' }, { segment_id: 'c' }, { segment_id: 'd' },
  ];
  const meanings = { a: 'Nghĩa A', b: 'Nghĩa B', c: 'Nghĩa C', d: '' };
  const meaningOf = (id) => meanings[id] || '';
  const check = buildUnderstandCheck(segs, 'a', meaningOf, 0);
  assert.ok(check, 'three segments have real distinct meanings: a check is built');
  assert.equal(check.options.length, 3);
  assert.ok(check.options.includes('Nghĩa A'));
  assert.equal(check.options[check.correctIndex], 'Nghĩa A');
  // A segment with an empty own meaning never builds a check for itself.
  assert.equal(buildUnderstandCheck(segs, 'd', meaningOf, 0), null);
  // `order` rotates the correct answer's slot deterministically (same inputs -> same output).
  const again = buildUnderstandCheck(segs, 'a', meaningOf, 0);
  assert.deepEqual(again, check);
  const rotated = buildUnderstandCheck(segs, 'a', meaningOf, 1);
  assert.notDeepEqual(rotated.options, check.options, 'a different order really rotates the option slots');
}

/* --- buildUnderstandCheck: only one other real meaning is not enough (rule 40: never one
   fabricated distractor) --- */
{
  const segs = [{ segment_id: 'a' }, { segment_id: 'b' }, { segment_id: 'c' }];
  const meanings = { a: 'Nghĩa A', b: 'Nghĩa B', c: '' };
  assert.equal(buildUnderstandCheck(segs, 'a', (id) => meanings[id] || '', 0), null);
}

/* --- mapCoaching on the REAL captured spoken-response answer: every field the Result step draws is
   really there, in the shape the model reads --- */
{
  const real = fixture('spoken_response.en.json');
  assert.equal(real.available, true);
  const mapped = mapCoaching(real);
  assert.equal(mapped.available, true);
  assert.ok(mapped.carried.length >= 1 && mapped.carried.every((c) => c.quote && c.why), 'carried: quote + why');
  assert.ok(mapped.landedDifferently.length >= 1 && mapped.landedDifferently.every((c) => c.quote && c.why && 'instead' in c), 'landed_differently: quote + why + instead');
  assert.ok(mapped.anotherWay.length > 0 && mapped.nextAttempt.length > 0 && mapped.sayAgain.length > 0);
  for (const item of [...mapped.carried, ...mapped.landedDifferently]) assert.ok(real.transcript.includes(item.quote), 'coaching only ever quotes what was said');
}

/* --- phraseReused: a fact the learner's own words settle; null (the tile's 0) when the line has no phrase --- */
{
  assert.equal(phraseReused('galaxy', 'Our galaxy is big.'), true);
  assert.equal(phraseReused('galaxy', 'There are many galaxies.'), true, 'stem-tolerant, like usefulPhrase');
  assert.equal(phraseReused('galaxy', 'I like stars.'), false);
  assert.equal(phraseReused('', 'anything'), null);
  assert.equal(phraseReused(null, 'anything'), null);
  assert.equal(phraseReused('输入', '我要输入一个词'), true, 'Chinese needs no stemming');
}

/* --- waveBars / promptKey: the frame's own arithmetic; the prompt alternates per New context --- */
{
  const bars = waveBars(32, 5);
  assert.equal(bars.length, 32);
  assert.ok(bars.every((b) => b.height >= 30 && b.height <= 100 && b.delay >= 0 && b.delay < 600));
  assert.deepEqual(waveBars(32, 5), bars, 'deterministic - a re-render never reshuffles the bars');
  assert.equal(promptKey(true, 0), 'promptWithPhrase');
  assert.equal(promptKey(true, 1), 'promptWithPhrase2');
  assert.equal(promptKey(true, 2), 'promptWithPhrase');
  assert.equal(promptKey(false, 1), 'promptGeneric2');
}

/* --- mapCoaching: the real `available`/carried/landed_differently shape, per
   writing_coach/media_interaction.py's own `_spoken_schema()` + `coach_spoken_response` return --- */
{
  const raw = {
    source_language: 'en',
    target_language: 'vi',
    transcript: 'I go to the market yesterday and I buy some fruit',
    situation: 'Use "extinct" in a new sentence of your own.',
    carried: [{ quote: 'I go to the market', why: 'Clear, simple structure that carries the idea.' }],
    landed_differently: [{ quote: 'I go', why: 'Past time needs past tense.', instead: 'I went', judgement: 'error' }],
    another_way: 'I went to the market yesterday and bought some fruit.',
    next_attempt: 'Try marking every past action with "-ed" or its irregular form.',
    say_again: 'I went to the market yesterday and bought some fruit.',
    available: true,
  };
  const mapped = mapCoaching(raw);
  assert.equal(mapped.available, true);
  assert.deepEqual(mapped.carried, raw.carried);
  assert.deepEqual(mapped.landedDifferently, raw.landed_differently);
  assert.equal(mapped.anotherWay, raw.another_way);
  assert.equal(mapped.nextAttempt, raw.next_attempt);
  assert.equal(mapped.sayAgain, raw.say_again);
}

/* --- mapCoaching: the honest `available:false` degrade (no AI provider, or nothing grounded
   found) - never rendered as if it were real coaching (rule 40) --- */
{
  const mapped = mapCoaching({ available: false, carried: [], landed_differently: [], another_way: '', next_attempt: '', say_again: '' });
  assert.equal(mapped.available, false);
  assert.deepEqual(mapped.carried, []);
  assert.deepEqual(mapped.landedDifferently, []);
}

/* --- mapCoaching: a null/undefined response (network error) never throws --- */
{
  const mapped = mapCoaching(null);
  assert.equal(mapped.available, false);
  assert.deepEqual(mapped.carried, []);
  assert.deepEqual(mapped.landedDifferently, []);
  assert.equal(mapped.anotherWay, '');
}

/* --- X-03 / HX-2 A: a result tile is drawn only with a real measurement, never as a bare 0 --- */
{
  assert.deepEqual(resultTiles(null, null), []);
  assert.deepEqual(resultTiles(true, null), [{ key: 'phraseReused', good: true, valueKey: 'yes' }]);
  assert.deepEqual(resultTiles(false, { verdict: 'partly' }).map((tile) => tile.key), ['intentAchieved', 'phraseReused']);
  assert.equal(mapCoaching({ available: true, intent_achieved: { verdict: 'yes', reason: 'It answered.' } }).intent.verdict, 'yes');
  assert.equal(mapCoaching({ available: true, intent_achieved: { verdict: 'maybe', reason: 'x' } }).intent, null, 'an unknown verdict is not drawn');
  assert.equal(mapCoaching({ available: true }).intent, null);
}

console.log('test_orena_screen_react.mjs: React / Reuse data mapping - real GET /api/listening/library/{id} captures (en+zh) + POST /api/dictionary/spoken-response serializer shape, rule 40 throughout: PASS');
