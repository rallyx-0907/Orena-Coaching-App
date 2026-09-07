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
  progressReporter,
  savedLanguageLink,
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
// Work that leaves the device reports in one voice, and a retry it offers is
// always already wired - a retry button rendered without a handler is the
// defect this primitive exists to make impossible.
function statusElement() {
  const node = {
    isConnected: true,
    innerHTML: '',
    handlers: {},
    querySelector(selector) {
      if (!node.innerHTML.includes(selector.replace(/[[\]]/g, ''))) return null;
      return {
        set onclick(fn) {
          node.handlers.retry = fn;
        },
        get onclick() {
          return node.handlers.retry;
        },
      };
    },
  };
  return node;
}
for (const ui of ['en', 'zh']) {
  const c = copy[ui];
  const element = statusElement();
  const report = progressReporter(element, { c });
  report.saving();
  assert.ok(element.innerHTML.includes(c.saving), `${ui}: saving speaks`);
  report.saved();
  assert.ok(element.innerHTML.includes(c.persisted), `${ui}: saved speaks`);
  report.saved(savedLanguageLink(c));
  assert.ok(
    element.innerHTML.includes('#/language') &&
      element.innerHTML.includes(c.memoryLink),
    `${ui}: kept language offers the way back to it`,
  );
  let retried = 0;
  report.failed(c.failedSave, () => retried++);
  assert.ok(element.innerHTML.includes(c.retry), `${ui}: failure offers a retry`);
  assert.equal(typeof element.handlers.retry, 'function', `${ui}: retry is wired`);
  element.handlers.retry();
  assert.equal(retried, 1, `${ui}: retry runs the caller's action`);
  report.failed(c.failedSave);
  assert.ok(
    !element.innerHTML.includes('data-retry-action'),
    `${ui}: no retry button without a retry`,
  );
  // A late answer must not land on a screen the learner already left.
  const gone = statusElement();
  const silent = progressReporter(gone, { c }, () => false);
  silent.saved();
  assert.equal(gone.innerHTML, '', `${ui}: a dead view stays untouched`);
}

// Every tinted panel ships with the ink that belongs on it, in both themes.
// Checking the tokens rather than the rendered pages means a new screen using
// a panel inherits a legible pairing instead of re-deciding one by hand.
const foundationCss = fs.readFileSync('static/orena/foundation.css', 'utf8');
function tokens(selector) {
  const block = foundationCss.split(selector)[1].split('}')[0];
  return Object.fromEntries(
    [...block.matchAll(/(--[\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]),
  );
}
function channelLuminance(hex) {
  const parts = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = parts.map((v) =>
    v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4),
  );
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(a, b) {
  const x = channelLuminance(a),
    y = channelLuminance(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
const pairings = [
  ['--sage-surface', '--on-sage', 4.5],
  ['--sage-surface', '--on-sage-muted', 4.5],
  ['--coral-surface', '--on-coral', 4.5],
  ['--coral-surface', '--on-coral-muted', 4.5],
  ['--night-surface', '--on-night', 4.5],
  ['--night-surface', '--on-night-muted', 4.5],
  ['--sun-surface', '--on-sun', 4.5],
  ['--paper', '--ink', 4.5],
  ['--paper', '--muted', 4.5],
  ['--surface', '--ink', 4.5],
];
for (const [themeName, selector] of [
  ['light', ':root {'],
  ['dark', ":root[data-theme='dark'] {"],
]) {
  const palette = tokens(selector);
  for (const [surface, ink, need] of pairings) {
    assert.ok(palette[surface], `${themeName}: missing ${surface}`);
    assert.ok(palette[ink], `${themeName}: missing ${ink}`);
    const ratio = contrast(palette[surface], palette[ink]);
    assert.ok(
      ratio >= need,
      `${themeName}: ${ink} on ${surface} is ${ratio.toFixed(2)}:1, below ${need}:1`,
    );
  }
}
// A panel colour must never be used as a background without its paired ink.
for (const name of ['foundation', 'world', 'experiences']) {
  const css = fs.readFileSync(`static/orena/${name}.css`, 'utf8');
  assert.doesNotMatch(
    css,
    /background:\s*var\(--(sage|coral|night|sun)\)/,
    `${name}: paint panels with the --*-surface token so the ink is paired`,
  );
}

console.log(
  'Golden Star: first-paint/live themes, paired panel tokens, EN/ZH patterns, contextual drafts, continuation and retry-safe evidence PASS',
);
