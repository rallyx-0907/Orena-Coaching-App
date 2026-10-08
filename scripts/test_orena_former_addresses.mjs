// Gate: every address of the UI `/` served before the cutover (D-091 item 5, D-143) opens a real place of the
// learner UI, and the learner UI's own addresses are left alone.
import assert from 'node:assert/strict';
import { formerAddress } from '../static/orena/shell/former-addresses.js';
import { match } from '../static/orena/shell/routes.js';

const cases = [
  ['#/encounter?id=media:abc', '#/content/media%3Aabc'],
  ['#/encounter?id=media:abc&intent=dictation', '#/content/media%3Aabc'],
  ['#/encounter', '#/discover'],
  ['#/content?id=article:12', '#/content/article%3A12'],
  ['#/book?id=pride', '#/content/book%3Apride'],
  ['#/book', '#/discover'],
  ['#/collection?id=c-1', '#/collection/c-1'],
  ['#/collection', '#/library'],
  ['#/admin?id=users', '#/admin/users'],
  ['#/admin?id=reading', '#/admin/reading'],
  ['#/admin?id=operations', '#/admin/operations'],
  ['#/admin?id=nonsense', '#/admin'],
  ['#/practice?intent=dictation&id=media:abc', '#/content/media%3Aabc'],
  ['#/practice?intent=shadowing', '#/practice'],
  ['#/practice?intent=writing', '#/write'],
  ['#/practice?intent=grammar', '#/grammar'],
  ['#/practice?intent=recall', '#/review'],
  ['#/practice?intent=follow', '#/discover'],
  ['#/practice?intent=unknown', '#/practice'],
  ['#/language', '#/library'],
  ['#/expression?id=x', '#/library'],
  ['#/writing', '#/write'],
  ['#/preferences', '#/settings'],
  ['#/continue', '#/today'],
  ['#/history', '#/progress'],
];
for (const [from, to] of cases) {
  assert.equal(formerAddress(from), to, from);
  assert.ok(match(to), `${from} -> ${to} is a route of the learner UI`);
}

// The learner UI's own addresses, including those whose path did not change, are not rewritten.
for (const own of ['', '#/', '#/today', '#/discover', '#/practice', '#/practice/speaking', '#/conversation', '#/progress?tab=trend',
  '#/profile', '#/search?q=cat', '#/admin', '#/admin/users', '#/content/media%3Aabc', '#/collection/c-1', '#/write', '#/welcome?step=languages']) {
  assert.equal(formerAddress(own), null, own);
}

console.log(`former addresses: ${cases.length} old addresses land on learner UI routes; own addresses untouched`);
