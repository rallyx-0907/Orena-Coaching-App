/* Adding a word, choosing its set, and making a new one.
 *
 * Frames 22, 23, 24, 25 and 29. The set is a Deck - Vocabulary's own - and
 * nothing here keeps a second copy of a word or a second list of sets.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');
const screens = read('ui/word-add.js');
const room = read('ui/expression.js');
const css = read('rooms.css');
const copy = read('ui/copy.js');
const copyVi = read('ui/copy-vi.js');

/* --- One store for the learner's sets ----------------------------------- */

/* The set is a **Deck**: Vocabulary's own learning/review set. A Deck and a
   My Library Collection are two different things (the human, 2026-09-23);
   test_orena_deck_domain.mjs holds that boundary, and this only checks the
   screens reach for the right one. */
assert.match(room, /api\.vocabularyDecks\(\)/, "the sets are Vocabulary's own decks");
assert.match(room, /api\.vocabularyDeckCreate\(/, 'a new set is made there');
assert.match(room, /cover: newDeck\.cover \|\| 'violet'/, 'with the cover the learner chose');
assert.match(room, /api\.vocabularyDeckAdd\(deckId, word\)/, 'and a word joins one by reference');
assert.doesNotMatch(room, /localStorage[^\n]*deck/i, 'no set is kept on the device');

/* A word is kept once, and a set refers to it: the word is saved first, so a
   failure to file never leaves one half-kept. */
assert.match(room, /if \(adding\.chosen\) await fileWord\(adding\.word\.trim\(\), adding\.chosen\);/,
  'the word is saved, then filed');

/* --- The frames' fields, in the frames' order --------------------------- */

const fields = [...screens.matchAll(/field\(\s*c\.(\w+)/g)].map((m) => m[1]);
assert.deepEqual(
  fields,
  ['addWordWord', 'addWordMeaning', 'addWordExample', 'deck', 'deckName', 'deckLanguage', 'deckCover'],
  'the add screen asks for the word, its meaning, a sentence and a set; the new set asks its name, language and cover',
);

/* The dictionary line is drawn only when the catalogue really has the word:
   the frame draws it in the affirmative only. */
assert.match(screens, /function dictionaryLine\(c, found\) \{\s*if \(!found\) return '';/,
  'a word the catalogue does not know says nothing rather than accusing the learner');

/* The desktop modal and the phone screen are one piece of markup. */
assert.doesNotMatch(screens, /matchMedia|innerWidth/, 'the module does not measure the window');
assert.match(css, /@media \(min-width: 1000px\) \{\n  \.word-add__body/, 'width alone makes the modal');

/* --- Measured ------------------------------------------------------------ */

for (const [what, rule] of [
  ['a set row', /\.deck-row \{\n  block-size: 56px;/],
  ['its cover', /\.deck-row__art \{[^}]*inline-size: 32px;[^}]*border-radius: 9px;/s],
  ["the sheet's save", /\.deck-sheet__save \{ block-size: 54px; min-block-size: 54px; border-radius: 17px; font-size: 16px; \}/],
  ['the word field', /\.word-add__input--word \{\n  block-size: 52px;/],
  ["a new set's cover", /\.deck-new__cover \{[^}]*block-size: 150px;[^}]*border-radius: 16px;/s],
  ['a language pill', /\.deck-new__lang \{[^}]*block-size: 40px;[^}]*border-radius: 11px;/s],
  ["the empty room's add", /\.vocab-empty__add \{[^}]*inline-size: 42px;[^}]*border-radius: 13px;/s],
])
  assert.match(css, rule, `${what} is the frame’s size`);

const from = css.indexOf('.word-add, .deck-new {');
assert.doesNotMatch(css.slice(from), /#[0-9a-fA-F]{3,8}\b/, 'these screens name no colour of their own');

/* --- Three languages ----------------------------------------------------- */

for (const key of [
  'addWord', 'addWordSelf', 'addWordWord', 'addWordMeaning', 'addWordExample',
  'addWordInDictionary', 'addAnother', 'optional', 'add', 'create', 'deck',
  'chooseDeck', 'createDeck', 'newDeck', 'deckName', 'deckLanguage',
  'deckLanguageLocked', 'deckCover', 'decksUnavailable', 'saveToDeck', 'saveWordTitle', 'saveIntoDeck',
  'vocabularyNoWordsYet', 'vocabularyNoWordsNote',
]) {
  assert.equal((copy.match(new RegExp(`\\b${key}:`, 'g')) || []).length, 2, `${key} in English and Chinese`);
  assert.ok(copyVi.includes(`${key}:`), `${key} in Vietnamese`);
}

console.log('test_orena_word_add.mjs: one word, one set, and one store behind both');
