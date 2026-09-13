import assert from 'node:assert/strict';
import {collection, contentFor, EXPLORE_LANGUAGES} from '../static/orena/content/texts.js';

// This is the entire Discover generated-fiction catalog - no server, no
// database, no rights gate. A schema mistake here ships straight to the
// learner-facing page with no other layer to catch it, and nothing
// previously checked EN/ZH parity or internal consistency for it.

const REQUIRED_STRING_FIELDS = ['id', 'kind', 'title', 'subtitle', 'topic', 'level', 'time', 'art', 'origin'];

for (const language of EXPLORE_LANGUAGES) {
  const items = contentFor(language);
  assert.ok(items.length > 0, `${language} has no generated content`);
  const ids = new Set();
  for (const item of items) {
    for (const field of REQUIRED_STRING_FIELDS) {
      assert.equal(typeof item[field], 'string', `${language}/${item.id}: ${field} must be a string`);
      assert.ok(item[field].trim().length > 0, `${language}/${item.id}: ${field} must not be empty`);
    }
    assert.equal(item.origin, 'generated', `${language}/${item.id}: this collection is generated fiction only`);
    assert.ok(!ids.has(item.id), `${language} has a duplicate id: ${item.id}`);
    ids.add(item.id);

    assert.ok(Array.isArray(item.paragraphs) && item.paragraphs.length > 0, `${language}/${item.id}: needs at least one paragraph`);
    for (const paragraph of item.paragraphs) {
      assert.equal(typeof paragraph, 'string', `${language}/${item.id}: every paragraph must be a string`);
      assert.ok(paragraph.trim().length > 0, `${language}/${item.id}: a paragraph must not be empty`);
    }

    assert.ok(Array.isArray(item.phrases), `${language}/${item.id}: phrases must be an array`);
    for (const phrase of item.phrases) {
      assert.equal(typeof phrase.word, 'string', `${language}/${item.id}: phrase.word must be a string`);
      assert.ok(phrase.word.trim().length > 0, `${language}/${item.id}: phrase.word must not be empty`);
      assert.equal(typeof phrase.definition, 'string', `${language}/${item.id}: phrase.definition must be a string`);
      assert.ok(phrase.definition.trim().length > 0, `${language}/${item.id}: phrase.definition must not be empty`);
      assert.ok(
        Number.isInteger(phrase.paragraph) && phrase.paragraph >= 0 && phrase.paragraph < item.paragraphs.length,
        `${language}/${item.id}: phrase "${phrase.word}" points at paragraph ${phrase.paragraph}, outside 0..${item.paragraphs.length - 1}`,
      );
    }
    if (language === 'zh') {
      for (const phrase of item.phrases) {
        assert.equal(typeof phrase.phonetic, 'string', `${language}/${item.id}: phrase "${phrase.word}" needs phonetic (pinyin)`);
        assert.ok(phrase.phonetic.trim().length > 0, `${language}/${item.id}: phrase "${phrase.word}" phonetic must not be empty`);
      }
    }

    for (const field of ['prompt', 'question', 'thought']) {
      assert.equal(typeof item[field], 'string', `${language}/${item.id}: ${field} must be a string`);
      assert.ok(item[field].trim().length > 0, `${language}/${item.id}: ${field} must not be empty`);
    }
  }
}

// Every id in one language exists in the other - EN/ZH parity is a promise
// about the whole catalog, not just the copy dictionary.
const enIds = new Set(collection.en.map((item) => item.id));
const zhIds = new Set(collection.zh.map((item) => item.id));
assert.deepEqual([...enIds].sort(), [...zhIds].sort(), 'EN and ZH must offer the exact same set of stories');

// No literal '?' floods a CJK string the way mis-encoded text would.
for (const item of collection.zh) {
  const text = [item.title, item.subtitle, item.topic, ...item.paragraphs, item.prompt, item.question, item.thought].join('');
  assert.ok(!/\?{3}/.test(text), `zh/${item.id}: looks like damaged/mis-encoded text`);
}

console.log(`Orena Discover text collection: ${collection.en.length} stories, EN/ZH parity, schema PASS`);
