/* The three language layers are independent (D-079, docs/product/ORENA_LANGUAGE_COHERENCE.md):
   interface (chrome), support (explanation, guidance), target (the material). This gate locks the
   source of truth - product/languages.js and the app's use of it - not individual strings, so a
   regression of the kind that mixed English, Vietnamese and Chinese on one screen fails here:
   the interface read from the support language, support read from the target, content following
   the interface, or a reload or a stale cache moving one layer away from the others. */
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  INTERFACE_KEY,
  interfaceLanguage,
  supportLanguage,
  learningLanguage,
  resolveLanguages,
  guidanceLocale,
  matchLocale,
} from '../static/orena/product/languages.js';

const supported = ['en', 'vi', 'zh']; // the locales copy/index.js ships (LOCALES)
const resolve = ({ stored = '', browser = [], support = '', native = '', active = '' }) =>
  resolveLanguages({ stored, browser, supported, profile: { support_language: support, native_language: native }, active });

// --- The human's acceptance cases --------------------------------------------------------------
assert.deepEqual(resolve({ stored: 'en', support: 'vi', active: 'zh' }), { ui: 'en', support: 'vi', language: 'zh' }, 'CASE A');
assert.deepEqual(resolve({ stored: 'vi', support: 'vi', active: 'en' }), { ui: 'vi', support: 'vi', language: 'en' }, 'CASE B');
assert.deepEqual(resolve({ stored: 'zh', support: 'en', active: 'zh' }), { ui: 'zh', support: 'en', language: 'zh' }, 'CASE C');

// --- No layer is inferred from another -----------------------------------------------------------
// The interface resolver cannot even be told the support or the target language.
assert.equal(/\bsupport\b|support_language|native_language|profile/.test(String(interfaceLanguage)), false, 'the interface resolver never reads a support language');
assert.equal(/\bactive\b|learning/.test(String(interfaceLanguage)), false, 'nor the learning language');
for (const ui of supported)
  for (const support of ['en', 'vi', 'zh', 'ja', 'ko'])
    for (const active of ['en', 'zh']) {
      const got = resolve({ stored: ui, support, active });
      assert.equal(got.ui, ui, `support ${support} / target ${active} must not move the interface ${ui}`);
      assert.equal(got.support, support, `interface ${ui} / target ${active} must not move support ${support}`);
      assert.equal(got.language, active, `interface ${ui} / support ${support} must not move the target ${active}`);
    }
// Unchosen, the interface is the browser's language when Orena speaks it, else English - not support.
assert.equal(resolve({ browser: ['vi-VN', 'en'], support: 'zh', active: 'en' }).ui, 'vi');
assert.equal(resolve({ browser: ['zh-Hans-CN'], support: 'vi', active: 'en' }).ui, 'zh');
assert.equal(resolve({ browser: ['fr-FR', 'de'], support: 'vi', active: 'zh' }).ui, 'en', 'no written interface: English, not the support language');
assert.equal(resolve({ stored: 'fr', browser: ['vi'], support: 'zh' }).ui, 'vi', 'an unwritten stored choice falls to the browser');
// Support comes from the account only; the target from the server only.
assert.equal(supportLanguage({ support_language: '', native_language: 'vi' }), 'vi');
assert.equal(supportLanguage({}), 'en');
assert.equal(learningLanguage(''), 'en');
assert.equal(matchLocale('ZH-hans', supported), 'zh');

// --- Reload and cache: the same sources give the same answer ---------------------------------------
{
  const first = resolve({ stored: 'en', browser: ['vi'], support: 'vi', active: 'zh' });
  const reload = resolve({ stored: 'en', browser: ['vi'], support: 'vi', active: 'zh' });
  assert.deepEqual(first, reload, 'a reload resolves the same three');
}
assert.equal(INTERFACE_KEY, 'orena.interface');

// --- The learner UI reads each layer through its own resolver ------------------------------------
const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');
const copyIndex = read('copy/index.js');
assert.match(copyIndex, /interfaceLanguage\(\{ stored, browser: navigator\.languages/, 'the interface comes from interfaceLanguage()');
assert.match(copyIndex, /setLanguages\(\{ support: supportLanguage\(profile\) \}\)/, 'support comes from supportLanguage(profile)');
assert.match(copyIndex, /layeredCopy\(table\.packs, table\.layers, current\.ui, current\.support\)/, 'every table is read by layer');
assert.match(copyIndex, /window\.localStorage\.setItem\(INTERFACE_KEY, code\)/, 'the interface is saved on the device under its own key');
assert.equal(/orena\.support/.test(copyIndex), false, 'the old support cache is neither read nor written');
assert.match(read('shell/context.js'), /state\.language = learningLanguage\(bootstrap\?\.language\?\.active\)/, 'the target comes from learningLanguage()');
// No learner module picks its chrome copy by the support or the target language.
function* walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) yield* walk(`${dir}/${entry.name}`);
    else if (entry.name.endsWith('.js')) yield `${dir}/${entry.name}`;
  }
}
const uiRoot = fileURLToPath(new URL('../static/orena', import.meta.url));
for (const dir of ['screens', 'shell', 'kit', 'copy'])
  for (const file of walk(`${uiRoot}/${dir}`)) {
    const src = readFileSync(file, 'utf8');
    assert.equal(/(copy|referenceCopy)\[\s*(ctx|state)\.(support|language)\s*\]/.test(src), false, `${file} reads chrome copy by a non-interface language`);
  }

console.log('Language layers: interface, support and target resolved independently: PASS');
