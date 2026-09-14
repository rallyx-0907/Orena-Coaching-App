/* Review-finding regression: My Language's `vocabularyCardFromLibraryItem`
   (static/orena/ui/expression.js) maps a saved-word list item into the one
   shared Vocabulary Card shape. It must preserve `item.orthography` - the
   server already projects it (writing_coach/orthography.py) onto saved
   Chinese words - so a kept Chinese word reaches the existing
   `renderVocabularyCard` stroke-order renderer instead of silently losing
   it in this second, page-local mapping.
   docs/superpowers/plans/2026-09-14-vocabulary-experience.md Task G. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const expression = read('static/orena/ui/expression.js');

const fnStart = expression.indexOf('function vocabularyCardFromLibraryItem');
assert.ok(fnStart >= 0, 'vocabularyCardFromLibraryItem must still exist');
const fnEnd = expression.indexOf('\n}', fnStart);
const fnBody = expression.slice(fnStart, fnEnd);

assert.match(
  fnBody,
  /if\s*\(item\.orthography\)\s*card\.orthography\s*=\s*item\.orthography;/,
  'vocabularyCardFromLibraryItem must carry item.orthography onto the mapped card, ' +
    'or a saved Chinese word loses its stroke-order rendering',
);

console.log('Orena Vocabulary saved-card mapping preserves orthography: PASS');
