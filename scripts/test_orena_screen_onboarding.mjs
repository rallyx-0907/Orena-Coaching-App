/* Onboarding: pure data mapping (Design Contract rule 40's zero fallback, EN/VI/ZH copy specifics,
   and every field this screen reads checked against a real captured payload - scripts/fixtures/api/
   README.md). No DOM - static/orena/screens/onboarding/model.js only. Browser behaviour (the real
   requests, the real device-memory writes, the measured layout) is checked in the browser per the
   surface-agent brief §5, not here. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  STEP_COUNT, STEPS, clampStep, stepDots,
  identityOf, targetOptions, targetLabel, endonym, supportOptions, INTERFACE_LOCALES, INTERFACE_ENDONYMS, interfaceOptions,
  LEVELS, levelsFor, defaultLevelCode, levelRow, declaredLevelPatch, greetingParams, languageName,
} from '../static/orena/screens/onboarding/model.js';
// NOTE (Wave B fix pass, 2026-09-29): levelsFor/defaultLevelCode/levelRow now take the platform's
// own level codes (no display spacing) and operate on the resolved grid (an array), not a language
// string, so a real listing narrows the grid instead of the fixed six always standing - the
// independent review's #6/#9 fixes (docs/project/UI_BACKEND_GAPS.md SH-2). greetingParams now
// greets the whole account name, not the frame's first word (#9 - which word is the "given" one
// depends on the culture).

const fixture = (name) => JSON.parse(readFileSync(fileURLToPath(new URL(`./fixtures/api/${name}`, import.meta.url)), 'utf8'));

/* --- clampStep / stepDots --------------------------------------------------- */
{
  assert.deepEqual(STEPS, ['welcome', 'account', 'languages', 'level', 'orena']);
  assert.equal(STEP_COUNT, 5);
  assert.equal(clampStep(2), 2);
  assert.equal(clampStep('3'), 3, 'a stored string round-trips');
  assert.equal(clampStep(-1), 0, 'never negative');
  assert.equal(clampStep(99), STEP_COUNT - 1, 'never past the last step');
  assert.equal(clampStep(undefined), 0, 'a missing value falls back to Welcome, never throws');
  assert.equal(clampStep('nonsense'), 0, 'a corrupted stored value falls back, never throws or NaNs');
  assert.equal(clampStep(1.6), 2, 'rounds');

  const dots = stepDots(2, ['a', 'b', 'c', 'd', 'e']);
  assert.equal(dots.length, 5);
  assert.deepEqual(dots.map((d) => d.done), [true, true, false, false, false]);
  assert.deepEqual(dots.map((d) => d.current), [false, false, true, false, false]);
}

/* --- identityOf: GET /api/me, both real captured shapes -------------------- */
{
  const local = fixture('me.json'); // { mode: "local", name: "Local user", email: "", picture: "" }
  assert.equal(local.mode, 'local', 'sandbox fixture sanity');
  const idLocal = identityOf(local);
  assert.equal(idLocal.name, 'Local user');
  assert.equal(idLocal.initial, 'L');
  assert.equal(idLocal.email, '', 'never invented - the real payload carries none');
  assert.equal(idLocal.picture, '');
  assert.equal(idLocal.google, false);

  const google = { mode: 'google', name: 'Calis', email: 'calis@example.com', picture: 'https://example.com/p.jpg' };
  const idGoogle = identityOf(google);
  assert.equal(idGoogle.email, 'calis@example.com');
  assert.equal(idGoogle.picture, 'https://example.com/p.jpg');
  assert.equal(idGoogle.google, true);

  assert.equal(identityOf(null).name, '', 'never throws on a missing user');
  assert.equal(identityOf({ name: '  ', picture: 'javascript:alert(1)' }).picture, '', 'a non-https picture is dropped, never rendered as a src');
}

/* --- targetOptions/targetLabel: GET /api/session/bootstrap `language.options` ----------------- */
{
  const bootstrap = fixture('session_bootstrap.json');
  const options = bootstrap.language.options;
  assert.deepEqual(options.map((o) => o.code), ['en', 'zh'], 'sandbox fixture sanity');

  const targets = targetOptions(options, 'en');
  assert.equal(targets.length, 2);
  assert.deepEqual(targets.map((o) => o.code), ['en', 'zh']);
  assert.equal(targets[0].selected, true);
  assert.equal(targets[1].selected, false);
  assert.equal(targets[0].glyph, 'En');
  assert.equal(targets[1].glyph, '中');
  assert.match(targets[0].tint, /^var\(--/, 'a token, never a raw colour');
  assert.match(targets[1].tint, /^var\(--/, 'a token, never a raw colour');
  assert.equal(targets.find((o) => o.code === 'zh').nativeName, '中文');
  assert.equal(targetOptions(null, 'en').length, 0, 'never throws on a missing list');
  assert.equal(targetOptions([null, { code: '' }], 'en').length, 0, 'malformed entries drop');

  assert.equal(targetLabel({ nativeName: 'English' }, 'English'), 'English', "English's own native name is not repeated");
  assert.equal(targetLabel({ nativeName: '中文' }, 'Chinese'), 'Chinese · 中文', 'the frame appends the native name in English');
  assert.equal(targetLabel({ nativeName: '中文' }, 'Chinese', 'en'), 'Chinese · 中文');
  assert.equal(targetLabel({ nativeName: '中文' }, 'Tiếng Trung', 'vi'), 'Tiếng Trung', 'the frame draws the bare Vietnamese name, so "中文" is never split across two lines on a phone');
  assert.equal(targetLabel({ nativeName: '中文' }, '中文', 'zh'), '中文', 'a Chinese interface already resolving lang_zh to 中文 must not double to "中文 · 中文" (P1, independent review - the same regression settings/screen.js already fixed)');
  assert.equal(targetLabel({ nativeName: '中文' }, '中文', 'en'), '中文', 'and not in English either, whatever the locale');
}

/* --- endonym / supportOptions: GET /api/platform/languages `support_languages` --------------- */
{
  assert.equal(endonym('en'), 'English');
  assert.equal(endonym('vi'), 'Tiếng Việt', 'the frame draws the support languages as endonyms');
  assert.equal(endonym('zh'), '中文');
  assert.equal(endonym('ja'), '日本語');
  assert.equal(endonym('es'), 'Español', 'a lower-case endonym takes a capital as a button label');
  assert.equal(endonym('not-a-language', 'Klingon'), 'Klingon', 'a code the platform has no name for falls back to the backend label, never throws');
  assert.equal(endonym('', 'Backend label'), 'Backend label');
  assert.equal(endonym('xx'), 'xx', 'and with nothing to fall back to, the code itself');

  const platform = fixture('platform_languages.json');
  const codes = platform.support_languages.map((s) => s.code);
  for (const code of ['en', 'vi', 'zh']) assert.ok(codes.includes(code), `the backend lists ${code} as a support language`);
  const supports = supportOptions(platform.support_languages, 'vi');
  assert.equal(supports.length, platform.support_languages.length, 'the real backend list, not a hardcoded subset');
  assert.deepEqual(supports.map((s) => s.code), codes, 'in the backend order');
  for (const entry of supports) assert.equal(entry.label, endonym(entry.code, entry.label), `${entry.code} is named in itself, identically in every interface language`);
  assert.equal(supports.find((s) => s.code === 'vi').label, 'Tiếng Việt');
  assert.equal(supports.find((s) => s.code === 'zh').label, '中文', 'not the backend\'s English "Simplified Chinese"');
  assert.equal(supports.find((s) => s.code === 'vi').selected, true);
  assert.equal(supports.find((s) => s.code === 'en').selected, false);
  assert.equal(supportOptions(null, '').length, 0, 'never throws');
  assert.equal(supportOptions([{ code: 'x' }], '').length, 0, 'a label-less entry drops');
  assert.equal(supportOptions([{ code: 'xx', label: 'Xish' }], '')[0].label, 'Xish', 'a code the platform cannot name keeps the backend label');
  const only = supportOptions(null, 'vi');
  assert.deepEqual(only, [{ code: 'vi', label: 'Tiếng Việt', selected: true }], 'a list that could not be read still shows the current support language, selected');
  assert.equal(supportOptions([], 'vi').length, 1, 'an empty list is the same case');
}

/* --- interfaceOptions --------------------------------------------------------------------------- */
{
  assert.deepEqual(INTERFACE_LOCALES, ['en', 'vi', 'zh']);
  const ifaces = interfaceOptions('zh');
  assert.deepEqual(ifaces.map((o) => o.code), ['en', 'vi', 'zh']);
  assert.equal(ifaces.find((o) => o.code === 'vi').label, INTERFACE_ENDONYMS.vi, 'the endonym, not a translation');
  assert.equal(ifaces.find((o) => o.code === 'zh').selected, true);
}

/* --- Level: CEFR for English, HSK for Chinese, both real standard frameworks ------------------- */
{
  assert.equal(levelsFor('en').length, 6);
  assert.equal(levelsFor('zh').length, 7, 'HSK 1-6 and one HSK 7-9 band');
  assert.deepEqual(levelsFor('en').map((l) => l.code), ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']);
  assert.deepEqual(levelsFor('zh').map((l) => l.code), ['HSK1', 'HSK2', 'HSK3', 'HSK4', 'HSK5', 'HSK6', 'HSK7-9'], "the platform's own codes (GET /api/platform/languages languages[].levels), never the frame's display spacing");
  assert.deepEqual(levelsFor('zh').map((l) => l.label), ['HSK 1', 'HSK 2', 'HSK 3', 'HSK 4', 'HSK 5', 'HSK 6', 'HSK 7–9'], "the cell's label keeps the frame's own spacing");
  assert.equal(levelsFor('fr').length, 6, 'an unknown target falls back to English, never throws or is empty');

  /* GET /api/platform/languages `languages[].levels`, the real captured shape - a shorter real
     listing narrows the grid to what the backend actually offers this learner, in the frame's own
     order; a missing or unreadable listing never empties the grid (the frame's own six stand). */
  const platformLanguages = fixture('platform_languages.json').languages;
  const enListed = platformLanguages.find((l) => l.code === 'en').levels;
  const zhListed = platformLanguages.find((l) => l.code === 'zh').levels;
  assert.deepEqual(enListed, ['A1', 'A2', 'B1'], 'sandbox fixture sanity');
  assert.deepEqual(zhListed, ['HSK1', 'HSK2', 'HSK3'], 'sandbox fixture sanity');
  assert.deepEqual(levelsFor('en', enListed).map((l) => l.code), ['A1', 'A2', 'B1']);
  assert.deepEqual(levelsFor('zh', zhListed).map((l) => l.code), ['HSK1', 'HSK2', 'HSK3']);
  assert.equal(levelsFor('zh', []).length, 7, 'an empty listing never empties the grid');
  assert.equal(levelsFor('zh', null).length, 7, 'a missing listing is the same case');
  assert.equal(levelsFor('zh').filter((l) => /^HSK[789]$/.test(l.code)).length, 0, 'never three separate HSK 7, 8, 9 cells');

  const enGrid = levelsFor('en');
  const zhGrid = levelsFor('zh');
  assert.equal(defaultLevelCode(enGrid), 'B1', 'the middle of six, never a first/invented pick');
  assert.equal(defaultLevelCode(zhGrid), 'HSK3');
  assert.equal(defaultLevelCode(levelsFor('en', enListed)), 'A2', "the middle of the narrowed real grid, not the fixed six's");

  assert.equal(levelRow(enGrid, 'C1').code, 'C1');
  assert.equal(levelRow(enGrid, 'nonsense').code, 'B1', 'an unknown code falls back to the middle, never throws');
  assert.equal(levelRow(zhGrid, 'HSK5').code, 'HSK5');
  assert.equal(levelRow(zhGrid, 'HSK5').label, 'HSK 5');

  /* Named contract change (D4 I1, migration 0017): the learner's pick is stored as `declared_level`,
     validated by the server against the scope language's own registry list, so an HSK code is sent
     like a CEFR one - and HSK7-9 is one band, sent when the platform lists it. Nothing the platform
     does not list for the language, and no unknown string, is ever sent. */
  assert.deepEqual(declaredLevelPatch('B1'), { declared_level: 'B1' });
  assert.deepEqual(declaredLevelPatch('HSK3', null, 'zh'), { declared_level: 'HSK3' });
  assert.equal(declaredLevelPatch('HSK3', null, 'en'), null, 'an HSK code is not an English level');
  assert.equal(declaredLevelPatch('B2', null, 'zh'), null, 'a CEFR code is not a Chinese level');
  assert.deepEqual(declaredLevelPatch('HSK7-9', null, 'zh'), { declared_level: 'HSK7-9' }, 'the band has its own cell after HSK 6');
  assert.equal(declaredLevelPatch('HSK7', null, 'zh'), null, 'no separate HSK 7 code');
  const zhBands = ['HSK1', 'HSK2', 'HSK3', 'HSK4', 'HSK5', 'HSK6', 'HSK7-9'];
  assert.deepEqual(declaredLevelPatch('HSK7-9', zhBands, 'zh'), { declared_level: 'HSK7-9' }, 'one band, as the registry lists it');
  assert.equal(declaredLevelPatch('HSK8', zhBands, 'zh'), null);
  assert.equal(declaredLevelPatch(''), null);
  assert.equal(declaredLevelPatch('nonsense'), null);
}

/* --- greetingParams / languageName: real, already-known state only, no invented data ---------- */
{
  const p1 = greetingParams({ name: 'Calis Nguyen', language: 'en', level: 'B2' }, 'vi');
  assert.equal(p1.name, 'Calis Nguyen', "the whole name, never only its first word - which word is the given one depends on the culture (a Vietnamese name ends with it, independent review #9); Today's own greeting uses the same whole-name rule");
  assert.equal(p1.level, 'B2');
  assert.equal(p1.target, 'en');
  assert.equal(p1.support, 'vi', 'the support language the learner picked');
  assert.equal(p1.zh, false);
  assert.equal(greetingParams({ name: '  Nguyễn   Văn   An  ', language: 'en' }).name, 'Nguyễn Văn An', 'inner whitespace collapses to single spaces; outer whitespace trims');

  const p2 = greetingParams({ name: '', language: 'zh', level: '' });
  assert.equal(p2.name, '', 'a missing name is empty, never invented');
  assert.equal(p2.level, 'HSK 3', 'a missing level falls back to the same middle default the Level step itself uses');
  assert.equal(p2.target, 'zh');
  assert.equal(p2.support, 'en', 'a missing support language is the documented English fallback');
  assert.equal(p2.zh, true);

  assert.equal(greetingParams({ language: 'zh', level: 'B2' }).level, 'HSK 3', "a CEFR level is not a Chinese learner's level (SH-2: the stored field is CEFR-only)");
  assert.equal(greetingParams({ language: 'en', level: 'HSK 4' }).level, 'B1', "an HSK level is not an English learner's level");
  assert.equal(greetingParams({ name: 'Local user', user: { mode: 'local' }, language: 'en' }).name, '', "a local device's placeholder identity is not a name to greet");
  assert.equal(greetingParams({ name: 'Calis', user: { mode: 'google' }, language: 'en' }).name, 'Calis', 'an account that supplies a name is greeted by it');
  assert.equal(greetingParams(null).name, '', 'never throws on a missing context');
  assert.equal(greetingParams(undefined).level, 'B1');

  /* A language's name in the language the sentence renders in: the platform's own CLDR names for
     every support language the backend lists, in every interface language. */
  assert.equal(languageName('en', 'en'), 'English');
  assert.equal(languageName('vi', 'en'), 'Vietnamese');
  assert.equal(languageName('en', 'vi'), 'tiếng Anh', 'Vietnamese names take a lower-case common noun mid-sentence, the proper noun keeps its capital');
  assert.equal(languageName('vi', 'vi'), 'tiếng Việt');
  assert.equal(languageName('zh', 'vi'), 'tiếng Trung');
  assert.equal(languageName('en', 'zh'), '英语');
  assert.equal(languageName('ja', 'zh'), '日语');
  for (const code of fixture('platform_languages.json').support_languages.map((s) => s.code)) {
    for (const locale of ['en', 'vi', 'zh']) assert.ok(languageName(code, locale).length > 1, `${code} has a name in ${locale}`);
  }
  assert.equal(languageName('', 'en', 'Backend label'), 'Backend label', 'an empty code falls back to the backend label');
  assert.equal(languageName('not-a-language', 'en', 'Klingon'), 'Klingon', 'a code the platform has no name for falls back, never throws');
  assert.equal(languageName('xx', 'en'), 'xx', 'and with nothing to fall back to, the code itself');
}

console.log('Onboarding: real shapes from /api/me, /api/session/bootstrap and /api/platform/languages, level frameworks, EN/ZH gaps and greeting fallbacks verified: PASS');

/* --- EN/VI/ZH copy specifics ------------------------------------------------------------------- */
{
  const store = new Map();
  globalThis.window = {
    localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) },
  };
  Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
  globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

  const { t } = await import('../static/orena/screens/onboarding/copy.js');
  const copy = await import('../static/orena/copy/index.js');
  const table = copy.registeredCopy().get('onboarding');
  assert.ok(table, 'the onboarding namespace registered');

  const supportKeys = new Set(Object.keys(table.layers).filter((k) => table.layers[k] === 'support'));
  assert.ok(supportKeys.has('greeting') && supportKeys.has('greetingAnon'), 'the greeting is explanation, following support - not chrome');
  assert.ok(supportKeys.has('levelA1Desc'), 'a level description explains, follows support');
  assert.equal(table.layers.levelA1Name, 'interface', 'the level name is a short chrome label');
  assert.equal(table.layers.stepWelcome, 'interface');

  // A pack that merely repeats the English string for real prose (not a universal notation like
  // CEFR/HSK's own "A1"/"HSK 3" codes) is the silent-English-fallback rule 26 forbids.
  const invariant = new Set(['targetSubEn']); // "CEFR A1–C2" is the same literal notation in every language
  for (const key of Object.keys(table.packs.en)) {
    if (invariant.has(key)) continue;
    assert.notEqual(table.packs.vi[key], table.packs.en[key], `vi.${key} must not silently equal English`);
    assert.notEqual(table.packs.zh[key], table.packs.en[key], `zh.${key} must not silently equal English`);
  }
  assert.equal(table.packs.vi.targetSubEn, table.packs.en.targetSubEn, 'CEFR notation is language-invariant by design, not a missed translation');

  assert.match(table.packs.vi.greeting, /[àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]/i, 'Vietnamese keeps its diacritics');
  assert.match(table.packs.zh.greeting, /[一-鿿]/, 'Chinese is Han script, not romanised');

  // Every placeholder is in every pack, identically (the copy engine's own gate checks the set; this
  // one checks the two greeting lines carry the support language the design's own line ends with).
  for (const lang of ['en', 'vi', 'zh']) {
    for (const key of ['greeting', 'greetingAnon']) {
      const line = table.packs[lang][key];
      for (const slot of ['{language}', '{level}', '{support}']) assert.ok(line.includes(slot), `${lang}.${key} carries ${slot}`);
    }
    assert.ok(table.packs[lang].greeting.includes('{name}'), `${lang}.greeting names the learner`);
    assert.ok(!table.packs[lang].greetingAnon.includes('{name}'), `${lang}.greetingAnon has no name slot, so it can never read "Hi !"`);
  }
  const greeting = t('greeting', { name: 'Calis', language: 'English', level: 'B2', support: 'Vietnamese' });
  assert.match(greeting, /Calis/);
  assert.match(greeting, /B2/);
  assert.match(greeting, /Vietnamese/);
  assert.doesNotMatch(t('greetingAnon', { language: 'English', level: 'B2', support: 'Vietnamese' }), /Hi !|\{/);

  // The words the frame draws twice with different copy: the aside's own headline and the Welcome
  // step's - never one string reused for both.
  assert.notEqual(table.packs.en.brandTitle, table.packs.en.welcomeHeadline);
  assert.notEqual(table.packs.en.brandSub, table.packs.en.welcomeSub);
  // Chinese punctuation is fullwidth in Chinese prose.
  for (const [key, text] of Object.entries(table.packs.zh)) assert.doesNotMatch(text, /[一-鿿][,?!]/, `zh.${key} uses fullwidth punctuation after Han text`);

  for (const [key, layer] of Object.entries(table.layers)) assert.ok(layer === 'interface' || layer === 'support', `${key} has a real layer`);
}

console.log('Onboarding: EN/VI/ZH copy layers, diacritics and Han script verified: PASS');
