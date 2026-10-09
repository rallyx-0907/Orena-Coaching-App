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
// Human-approved Visual Skin owns visual treatment; screen pins still own composition.
const skins = ['EN', 'ZH'].map((lang) => {
  const exported = fs.readFileSync(`docs/design/canonical-ui/screens/Orena Visual Skin ${lang}.html`, 'utf8');
  const template = /<script type="__bundler\/template">([\s\S]*?)<\/script>/.exec(exported);
  assert.ok(template, `${lang}: original Visual Skin template present`);
  return JSON.parse(template[1]);
});
const skinDark = vars(/const D = \{([^}]+)\}/.exec(skins[0])[1].replace(/'([^']+)'\s*:\s*'([^']+)'/g, '$1:$2;'));
const skinPage = /document.body.style.background = dark \? '([^']+) fixed'/.exec(skins[0])[1];
for (const source of skins) {
  assert.ok(source.includes(skinPage));
  assert.ok(source.includes(skinDark['ai-soft'].toUpperCase()));
  assert.ok(source.includes(skinDark['ai-ink'].toUpperCase()));
}

// 1. Tokens: both themes, exactly the design's - except the smallest AA adjustments the human
// approved (D-093, rule 41) and the two tokens they added (a fill for white-on-violet controls, the
// ink of the red count badge).
const ADJUSTED = {
  dark: { text3: '#858599', accent: '#847ff6' },
  // bg/sh1/text3: the human's raised-card page (D-151, 2026-10-09), text3 kept at AA on it.
  light: { text3: '#68687f', bg: '#ecedf4', green: '#117e52', red: '#d0292e', amber: '#a16000', sh1: '0 1px 2px rgba(23, 23, 50, .07), 0 3px 12px rgba(23, 23, 50, .07)' },
};
const ADDED = ['accent-fill', 'accent-fill-hover', 'accent-fill-press', 'badge-ink'];
for (const theme of ['dark', 'light']) {
  const design = vars(block(helmet, `body[data-theme="${theme}"]`));
  const ours = vars(block(tokens, `:root[data-theme="${theme}"]`));
  // The design's bezel and frame border draw the prototype device; the product has none (N-4).
  for (const prototypeOnly of ['bezel', 'frame-border']) delete design[prototypeOnly];
  assert.deepEqual(Object.keys(ours).sort(), [...Object.keys(design), ...ADDED].sort(), `${theme}: the design's token names plus the D-093 additions`);
  for (const [name, value] of Object.entries(design)) {
    const skinValue = theme === 'dark' ? ({ page: skinPage, 'ai-soft': skinDark['ai-soft'], 'ai-ink': skinDark['ai-ink'] })[name] : null;
    const expected = norm(ADJUSTED[theme][name] || skinValue || value);
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
// Oklch mixing with black scales linear RGB by the cube of the retained share.
// The darker action step must carry small white labels in every new palette.
for (const [, name, base] of tokens.matchAll(/data-palette="(orchid|blue|rose)"\]\s*\{\s*--palette-base:\s*(#[\da-f]+);/gi)) {
  const ratio = 1.05 / (lum(base) * .9 ** 3 + .05);
  assert.ok(ratio >= 4.5, `${name}: white/action fill ${ratio.toFixed(2)}:1 needs AA`);
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
const template = fs.readFileSync('templates/orena/index.html', 'utf8');
for (const old of ['theme.css', 'theme.js', 'foundation.css', 'world.css', 'rooms.css', '/orena-assets/app.js']) {
  assert.ok(!template.includes(`/orena-assets/${old}`), `index.html does not load the old ${old}`);
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

// BACKDROP (PUB-4, D-16W; Orena.dc.html body[data-backdrop=on], Orena-Admin.dc.html, Onboarding.dc.html). The learner shell, the
// Admin shell and Onboarding draw the design's photo under the design's scrim; the rail, the desktop top bar and the phone bar
// are glass at the design's alpha; the photo shows fully (no veil); every content surface stays solid. Accessibility never
// redesigns the baseline, so AA over the photo is met by scoped TEXT tokens (kit/tokens.css: --bd-chrome-*, --bd-page-*) and,
// for Onboarding's aside, the least extra alpha. ADJUSTED values are listed in docs/project/UI_BACKEND_GAPS.md (PUB-4).
// The photo's lightest/darkest blurred region behind each surface comes from scripts/fixtures/backdrop_extremes.json
// (scripts/measure_backdrop_extremes.py; the photos' sha256 are checked here).
{
  const read = (p) => fs.readFileSync(p, 'utf8');
  const shellCss = read(path.join(ROOT, 'shell/shell.css'));
  const adminCss = read(path.join(ROOT, 'screens/admin/admin.css'));
  const onboardingCss = read(path.join(ROOT, 'screens/onboarding/onboarding.css'));
  const fixture = JSON.parse(read('scripts/fixtures/backdrop_extremes.json'));
  const sectionAt = tokens.indexOf('The backdrop (PUB-4');
  assert.ok(sectionAt > 0, 'tokens.css carries the backdrop section');
  const backdropTokens = tokens.slice(sectionAt);

  // 1. Present on the three surfaces, per theme and device, from the four pinned photos; the bytes are the design's.
  for (const [selector, label] of [['.o-frame', 'learner shell'], ['.a-shell', 'Admin shell']]) {
    assert.ok(shellCss.includes(`${selector}::before`) && shellCss.includes(`${selector}::after`), `${label}: photo and scrim layers`);
  }
  assert.match(shellCss, /\.o-frame::before,\s*\.a-shell::before \{\s*background: var\(--bd-img\)/, 'the photo layer');
  assert.match(shellCss, /\.o-frame::after,\s*\.a-shell::after \{\s*background: var\(--bd-scrim\);\s*opacity: var\(--bd-strength\);/, "the design's scrim at its strength");
  for (const [theme, device, name] of [['light', 'desktop', 'paper-wide'], ['dark', 'desktop', 'midnight-wide'], ['light', 'mobile', 'paper-tall'], ['dark', 'mobile', 'midnight-tall']]) {
    assert.ok(shellCss.includes(`public/bg/${name}.jpg`), `${theme}/${device}: ${name} is mapped in the shell`);
    assert.ok(onboardingCss.includes(`public/bg/${name}.jpg`), `${theme}/${device}: ${name} is mapped in Onboarding`);
    assert.ok(fs.readFileSync(`docs/design/canonical-ui/screens/assets/bg/${name}.jpg`).equals(fs.readFileSync(`static/orena/public/bg/${name}.jpg`)), `${name}.jpg is the pinned design's file`);
  }
  assert.match(onboardingCss, /\.s-onboarding \{[^}]*background: var\(--ob-scrim\), var\(--ob-img\)/, 'Onboarding: its scrim over its photo');
  assert.match(onboardingCss, /\.s-onboarding__aside \{[^}]*background: var\(--ob-aside\);[^}]*backdrop-filter: blur\(2px\)/, "Onboarding: the aside is translucent with the design's 2px blur");
  assert.doesNotMatch(onboardingCss, /s-onboarding__main \{[^}]*(background|backdrop-filter)/, 'Onboarding: no panel over the photo (the design draws none)');
  assert.doesNotMatch(tokens + shellCss + adminCss + onboardingCss, /--bd-veil|--ob-panel/, 'no veil and no panel: the photo shows fully');

  // 2. The design's own values, exactly: scrims, strength, glass alpha, blur.
  const pinScrim = (theme) => helmet.match(new RegExp(`body\\[data-backdrop="on"\\]\\[data-theme="${theme}"\\]\\{--bdscrim:(radial-gradient\\([^;]*?\\));--chrome:(rgba\\([^)]*\\));--chromeBlur:([^;]*);`));
  for (const theme of ['dark', 'light']) {
    const [, scrim, chrome, blur] = pinScrim(theme);
    const rule = theme === 'dark' ? ":root[data-theme='dark'] {" : ":root:not([data-theme='dark']) {";
    const bd = vars(block(backdropTokens, rule));
    const squash = (v) => v.toLowerCase().replace(/\s+/g, '').replace(/\.(\d)/g, '0.$1').replace(/\b0\./g, '.');
    assert.equal(squash(bd['bd-scrim']), squash(scrim).replace(/56%46%/, '56%46%'), `${theme}: the app scrim is the design's`);
    assert.equal(squash(bd['bd-chrome']), squash(chrome), `${theme}: the glass alpha is the design's`);
    assert.equal(squash(bd['bd-chrome-blur']), squash(blur), `${theme}: the blur is the design's`);
    assert.equal(bd['bd-strength'], '.6', 'the design backdropDim default');
  }
  assert.equal(fixture.strength, 0.6, 'the fixture was measured at the shipped strength');
  assert.match(PIN, /backdropDim\?\?\.6/, 'the design strength is .6');

  // 3. Glass chrome (learner rail / top bar / phone bar; Admin rail / header / chips); the edge is --edge-light (D-147).
  for (const [css, selectors] of [[shellCss, ['.o-rail', '.o-topbar', '.o-bnav']], [adminCss, ['.a-rail', '.a-top', '.a-mnav']]]) {
    for (const selector of selectors) {
      const body = block(css, `\n${selector} {`);
      assert.match(body, /background:\s*var\(--bd-chrome\)/, `${selector}: glass ground`);
      assert.match(body, /backdrop-filter:\s*var\(--bd-chrome-blur\)/, `${selector}: the design's blur`);
      assert.match(body, /box-shadow:[^;]*var\(--edge-light\)/, `${selector}: the edge is --edge-light, not a coloured line`);
      assert.doesNotMatch(body, /border[^:]*:[^;]*(var\(--(accent|ring|ai-line)|#|rgba)/, `${selector}: no violet or coloured outline (D-147)`);
    }
  }
  // Solid fallbacks and no learner control.
  assert.match(shellCss, /:root\[data-backdrop='off'\]/, 'a non-UI kill switch exists');
  assert.match(shellCss, /@media \(prefers-reduced-transparency: reduce\)/, 'reduced transparency gets solid chrome');
  assert.match(shellCss, /@supports not \(\(backdrop-filter: blur\(1px\)\)/, 'no backdrop-filter gets solid chrome');
  assert.match(shellCss, /@media not \(prefers-reduced-transparency: reduce\) \{\s*@supports \(\(backdrop-filter/, 'the scoped text tokens apply only while the photo is drawn');
  for (const dir of ['shell', 'screens', 'kit']) {
    for (const file of fs.readdirSync(path.join(ROOT, dir), { recursive: true }).filter((f) => f.endsWith('.js'))) {
      assert.doesNotMatch(read(path.join(ROOT, dir, file)), /data-backdrop|dataset\.backdrop/, `${dir}/${file}: the backdrop has no learner control`);
    }
  }

  // 4. Content stays solid: only the shell chrome, Admin chrome, Onboarding's aside and CTA blur, and the two pre-existing media
  // overlays use backdrop-filter; the --bd-/--ob- tokens are used nowhere else.
  const FILTER_OK = new Set(['kit/components.css', 'shell/shell.css', 'screens/admin/admin.css', 'screens/onboarding/onboarding.css', 'screens/listening/listening.css']);
  const TOKEN_OK = new Set(['kit/tokens.css', 'shell/shell.css', 'screens/admin/admin.css', 'screens/onboarding/onboarding.css']);
  for (const file of fs.readdirSync(ROOT, { recursive: true }).map((f) => f.replace(/\\/g, '/'))) {
    if (!/\.(css|js)$/.test(file) || file.startsWith('vendor/') || file.startsWith('public/')) continue;
    const text = read(path.join(ROOT, file));
    if (/backdrop-filter/.test(text)) assert.ok(FILTER_OK.has(file), `${file}: a content surface may not use backdrop-filter`);
    if (/--(bd|ob)-(img|scrim|strength|chrome|page|aside)/.test(text)) assert.ok(TOKEN_OK.has(file), `${file}: uses a backdrop token outside the shell, Admin and Onboarding`);
  }
  assert.doesNotMatch(read(path.join(ROOT, 'kit/components.css')), /var\(--(bd|ob)-/, 'shared components keep their solid surfaces');

  // 5. AA over the worst blurred region of the photo (fixture), with the scoped tokens, for every text pair the surfaces draw.
  const hexOf = (h) => rgb(h).map((c) => c * 255);
  const lumRgb = (c) => c.map((v) => v / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)).reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
  const contrastRgb = (a, b) => { const [x, y] = [lumRgb(a), lumRgb(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const over = (fg, a, bg) => fg.map((c, i) => c * a + bg[i] * (1 - a));
  const rgbaOf = (value) => { const m = value.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([.\d]+)\)/); return { c: m.slice(1, 4).map(Number), a: Number(m[4]) }; };
  const crypto = await import('node:crypto');
  const table = [];
  const need = (label, value) => { assert.ok(value >= 4.5, `${label} is ${value.toFixed(2)}:1, AA needs 4.5`); table.push(`${label} ${value.toFixed(2)}`); };
  for (const theme of ['dark', 'light']) {
    const t = vars(block(tokens, `:root[data-theme="${theme}"]`));
    const rule = theme === 'dark' ? ":root[data-theme='dark'] {" : ":root:not([data-theme='dark']) {";
    const bd = vars(block(backdropTokens, rule));
    const chrome = rgbaOf(bd['bd-chrome']);
    const scoped = { chrome: { text: t.text, muted: t.muted, text3: bd['bd-chrome-text3'], accent: bd['bd-chrome-accent'] }, page: { text: t.text, muted: bd['bd-page-muted'], text3: bd['bd-page-text3'] } };
    for (const [key, entry] of Object.entries(fixture.regions)) {
      if (!key.includes(`/${theme}/`)) continue;
      const sha = crypto.createHash('sha256').update(fs.readFileSync(`static/orena/public/bg/${entry.photo}.jpg`)).digest('hex');
      assert.equal(sha, entry.sha256, `${entry.photo}.jpg is the photo the fixture measured (run scripts/measure_backdrop_extremes.py)`);
      const [kind, , region] = key.split('/');
      if (region === 'aside') continue;
      const isChrome = kind === 'shell' && ['rail', 'topbar', 'bar', 'chips'].includes(region);
      const tokensHere = isChrome ? scoped.chrome : scoped.page;
      for (const [name, value] of Object.entries(tokensHere)) {
        const worst = Math.min(...[entry.lightest, entry.darkest].map((g) => contrastRgb(hexOf(value), isChrome ? over(chrome.c, chrome.a, g) : g)));
        need(`${key} --${name}`, worst);
      }
    }
    // The scoped tokens stay valid on the solid surfaces they also reach, and keep their order (text >= muted >= text3 in strength).
    for (const [name, value] of [['muted', bd['bd-page-muted']], ['text3', bd['bd-page-text3']], ['text3', bd['bd-chrome-text3']], ['accent', bd['bd-chrome-accent']]]) {
      for (const ground of ['bg', 'surface', 'surface2']) {
        assert.ok(contrast(value, t[ground]) >= 4.5, `${theme} scoped --${name} ${value} on --${ground} stays AA`);
      }
    }
    // Chrome shifts are small: the base token moved no more than 12% toward --text.
    for (const [name, value] of [['text3', bd['bd-chrome-text3']], ['accent', bd['bd-chrome-accent']]]) {
      const share = hexOf(t[name]).map((c, i) => (c === hexOf(t.text)[i] ? 0 : (hexOf(value)[i] - c) / (hexOf(t.text)[i] - c))).filter((s) => Number.isFinite(s)).reduce((a, b) => Math.max(a, b), 0);
      assert.ok(share <= 0.13, `${theme} chrome --${name} moved ${(share * 100).toFixed(0)}% toward --text`);
    }
    // --accent as text directly on the photo is the recorded exception (it is also the fill of bars and dots): report, never assume.
    for (const key of [`shell/${theme}/main/desktop`, `shell/${theme}/page/mobile`]) {
      const entry = fixture.regions[key];
      const worst = Math.min(...[entry.lightest, entry.darkest].map((g) => contrastRgb(hexOf(t.accent), g)));
      table.push(`RECORDED-EXCEPTION ${key} --accent ${worst.toFixed(2)}`);
    }
  }
  // Onboarding's aside: white ink at the step list's alphas, over the lightest and darkest aside region, at each gradient stop.
  for (const theme of ['dark', 'light']) {
    const rule = theme === 'dark' ? ":root[data-theme='dark'] {" : ":root:not([data-theme='dark']) {";
    const stops = [...vars(block(backdropTokens, rule))['ob-aside'].matchAll(/rgba\((\d+),(\d+),(\d+),([.\d]+)\)/g)].map((m) => ({ c: m.slice(1, 4).map(Number), a: Number(m[4]) }));
    assert.equal(stops.length, 3, "the aside gradient has the design's three stops");
    const design = [0.82, 0.74, 0.55];
    stops.forEach((s, i) => assert.ok(s.a >= design[i], `${theme}: aside stop ${i + 1} is not below the design's ${design[i]}`));
    const entry = fixture.regions[`onboarding/${theme}/aside`];
    for (const [ink, label] of [[1, 'white'], [0.8, 'white 80% (done step)'], [0.7, 'white 70% (subhead)'], [0.5, 'white 50% (upcoming step)']]) {
      const worst = Math.min(...stops.flatMap((s) => [entry.lightest, entry.darkest].map((g) => {
        const surface = over(s.c, s.a, g);
        return contrastRgb(over([255, 255, 255], ink, surface), surface);
      })));
      need(`onboarding/${theme}/aside ${label}`, worst);
    }
  }
  console.log(`BACKDROP contrast (worst region): ${table.join('; ')}`);
}

console.log(`Orena kit: tokens and device variables are the pinned design's, AA holds in both themes (${measured.length} pairs; D-093 adjustments), icons are lucide-static@${release}, one colour owner, no old UI imported: PASS`);
