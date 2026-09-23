/* A Deck is Vocabulary's; a Collection is My Library's.
 *
 * The human settled this on 2026-09-23 after an earlier pass used
 * `library_collections` as the deck store. These assertions are what stops it
 * happening again: the Vocabulary screens must not reach into the library's
 * relationship layer, and the library's room must not grow a study set.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const at = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const room = at('static/orena/ui/expression.js');
const screens = at('static/orena/ui/word-add.js');
const library = at('static/orena/ui/collection.js');
const api = at('static/orena/infrastructure/api.js');
const deckApi = at('writing_coach/deck_api.py');
const deckRepo = at('writing_coach/persistence/deck_repository.py');

/* --- The Vocabulary screens use Vocabulary's own contract ---------------- */

assert.match(api, /vocabularyDecks:\(\)=>/, 'there is a deck contract');
assert.match(room, /api\.vocabularyDecks\(\)/, 'the room reads decks');
assert.match(room, /api\.vocabularyDeckCreate\(/, 'and creates them');
assert.match(room, /api\.vocabularyDeckAdd\(deckId, word\)/, 'and files words into them');

/* Not one of these may come back into the Vocabulary room or its screens. */
for (const wrong of [
  'libraryCollections(',
  'libraryCollectionCreate(',
  'libraryCollectionAdd(',
  'libraryCollectionItems(',
]) {
  assert.ok(!room.includes(wrong), `the Vocabulary room must not call ${wrong}`);
  assert.ok(!screens.includes(wrong), `the deck screens must not call ${wrong}`);
}
/* `material: 'collection'` is the shared cover system's own argument and says
   nothing about domains; what must not appear is a call into My Library. */
assert.doesNotMatch(screens, /api\.library/, 'the screens call nothing in the library layer');
assert.doesNotMatch(screens, /collections = \[\]|collections\.find/, 'and hold no list called collections');

/* --- My Library keeps its own, and gains no study set ------------------- */

assert.match(library, /api\.libraryCollections\(/, "My Library still has its collections");
assert.ok(!library.includes('vocabularyDeck'), 'and knows nothing about decks');

/* --- A set stores a reference, and no schedule -------------------------- */

assert.match(deckRepo, /saved_word_id/, 'a member points at the learner’s word');
for (const field of ['next_review_at', 'review_stage', 'last_reviewed_at'])
  assert.ok(!deckRepo.includes(field), `the deck repository must not touch ${field}`);

/* --- The cover is a name the theme owns, never a colour ----------------- */

assert.match(deckApi, /if value not in DECK_COVERS:/, 'an unknown cover is refused');
assert.doesNotMatch(deckRepo, /#[0-9a-fA-F]{6}/, 'no colour value is stored');
assert.match(at('static/orena/rooms.css'), /\[data-cover='sea'\] \{ --cover-hue: 235; \}/,
  'the stylesheet is the one thing that knows what a cover looks like');

/* --- Unapplied schema is said, not worked around ------------------------ */

assert.match(deckRepo, /def available\(self\) -> bool:/, 'the repository knows whether its tables exist');
assert.match(deckApi, /"decks_unavailable"/, 'and the API says so');
assert.ok(
  at('migrations/proposed/20260923_0014_vocabulary_decks.py').includes('PROPOSED'),
  'the migration is a proposal until a reviewer says otherwise',
);
/* It must not have been slipped into versions/ by the same hand that wrote it. */
let applied = false;
try {
  at('migrations/versions/20260923_0014_vocabulary_decks.py');
  applied = true;
} catch {
  applied = false;
}
assert.equal(applied, false, 'an implementer may not self-approve its own schema change');

console.log('test_orena_deck_domain.mjs: a Deck is Vocabulary’s, a Collection is My Library’s');
