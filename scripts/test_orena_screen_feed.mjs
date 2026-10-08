/* Gate for Vocabulary Daily Feed's pure data mapping (static/orena/screens/feed/model.js), D-091.
   Imports only DOM-free modules - no globals to stub. */
import assert from 'node:assert/strict';
import { cardScript, primaryExample, mapFeedCard, mapFeedCards, savePayload } from '../static/orena/screens/feed/model.js';

/* --- cardScript: the real identity.language field, falling back to a Han-range check --- */
assert.equal(cardScript({ headword: 'buffer', identity: { language: 'en' } }), 'latin');
assert.equal(cardScript({ headword: '缓冲', identity: { language: 'zh' } }), 'hanzi');
assert.equal(cardScript({ headword: '缓冲', identity: {} }), 'hanzi', 'falls back to the Han-range check when identity.language is missing');
assert.equal(cardScript({ headword: '', identity: {} }), 'latin');

/* --- primaryExample: the one authored example, never invented --- */
assert.equal(primaryExample(null), '');
assert.equal(primaryExample([]), '');
assert.equal(primaryExample([{ language: 'en', text: 'Keep a buffer.' }, { language: 'en', text: 'second' }]), 'Keep a buffer.');

/* --- mapFeedCard: rule 40 throughout - no schedule/mastery field exists on a never-saved
   catalogue entry, so none is fabricated here --- */
const card = mapFeedCard({
  headword: 'buffer',
  identity: { language: 'en' },
  meanings: [{ language: 'en', text: 'extra room kept in reserve' }, { language: 'vi', text: 'khoảng đệm' }],
  examples: [{ language: 'en', text: 'Keep a buffer before the deadline.' }],
  pronunciation: '/ˈbʌfər/',
  part_of_speech: 'noun',
  level: 'B1',
}, 'vi');
assert.equal(card.word, 'buffer');
assert.equal(card.script, 'latin');
assert.equal(card.meaning, 'khoảng đệm', 'the support-language meaning is picked when it exists');
assert.equal(card.hasExample, true);
assert.ok(card.exampleParts.some((part) => part.hit));
assert.equal(card.hasLevel, true);
assert.ok(!('saved' in card), 'a feed candidate carries no saved/schedule field at all - never invented');
assert.ok(!('filled' in card) && !('stageKey' in card), 'no mastery fields either - the card was never saved');

const noMeaningCard = mapFeedCard({ headword: 'zap', identity: { language: 'en' }, meanings: [], examples: [] }, 'vi');
assert.equal(noMeaningCard.hasMeaning, false);
assert.equal(noMeaningCard.hasExample, false);

/* --- mapFeedCards: only real, headworded entries --- */
assert.deepEqual(mapFeedCards(null, 'vi'), []);
const cards = mapFeedCards({ items: [{ headword: 'buffer', meanings: [] }, { headword: '' }, null] }, 'vi');
assert.equal(cards.length, 1);
assert.equal(cards[0].word, 'buffer');

/* --- savePayload: source_kind 'feed' (app.py's own comment: reuses POST
   /api/library/vocabulary, no new save endpoint) --- */
const payload = savePayload({ word: 'buffer', ipa: '/ˈbʌfər/', pos: 'noun', meaning: 'extra room kept in reserve' });
assert.equal(payload.source_kind, 'feed');
assert.equal(payload.word, 'buffer');
assert.equal(payload.definition, 'extra room kept in reserve');

console.log('test_orena_screen_feed.mjs: Vocabulary Daily Feed data mapping - real catalogue contract, rule 40 throughout: PASS');
