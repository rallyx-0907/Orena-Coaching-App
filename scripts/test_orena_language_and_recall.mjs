/* My Language and Recall: the language a learner kept, and meeting it again.

   Two rooms, one contract. My Language is where saved language lives; Recall
   is the review loop over the part of it that is due. Neither owns a store of
   its own - both read `api.libraryVocabulary()` and grade through
   `api.reviewLibraryVocabulary()`, which is also the scheduler. A second
   vocabulary database or a second review algorithm is the failure these
   assertions exist to prevent.

   What else they guard: that the room opens on the learner's own language
   rather than a count of it, that a saved word keeps the sentence it was met
   in, that Chinese is a first-class citizen rather than English with a note,
   and that nothing here invents a score, a streak or a mastery figure. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { renderVocabularyRow, vocabularyStatus } from '../static/orena/ui/vocabulary-experience.js';
import { recallShape, gradable, blankContext } from '../static/orena/product/recall.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const expression = read('static/orena/ui/expression.js');
const experience = read('static/orena/ui/vocabulary-experience.js');
const rooms = read('static/orena/rooms.css');
const api = read('static/orena/infrastructure/api.js');

/* --- One store, one scheduler ------------------------------------------- */
/* Both rooms read the same saved-language contract and grade through the same
   endpoint. Nothing here keeps its own copy of a learner's vocabulary. */
for (const contract of ['libraryVocabulary', 'saveLibraryVocabulary', 'reviewLibraryVocabulary', 'deleteLibraryVocabulary'])
  assert.match(api, new RegExp(`${contract}:`), `${contract} is the shared contract`);
assert.match(expression, /api\.libraryVocabulary\(\)/, 'My Language reads the saved language');
const recallRoom = expression.slice(
  expression.indexOf('async function renderRecallLanguage('),
  expression.indexOf('export async function renderLanguage('),
);
assert.match(recallRoom, /api\.libraryVocabulary\(\)/, 'and so does Recall');
assert.match(recallRoom, /api\.reviewLibraryVocabulary\(current\.word, button\.dataset\.grade\)/,
  'which grades through the scheduler that already exists');
assert.doesNotMatch(recallRoom, /localStorage|indexedDB|new Map\(\)/, 'Recall keeps no store of its own');
/* No second algorithm: what to ask and whether an attempt counts are decided
   in `product/recall.js`, not re-derived in the room. */
assert.match(recallRoom, /recallShape\(current, keptNow\)/, 'the question comes from the shared rule');
assert.equal(gradable(false), false, 'seeing a card is not recall');
assert.equal(gradable(true), true, 'committing to an answer is');

/* --- The room opens on the language, not on a count of it --------------- */
assert.doesNotMatch(expression, /vocabulary-summary-metrics/, 'the four metric tiles are gone');
assert.match(expression, /class="vocabulary-tally"/, 'the counts are one quiet line');
const overview = expression.slice(
  expression.indexOf('const overview = () => {'),
  expression.indexOf('const libraryView = () => {'),
);
assert.ok(
  overview.indexOf('reviewBlock') < overview.indexOf('keptBlock'),
  'what is due comes first',
);
assert.ok(
  overview.indexOf('${keptBlock}') < overview.indexOf('vocabulary-dashboard__library'),
  "then the learner's own kept language, before the catalogue",
);
assert.ok(
  overview.lastIndexOf('${statusSummary}') > overview.indexOf('${keptBlock}'),
  'and the numbers last',
);
/* Due is shown only when something is actually due. Nothing is manufactured. */
assert.match(overview, /dueItems\.length\s*\?/, 'a review block appears only when there is one');
assert.match(recallRoom, /due\.length\s*\n?\s*\?/, 'and so does the Recall landing');

/* --- A saved word keeps where it was met -------------------------------- */
assert.match(experience, /function sourceLine\(/, 'a row can say where its word came from');
assert.match(experience, /source_encounters \|\| \[\]/, 'from the encounters the record already carries');
assert.match(expression, /where = String\(item\.focus_note/, 'the title comes from the saved record');
assert.match(expression, /\[\{ kind, fragment, where \}\]/, 'and travels with the fragment');
const card = {
  identity: { language: 'en', normalized: 'cloak' },
  headword: 'cloak',
  pronunciation: '/kləʊk/',
  meanings: [{ language: 'vi', text: 'áo choàng' }],
  source_encounters: [{ kind: 'reading', fragment: 'He wrapped his cloak around him.', where: 'The North Wind and the Sun' }],
  saved: true,
};
const row = renderVocabularyRow({ ...copy.vi, supportLanguage: 'vi' }, card, { index: 0 });
assert.ok(row.includes('cloak'), 'the word is there');
assert.ok(row.includes('/kləʊk/'), 'with how it is said');
assert.ok(row.includes('áo choàng'), 'and what it means, in the support language');
assert.ok(row.includes('The North Wind and the Sun'), 'and the piece it came from');
assert.ok(row.includes('He wrapped his cloak around him.'), 'and the sentence it was met in');
assert.ok(row.includes('<q lang="en">'), 'the sentence is the learning language, because it is content');
/* A word with no recorded encounter simply has no source line - nothing is
   invented to fill the space. */
const bare = renderVocabularyRow({ ...copy.vi, supportLanguage: 'vi' }, { ...card, source_encounters: [] }, { index: 0 });
assert.ok(!bare.includes('vocabulary-row__source'), 'no encounter, no source line');

/* --- Chinese is a first-class citizen ----------------------------------- */
const hanzi = renderVocabularyRow(
  { ...copy.vi, supportLanguage: 'vi' },
  {
    identity: { language: 'zh', normalized: '图书馆' },
    headword: '图书馆',
    pronunciation: 'túshūguǎn',
    meanings: [{ language: 'vi', text: 'thư viện' }],
    source_encounters: [],
    saved: true,
  },
  { index: 0 },
);
assert.ok(hanzi.includes('lang="zh"'), 'the word is marked as Chinese');
assert.ok(hanzi.includes('图书馆'), 'the whole lexical unit, not its characters');
assert.ok(hanzi.includes('túshūguǎn'), 'with tone-marked pinyin');
assert.ok(hanzi.includes('thư viện'), 'and the support-language meaning');

/* --- Recall: what is waiting, one item, what happened ------------------- */
assert.match(recallRoom, /stage = 'landing'/, 'a session starts by saying what is waiting');
assert.match(recallRoom, /class="recall-landing"/, 'as its own step');
assert.match(recallRoom, /data-recall-start/, 'with one way in');
assert.match(recallRoom, /stage === 'landing' \? landing : current \? card : done/,
  'then one item at a time, then what happened');
assert.match(recallRoom, /reviewed \+= 1/, 'what was reviewed is counted');
assert.match(recallRoom, /class="empty recall-done"/, 'and said at the end');
assert.match(recallRoom, /\$\{reviewed\} \$\{esc\(c\.vocabularyWordCount\)\}/, 'as a real count');
/* Real numbers only. No score, no streak, no mastery invented for the end of
   a session. */
for (const invention of ['XP', 'streak', 'accuracy', 'combo', 'confetti', 'mastery'])
  assert.doesNotMatch(recallRoom, new RegExp(`\b${invention}\b`, 'i'), `no ${invention}`);
assert.doesNotMatch(recallRoom, /Math\.round\([^)]*\/[^)]*\) *\+ *'%'/, 'and no percentage computed here');
/* The wall of vocabulary cards that used to sit under the session is gone:
   browsing saved language is My Language's job, and it was the same list
   twice. */
assert.doesNotMatch(expression, /language-cabinet/, 'Recall does not also browse the collection');

/* --- One item, and it does not give itself away ------------------------- */
/* The sentence is the best scaffold retrieval has, so it is shown - with the
   phrase withheld at every occurrence until the learner commits. */
const gap = blankContext('He wrapped his cloak around him, and the cloak held.', 'cloak');
assert.ok(gap, 'a sentence containing the word can be blanked');
assert.equal(gap.segments.length, 3, 'at every occurrence, not just the first');
assert.ok(!gap.segments.join('').includes('cloak'), 'and the word is not left in it');
assert.equal(recallShape({ source_fragment: 'a sentence with cloak in it', word: 'cloak' }, null), 'in_context',
  'a word met in a sentence comes back inside it');
assert.equal(recallShape({ word: 'cloak' }, null), 'meaning', 'one met without a sentence comes back by meaning');
assert.equal(recallShape({ word: 'cloak' }, { why: 'from_speaking' }), 'say', 'something said comes back by saying it');
assert.ok(
  recallRoom.indexOf('data-grade="again"') < recallRoom.indexOf('data-reveal>'),
  'grades belong to the revealed branch, the reveal button to the other one',
);

/* --- Where it came from, after the answer, not before ------------------- */
assert.match(recallRoom, /revealed\s*\n?\s*\? .*recall-where/s, 'the source is shown once the learner has committed');
assert.match(recallRoom, /current\.source_fragment \? `<button/, 'and can be asked about through the shared surface');
assert.match(recallRoom, /openUnderstanding\(ctx, \{/, 'which is the same one every other room uses');

/* --- Support language owns every word Orena says ------------------------ */
for (const ui of ['en', 'zh', 'vi'])
  for (const key of ['vocabularyTitle', 'vocabularyDueState', 'vocabularyWordCount', 'vocabularyContinueReview',
    'recallTitle', 'recallTruth', 'again', 'gotIt', 'allDone', 'allDoneNote', 'noWords', 'noWordsNote']) {
    assert.equal(typeof copy[ui][key], 'string', `${ui}.${key} exists`);
    assert.ok(copy[ui][key].trim(), `${ui}.${key} is not empty`);
  }
for (const key of ['vocabularyTitle', 'recallTitle', 'gotIt'])
  assert.equal(new Set([copy.en[key], copy.zh[key], copy.vi[key]]).size, 3,
    `${key} reads differently in each supported language`);
/* Self-report is self-report: the grade line says so, and does not claim to be
   a test score or a mastery figure. */
assert.ok(copy.en.recallTruth.toLowerCase().includes('not a test score'), 'the truth is stated');

/* --- The phone gets a composition, not a tower of cards ----------------- */
assert.match(rooms, /\.recall-landing \{/, 'the Recall landing has a shape of its own');
assert.match(rooms, /\.language-due \{/, 'and so does what is due in My Language');
assert.match(rooms, /\.vocabulary-row__source \{[^}]*grid-column: 1 \/ -1/,
  'the source takes its own line in the row rather than a column of chips');

/* --- The status a saved word is in is the scheduler's, not a guess ------ */
assert.equal(vocabularyStatus({ saved: true, due: true }), 'due');
assert.equal(vocabularyStatus({ saved: true, review_stage: 3 }), 'mastered');
assert.equal(vocabularyStatus({ saved: true, review_stage: 1 }), 'learning');
assert.equal(vocabularyStatus({}), 'new', 'nothing saved is nothing learned');

console.log('My Language and Recall: one store, one scheduler, source kept, nothing invented, EN/ZH/VI: PASS');
