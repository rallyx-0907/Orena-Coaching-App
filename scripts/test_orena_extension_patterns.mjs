import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { patternsFor } from '../static/orena/content/patterns.js';
import {
  grammarShelf,
  filterGrammar,
} from '../static/orena/product/grammar-shelf.js';
import {
  revisionTarget,
  applyRevision,
} from '../static/orena/product/revision.js';
for (const language of ['en', 'zh']) {
  const folder = language === 'en' ? 'english' : 'chinese';
  const read = (name) =>
    JSON.parse(
      readFileSync(`writing_coach/languages/${folder}/${name}.json`, 'utf8'),
    );
  const curriculum = read('grammar_curriculum'),
    knowledge = read('grammar_knowledge');
  for (const note of patternsFor(language))
    assert.ok(
      curriculum.some((x) => x.id === note.id),
      `Unknown Concept ID: ${note.id}`,
    );
  const lessons = curriculum.map((x) => {
    const example = knowledge.find((k) => k.id === x.id)?.lesson?.examples?.[0];
    return {
      ...x,
      preview: example
        ? { text: example.target || example.en || example.zh }
        : null,
    };
  });
  const shelf = grammarShelf({ lessons }, patternsFor(language), language);
  assert.ok(
    shelf.length > patternsFor(language).length,
    'The catalog must not be narrowed to editorial notes',
  );
  for (const item of shelf)
    assert.ok(
      item.heading && item.line && curriculum.some((x) => x.id === item.id),
    );
  const level = shelf.at(-1).level;
  assert.ok(filterGrammar(shelf, { level }).every((x) => x.level === level));
  assert.equal(
    filterGrammar(shelf, { query: 'missing-nonsense-pattern' }).length,
    0,
  );
  console.log(
    `${language}: ${shelf.length} real concept entries, ${patternsFor(language).length} editorial references`,
  );
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
  'Extension patterns: real catalog breadth, stable IDs, language-neutral filters, unique/still-present revision anchors PASS',
);
