/* Vocabulary contracts that outlived the retired UI (D-143). Ported from test_orena_deck_domain,
 * test_orena_review_states and test_orena_word_clips, which checked them through the deleted ui/*.js
 * screens; here they are checked against the backend and the learner UI modules that carry them now.
 *
 * - A Deck is Vocabulary's; a Collection is My Library's (human decision 2026-09-23).
 * - A review answer given with no network is not lost, not reordered, and not retried forever.
 * - A word's context clips are real moments in real media; nothing is synthesized.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { MAX_WAITING, flushQueue, readQueue, withWaiting, worthKeeping } from '../static/orena/product/review-queue.js';

const at = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

/* --- A Deck is Vocabulary's; a Collection is My Library's ----------------- */
{
  const api = at('static/orena/infrastructure/api.js');
  const deckApi = at('writing_coach/deck_api.py');
  const deckRepo = at('writing_coach/persistence/deck_repository.py');
  const dispatcher = at('static/orena/agent/dispatcher.js');
  assert.match(api, /vocabularyDecks:\(word=''\)=>/, 'there is a deck contract');
  // Filing a word goes to the system the target belongs to, never across.
  assert.match(dispatcher, /target\.system === 'deck'\) await api\.vocabularyDeckAdd\(/, 'a deck target files through the deck contract');
  assert.match(dispatcher, /api\.libraryCollectionAdd\(/, 'a collection target files through My Library');
  // A set stores a reference to the learner's word, and no schedule.
  assert.match(deckRepo, /saved_word_id/, 'a member points at the learner’s word');
  for (const field of ['next_review_at', 'review_stage', 'last_reviewed_at'])
    assert.ok(!deckRepo.includes(field), `the deck repository must not touch ${field}`);
  // The cover is a name the theme owns, never a colour.
  assert.match(deckApi, /if value not in DECK_COVERS:/, 'an unknown cover is refused');
  assert.doesNotMatch(deckRepo, /#[0-9a-fA-F]{6}/, 'no colour value is stored');
  // Unapplied schema is said, not worked around.
  assert.match(deckRepo, /def available\(self\) -> bool:/, 'the repository knows whether its tables exist');
  assert.match(deckApi, /"decks_unavailable"/, 'and the API says so');
}

/* --- Review answers that wait ------------------------------------------- */
{
  const when = '2026-09-23T10:00:00Z';
  let queue = withWaiting([], 'harbour', 'got_it', when);
  queue = withWaiting(queue, 'lantern', 'again', when);
  assert.deepEqual(queue.map((item) => item.word), ['harbour', 'lantern'], 'answers wait in the order they were given');
  const sent = [];
  assert.deepEqual(await flushQueue(queue, (item) => { sent.push(item.word); return Promise.resolve(); }), [], 'nothing is left behind');
  assert.deepEqual(sent, ['harbour', 'lantern'], 'and they go up in that order');
  const held = await flushQueue(queue, (item) =>
    item.word === 'harbour' ? Promise.reject(Object.assign(new Error('down'), { status: 503 })) : Promise.resolve());
  assert.deepEqual(held.map((i) => i.word), ['harbour', 'lantern'], 'a failure holds the queue: later answers are not sent first');
  const refused = await flushQueue(queue, (item) =>
    item.word === 'harbour' ? Promise.reject(Object.assign(new Error('gone'), { status: 404 })) : Promise.resolve());
  assert.deepEqual(refused, [], 'a refusal is dropped, not retried forever');
  assert.equal(worthKeeping({ status: 503 }), true);
  assert.equal(worthKeeping({ status: 422 }), false);
  assert.equal(worthKeeping(new Error('failed to fetch')), true);
  assert.deepEqual(readQueue([{ word: 'x', grade: 'brilliant', at: when }]), [], 'an unknown grade is not a grade');
  assert.deepEqual(readQueue('not a queue'), []);
  assert.equal(readQueue(Array.from({ length: 400 }, () => ({ word: 'x', grade: 'again', at: when }))).length, MAX_WAITING);

  // The learner UI's Review uses that queue: answers wait on the device and go up when the connection returns.
  const review = at('static/orena/screens/review/screen.js');
  assert.match(review, /import \{ flushQueue, withWaiting \} from '\.\.\/\.\.\/product\/review-queue\.js';/);
  assert.match(review, /waiting = withWaiting\(waiting, word, grade, /, 'an answer that cannot go up waits');
  assert.match(review, /memory\?\.setReviewQueue\?\.\(waiting\)/, 'what waits is the device’s memory');
  assert.match(review, /window\.addEventListener\('online', onOnline\)/, 'and goes up when there is a connection');
  assert.match(review, /window\.removeEventListener\('online', onOnline\)/, 'and the listener leaves with the screen');
}

/* --- Context clips are real media --------------------------------------- */
{
  const clipsPy = at('writing_coach/word_clips.py');
  assert.match(clipsPy, /if not text or folded not in text\.casefold\(\):\n\s*continue/,
    "only a segment's own transcript decides that the word is said in it");
  assert.doesNotMatch(clipsPy, /^from writing_coach\.word_audio|^import.*kokoro/im, 'no voice is imported');
  assert.doesNotMatch(clipsPy, /WordAudioLibrary|synthesize|speak\(/, 'and no audio is made');
  const word = at('static/orena/screens/word/screen.js');
  assert.match(word, /api\.wordClips\(word, 6\)/, 'the word page asks for real clips');
  assert.match(word, /clips\.length \? clips\.map\(/, 'it draws the clips it was given');
  assert.match(word, /t\('contextClipsEmpty'\)/, 'and says so when there are none, never inventing one');
  assert.match(word, /audio\.currentTime = startMs \/ 1000;/, 'a clip plays from where it starts');
}

console.log('test_orena_vocabulary_contracts.mjs: decks vs collections, waiting review answers, real context clips: PASS');
