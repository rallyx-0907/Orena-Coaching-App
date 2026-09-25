import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import * as readingContent from '../static/orena/content/reading.js';
import { comprehensionSection } from '../static/orena/ui/comprehension.js';
import { copy } from '../static/orena/ui/copy.js';

/* The generated-reading session adapters are retired with the generator
   (D-075): a learner reads the published corpus, and its check is an
   Admin-approved set. Nothing may bring the adapters back. */
for (const name of ['readingText', 'readingEntry', 'readingSessionId', 'readingId'])
  assert.ok(!(name in readingContent), `${name} is retired with the generated sessions`);

for (const language of ['en', 'zh']) {
  const questions = [
    { id: 'q1', question: '<Why?>', options: ['<one>', 'two', 'three', 'four'] },
  ];
  /* The approved check (D-059 Phase 5) is one question at a time, opened from
     an invitation: the questions themselves are never on the page until the
     learner asks for them, and a hostile option never renders as markup. */
  const markup = comprehensionSection(copy[language], questions);
  assert.match(markup, /^<section class="quiz"/);
  assert.match(markup, /data-quiz-start/, 'the check is offered, not started');
  assert.ok(!markup.includes('<form'), 'the questions wait until the check is opened');
  assert.ok(!markup.includes('<one>'), 'a hostile option never renders as markup');
  assert.ok(
    markup.includes(copy[language].comprehensionOptional),
    'the check says it is optional where it is offered',
  );
  /* A text with no questions used to render nothing at all, which is
     indistinguishable from a check that failed to load. Pure reading is valid,
     so the absence is now stated: still no form, but no silence either. */
  const none = comprehensionSection(copy[language], []);
  assert.ok(!none.includes('data-quiz-start'), 'no questions means no check to open');
  assert.ok(!none.includes('<form'), 'no questions means nothing to answer');
  assert.ok(
    none.includes(copy[language].readingOnlyNote),
    'a text without questions says so',
  );
}

/* A published article's check is the approved set served for it, and its
   answers are saved as canonical Reading evidence under one operation id that
   every retry reuses. */
const encounter = readFileSync('static/orena/ui/encounter.js', 'utf8');
assert.match(encounter, /api\.readingPracticeSet\(articleId\)/, 'the article reads its approved set');
assert.match(encounter, /practice\?\.submit_enabled/, 'questions are offered only while submit is open');
assert.match(encounter, /operationId \|\|=/, 'one operation id per answer sheet, reused on retry');
assert.match(encounter, /api\.submitReadingPractice\(/, 'answers go to canonical evidence');
assert.doesNotMatch(readFileSync('static/orena/infrastructure/api.js', 'utf8') + encounter, /selection_policy_version|selectionPolicyVersion/,
  'whether the selection policy chose a set is the server\'s to record, never the client\'s to claim');
assert.match(encounter, /practiceSubmit\(api, served, location\.rec\)/,
  'the signed recommendation travels from the address to the submit, untouched');
{
  const { route, link } = await import('../static/orena/product/intent.js');
  assert.equal(route(link('encounter', { id: 'article:a1', intent: 'reading', rec: 'rr1.p.s' }).slice(1)).rec, 'rr1.p.s',
    'a recommendation survives the address it rides in');
  assert.equal(route(link('encounter', { id: 'article:a1', intent: 'reading' }).slice(1)).rec, '',
    'and an address without one carries none');
}
assert.doesNotMatch(encounter, /readingSession|'reading:'/, 'no generated session is opened');
const history = readFileSync('static/orena/ui/history.js', 'utf8');
assert.match(history, /api\.readingEvidence\(30\)/, 'history reads canonical Reading evidence');
assert.doesNotMatch(history, /readingSessions/, 'and never the retired sessions');

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

// The generated-passage studio is retired (D-075): no internal AI writes a
// source passage, so neither its service nor its routes may come back.
assert.ok(
  !existsSync(new URL('../writing_coach/becoming_reading.py', import.meta.url)),
  'the AI passage generator is removed, not kept beside the corpus',
);
const appSource = readFileSync(new URL('../app.py', import.meta.url), 'utf8');
assert.ok(
  !appSource.includes('"/api/reading/session'),
  'no route serves or creates a generated reading session',
);
