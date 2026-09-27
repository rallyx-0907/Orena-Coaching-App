/* Gate for Collection Detail's data mapping (Design Contract rules 40, 42; frame
   21-Collection-Detail.html, D2 §6). screens/collection/model.js is DOM-free - imported
   directly, no globals to stub. */
import assert from 'node:assert/strict';
import { supportMeaning, wordRow, collectionViewModel } from '../static/orena/screens/collection/model.js';

// 1. supportMeaning: the learner's support language wins; failing that, any meaning that is not
// the word's own target-language definition; failing that, whatever is first. Never a hardcoded
// language (no literal 'vi' special-cased).
{
  const card = {
    identity: { language: 'en' },
    meanings: [
      { language: 'en', text: 'to move quickly' },
      { language: 'vi', text: 'di chuyển nhanh' },
      { language: 'zh', text: '快速移动' },
    ],
  };
  assert.equal(supportMeaning(card, 'zh'), '快速移动', 'exact support-language match wins');
  assert.equal(supportMeaning(card, 'ko'), 'di chuyển nhanh', 'no match for the support language: falls back to a meaning that is not the target-language one (first non-English here)');
  assert.equal(supportMeaning({ identity: { language: 'en' }, meanings: [{ language: 'en', text: 'x' }] }, 'zh'), 'x', 'nothing but the target-language meaning exists: that is what is shown, not blank');
  assert.equal(supportMeaning({}, 'vi'), '', 'no meanings at all: empty, not invented');
}

// 2. wordRow: a never-saved word is NEW; a saved word shows a 4-bar meter filled to its
// review_stage (clamped 0-4), never mixed with the NEW badge (D2: isNew/notNew are exclusive).
{
  const fresh = wordRow({ headword: 'buffer', saved: false, review_stage: 0, identity: { language: 'en' }, meanings: [{ language: 'vi', text: 'vùng đệm' }] }, 'vi');
  assert.equal(fresh.isNew, true);
  assert.equal(fresh.filled, 0);
  assert.equal(fresh.meaning, 'vùng đệm');

  const partway = wordRow({ headword: 'hectic', saved: true, review_stage: 2, identity: { language: 'en' }, meanings: [] }, 'vi');
  assert.equal(partway.isNew, false);
  assert.equal(partway.filled, 2);
  assert.equal(partway.total, 4);

  const overStage = wordRow({ headword: 'packed', saved: true, review_stage: 9 }, 'vi');
  assert.equal(overStage.filled, 4, 'review_stage is clamped to the 4-bar meter, never overflowing it');

  const savedButNoStage = wordRow({ headword: 'x', saved: true }, 'vi');
  assert.equal(savedButNoStage.filled, 0, 'a saved word with no review_stage yet is 0 filled bars, not NEW (rule 40: no fabricated stage)');
}

// 3. collectionViewModel: percent is learned_count / item_count (the same real metric Discover's
// own entryFromCollection uses), clamped and zero-safe; the two fields the backend cannot supply
// at all (description, "met in your sources") are always empty/0, never guessed at.
{
  const model = collectionViewModel({
    id: 'toeic-600', title: 'TOEIC 600', level_range: 'B1-B2', item_count: 40,
    progress: { learned_count: 10, learning_count: 6, due_count: 2, mastered_count: 4 },
    items: [
      { headword: 'a', saved: true, review_stage: 3, identity: { language: 'en' }, meanings: [{ language: 'vi', text: 'a-vi' }] },
      { headword: 'b', saved: false, identity: { language: 'en' }, meanings: [] },
    ],
  }, 'vi');
  assert.equal(model.id, 'toeic-600');
  assert.equal(model.level, 'B1-B2');
  assert.equal(model.wordCount, 40, 'the collection\'s own item_count, not just the items on this page');
  assert.equal(model.percent, 25, '10 / 40 learned = 25%');
  assert.equal(model.description, '', 'backend gap: VocabularyCollection has no description column');
  assert.equal(model.metInSources, 0, 'backend gap: no source-encounter aggregate exists for a collection');
  assert.equal(model.words.length, 2);
  assert.equal(model.words[0].meaning, 'a-vi');
  assert.equal(model.words[1].isNew, true);

  const empty = collectionViewModel({ id: 'x', title: 'x', item_count: 0, items: [] }, 'vi');
  assert.equal(empty.percent, 0, 'an empty collection is 0%, never a division by zero');
  assert.equal(empty.level, '', 'no level or level_range at all reads as no level, not a placeholder string');

  const levelFallback = collectionViewModel({ id: 'x', title: 'x', level: 'A2', item_count: 1, items: [] }, 'vi');
  assert.equal(levelFallback.level, 'A2', 'level_range missing: falls back to the single level');
}

console.log('Orena Collection Detail: support-language meaning, mastery-bar mapping, progress percent and the two backend-gap fields are all pure and honest, no invented data: PASS');
