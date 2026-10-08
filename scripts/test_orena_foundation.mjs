/* The foundation under the learner UI: owned memory, retry-safe evidence, the topic vocabulary the
   catalog ships, and the retired visual systems staying retired. The colour, token and contrast
   assertions that used to live here belonged to the pre-cutover theme (theme.css, D-066); the learner
   UI's one colour owner is kit/tokens.css and scripts/test_orena_kit.mjs pins it to the design and to
   AA in both themes (D-143). */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { learnerMemory } from '../static/orena/product/memory.js';
import {
  dictationEvidence,
  recoverListeningEvidence,
} from '../static/orena/product/evidence.js';
import { registeredCopy } from '../static/orena/copy/index.js';
import { KNOWN_TOPICS, topicKey } from '../static/orena/screens/discover/model.js';
import '../static/orena/screens/discover/copy.js';

// Ink, Paper, sepia and the pre-cutover Dark Glass sheet do not come back (D-059, D-066, D-143).
for (const retired of ['theme-paper.css', 'theme.css', 'theme.js', 'foundation.css', 'world.css', 'app.js']) {
  assert.ok(!fs.existsSync(`static/orena/${retired}`), `static/orena/${retired} is retired`);
}
const tokens = fs.readFileSync('static/orena/kit/tokens.css', 'utf8');
assert.deepEqual(
  [...tokens.matchAll(/:root\[data-theme="([\w-]+)"\]\s*\{/g)].map((m) => m[1]).sort(),
  ['dark', 'light'],
  'the design has two themes, light and dark, and no third',
);

// Continuation survives a reload, for each language, and is stored as data - never as markup.
const data = new Map();
const storage = {
  getItem: (key) => data.get(key),
  setItem: (key, value) => data.set(key, value),
};
for (const language of ['en', 'zh']) {
  const memory = learnerMemory(storage, 'foundation-test', language);
  assert.equal(memory.value.continuation.length, 0, 'No fabricated continuation on first entry');
  memory.enter({
    id: 'media:shared',
    title: language === 'en' ? 'A voice' : '一个声音',
    segment: 'second',
    excerpt: 'original context',
  });
  memory.write('media:shared', '<script>not markup</script>');
  memory.enter({ id: 'media:shared', title: 'A voice', intent: 'writing' });
  const restored = learnerMemory(storage, 'foundation-test', language);
  assert.equal(restored.value.continuation[0].excerpt, 'original context');
  assert.equal(restored.value.continuation[0].segment, 'second');
  assert.equal(restored.value.expressions['media:shared'], '<script>not markup</script>');
}

// A failed initial evidence read followed by two saves used to double-count
// the first attempt. A lost write response must also be safe to retry.
let reads = 0;
const recover = recoverListeningEvidence(async () => {
  reads++;
  return { checked_attempt_count: 4, best_accuracy_percent: 95 };
});
const evidence = dictationEvidence({
  asset: 'a',
  segment: { segment_id: 's', original_text: 'A real voice.' },
  language: 'en',
});
evidence.compare('A voice');
assert.equal((await recover(evidence.value)).checked_attempt_count, 5);
assert.equal(
  (await recover(evidence.value)).checked_attempt_count,
  5,
  'Retry is idempotent',
);
evidence.compare('A real voice.');
assert.equal(
  (await recover(evidence.value)).checked_attempt_count,
  6,
  'Only the new attempt is added',
);
assert.equal(reads, 1);
let fail = true;
const retryRead = recoverListeningEvidence(async () => {
  if (fail) throw Error('offline');
  return { checked_attempt_count: 2 };
});
await assert.rejects(() => retryRead(evidence.value));
fail = false;
assert.equal((await retryRead(evidence.value)).checked_attempt_count, 4);

// Every topic the catalog actually ships is named in every interface language. A missing label is
// silent - the card simply loses its topic - so the gap only ever shows up as one language quietly
// losing its framing.
const catalog = JSON.parse(
  fs.readFileSync('writing_coach/content/listening_catalog.v1.json', 'utf8'),
);
const catalogTopics = new Set();
(function collect(node) {
  if (Array.isArray(node)) return node.forEach(collect);
  if (!node || typeof node !== 'object') return;
  if (typeof node.topic === 'string') catalogTopics.add(node.topic);
  Object.values(node).forEach(collect);
})(catalog);
assert.ok(catalogTopics.size, 'the catalog should declare topics');
const discover = registeredCopy().get('discover');
for (const topic of catalogTopics) {
  const key = topicKey(topic);
  assert.ok(key, `catalog topic "${topic}" is not one of Discover's topics, so it never reaches a learner`);
  for (const ui of ['en', 'vi', 'zh']) {
    assert.ok(
      discover.packs[ui][`topic_${key}`],
      `${ui}: catalog topic "${topic}" has no label, so its cards lose the framing the other languages keep`,
    );
  }
}
for (const key of KNOWN_TOPICS) {
  for (const ui of ['en', 'vi', 'zh']) assert.ok(discover.packs[ui][`topic_${key}`], `${ui}: topic_${key}`);
}

console.log(
  'Foundation: retired visual systems stay retired, owned continuation, retry-safe evidence and the shipped topics named in EN/VI/ZH PASS',
);
