/* Gate for the Chinese script label (D-197): a Traditional Chinese article is labelled where the design already
   draws a meta line or a tag (Discover card tag, Content Detail hero meta, Reader toolbar meta); Simplified
   is the default and is never labelled; `mixed` and `unknown` draw nothing for the learner. EN / VI / ZH copy. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const { isTraditional } = await import('../static/orena/product/script.js');
const { entryFromArticle, presentCard } = await import('../static/orena/screens/discover/model.js');
const { normalizeArticle } = await import('../static/orena/screens/content/model.js');
const { toolbarMeta } = await import('../static/orena/screens/reader/model.js');

// 1. Only a Traditional Chinese article is Traditional.
assert.equal(isTraditional({ language: 'zh', script: 'zh-Hant' }), true);
for (const script of ['zh-Hans', 'mixed', 'unknown', '', undefined]) {
  assert.equal(isTraditional({ language: 'zh', script }), false, `${script} is not labelled`);
}
assert.equal(isTraditional({ language: 'en', script: 'zh-Hant' }), false, 'a script on a non-Chinese article is ignored');
assert.equal(isTraditional(null), false);
assert.equal(isTraditional({ language: 'zh' }), false, 'an older payload with no script is unlabelled');

// 2. The Discover card: a tag in the existing tag list, after the level; Simplified draws none.
const t = Object.assign((key) => key, { plural: (key) => key });
const trad = presentCard(entryFromArticle({ id: 'a', title: 'T', language: 'zh', level: 'HSK3', script: 'zh-Hant' }, []), t);
assert.deepEqual(trad.tags.map((tag) => tag.label), ['HSK3', 'scriptTraditional']);
const simp = presentCard(entryFromArticle({ id: 'b', title: 'T', language: 'zh', level: 'HSK3', script: 'zh-Hans' }, []), t);
assert.deepEqual(simp.tags.map((tag) => tag.label), ['HSK3']);
const mixed = presentCard(entryFromArticle({ id: 'c', title: 'T', language: 'zh', level: 'HSK3', script: 'mixed' }, []), t);
assert.deepEqual(mixed.tags.map((tag) => tag.label), ['HSK3'], 'a mixed text is a reviewer signal, not learner copy');

// 3. Content Detail.
assert.equal(normalizeArticle({ title: 'T', language: 'zh', script: 'zh-Hant' }).traditional, true);
assert.equal(normalizeArticle({ title: 'T', language: 'zh', script: 'zh-Hans' }).traditional, false);

// 4. The Reader toolbar meta line: after the level, before the mode.
assert.equal(
  toolbarMeta({ isBook: false, author: 'Source', kindLabel: 'Article', level: 'HSK3', scriptLabel: 'Traditional', modeLabel: 'Active', pageLabel: 'p. 1 of 3' }),
  'Source · Article · HSK3 · Traditional · Active · p. 1 of 3',
);
assert.equal(
  toolbarMeta({ isBook: false, author: 'Source', kindLabel: 'Article', level: 'HSK3', modeLabel: 'Active', pageLabel: 'p. 1 of 3' }),
  'Source · Article · HSK3 · Active · p. 1 of 3',
  'no label, no gap',
);

// 5. Copy in three languages on each surface, plus the admin evidence copy; the Chinese label is 繁體.
const expected = { en: 'Traditional', vi: 'Phồn thể', zh: '繁體' };
for (const surface of ['discover', 'content', 'reader']) {
  const source = readFileSync(new URL(`../static/orena/screens/${surface}/copy.js`, import.meta.url), 'utf8');
  assert.equal((source.match(/scriptTraditional:/g) || []).length, 3, `${surface}: scriptTraditional in en, vi, zh`);
  for (const [lang, label] of Object.entries(expected)) assert.ok(source.includes(`scriptTraditional: '${label}'`), `${surface} ${lang}`);
  assert.ok(/'scriptTraditional'/.test(source), `${surface}: declared in KEYS`);
}
const admin = readFileSync(new URL('../static/orena/screens/admin/copy-reading.js', import.meta.url), 'utf8');
for (const key of ['rdIssue_script_mixed', 'rdEvScript', 'rdScript_zh_Hans', 'rdScript_zh_Hant', 'rdScript_mixed', 'rdScript_unknown']) {
  assert.equal((admin.match(new RegExp(`${key}:`, 'g')) || []).length, 3, `${key} in en, vi, zh`);
}

console.log('reading script gate: ok');
