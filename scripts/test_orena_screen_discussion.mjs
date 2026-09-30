/* Gate for the Discussion screen's DOM-free logic (design route `discussion`, frame 46,
   static/orena/screens/discussion/model.js). Loads the real captured payloads
   (scripts/fixtures/api/text_discussion_empty.json, text_discussion_thread.json,
   text_discussion_turn_response.json) so a screen field read that does not exist in the real
   backend shape fails here. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const { parseContentId, discussionSourceFor, newRequestId, mapTurns, canSend, isSendKey, optimisticTurn, MAX_BODY_CHARACTERS } = await import(
  '../static/orena/screens/discussion/model.js'
);

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url)));
}

// 1. The shared content-id scheme, including the book-chapter split this screen's own source
// mapping needs.
assert.deepEqual(parseContentId('article:abc-1'), { kind: 'article', id: 'abc-1' });
assert.deepEqual(parseContentId('book:b1'), { kind: 'book', id: 'b1', chapterId: '' });
assert.deepEqual(parseContentId('book:b1:c2'), { kind: 'book', id: 'b1', chapterId: 'c2' });
assert.deepEqual(parseContentId('media:m9'), { kind: 'media', id: 'm9' });
assert.deepEqual(parseContentId('text:t7'), { kind: 'text', id: 't7' });
assert.deepEqual(parseContentId(''), { kind: '', id: '' });

// 2. The mapping onto the backend's real source-kind vocabulary
// (writing_coach/persistence/discussion_repository.py SOURCE_KINDS: story/media/reading_session/
// book_chapter) - an article and a learner's own text both fall to the generic "story" kind (the
// backend has no "article" kind of its own), a book chapter keeps the "<bookId>:<chapterId>"
// shape the backend's own book-chapter routing already uses elsewhere.
assert.deepEqual(discussionSourceFor({ kind: 'article', id: 'a1' }), { source_kind: 'story', source_id: 'a1' });
assert.deepEqual(discussionSourceFor({ kind: 'text', id: 't7' }), { source_kind: 'story', source_id: 't7' });
assert.deepEqual(discussionSourceFor({ kind: 'book', id: 'b1', chapterId: 'c2' }), { source_kind: 'book_chapter', source_id: 'b1:c2' });
assert.deepEqual(discussionSourceFor({ kind: 'book', id: 'b1', chapterId: '' }), { source_kind: 'book_chapter', source_id: 'b1' });
assert.deepEqual(discussionSourceFor({ kind: 'media', id: 'm9' }), { source_kind: 'media', source_id: 'm9' });

// 3. Request ids: real, short enough for the backend's own 64-char cap, and not equal across
// two calls (the endpoint's own dedup key - equal ids would collapse two different questions
// into "the same submission").
const id1 = newRequestId();
const id2 = newRequestId();
assert.ok(id1.length > 0 && id1.length <= 64);
assert.notEqual(id1, id2);

// 4. canSend: real, non-empty, non-whitespace-only text under the backend's own 4000-char cap
// (writing_coach/text_discussion.py MAX_BODY_CHARACTERS via discussion_repository.py).
assert.equal(canSend(''), false);
assert.equal(canSend('   '), false);
assert.equal(canSend('Why does the fox say that?'), true);
assert.equal(canSend('x'.repeat(4001)), false);
assert.equal(canSend('x'.repeat(4000)), true);

// 5. mapTurns against the real (captured) empty shape and the real (captured) populated shape -
// every field read (ordinal, role, body) is one the backend's own _turn_payload() actually returns; an unrecognised role is dropped, never
// guessed onto a side.
const empty = fixture('text_discussion_empty.json');
assert.deepEqual(mapTurns(empty.turns), []);

const populated = fixture('text_discussion_thread.json');
const mapped = mapTurns(populated.turns);
assert.equal(mapped.length, 2);
assert.equal(mapped[0].role, 'learner');
assert.equal(mapped[0].isAssistant, false);
assert.equal(mapped[0].body, populated.turns[0].body);
assert.equal(mapped[1].role, 'assistant');
assert.equal(mapped[1].isAssistant, true);

// Turns arrive out of ordinal order, or with a row this UI has no bubble side for: sorted, and
// the unrecognised row is dropped rather than shown as either speaker.
const reordered = mapTurns([
  { ordinal: 2, role: 'assistant', body: 'second' },
  { ordinal: 1, role: 'learner', body: 'first' },
  { ordinal: 3, role: 'system', body: 'unrecognised' },
]);
assert.deepEqual(reordered.map((turn) => turn.body), ['first', 'second']);

// The exchange's own response (POST .../turns) carries the same thread, so it can stand in for a
// refetch that fails: the screen reads `turns` from it.
const turnResponse = fixture('text_discussion_turn_response.json');
assert.deepEqual(mapTurns(turnResponse.turns), mapped, 'the exchange response and the thread read back are the same turns');
assert.ok('reused' in turnResponse && Array.isArray(turnResponse.turns));
assert.equal(populated.max_turns, 200, 'the real thread carries the cap the 409 toast quotes');

// 6. The body cap is the backend's own, read from its source so it cannot drift.
const repository = readFileSync(new URL('../writing_coach/persistence/discussion_repository.py', import.meta.url), 'utf8');
assert.equal(Number(repository.match(/^MAX_BODY_CHARACTERS = (\d+)/m)[1]), MAX_BODY_CHARACTERS);
assert.equal(canSend('x'.repeat(MAX_BODY_CHARACTERS)), true);
assert.equal(canSend('x'.repeat(MAX_BODY_CHARACTERS + 1)), false);

// 7. Enter sends, except the Enter that confirms an input-method candidate (Chinese input).
assert.equal(isSendKey({ key: 'Enter' }), true);
assert.equal(isSendKey({ key: 'Enter', isComposing: false, keyCode: 13 }), true);
assert.equal(isSendKey({ key: 'Enter', isComposing: true }), false, 'a composition is being confirmed, not sent');
assert.equal(isSendKey({ key: 'Enter', keyCode: 229 }), false, 'the legacy composition keyCode');
assert.equal(isSendKey({ key: 'a' }), false);
assert.equal(isSendKey(), false);

// 8. The optimistic turn is the learner's own trimmed words on the learner's side, and it maps
// like a server turn so the thread paints both the same way.
assert.deepEqual(optimisticTurn('  Why sour?  '), { role: 'learner', isAssistant: false, body: 'Why sour?' });
assert.deepEqual(mapTurns([{ ordinal: 1, role: 'learner', body: 'Why sour?' }])[0], optimisticTurn('Why sour?'));

console.log('test_orena_screen_discussion.mjs: Discussion model - content-id source mapping, request ids, send guard, real thread shape: PASS');
