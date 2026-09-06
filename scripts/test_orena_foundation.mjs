import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { copy } from '../static/orena/ui/copy.js';
import { learnerMemory } from '../static/orena/product/memory.js';
import {
  pageIntro,
  intentNavigation,
  continuationShelf,
  responseComposer,
} from '../static/orena/ui/patterns.js';
import {
  dictationEvidence,
  recoverListeningEvidence,
} from '../static/orena/product/evidence.js';

// The first-paint adapter runs without auth, even with inaccessible storage.
const themeCode = fs.readFileSync('static/orena/theme.js', 'utf8');
function themeHarness(saved, dark = false, blocked = false) {
  const callbacks = {},
    dataset = {},
    values = new Map([['orena.theme', saved]]);
  const media = {
    matches: dark,
    addEventListener: (_, fn) => (callbacks.system = fn),
  };
  const window = {
    matchMedia: () => media,
    addEventListener: (_, fn) => (callbacks.storage = fn),
  };
  const document = {
    documentElement: { dataset },
    querySelector: () => ({
      setAttribute: (_, value) => (callbacks.chrome = value),
    }),
  };
  vm.runInNewContext(themeCode, {
    window,
    document,
    localStorage: {
      getItem: (key) => {
        if (blocked) throw Error('denied');
        return values.get(key);
      },
      setItem: (key, value) => {
        if (blocked) throw Error('denied');
        values.set(key, value);
      },
    },
  });
  return { theme: window.orenaTheme, dataset, callbacks, media };
}
const auto = themeHarness(null, true);
assert.equal(auto.dataset.theme, 'dark');
auto.media.matches = false;
auto.callbacks.system();
assert.equal(auto.dataset.theme, 'light');
auto.theme.set('dark');
auto.callbacks.system();
assert.equal(auto.dataset.theme, 'dark', 'Explicit choice survives OS changes');
auto.callbacks.storage({ key: 'orena.theme', newValue: 'system' });
assert.equal(
  auto.dataset.theme,
  'light',
  'Another tab can restore the live device preference',
);
assert.equal(themeHarness('light', true).dataset.theme, 'light');
const blocked = themeHarness(null, true, true);
blocked.theme.set('light');
assert.equal(
  blocked.dataset.theme,
  'light',
  'A storage failure must not break a live theme choice',
);

const data = new Map();
const storage = {
  getItem: (key) => data.get(key),
  setItem: (key, value) => data.set(key, value),
};
for (const language of ['en', 'zh']) {
  const memory = learnerMemory(storage, 'foundation-test', language);
  const ctx = { memory, language, c: copy[language] };
  assert.equal(
    continuationShelf(ctx),
    '',
    'No fabricated continuation on first entry',
  );
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
  const thread = continuationShelf(ctx);
  assert.match(thread, /#\/expression\?id=media%3Ashared/);
  assert.ok(thread.includes('&lt;script&gt;'));
  assert.ok(!thread.includes('<script>'));
  assert.match(
    responseComposer(ctx, { id: 'media:shared', title: 'A voice' }),
    /&lt;script&gt;/,
  );
  assert.match(
    pageIntro({ title: '<script>', note: 'A & B' }),
    /&lt;script&gt;/,
  );
  assert.equal(
    (intentNavigation(ctx.c, 'writing').match(/aria-current/g) || []).length,
    1,
  );
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

// A page cannot quietly shrink supporting copy below the shared readable scale.
for (const name of ['foundation', 'world', 'experiences']) {
  const css = fs.readFileSync(`static/orena/${name}.css`, 'utf8');
  assert.doesNotMatch(
    css,
    /font-size:\s*(?:9|10|11|12|13)px\s*;/,
    `${name}: use the text scale`,
  );
}
console.log(
  'Golden Star: first-paint/live themes, EN/ZH patterns, contextual drafts, continuation and retry-safe evidence PASS',
);
