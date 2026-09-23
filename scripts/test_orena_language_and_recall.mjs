/* My Language and Recall: the language a learner kept, and meeting it again.

   Two rooms, one contract. My Language is where saved language lives; Recall
   is the review loop over the part of it that is due. Neither owns a store of
   its own - both read pages of `api.libraryVocabulary(...)` and grade through
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
/* A page of the saved language, asked for as a page. Reading all of it was
   what made Vocabulary, Tiến độ and Hồ sơ cost more with every saved word. */
assert.match(expression, /api\.libraryVocabulary\(\{[^}]*limit:/, 'My Language reads a page of the saved language');
assert.doesNotMatch(expression, /api\.libraryVocabulary\(\s*\)/, 'and never the whole of it');
assert.match(expression, /status: 'due', order: 'due'/, 'and asks the server for what is due');
const recallRoom = expression.slice(
  expression.indexOf('async function renderRecallLanguage('),
  expression.indexOf('export async function renderLanguage('),
);
assert.match(recallRoom, /api\.libraryVocabulary\(\{ status: 'due', order: 'due'/, 'and Recall asks for the due queue');
assert.match(recallRoom, /api\.reviewLibraryVocabulary\(current\.word, button\.dataset\.grade\)/,
  'which grades through the scheduler that already exists');
assert.doesNotMatch(recallRoom, /localStorage|indexedDB|new Map\(\)/, 'Recall keeps no store of its own');
/* No second algorithm: what to ask and whether an attempt counts are decided
   in `product/recall.js`, not re-derived in the room. */
assert.match(recallRoom, /recallShape\(current, keptNow\)/, 'the question comes from the shared rule');
assert.equal(gradable(false), false, 'seeing a card is not recall');
assert.equal(gradable(true), true, 'committing to an answer is');

/* --- The room opens on its library (D-067, "Vocabulary library") --------
   The filter chips, then a grid of collections - a cover with its progress,
   the name and one line saying what the pack is. The learner's own two rows
   follow, because the design has no screen for a learner's own set yet (its
   matrix marks "My Content" INCOMPLETE) and their words must stay reachable;
   that difference is recorded in UI_BACKEND_GAPS.md. */
assert.doesNotMatch(expression, /vocabulary-summary-metrics/, 'the four metric tiles are gone');
/* The library and the two helpers that draw its covers are read together:
   they are one composition. */
const overview = expression.slice(
  expression.indexOf('const collectionCover = (collection) => {'),
  expression.indexOf('const libraryView = () => {'),
);
assert.match(overview, /class="vocab-library"/, 'the room is the library');
assert.doesNotMatch(overview, /class="vocab-home"/, 'the old home panel is gone, not restyled');
assert.match(overview, /class="vocab-chips"/, 'with the chips the frame draws');
assert.match(overview, /class="vocab-packs"/, 'and the grid of collections');
assert.ok(
  overview.indexOf('vocab-packs') < overview.indexOf('vocab-own-rows'),
  'the catalogue first, the learner\'s own under it',
);
/* Due is shown only when something is actually due, and an empty catalogue
   says so rather than drawing covers for packs that do not exist. */
assert.match(overview, /const due = dueItems[.]length\s*\n?\s*\?/, 'a review row appears only when there is one');
assert.match(overview, /vocabularyLibraryEmpty/, 'an empty catalogue says it is empty');
assert.match(recallRoom, /const landing = due[.]length/, 'and so does the Recall landing');
/* A cover is generated from the collection itself - no artwork to keep in
   step, and no placeholder pretending to be one. */
assert.match(overview, /const collectionCover = /, 'the cover is generated');
assert.match(overview, /--cover-hue/, 'with a hue the collection decides');

/* The review, as "Vocabulary review" draws it: the card is the screen. One way
   back, one segment per card, the count, the card itself, and - only once it is
   open - three grades, each printing what it will do to this card.

   The scheduler takes all three now, so nothing on this screen is disabled and
   nothing is drawn that cannot be pressed (the two dead buttons and GAP-019
   went with the old panel). */
assert.match(recallRoom, /class="vocab-review"/, 'the session is the card composition');
assert.match(recallRoom, /class="vocab-review__rail"/, 'with the segmented rail the source draws');
assert.match(recallRoom, /class="vocab-card" data-flip/, 'and the card the learner turns');
assert.doesNotMatch(recallRoom, /class="review-session"/, 'the old panel is gone, not restyled');
assert.doesNotMatch(recallRoom, /vocabGradeUnavailable|vocabGradeHard|vocabGradeEasy/,
  'and so are the grades the scheduler could not take');
assert.deepEqual(
  (recallRoom.match(/grade\('(\w+)'/g) || []).map((call) => call.slice(7, -1)),
  ['again', 'unsure', 'got_it'],
  'three grades, in the source\'s order',
);
/* The interval under each grade comes from the card, which carries the
   scheduler's own answer - never a number written on the button. */
assert.match(recallRoom, /current\?\.schedule\?\.\[key\]/, 'each grade reads its own interval');
assert.doesNotMatch(recallRoom, /'<1m'|'4d'/, 'no interval is written into the room');

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
/* The grades exist only once the card is open - the source says so on the
   closed card itself ("the grades appear once the card is open"). */
assert.match(recallRoom, /revealed \? grades : `<p class="vocab-review__hint">/,
  'the grades belong to the open card, and the closed one says so');
assert.doesNotMatch(recallRoom, /data-reveal>/, 'there is no separate reveal button: the card turns');

/* --- Where it came from, after the answer, not before ------------------- */
assert.match(recallRoom, /const back = [\s\S]*recall-where/, 'the back of the card says where the word was met');
assert.match(recallRoom, /\$\{revealed \? back : front\}/, 'and the back is only shown once the card is open');
/* The card draws no way to question the word: the source draws none there, so
   the control and its handler went together (rule 44). The shared explanation
   is still reached from the Quick Sheet and the reader, where the source does
   draw it - recorded in UI_BACKEND_GAPS.md. */
assert.doesNotMatch(recallRoom, /data-word-explain/, 'no control the source does not draw');
assert.doesNotMatch(recallRoom, /openUnderstanding\(/, 'and no handler left bound to nothing');

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
assert.match(rooms, /\.vocab-card \{/, 'and the card has the source\'s measurements');
assert.match(rooms, /inline-size: 420px/, 'four hundred and twenty wide');
assert.match(rooms, /block-size: 560px/, 'five hundred and sixty tall');
assert.match(rooms, /\.language-due \{/, 'and so does what is due in My Language');
assert.match(rooms, /\.vocabulary-row__source \{[^}]*grid-column: 1 \/ -1/,
  'the source takes its own line in the row rather than a column of chips');

/* --- The status a saved word is in is the scheduler's, not a guess ------ */
assert.equal(vocabularyStatus({ saved: true, due: true }), 'due');
assert.equal(vocabularyStatus({ saved: true, review_stage: 3 }), 'mastered');
assert.equal(vocabularyStatus({ saved: true, review_stage: 1 }), 'learning');
assert.equal(vocabularyStatus({}), 'new', 'nothing saved is nothing learned');

console.log('My Language and Recall: one store, one scheduler, source kept, nothing invented, EN/ZH/VI: PASS');
