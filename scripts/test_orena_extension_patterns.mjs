import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  revisionTarget,
  applyRevision,
} from '../static/orena/product/revision.js';
/* The grammar catalogue the learner UI reads from the server: stable, unique Concept IDs, each one
   with its knowledge entry, in both languages. */
for (const language of ['en', 'zh']) {
  const folder = language === 'en' ? 'english' : 'chinese';
  const read = (name) =>
    JSON.parse(
      readFileSync(`writing_coach/languages/${folder}/${name}.json`, 'utf8'),
    );
  const curriculum = read('grammar_curriculum'),
    knowledge = read('grammar_knowledge');
  assert.ok(curriculum.length > 100, `${language}: the catalogue is not narrowed`);
  assert.equal(new Set(curriculum.map((x) => x.id)).size, curriculum.length, `${language}: Concept IDs are unique`);
  for (const item of curriculum) {
    assert.ok(item.id && item.level && item.title, `${language}/${item.id}: id, level and title`);
    assert.ok(knowledge.some((k) => k.id === item.id), `${language}/${item.id}: no knowledge entry`);
  }
  console.log(`${language}: ${curriculum.length} real concept entries`);
}
assert.deepEqual(revisionTarget('A small thing.', 'small'), {
  start: 2,
  end: 7,
  quote: 'small',
});
assert.equal(
  applyRevision('A small thing.', 'small', 'meaningful'),
  'A meaningful thing.',
);
assert.equal(
  applyRevision('我喜欢这里。', '这里', '这座城市'),
  '我喜欢这座城市。',
);
assert.equal(applyRevision('An edited sentence.', 'original', 'new'), null);
assert.equal(
  applyRevision('same and same', 'same', 'new'),
  null,
  'A repeated quote requires the learner to choose',
);
assert.equal(applyRevision('abc', 'b', ''), null);
assert.equal(applyRevision('a', 'a', 'b'.repeat(12001)), null);
console.log(
  'Extension patterns: real catalog breadth, stable IDs, unique/still-present revision anchors PASS',
);
