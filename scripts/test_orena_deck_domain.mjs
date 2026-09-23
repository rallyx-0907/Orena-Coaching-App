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

assert.match(api, /vocabularyDecks:\(word=''\)=>/, 'there is a deck contract');
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
/* It reads decks for exactly one reason: deleting a word cascades its deck
   memberships away, so undo has to carry them back (review round 1, P2). It
   may read them and put a word back into one. It may not make, rename or
   delete a deck - that is Vocabulary's. */
assert.match(library, /\.vocabularyDecks\(entry\.title\)/, 'it reads which sets a word was in');
assert.match(library, /api\.vocabularyDeckAdd\(deck\.id, entry\.payload\.word\)/, 'and puts it back');
for (const owning of ['vocabularyDeckCreate', 'vocabularyDeckPatch', 'vocabularyDeckDelete'])
  assert.ok(!library.includes(owning), `My Library must not ${owning}`);

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
/* The migration landed only after an independent review, and the record says
   who reviewed it and at which commit - which is what AGENTS.md requires to be
   in Git, not just asserted. */
const landed = at('migrations/versions/20260923_0014_vocabulary_decks.py');
assert.match(landed, /Independent architecture review 2026-09-23: \*\*APPROVED\*\*/, 'the verdict is recorded');
assert.match(landed, /Reviewer: Claude\s+Sonnet 5 as Delegated Architecture Reviewer/, 'and who gave it');
assert.match(landed, /reviewed commit `9f94ad54/, 'and what they reviewed');
assert.match(landed, /\*\*dev and sandbox\s+only\*\* - explicitly not production/, 'and how far it was authorized');
const record = at('docs/project/VOCABULARY_DECK_SCHEMA_REVIEW_REQUEST.md');
assert.match(record, /## 7\. Review round 1/, 'the full record is beside it');

console.log('test_orena_deck_domain.mjs: a Deck is Vocabulary’s, a Collection is My Library’s');
