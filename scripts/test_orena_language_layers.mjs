/* The three language layers are independent (D-079, docs/product/ORENA_LANGUAGE_COHERENCE.md):
   interface (chrome), support (explanation, guidance), target (the material). This gate locks the
   source of truth - product/languages.js and the app's use of it - not individual strings, so a
   regression of the kind that mixed English, Vietnamese and Chinese on one screen fails here:
   the interface read from the support language, support read from the target, content following
   the interface, or a reload or a stale cache moving one layer away from the others. */
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import {
  INTERFACE_KEY,
  interfaceLanguage,
  supportLanguage,
  learningLanguage,
  resolveLanguages,
  guidanceLocale,
  matchLocale,
} from '../static/orena/product/languages.js';
import { supportedLocales } from '../static/orena/ui/copy.js';
import { speakCopy, speakingCopy, GUIDANCE_KEYS } from '../static/orena/ui/speaking-copy.js';

const supported = supportedLocales;
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

// --- Reload and cache: the same sources give the same answer; a stale cache is not a source -------
{
  const first = resolve({ stored: 'en', browser: ['vi'], support: 'vi', active: 'zh' });
  const reload = resolve({ stored: 'en', browser: ['vi'], support: 'vi', active: 'zh' });
  assert.deepEqual(first, reload, 'a reload resolves the same three');
}
const app = readFileSync(new URL('../static/orena/app.js', import.meta.url), 'utf8');
assert.equal(/orena\.support/.test(app), false, 'the old support cache is neither read nor written');
assert.equal(/uiLocale/.test(app), false, 'the support-derived interface resolver is gone');
assert.equal(INTERFACE_KEY, 'orena.interface');
// Every assignment of a layer goes through its own resolver.
for (const [layer, via] of [['ui', 'interfaceLanguage'], ['support', 'supportLanguage'], ['language', 'learningLanguage']]) {
  const assignments = [...app.matchAll(new RegExp(`ctx\\.${layer} = ([^;]+);`, 'g'))].map((m) => m[1]);
  assert.ok(assignments.length, `ctx.${layer} is assigned`);
  for (const value of assignments) assert.match(value, new RegExp(`^${via}\\(`), `ctx.${layer} = ${value} must come from ${via}()`);
}
// Every way into the preferences opens them, including the rows a room draws after the shell (Profile's
// Languages row once did nothing): one delegated listener, not per-button bindings made too early.
assert.match(app, /document\.addEventListener\("click", \(event\) => \{\s*const opener = event\.target\.closest\?\.\("\[data-preference\]"\);/);
assert.equal(/querySelectorAll\("(#shell )?\[data-preference\]"\)\s*\.forEach\(\(x\) => \(x\.onclick/.test(app), false, 'no early per-button binding');
// The interface is chosen on its own in the preferences, and saved on the device under its own key.
assert.match(app, /<select name="interface">/);
assert.match(app, /storage\.setItem\(INTERFACE_KEY, ctx\.ui\)/);
assert.match(app, /stored: storage\.getItem\(INTERFACE_KEY\)/);
// The profile answers for support only: nothing near the profile read touches ctx.ui.
{
  const from = app.indexOf('ctx.profile = profile;');
  const load = app.slice(from, app.indexOf('ctx.memory = learnerMemory(storage, ctx.owner, ctx.language);', from));
  assert.ok(from > 0 && load.length > 0, 'the profile load is found');
  assert.equal(/ctx\.ui\b/.test(load), false, 'loading the profile does not change the interface');
}
// No learner surface picks its chrome copy by the support or the target language.
const uiDir = new URL('../static/orena/ui/', import.meta.url);
for (const file of readdirSync(uiDir).filter((name) => name.endsWith('.js'))) {
  const src = readFileSync(new URL(file, uiDir), 'utf8');
  assert.equal(/\b(copy|referenceCopy)\[\s*ctx\.(support|language)\s*\]/.test(src), false, `${file} reads chrome copy by a non-interface language`);
}

// --- Speaking: chrome in the interface language, guidance in the support language ------------------
for (const key of GUIDANCE_KEYS)
  for (const pack of Object.keys(speakingCopy)) assert.ok(speakingCopy[pack][key], `${pack}.${key} exists`);
{
  const a = speakCopy('en', 'vi'); // CASE A
  assert.equal(a.nextLine, speakingCopy.en.nextLine, 'A: a button is the interface language');
  assert.equal(a.eachWord_zh, speakingCopy.en.eachWord_zh, 'A: a section label is the interface language');
  assert.equal(a.tapWord_zh, speakingCopy.vi.tapWord_zh, 'A: a hint is the support language');
  assert.equal(a.passed, speakingCopy.vi.passed, 'A: a verdict is the support language');
  assert.equal(a.detailSaid, speakingCopy.vi.detailSaid, 'A: the sheet sentence is the support language');
  assert.equal(a.langOf('nextLine'), 'en');
  assert.equal(a.langOf('subTap'), 'vi');
  assert.equal(a.room, 'Speaking', 'A: the shared room name is the interface language');
  const c = speakCopy('zh', 'en'); // CASE C
  assert.equal(c.nextLine, speakingCopy.zh.nextLine);
  assert.equal(c.subTap, speakingCopy.en.subTap);
  const b = speakCopy('vi', 'vi'); // CASE B
  assert.equal(b.nextLine, speakingCopy.vi.nextLine);
  assert.equal(b.subTap, speakingCopy.vi.subTap);
  // A support language Orena has no written pack for reads its guidance in English, never in the interface's.
  const ja = speakCopy('zh', 'ja');
  assert.equal(ja.subTap, speakingCopy.en.subTap);
  assert.equal(ja.nextLine, speakingCopy.zh.nextLine);
  assert.equal(guidanceLocale('ja', Object.keys(speakingCopy)), 'en');
}
for (const file of ['speaking-workspace.js', 'speaking-free.js', 'speaking.js']) {
  const src = readFileSync(new URL(file, uiDir), 'utf8');
  const calls = [...src.matchAll(/speakCopy\(([^)]*)\)/g)].map((m) => m[1]);
  assert.ok(calls.length, `${file} uses the Speaking copy`);
  for (const args of calls) assert.equal(args, 'ctx.ui, ctx.support', `${file}: speakCopy(${args}) must be given both layers`);
}

console.log('Language layers: interface, support and target resolved independently; Speaking splits chrome from guidance: PASS');
