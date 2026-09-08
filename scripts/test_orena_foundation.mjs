import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { copy } from '../static/orena/ui/copy.js';
import { learnerMemory } from '../static/orena/product/memory.js';
import { practiceIntentions } from '../static/orena/product/intent.js';
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
    readyState: 'complete',
    addEventListener: (_, fn) => (callbacks.ready = fn),
    querySelector: () => ({
      setAttribute: (_, value) => (callbacks.chrome = value),
    }),
  };
  /* The browser chrome colour is read from the resolved token rather than
     kept as a second copy of the palette, so the harness has to answer the
     same question a stylesheet would. */
  const grounds = {
    paper: '#f8f3e9',
    'night-ink': '#102538',
    'deep-forest': '#1e3a3c',
    'sage-field': '#eff2ec',
  };
  vm.runInNewContext(themeCode, {
    window,
    document,
    getComputedStyle: () => ({
      getPropertyValue: (name) =>
        name === '--paper' ? grounds[dataset.theme] || '' : '',
    }),
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
/* A theme has an identity and, separately, an appearance. The product used to
   store the appearance as the preference - the string was literally 'light' or
   'dark' - which is why a third theme could not exist. These hold the two
   apart, because every future theme depends on the distinction. */
const auto = themeHarness(null, true);
assert.equal(auto.dataset.theme, 'night-ink', 'a dark device gets a named theme');
assert.equal(auto.dataset.appearance, 'dark', 'appearance is tracked separately');
auto.media.matches = false;
auto.callbacks.system();
assert.equal(auto.dataset.theme, 'paper');
assert.equal(auto.dataset.appearance, 'light');
auto.theme.set('deep-forest');
auto.callbacks.system();
assert.equal(
  auto.dataset.theme,
  'deep-forest',
  'Explicit choice survives OS changes',
);
assert.equal(
  auto.dataset.appearance,
  'dark',
  'a chosen theme brings its own appearance, whatever the device says',
);
auto.callbacks.storage({ key: 'orena.theme', newValue: 'system' });
assert.equal(
  auto.dataset.theme,
  'paper',
  'Another tab can restore the live device preference',
);

// Every registered theme is selectable and declares an appearance, so the
// settings UI can be built from the registry rather than from a second list.
const registry = auto.theme.themes;
assert.ok(registry.length >= 4, 'the registry carries the approved themes');
for (const entry of registry) {
  assert.ok(entry.id && entry.mood, `${entry.id}: incomplete registration`);
  assert.ok(['light', 'dark'].includes(entry.appearance), `${entry.id}: appearance`);
  auto.theme.set(entry.id);
  assert.equal(auto.dataset.theme, entry.id);
  assert.equal(auto.dataset.appearance, entry.appearance);
  // Named in both interface languages, like every other learner-facing string.
  for (const ui of ['en', 'zh']) {
    assert.ok(copy[ui][`theme_${entry.id}`], `${ui}: ${entry.id} has no name`);
    assert.ok(copy[ui][`theme_${entry.id}Note`], `${ui}: ${entry.id} has no note`);
  }
}
// An unknown theme falls back rather than leaving the page with no tokens.
auto.theme.set('not-a-theme');
assert.equal(auto.dataset.theme, 'paper', 'an unknown id is not applied');

/* A preference written by an older build said 'light' or 'dark'. Each still
   names exactly one theme, so it is read as that theme: nobody loses their
   choice to an upgrade. */
assert.equal(themeHarness('light', true).dataset.theme, 'paper');
assert.equal(themeHarness('dark', false).dataset.theme, 'night-ink');

/* The browser chrome follows the resolved ground rather than a hardcoded
   pair, which is how it came to be serving a pre-brand green while the page
   had been ivory for some time. */
const chrome = themeHarness('deep-forest', false);
assert.equal(chrome.callbacks.chrome, '#1e3a3c', 'chrome matches the theme it frames');

const blocked = themeHarness(null, true, true);
blocked.theme.set('sage-field');
assert.equal(
  blocked.dataset.theme,
  'sage-field',
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
// Practice intentions are looked up the same silent way: c[intent + 'Name'] in
// the navigation and the shelf, c[intent] and c[intent + 'Note'] on the page.
// Adding an intention without its labels degrades to blank rather than failing.
for (const intent of practiceIntentions) {
  for (const ui of ['en', 'zh']) {
    for (const key of [intent, `${intent}Name`, `${intent}Note`]) {
      assert.ok(
        copy[ui][key],
        `${ui}: practice intention "${intent}" is missing ${key}`,
      );
    }
  }
}

// Every topic the catalog actually ships is named in both languages. A missing
// label is silent - the encounter simply falls back to the generic line - so
// the gap only ever shows up as one language quietly losing its framing.
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
for (const topic of catalogTopics) {
  for (const ui of ['en', 'zh']) {
    assert.ok(
      copy[ui][`topic_${topic}`],
      `${ui}: catalog topic "${topic}" has no label, so its encounters lose the framing the other language keeps`,
    );
  }
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
/* Colour has one owner now: theme.css, where a foundation layer names the
   approved palette and a semantic block per theme says what each colour is
   for. A semantic token may point at a foundation token, so resolve one hop
   before measuring - otherwise the check silently skips every token that was
   written the right way. */
const themeCss = fs.readFileSync('static/orena/theme.css', 'utf8');
const declarations = (block) =>
  Object.fromEntries(
    [...block.matchAll(/(--[\w-]+):\s*(#[0-9a-f]{6}|var\(--[\w-]+\))/gi)].map(
      (m) => [m[1], m[2]],
    ),
  );
const foundation = declarations(themeCss.split(':root {')[1].split('}')[0]);
function tokens(selector) {
  const block = themeCss.split(selector)[1].split('}')[0];
  const own = declarations(block);
  const resolve = (value) => {
    const reference = /^var\((--[\w-]+)\)$/.exec(value);
    return reference ? foundation[reference[1]] : value;
  };
  return Object.fromEntries(
    Object.entries(own).map(([name, value]) => [name, resolve(value)]),
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
/* Every registered theme, not just two. A palette that cannot carry its own
   text is not a theme, however good it looks in a swatch. */
const themeBlocks = [...themeCss.matchAll(/\[data-theme='([\w-]+)'\] \{/g)].map(
  (m) => [m[1], m[0]],
);
assert.ok(themeBlocks.length >= 4, 'every approved theme declares its tokens');
for (const [themeName, selector] of themeBlocks) {
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
/* Colour has exactly one owner. Two competing :root blocks - foundation.css
   and reference.css - used to declare overlapping palettes, and which one won
   was decided by <link> order. That is how --paper came to be on-brand while
   --sage was still a pre-brand mint, and it is why a third theme could not be
   added without fighting the cascade. */
for (const name of ['foundation', 'world', 'experiences', 'reference', 'rooms']) {
  const css = fs.readFileSync(`static/orena/${name}.css`, 'utf8');
  const blocks = css.match(/:root[^{]*\{[^}]*\}/g) || [];
  for (const block of blocks) {
    const colours = block.match(/--[\w-]+:\s*#[0-9a-f]{3,8}/gi) || [];
    assert.equal(
      colours.length,
      0,
      `${name}.css declares colour tokens (${colours.slice(0, 3).join(', ')}); theme.css owns colour`,
    );
  }
}

/* Every theme names an appearance, and appearance is styled separately from
   identity - form controls, scrollbars and the part-of-speech inks need to
   know how bright a theme is, not which theme it is. */
assert.match(themeCss, /\[data-appearance='light'\] \{\s*color-scheme: light;/);
assert.match(themeCss, /\[data-appearance='dark'\] \{\s*color-scheme: dark;/);
for (const ink of ['--word-thing', '--word-action', '--word-detail']) {
  const uses = themeCss.split(ink).length - 1;
  assert.equal(uses, 2, `${ink} is defined once per appearance, not per theme`);
}

/* The canonical brand colour stays canonical. It is kept in the foundation
   layer under its own name and given a contrast-safe partner, rather than
   being quietly redefined to whatever passes a check. */
assert.equal(foundation['--o-orange'], '#ff7a3d', 'Orena Orange is canonical');
assert.equal(foundation['--o-forest-ink'], '#0e2a47', 'Forest Ink is canonical');
assert.equal(foundation['--o-paper-ivory'], '#f8f3e9', 'Paper Ivory is canonical');
assert.ok(foundation['--o-action-warm'], 'the contrast-safe action partner exists');
assert.notEqual(
  foundation['--o-action-warm'],
  foundation['--o-orange'],
  'the action colour is a partner, not a replacement for the brand colour',
);

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
