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
  const markup = comprehensionSection(copy[language], content.questions);
  assert.match(markup, /^<details/);
  assert.ok(!markup.includes('<details open'));
  assert.match(markup, /&lt;one&gt;/);
  assert.equal(comprehensionSection(copy[language], []), '');
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
