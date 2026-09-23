import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  readingText,
  readingEntry,
  readingSessionId,
} from '../static/orena/content/reading.js';
import { comprehensionSection } from '../static/orena/ui/comprehension.js';
import { copy } from '../static/orena/ui/copy.js';
import { origin } from '../static/orena/ui/content.js';

for (const language of ['en', 'zh']) {
  const passage =
    language === 'en'
      ? 'First line.\nStill here.\n\nA second paragraph.'
      : '第一行。\n还在这里。\n\n第二段。';
  const session = {
    id: 12,
    language_code: language,
    passage,
    title: '<a title>',
    generation_mode: 'built-in',
    topic: 'work',
    material: 'news',
    questions: [
      { question: 'Why?', options: ['<one>', 'two', 'three', 'four'] },
    ],
  };
  const content = readingText(session, language);
  assert.equal(content.paragraphs.length, 2);
  assert.equal(content.paragraphs[0], passage.split('\n\n')[0]);
  /* A built-in passage answers every subject and form with the same words, so
     it must not echo the request back as though it had honoured it. It used to
     carry these as empty strings; the readable contract leaves out what a
     source cannot honestly supply, so now they are absent entirely - the same
     guarantee, stated more strictly. */
  assert.ok(!('topic' in content), 'a built-in passage claims no subject');
  assert.ok(!('material' in content), 'a built-in passage claims no form');
  // A generated one did honour the request, and says so.
  const written = readingText(
    { ...session, generation_mode: 'generated' },
    language,
  );
  assert.equal(written.topic, 'work');
  assert.equal(written.material, 'news');
  assert.equal(origin(content, copy[language]), copy[language].readingBuiltIn);
  assert.equal(
    readingText(
      { ...session, language_code: language === 'en' ? 'zh' : 'en' },
      language,
    ),
    null,
  );
  assert.equal(readingText({ ...session, id: '../evil' }, language), null);
  assert.equal(readingText({ ...session, passage: '' }, language), null);
  assert.equal(readingEntry(session, language).attempted, false);
  assert.equal(
    readingEntry(
      { ...session, latest_attempt: { total: 4, correct_count: 0 } },
      language,
    ).attempted,
    true,
  );
  /* The canonical check (D-067) opens at its first question - the frames draw
     no invitation card - and the questions themselves are never in the page
     markup, so a hostile option never renders as markup either. */
  const markup = comprehensionSection(copy[language], content.questions);
  assert.match(markup, /^<section class="quiz"/);
  assert.match(markup, /data-quiz-step/, 'the check is a step, painted when it opens');
  assert.ok(!markup.includes('data-quiz-start'), 'the invitation card is gone (rule 44)');
  assert.ok(!markup.includes('<form'), 'the questions are not in the page');
  /* A text with no questions used to render nothing at all, which is
     indistinguishable from a check that failed to load. Pure reading is valid,
     so the absence is now stated: still no form, but no silence either. */
  const none = comprehensionSection(copy[language], []);
  assert.ok(!none.includes('data-quiz-step'), 'no questions means no check to open');
  assert.ok(!none.includes('<form'), 'no questions means nothing to answer');
  assert.ok(
    none.includes(copy[language].readingOnlyNote),
    'a text without questions says so',
  );
}
for (const id of [
  '',
  'reading:0',
  'reading:-1',
  'reading:1/answer',
  'reading:01',
])
  assert.equal(readingSessionId(id), null);
assert.equal(readingSessionId('reading:12'), 12);
const encounter = readFileSync('static/orena/ui/encounter.js', 'utf8');
assert.match(
  encounter,
  /payload\.found \? payload\.session : null/,
  'Read the real API envelope',
);

/* The readable contract. Books, public-domain works, articles and dialogues
   are more of what Reading already handles, and adding one should mean writing
   an adapter rather than redesigning the experience. These hold the gate every
   adapter ends at. */
const { readable, readableSource } = await import('../static/orena/content/reading.js');

// What a source cannot honestly supply is left out, never defaulted into a
// claim. An unknown licence stays unknown rather than becoming an empty one.
assert.equal(readableSource(null), null);
assert.equal(readableSource({}), null);
assert.equal(readableSource({ creator: '  ', license: '', provenance_url: '' }), null);
assert.deepEqual(
  readableSource({ creator: 'A. Author', license: 'Public domain', provenance_url: 'https://example.org/x' }),
  { creator: 'A. Author', license: 'Public domain', provenance_url: 'https://example.org/x' },
);
// One of the three is enough to be worth showing; the others stay empty rather
// than being invented.
assert.equal(readableSource({ license: 'CC BY-SA 4.0' }).creator, '');

// Nothing without an id, a title and real paragraphs reaches the encounter.
assert.equal(readable(null), null);
assert.equal(readable({ id: 'a:1', title: 'T', paragraphs: [] }), null);
assert.equal(readable({ id: 'a:1', title: 'T', paragraphs: ['   '] }), null);
assert.equal(readable({ id: '', title: 'T', paragraphs: ['One.'] }), null);
assert.equal(readable({ id: 'a:1', title: '', paragraphs: ['One.'] }), null);

const book = readable({
  id: 'book:persuasion-1',
  title: 'Persuasion, chapter one',
  language: 'en',
  paragraphs: ['One.', '  ', 'Two.'],
  level: 'B2',
  source: { creator: 'Jane Austen', license: 'Public domain', provenance_url: 'https://example.org/persuasion' },
});
assert.deepEqual(book.paragraphs, ['One.', 'Two.'], 'blank paragraphs are not paragraphs');
assert.equal(book.kind, 'text');
assert.equal(book.source.creator, 'Jane Austen');
assert.equal(book.level, 'B2');
assert.ok(!('questions' in book), 'a text without questions claims none');
assert.ok(!('generation_mode' in book), 'a text nobody generated says nothing about generation');
assert.equal(
  readable({ id: 'x:1', title: 'T', paragraphs: ['One.'], kind: 'conversation' }).kind,
  'conversation',
  'a dialogue keeps the kind the encounter lays out line by line',
);

// The encounter shows rights when a text carries them, through the same block
// media uses - one vocabulary for the same question, not two.
const encounterSource = readFileSync(
  new URL('../static/orena/ui/encounter.js', import.meta.url),
  'utf8',
);
assert.ok(
  encounterSource.includes('item.source ? `<details class="source">'),
  'a text that carries rights must be able to show them',
);
assert.ok(
  encounterSource.includes('safeExternal(item.source.provenance_url)'),
  'a source link is checked before it is offered',
);
// Every text source ends at the one gate, so a new adapter cannot skip it.
assert.ok(
  encounterSource.includes('readable({'),
  'the authored collection and learner imports pass through the contract',
);

console.log(
  'Reading: source truth, EN/ZH, paragraph fidelity, optional comprehension, readable contract PASS',
);

/* Optional comprehension, made legible. Pure reading is a complete thing to
   do, so a text without questions says so rather than looking identical to one
   whose questions failed to load - and nothing is fabricated to make every
   text carry a check. */
const { checkLabel } = await import('../static/orena/ui/reading.js');

for (const ui of ['en', 'zh']) {
  const c = copy[ui];
  assert.ok(c.readingOnly, `${ui}: no label for a text without questions`);
  assert.ok(c.readingOnlyNote, `${ui}: the encounter cannot say a text has none`);
  assert.ok(c.comprehensionWaiting, `${ui}: no label for waiting questions`);
  assert.notEqual(c.readingOnly, c.comprehensionDone, `${ui}: two states read alike`);

  // A list entry from the API states its count.
  assert.equal(checkLabel(c, { question_count: 4 }), `4 ${c.comprehensionWaiting}`);
  assert.equal(checkLabel(c, { question_count: 0 }), c.readingOnly);
  // A full item knows its own absence: `readable()` sets the field only when
  // there are questions, so no field on a whole text means none.
  assert.equal(checkLabel(c, { paragraphs: ['One.'] }), c.readingOnly);
  assert.equal(
    checkLabel(c, { paragraphs: ['One.'], questions: [{ question: 'q' }] }),
    `1 ${c.comprehensionWaiting}`,
  );
  assert.equal(checkLabel(c, { text: 'A text the learner brought.' }), c.readingOnly);
  // Having answered is worth saying over the count.
  assert.equal(checkLabel(c, { question_count: 4, attempted: true }), c.comprehensionDone);
  // A stub carrying neither says nothing: "no questions" and "not loaded yet"
  // are different claims, and only one of them is knowable here.
  assert.equal(checkLabel(c, { title: 'Only a title' }), '');
}

// The encounter says it too, in place of an empty section.
const comprehension = readFileSync(
  new URL('../static/orena/ui/comprehension.js', import.meta.url),
  'utf8',
);
assert.ok(
  comprehension.includes('comprehension-absent'),
  'a text with no questions must say so rather than render nothing',
);
assert.ok(
  comprehension.includes('c.readingOnlyNote'),
  'the absence is stated in copy, not left to the learner to infer',
);

// The count travels from the API rather than being guessed from the id.
const readingService = readFileSync(
  new URL('../writing_coach/becoming_reading.py', import.meta.url),
  'utf8',
);
assert.ok(
  readingService.includes('"question_count":len(_safe_json(row["questions_json"],[]))'),
  'the sessions list must report how many questions a passage carries',
);
