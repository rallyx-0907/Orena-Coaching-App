/* My Language and Recall: one store, one scheduler.

   The learner UI's Review screen reads pages of `api.libraryVocabulary(...)` and grades through
   `api.reviewLibraryVocabulary()`, which is also the scheduler. A second vocabulary database or a
   second review algorithm is the failure these assertions exist to prevent. The grades, the cloze,
   the offline queue and the session tally are test_orena_screen_review.mjs; this keeps the contract
   the screen stands on and the rule that it persists nothing of its own, and that nothing here
   invents a score, a streak or a mastery figure. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const api = read('static/orena/infrastructure/api.js');
const review = read('static/orena/screens/review/screen.js');

/* --- One store, one scheduler ------------------------------------------- */
for (const contract of ['libraryVocabulary', 'saveLibraryVocabulary', 'reviewLibraryVocabulary', 'deleteLibraryVocabulary'])
  assert.match(api, new RegExp(`${contract}:`), `${contract} is the shared contract`);
/* A page of the saved language is asked for as a page, never the whole of it. */
const reads = review.match(/api\.libraryVocabulary\([^)]*\)/g) || [];
assert.ok(reads.length >= 3, 'the review screen reads the saved language');
for (const call of reads) assert.match(call, /limit:/, `${call} asks for a page`);
assert.match(review, /api\.libraryVocabulary\(\{ status: 'due', order: 'due'/, 'Review asks the server for what is due');
/* Every grade goes through the scheduler that already exists, queued or live. */
assert.match(review, /api\.reviewLibraryVocabulary\(word, grade\)/, 'a grade goes to the scheduler');
assert.match(review, /flushQueue\(sent, \(item\) => api\.reviewLibraryVocabulary\(item\.word, item\.grade\)\)/, 'an answer with no network waits and is sent again');
/* Review keeps no store of its own for words, meanings or review state. */
assert.doesNotMatch(review, /indexedDB|sessionStorage/, 'Review keeps no database of its own');

/* --- Real numbers only: no invented score, streak or mastery ------------ */
for (const invention of ['streak', 'combo', 'confetti', 'mastery'])
  assert.doesNotMatch(review, new RegExp(`\\b${invention}\\b`, 'i'), `no ${invention}`);

console.log('My Language and Recall: one store, one scheduler, nothing invented: PASS');
