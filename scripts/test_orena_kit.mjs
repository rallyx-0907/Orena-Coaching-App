/* Gate for the new learner UI's kit (D-088, D-089, D-091; Design Contract rules 16, 30, 34, 41, 46).

   - kit/tokens.css holds exactly the pinned design's light and dark tokens, and kit/device.css
     exactly its device and focus variables (docs/design/canonical-ui/screens/Orena.dc.html);
   - text and controls pass AA in both themes, or the pair is a recorded deviation;
   - icons come from the pinned Lucide release and every icon the new UI asks for exists;
   - no colour literal lives anywhere in the new UI but kit/tokens.css;
   - the new UI never imports the old UI's presentation or stylesheets;
   - kit/html.js escapes by default. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = 'static/orena';
const NEW_TREE = ['kit', 'shell', 'screens', 'copy', 'agent'].map((dir) => path.join(ROOT, dir));
const PIN = fs.readFileSync('docs/design/canonical-ui/screens/Orena.dc.html', 'utf8');
const helmet = PIN.slice(PIN.indexOf('<helmet>'), PIN.indexOf('</helmet>'));

function block(source, selector) {
  const at = source.indexOf(selector);
  assert.ok(at >= 0, `${selector} present`);
  const open = source.indexOf('{', at);
  let depth = 0;
  for (let i = open; i < source.length; i += 1) {
    if (source[i] === '{') depth += 1;
    else if (source[i] === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(open + 1, i);
    }
  }
  throw new Error(`unclosed ${selector}`);
}

function vars(body) {
  const out = {};
  for (const match of body.matchAll(/--([\w-]+)\s*:\s*([^;]+)(;|$)/g)) out[match[1]] = norm(match[2]);
  return out;
}

function norm(value) {
  return String(value).replace(/\s+/g, '').replace(/0(\.\d)/g, '$1').toLowerCase();
}

const tokens = fs.readFileSync(path.join(ROOT, 'kit/tokens.css'), 'utf8');
const device = fs.readFileSync(path.join(ROOT, 'kit/device.css'), 'utf8');

// 1. Tokens: both themes, exactly the design's - except the smallest AA adjustments the human
// approved (D-093, rule 41) and the two tokens they added (a fill for white-on-violet controls, the
// ink of the red count badge).
const ADJUSTED = {
  dark: { text3: '#858599', accent: '#847ff6' },
  light: { text3: '#6e6e86', green: '#117e52', red: '#d0292e', amber: '#a16000' },
};
const ADDED = ['accent-fill', 'accent-fill-hover', 'accent-fill-press', 'badge-ink'];
for (const theme of ['dark', 'light']) {
  const design = vars(block(helmet, `body[data-theme="${theme}"]`));
  const ours = vars(block(tokens, `:root[data-theme="${theme}"]`));
  // The design's bezel and frame border draw the prototype device; the product has none (N-4).
  for (const prototypeOnly of ['bezel', 'frame-border']) delete design[prototypeOnly];
  assert.deepEqual(Object.keys(ours).sort(), [...Object.keys(design), ...ADDED].sort(), `${theme}: the design's token names plus the D-093 additions`);
  for (const [name, value] of Object.entries(design)) {
    const expected = ADJUSTED[theme][name] ? norm(ADJUSTED[theme][name]) : value;
    assert.equal(ours[name], expected, `${theme} --${name} is ${ADJUSTED[theme][name] ? 'the D-093 value' : "the design's value"}`);
  }
}
const hues = vars(block(helmet, 'body{--tone1'.replace('body{', 'body{')));
const ourRoot = vars(block(tokens, ':root {'));
for (const [name, value] of Object.entries(hues)) assert.equal(ourRoot[name], value, `--${name} is the design's value`);

// 2. Device and focus variables: exactly the design's, minus the prototype's bezel frame.
for (const kind of ['desktop', 'mobile']) {
  const design = vars(block(helmet, `body[data-device="${kind}"]`));
  for (const name of Object.keys(design)) if (name.startsWith('frame-')) delete design[name];
  const ours = vars(block(device, `:root[data-device="${kind}"]`));
  assert.deepEqual(ours, design, `${kind}: device variables are the design's`);
}
assert.deepEqual(vars(block(device, ':root[data-focus="1"]')), vars(block(helmet, 'body[data-focus="1"]')), 'focus mode hides what the design hides');

// 3. AA contrast in both themes (rule 41). Pairs are the ones the design draws as text or icons.
function rgb(hex) {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h.slice(0, 6);
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
}
function lum(hex) {
  return rgb(hex)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
}
function contrast(a, b) {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}
// Every pair the design draws as text or an icon on a ground. Interface text here is small
// (11-15px, the bold ones below 18.66px), so AA is 4.5:1 for every pair, in both themes.
const PAIRS = [
  ['text', 'bg'], ['text', 'surface'], ['text', 'surface2'],
  ['muted', 'bg'], ['muted', 'surface'], ['muted', 'surface2'],
  ['text3', 'bg'], ['text3', 'surface'], ['text3', 'surface2'],
  ['accent', 'bg'], ['accent', 'surface'], ['accent', 'accent-soft'], ['accent-text', 'accent-soft'], ['accent-text', 'surface'],
  ['accent-ink', 'accent-fill'], ['accent-ink', 'accent-fill-hover'], ['accent-ink', 'accent-fill-press'],
  // kit.css's .o-banner__glyph (every kind: ok/info/warn/err) reads --badge-ink against its own
  // kind's solid fill, not --accent-ink (D-091 kit fidelity pass - white ink fails AA against all
  // four in dark theme; --badge-ink is the same fix grammar-concept.css already used for its own
  // mistake/quiz glyphs).
  ['badge-ink', 'red'], ['badge-ink', 'green'], ['badge-ink', 'amber'], ['badge-ink', 'accent-text'],
  ['green', 'green-soft'], ['red', 'red-soft'], ['amber', 'amber-soft'], ['ai-ink', 'ai-soft'],
  ['green', 'surface'], ['red', 'surface'], ['amber', 'surface'],
  // heroMedia()'s overlay text/pill (components.css .c-hero__content/.c-hero__pill) and the toast
  // both draw white ink on this fixed-dark, theme-independent pairing (D-093 AA fix: the hero's
  // own `background-color` fallback used to be the themed --surface2, near-white in light theme).
  ['toast-ink', 'toast-bg'],
];
const measured = [];
for (const theme of ['dark', 'light']) {
  const palette = { ...vars(block(tokens, ':root {')), ...vars(block(tokens, `:root[data-theme="${theme}"]`)) };
  for (const [ink, ground] of PAIRS) {
    const ratio = contrast(palette[ink], palette[ground]);
    measured.push(`${theme} ${ink}/${ground} ${ratio.toFixed(2)}`);
    assert.ok(ratio >= 4.5, `${theme}: --${ink} on --${ground} is ${ratio.toFixed(2)}:1, needs 4.5:1`);
  }
}

// 4. Icons: the pinned Lucide release, and every name the new UI asks for exists.
const iconsSource = fs.readFileSync(path.join(ROOT, 'kit/icons.js'), 'utf8');
assert.match(iconsSource, /GENERATED by scripts\/sync_lucide_icons\.py/, 'icons.js is generated, not hand-edited');
const release = iconsSource.match(/LUCIDE_RELEASE = "([\d.]+)"/)[1];
const sync = fs.readFileSync('scripts/sync_lucide_icons.py', 'utf8');
assert.equal(sync.match(/RELEASE = "([\d.]+)"/)[1], release, 'icons.js was generated from the pinned release');
const available = new Set([...iconsSource.matchAll(/^\s{2}"([a-z0-9-]+)":/gm)].map((m) => m[1]));
for (const name of [...sync.matchAll(/^\s{8}"([a-z0-9-]+)",$/gm)].map((m) => m[1])) assert.ok(available.has(name), `icon ${name} generated`);

function walk(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? walk(full) : [full];
  });
}
const files = [...NEW_TREE.flatMap(walk), path.join(ROOT, 'main.js')].filter((file) => /\.(js|css)$/.test(file));
assert.ok(files.length > 10, 'the new UI tree is present');
for (const file of files) {
  const source = fs.readFileSync(file, 'utf8');
  for (const match of source.matchAll(/\bicon\(\s*'([a-z0-9-]+)'/g)) assert.ok(available.has(match[1]), `${file}: icon "${match[1]}" is in kit/icons.js`);
  // 5. One colour owner.
  if (file.endsWith(path.join('kit', 'tokens.css')) || file.endsWith(path.join('kit', 'icons.js'))) continue;
  const code = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  const literal = code.match(/(?<![&\w])#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/);
  assert.equal(literal, null, `${file}: colour literal ${literal?.[0]} - colours live only in kit/tokens.css`);
  // White text never sits on --accent: filled controls use --accent-fill (D-093).
  if (file.endsWith('.css')) {
    for (const rule of code.split('}')) {
      if (/background:\s*var\(--accent\)\s*;/.test(rule) && /(^|[^-])color:\s*var\(--(accent-ink|badge-ink)\)/.test(rule)) {
        assert.fail(`${file}: white ink on --accent - use --accent-fill (D-093)`);
      }
      // Nor on a solid semantic fill: white on --red/--green/--amber fails AA in the dark theme,
      // where --badge-ink is the ink the pairs above hold to AA.
      if (/background:\s*var\(--(red|green|amber)\)\s*;/.test(rule) && /(^|[^-])color:\s*var\(--accent-ink\)/.test(rule)) {
        assert.fail(`${file}: white ink on a solid --red/--green/--amber fill - use --badge-ink`);
      }
    }
  }
  // 6. The new UI does not import the old UI.
  for (const spec of source.matchAll(/(?:import|from)\s*\(?\s*['"]([^'"]+)['"]/g)) {
    assert.ok(!/(^|\/)ui\/[\w-]+\.js$/.test(spec[1]), `${file} imports old presentation ${spec[1]}`);
    assert.ok(!/(theme|foundation|world|rooms|experiences|reference|reader|listening|dictation|speaking|writing|home|shell)\.css$/.test(spec[1]) || spec[1].includes('/shell/') || spec[1].includes('screens/'), `${file} imports an old stylesheet ${spec[1]}`);
  }
}
const template = fs.readFileSync('templates/orena/next.html', 'utf8');
for (const old of ['theme.css', 'theme.js', 'foundation.css', 'world.css', 'rooms.css', '/orena-assets/app.js']) {
  assert.ok(!template.includes(`/orena-assets/${old}`), `next.html does not load the old ${old}`);
}

// 7. Markup escapes by default.
const { html, raw } = await import('../static/orena/kit/html.js');
assert.equal(String(html`<p>${'<b>&"'}</p>`), '<p>&lt;b&gt;&amp;&quot;</p>');
assert.equal(String(html`<p>${raw('<b>x</b>')}</p>`), '<p><b>x</b></p>');
assert.equal(String(html`<ul>${['<a>', html`<li>ok</li>`]}</ul>`), '<ul>&lt;a&gt;<li>ok</li></ul>');
assert.equal(String(html`${null}${false}${undefined}${0}`), '0');

// 8. Two verify-fix regressions (kit group, languages-1/languages-2):
const componentsCss = fs.readFileSync(path.join(ROOT, 'kit/components.css'), 'utf8');
assert.match(
  block(componentsCss, '.c-hero {'),
  /background-color:\s*var\(--toast-bg\)/,
  '.c-hero: no-image fallback stays the fixed-dark --toast-bg, not a themed surface (D-093 AA - white overlay text must hold contrast with no cover photo)',
);
const kitCss = fs.readFileSync(path.join(ROOT, 'kit/kit.css'), 'utf8');
assert.match(
  block(kitCss, '.o-chip {'),
  /flex-shrink:\s*0/,
  '.o-chip: never shrinks below its label (its row scrolls or wraps instead) - a shrunk chip clips its own text',
);

console.log(`Orena kit: tokens and device variables are the pinned design's, AA holds in both themes (${measured.length} pairs; D-093 adjustments), icons are lucide-static@${release}, one colour owner, no old UI imported: PASS`);
