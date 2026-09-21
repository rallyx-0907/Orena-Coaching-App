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
// D-066: there is one visual system, so it marks the document and reads nothing.
const themeCode = fs.readFileSync('static/orena/theme.js', 'utf8');
function themeHarness(blocked = false) {
  const dataset = {};
  const callbacks = {};
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
  vm.runInNewContext(themeCode, {
    document,
    getComputedStyle: () => ({
      getPropertyValue: (name) => (name === '--paper' ? '#050310' : ''),
    }),
    localStorage: {
      getItem: () => {
        throw Error(blocked ? 'denied' : 'theme.js must not read a stored theme');
      },
    },
  });
  return { dataset, callbacks };
}
for (const blocked of [false, true]) {
  const page = themeHarness(blocked);
  assert.equal(page.dataset.theme, 'glass', 'the one theme is applied');
  assert.equal(page.dataset.appearance, 'dark', 'and it is dark');
  assert.equal(page.callbacks.chrome, '#050310', 'chrome matches the ground it frames');
}
assert.ok(
  !fs.existsSync('static/orena/theme-paper.css') &&
    !/data-theme='(?:ink|paper|sepia)'/.test(fs.readFileSync('static/orena/theme.css', 'utf8')),
  'Ink, Paper and sepia are retired (D-066)',
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
  // A token may point at another semantic token, or at the foundation.
  const resolve = (value, hops = 0) => {
    const reference = /^var\((--[\w-]+)\)$/.exec(value);
    if (!reference || hops > 4) return value;
    const next = own[reference[1]] ?? foundation[reference[1]];
    return next === undefined ? undefined : resolve(next, hops + 1);
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
  // The D-059 semantic layer: text, links and progress figures on both grounds.
  ['--surface-canvas', '--text-primary', 4.5],
  ['--surface-canvas', '--text-secondary', 4.5],
  ['--surface-primary', '--text-secondary', 4.5],
  ['--surface-canvas', '--action-text', 4.5],
  ['--surface-primary', '--action-text', 4.5],
  ['--surface-canvas', '--progress-text', 4.5],
];
/* Every registered theme, not just two. A palette that cannot carry its own
   text is not a theme, however good it looks in a swatch. */
const themeBlocks = [...themeCss.matchAll(/\[data-theme='([\w-]+)'\] \{/g)].map(
  (m) => [m[1], m[0]],
);
assert.deepEqual(
  themeBlocks.map(([name]) => name),
  ['glass'],
  'Dark Glass is the only theme (D-066)',
);
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

/* One appearance, dark, and the part-of-speech inks that track it. */
assert.match(themeCss, /color-scheme: dark;/);
assert.doesNotMatch(themeCss, /color-scheme: light|data-appearance/);
for (const ink of ['--word-thing', '--word-action', '--word-detail'])
  assert.equal(themeCss.split(ink + ':').length - 1, 1, `${ink} is defined once`);

/* The colours are the pinned baseline's (D-066). theme.css is checked against
   docs/design/canonical-ui/tokens.json rather than against a second copy of the
   values written here, so the stylesheet cannot drift from the baseline and the
   baseline cannot be edited to match the stylesheet without the pin changing. */
const baseline = JSON.parse(fs.readFileSync('docs/design/canonical-ui/tokens.json', 'utf8'));
const norm = (value) =>
  String(value)
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/(\.\d*?)0+(?!\d)/g, '$1')
    .replace(/\.(?=\D)/g, '');
const css = norm(themeCss);
const mustCarry = (label, value) =>
  assert.ok(css.includes(norm(value)), `theme.css does not carry the baseline's ${label}: ${value}`);
mustCarry('canvas', baseline.base.canvas);
mustCarry('ink', baseline.base.ink);
for (const layer of baseline.cosmicField.layers) mustCarry('cosmic layer', layer);
mustCarry('cosmic size', baseline.cosmicField.size);
for (const [name, value] of Object.entries(baseline.glass)) mustCarry(`glass.${name}`, value);
for (const [name, value] of Object.entries(baseline.accent)) {
  if (name === 'gradient') continue; // written from its two stops, checked below
  mustCarry(`accent.${name}`, value);
}
for (const [name, value] of Object.entries(baseline.semantic)) {
  // warn and bad are oklch in the baseline and a hex here (see the note in theme.css).
  if (!value.startsWith('oklch')) mustCarry(`semantic.${name}`, value);
}
assert.equal(foundation['--o-accent-top'], '#9b67ff');
assert.equal(foundation['--o-accent-base'], '#6a32e0');
assert.equal(foundation['--o-accent-ink'], '#d5c0ff');
assert.equal(foundation['--o-canvas'], '#050310');
assert.equal(foundation['--o-orange'], '#ff7a3d', 'Orena Orange stays the artwork colour');
for (const [skill, hue] of Object.entries(baseline.skillHue)) {
  const token = { Reading: 'reading', Listening: 'listening', Speaking: 'speaking', Writing: 'writing', Vocabulary: 'vocabulary', Dictation: 'dictation' }[skill];
  assert.ok(themeCss.includes(`--domain-${token}: oklch(0.78 0.12 ${hue});`), `${skill} hue ${hue}`);
}
/* Semantic colour is ink, not a fill: no surface token is a status colour. */
const glass = tokens("[data-theme='glass'] {");
for (const surface of Object.keys(glass).filter((name) => name.startsWith('--surface-')))
  for (const status of ['--o-good', '--o-warn', '--o-bad', '--o-info'])
    assert.notEqual(glass[surface], foundation[status], `${surface} is not painted with ${status}`);

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
  'Golden Star: Dark Glass foundation pinned to the baseline, first paint, paired panel tokens, EN/ZH patterns, contextual drafts, continuation and retry-safe evidence PASS',
);
