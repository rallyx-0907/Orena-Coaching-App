/* Gate for the Free Talk screen's pure data mapping (frame 29, route 'freetalk'; Design Contract
   rule 40). Imports only the DOM-free module (static/orena/screens/free-talk/model.js), no browser,
   no network. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const read = (name) => fs.readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url), 'utf8');
const fixture = (name) => JSON.parse(read(name));

const {
  DURATIONS_MS, topics, formatClock, waveBars, resultStats, ledgerFacts, unitCount, pace, fixesOf, strengthsOf, phraseWords, headlineKind,
} = await import('../static/orena/screens/free-talk/model.js');

// 1. Duration caps: exactly the frame's own three pills, in milliseconds.
assert.deepEqual(DURATIONS_MS, [60_000, 120_000, 180_000]);

// 2. Topics: real, Orena-authored situations (content/voice-invitations.js), not the frame's own
// fixed prompt strings - and they exist for both learning languages.
{
  const en = topics('en');
  assert.equal(en.length, 3);
  for (const item of en) {
    assert.equal(typeof item.title, 'string');
    assert.ok(item.title.length > 0);
    assert.equal(typeof item.prompt, 'string');
    assert.ok(item.prompt.length > 0, 'a real situation to talk about, not a placeholder');
  }
  const zh = topics('zh');
  assert.equal(zh.length, 3);
  assert.notEqual(zh[0].title, en[0].title, 'zh gets its own authored text, not a copy of English');
}

// 3. Clock formatting: the frame's own m:ss (minutes are not zero-padded), never negative.
assert.equal(formatClock(0), '0:00');
assert.equal(formatClock(12_400), '0:12');
assert.equal(formatClock(65_000), '1:05');
assert.equal(formatClock(-5), '0:00', 'never a negative clock');
assert.equal(formatClock(NaN), '0:00');

// 3b. The recording wave: 40 bars, heights 25-100 percent, the source's own delay pattern.
{
  const bars = waveBars();
  assert.equal(bars.length, 40);
  for (const bar of bars) assert.ok(bar.height >= 25 && bar.height <= 100);
  assert.equal(bars[0].delay, 0);
  assert.equal(bars[1].delay, 41);
  assert.equal(bars[18].delay, (18 * 41) % 700);
}

// 4. Word/character counting is language-aware: whitespace words for en, Han characters for zh -
// never a whitespace split on Chinese, which would undercount to ~0.
assert.equal(unitCount('Honestly my mornings are the same', 'en'), 6);
assert.equal(unitCount('', 'en'), 0);
assert.equal(unitCount('   ', 'zh'), 0);
assert.equal(unitCount('我今天很忙', 'zh'), 5);
assert.equal(unitCount('我 today 很忙', 'zh'), 3, 'only the Han characters count for zh, not the Latin word mixed in');

// 5. Pace: real units / real minutes, 0 when there is no elapsed time to divide by (rule 40 - not
// a guessed "0 wpm said fast").
assert.equal(pace('one two three four five six', 30_000, 'en'), 12, '6 words in 30s = 12/min');
assert.equal(pace('one two three four five six', 5_000, 'en'), 72, 'exactly 5 s is measurable');
assert.equal(pace('one two three', 0, 'en'), null, 'no elapsed time is unmeasured (the frame draws a dash), not 0 wpm');
assert.equal(pace('one two three', 4_999, 'en'), null, 'under 5 s is too short to say');
assert.equal(pace('一二三四', 30_000, 'zh'), 8);

// 5b. The result tiles: Words and Pace measured, Linking the layout's 0 (rule 40), never a score.
{
  assert.deepEqual(resultStats('one two three four five six', 30_000, 'en'), { words: 6, pace: 12, linking: 0 });
  assert.deepEqual(resultStats('我今天很忙', 30_000, 'zh'), { words: 5, pace: 10, linking: 0 });
  {
  const { countLinkers } = await import('../static/orena/screens/free-talk/linking.js');
  assert.equal(countLinkers('I was late because the bus broke down, so I walked. However, it was fine.', 'en'), 3);
  assert.equal(countLinkers('First I woke up, and then I ate. For example, rice. Also tea, but finally coffee.', 'en'), 6);
  assert.equal(countLinkers('She is also absolutely sober and thoughtful', 'en'), 1, 'whole words only: "so" inside "also"/"sober" is not a linker');
  assert.equal(countLinkers('Because', 'en'), 1);
  assert.equal(countLinkers('', 'en'), 0);
  assert.equal(countLinkers('因为下雨，所以我没去。但是我很开心，然后我们回家了。', 'zh'), 4);
  assert.equal(countLinkers('首先我吃饭，而且我喝茶。比如米饭。最后我睡觉。', 'zh'), 4);
  assert.equal(countLinkers('我今天很忙', 'zh'), 0);
  assert.equal(countLinkers('', 'zh'), 0);
  assert.equal(resultStats('I ran but I was late.', 30_000, 'en').linking, 1);
  assert.equal(resultStats('我很忙，但是我来了', 30_000, 'zh').linking, 1);
}
assert.deepEqual(resultStats('', 0, 'en'), { words: 0, pace: null, linking: 0 }, 'nothing measured: words 0, pace a dash, linking 0');
  const labels = { words: 'Words', pace: 'Pace', paceUnit: 'wpm' };
  assert.deepEqual(ledgerFacts({ words: 6, pace: 12, linking: 0 }, labels), [{ label: 'Words', value: '6' }, { label: 'Pace', value: '12 wpm' }]);
  assert.deepEqual(ledgerFacts({ words: 6, pace: null, linking: 0 }, labels), [{ label: 'Words', value: '6' }], 'no pace measured, none logged');
  for (const fact of ledgerFacts({ words: 6, pace: 12, linking: 0 }, labels)) assert.equal(typeof fact.value, 'string', 'counts, not scores: the summary lowest-score reducer reads numbers only');
}

// 6. fixesOf / strengthsOf: the real spokenResponseCoaching shape (carried / landed_differently),
// capped at 3, items without a quote dropped - exactly the current Free Talk's own fixesOf
// (ui/speaking-free.js), reimplemented against the same data shape.
{
  const coaching = {
    carried: [{ quote: 'a' }, { quote: 'b' }, {}, { quote: 'c' }, { quote: 'd' }],
    landed_differently: [{ quote: 'x', instead: 'y', why: 'z' }],
  };
  assert.equal(strengthsOf(coaching).length, 3, 'capped at 3, empty entries dropped');
  assert.deepEqual(fixesOf(coaching), [{ quote: 'x', instead: 'y', why: 'z' }]);
  assert.deepEqual(fixesOf(null), []);
  assert.deepEqual(strengthsOf(undefined), []);
}

// 7. phraseWords: up to 4 of the learner's real saved words, blank entries dropped.
{
  const page = { items: [{ word: 'buffer' }, { word: '  ' }, { word: 'linger' }, { word: 'poised' }, { word: 'candid' }, { word: 'extra' }] };
  assert.deepEqual(phraseWords(page), ['buffer', 'linger', 'poised', 'candid'], 'capped at 4, a blank word dropped');
  assert.deepEqual(phraseWords(null), []);
  assert.deepEqual(phraseWords({ items: [] }), []);
  assert.deepEqual(phraseWords({ items: [{ word: 'With the big bang starting the year and as cheering began, we left.' }, { word: 'take a break' }, { word: '重要' }] }), ['take a break', '重要'], 'a whole sentence is not a useful-phrase chip (S-18)');
}

// 8. headlineKind: the 3-way split the frame's own headline draws (none / one / many), against a
// real fix count.
assert.equal(headlineKind(0), 'none');
assert.equal(headlineKind(1), 'one');
assert.equal(headlineKind(2), 'many');
assert.equal(headlineKind(5), 'many');

// 9. The real spoken-response captures (scripts/fixtures/api): every field this screen reads is really
// there, and the model maps it - a renamed field fails here, not in a browser.
{
  for (const name of ['spoken_response.json', 'spoken_response_landed.json']) {
    const real = fixture(name);
    assert.equal(real.available, true, name);
    assert.ok(Array.isArray(real.carried) && Array.isArray(real.landed_differently), name);
    for (const item of real.carried) assert.ok(item.quote && item.why, `${name} carried item carries quote + why`);
    for (const item of real.landed_differently) assert.ok(item.quote && item.why && 'instead' in item && item.judgement, `${name} landed item carries quote + instead + why + judgement`);
    assert.equal(typeof real.say_again, 'string', name);
    assert.equal(strengthsOf(real).length, Math.min(3, real.carried.length), name);
    assert.equal(fixesOf(real).length, Math.min(3, real.landed_differently.length), name);
  }
  assert.ok(fixture('spoken_response_landed.json').landed_differently.length > 0, 'one capture has real fixes, the shape the Fixes rows read');
}

// 10. The transcribe route returns the text this screen reads (a success needs a speech provider this
// sandbox does not have, so the field is checked in the serializer's own source, as scripts/
// test_orena_screen_word.mjs does for its restore fields) and answers with a `detail` error otherwise.
{
  const source = fs.readFileSync(new URL('../writing_coach/speech_api.py', import.meta.url), 'utf8');
  assert.match(source, /"text": result\.text/, 'POST /api/speech/transcribe returns { text }');
  const outage = fixture('speech_transcribe_unavailable.json');
  assert.equal(outage.detail.category, 'speech_asr_unconfigured', 'the real outage shape the screen treats as "provider unavailable"');
}

// A Chinese take is counted in characters (unitCount), so its tiles say characters in every interface language.
{
  const screen = fs.readFileSync(new URL('../static/orena/screens/free-talk/screen.js', import.meta.url), 'utf8');
  assert.match(screen, /language === 'zh' \? \{ count: 'statChars', pace: 'statPaceUnitChars' \}/, 'the unit label follows the learning language');
  assert.doesNotMatch(screen, /t\('statWords'\)|t\('statPaceUnit'\)/, 'no tile names its unit without the learning language');
}

/* --- LEX-051: saved items are called what they are, and only called "related" with evidence --- */
{
  const { phrasesFor, relatesToTopic } = await import('../static/orena/screens/free-talk/model.js');
  const page = { items: [{ word: '黄' }, { word: '城市' }, { word: '花生' }, { word: 'With the big bang starting the year and as cheering began, we left.' }, { word: 'commute' }] };
  assert.deepEqual(phrasesFor(page, ''), { kind: 'library', items: ['黄', '城市', '花生', 'commute'] }, 'no topic: the library, sentences never');
  assert.deepEqual(phrasesFor(page, '带一个人认识你的城市 一位朋友刚搬到你的城市'), { kind: 'topic', items: ['城市'] }, 'a Chinese item inside the topic is related');
  assert.equal(phrasesFor(page, '换个角度看').kind, 'library', 'nothing overlaps: no relatedness is claimed');
  assert.equal(relatesToTopic('commute', 'My daily commute to work'), true);
  assert.equal(relatesToTopic('so', 'also so'), false, 'a short word proves nothing');
  assert.equal(relatesToTopic('黄', '黄色的城市'), false, 'a single character proves nothing');
  assert.equal(phrasesFor(null, '城市').items.length, 0);
  assert.equal(phrasesFor(page, '').items.length <= 4, true);
}

console.log('Orena screen free-talk: model mapping (topics, clock, wave, counts, pace, result tiles, ledger facts, headline) and the real spoken-response captures: PASS');
