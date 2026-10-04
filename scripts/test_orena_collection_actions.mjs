import assert from 'node:assert/strict';
import { readCollection, keepCollectionWords, collectionSavePayload } from '../static/orena/screens/collection/actions.js';

for (const [language, word] of [['en', 'book'], ['zh', '书']]) {
  const card = { headword: word, identity: { language, normalized: word },
    pronunciation: language === 'zh' ? 'shū' : 'bʊk',
    meanings: [{ language, text: 'source definition' }, { language: 'vi', text: 'sách' }],
    examples: [{ language, text: `${word}.` }], saved: false };
  const body = collectionSavePayload(card);
  assert.equal(body.word, word);
  assert.equal(body.source_kind, 'collection');
  assert.equal(body.definition, 'source definition');
  assert.equal(body.translation_vi, 'sách');
  assert.equal(body.source_fragment, `${word}.`);
  assert.equal(body.reading, card.pronunciation);
  assert.equal(collectionSavePayload({ ...card, readings: ['persisted reading'] }).reading, 'persisted reading');
  const saved = { ...card, identity: { language, normalized: 'held' }, headword: 'held', saved: true, review_stage: 4 };
  const collection = { language_code: language, items: [saved, card] };
  const calls = [];
  const result = await keepCollectionWords(collection, { language, save: async (payload) => { calls.push(payload); return { saved: true }; } });
  assert.equal(result.added, 1);
  assert.equal(result.remaining, 0);
  assert.equal(calls.length, 1, 'never resave/reset a previously held word');
  assert.equal(saved.review_stage, 4);
  await keepCollectionWords(collection, { language, save: async () => assert.fail('reopen/retry must skip held words') });
  await assert.rejects(keepCollectionWords(collection, { language: language === 'en' ? 'zh' : 'en', save: async () => assert.fail() }), /language/);
}
{
  const collection = { language_code: 'en', items: ['a', 'b', 'c'].map(headword => ({ headword, identity: { language: 'en' }, saved: false })) };
  const first = await keepCollectionWords(collection, { language: 'en', save: async (body) => { if (body.word === 'b') throw new Error('offline'); return { saved: true }; } });
  assert.equal(first.added, 1);
  assert.equal(first.remaining, 2);
  assert.ok(first.error);
  const retry = [];
  await keepCollectionWords(collection, { language: 'en', save: async (body) => { retry.push(body.word); return { saved: true }; } });
  assert.deepEqual(retry, ['b', 'c']);
}
{
  const offsets = [];
  const payload = await readCollection('pack', async (_id, params) => {
    offsets.push(params.offset);
    return { id: 'pack', language_code: 'zh', items: [{ headword: params.offset ? '乙' : '甲' }],
      review_items: [{ word: params.offset ? '乙' : '甲', review_stage: 2 }, { word: 'shared', review_stage: 2 }], has_more: !params.offset };
  }, { includeReview: true });
  assert.deepEqual(offsets, [0, 1]);
  assert.equal(payload.items.length, 2);
  assert.equal(payload.review_items.length, 3, 'collection review reads complete scoped saved rows and dedupes across pages');
  await assert.rejects(readCollection('pack', async () => ({ items: [], has_more: true })), /page/);
}
console.log('Collection actions: EN/ZH explicit saves, idempotent retry, provenance and complete scoped pages: PASS');
{
  let active = true;
  const calls = [];
  const collection = { language_code: 'en', items: ['a', 'b'].map(headword => ({ headword })) };
  const result = await keepCollectionWords(collection, { language: 'en', isCurrent: () => active,
    save: async (body) => { calls.push(body.word); active = false; return { saved: true }; } });
  assert.deepEqual(calls, ['a'], 'leaving stops subsequent saves');
  assert.equal(result.remaining, 1);
}
{
  const items = ['Book', 'book', 'pen'].map(headword => ({ headword, saved: false }));
  const calls = [];
  const progress = [];
  const result = await keepCollectionWords({ language_code: 'en', items }, { language: 'en',
    save: async (body) => { calls.push(body.word); return { saved: true }; },
    onProgress: (n, total) => progress.push([n, total]) });
  assert.deepEqual(calls, ['book', 'pen']);
  assert.deepEqual(progress, [[1, 2], [2, 2]]);
  assert.equal(result.remaining, 0);
  assert.ok(items.every(card => card.saved));
}
