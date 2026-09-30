/* Settings: pure data mapping (Design Contract rule 40's zero fallback for every row this screen
   cannot back with a real source, EN/ZH copy specifics). No DOM, no network - static/orena/screens/
   settings/model.js only. Browser behaviour (the real requests, the real device-memory writes, the
   measured layout) is checked in the browser per the surface-agent brief §5, not here. */
import assert from 'node:assert/strict';
import {
  TABS,
  tabFromQuery,
  INTERFACE_ENDONYMS,
  targetLanguageOptions,
  supportLanguageOptions,
  interfaceLanguageOptions,
  barPercent,
  languageRows,
  learningRows,
  reviewRows,
  notificationRows,
  planRows,
  rowsForTab,
  SESSION_LENGTH_FALLBACK,
  SEGMENTED_MAX_OPTIONS,
  usesPicker,
} from '../static/orena/screens/settings/model.js';
import { sizeBucketOf, READER_SIZE, READER_DEFAULTS } from '../static/orena/product/reader-settings.js';

/* --- tabFromQuery --------------------------------------------------------- */
{
  assert.equal(tabFromQuery('plan'), 'plan');
  assert.equal(tabFromQuery('PLAN'), 'plan', 'case-insensitive');
  assert.equal(tabFromQuery(' review '), 'review', 'trims');
  assert.equal(tabFromQuery(''), TABS[0], 'empty falls back to the first tab');
  assert.equal(tabFromQuery('nope'), TABS[0], 'an unknown slug falls back, never throws');
  assert.equal(tabFromQuery(undefined), TABS[0]);
  assert.deepEqual(TABS, ['languages', 'learning', 'review', 'notifications', 'plan']);
}

/* --- Language option builders --------------------------------------------- */
{
  const languages = [
    { code: 'en', name: 'English', native_name: 'English', enabled: true },
    { code: 'zh', name: 'Chinese', native_name: '中文', enabled: true },
    { code: 'fr', name: 'French', native_name: 'Français', enabled: false },
  ];
  const target = targetLanguageOptions(languages);
  assert.equal(target.length, 2, 'disabled languages are dropped');
  assert.deepEqual(target.map((o) => o.code), ['en', 'zh']);
  assert.equal(target.find((o) => o.code === 'zh').nativeName, '中文');
  assert.equal(targetLanguageOptions(null).length, 0, 'never throws on a missing list');
  assert.equal(targetLanguageOptions([null, { code: '', enabled: true }]).length, 0, 'malformed entries drop');

  const support = supportLanguageOptions([
    { code: 'en', label: 'English' },
    { code: 'vi', label: 'Vietnamese' },
    { code: 'ja', label: 'Japanese' },
    { bad: true },
  ]);
  assert.equal(support.length, 3, 'the real backend list is not truncated to a hardcoded 2');
  assert.deepEqual(support.map((o) => o.code), ['en', 'vi', 'ja']);

  const iface = interfaceLanguageOptions();
  assert.deepEqual(iface.map((o) => o.code), ['en', 'vi', 'zh']);
  assert.equal(iface.find((o) => o.code === 'vi').label, 'Tiếng Việt', 'the endonym, not a translation');
  assert.equal(iface.find((o) => o.code === 'zh').label, '中文');
  assert.equal(INTERFACE_ENDONYMS.en, 'English');
}

/* --- barPercent: rule 40's zero fallback ----------------------------------- */
{
  assert.equal(barPercent(5, 0), 0, 'a zero limit is 0, never a divide-by-zero figure');
  assert.equal(barPercent(5, -1), 0, 'a negative limit is 0');
  assert.equal(barPercent(5, null), 0, 'a missing limit is 0');
  assert.equal(barPercent('x', 10), 0, 'a non-numeric used is 0');
  assert.equal(barPercent(5, 10), 50);
  assert.equal(barPercent(15, 10), 100, 'usage past the limit clamps, never overflows the track');
  assert.equal(barPercent(0, 10), 0);
}

/* --- Reader size bucketing (shared with product/reader-settings.js) -------- */
{
  assert.equal(sizeBucketOf(READER_SIZE.min), 'S');
  assert.equal(sizeBucketOf(READER_DEFAULTS.size), 'M');
  assert.equal(sizeBucketOf(READER_SIZE.max), 'L');
  assert.equal(sizeBucketOf(undefined), 'M', 'an unreadable size is the middle, not an edge');
}

/* --- languageRows ----------------------------------------------------------- */
{
  const rows = languageRows({
    languages: [{ code: 'en', name: 'English', native_name: 'English', enabled: true }],
    supportLanguages: [{ code: 'vi', label: 'Vietnamese' }],
    targetCode: 'en',
    supportCode: 'vi',
    interfaceCode: 'zh',
  });
  assert.equal(rows.length, 3);
  assert.deepEqual(rows.map((r) => r.id), ['target', 'support', 'interface']);
  for (const row of rows) {
    assert.equal(row.kind, 'choice');
    assert.equal(row.disabled, false, `${row.id} is a real, working control`);
  }
  assert.equal(rows[0].value, 'en');
  assert.equal(rows[2].value, 'zh');
}

/* --- learningRows: two real, two gaps -------------------------------------- */
{
  const rows = learningRows({ sizeBucket: 'L', autoscroll: false, meaning: true, theme: 'dark' });
  const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
  assert.deepEqual(rows.map((r) => r.id), ['theme', 'readerSize', 'autoscroll', 'meaning', 'wordHighlight', 'autoplay'], 'Appearance leads Learning (D-067): the only other pure device-display preference in Settings');
  assert.equal(byId.theme.value, 'dark');
  assert.equal(byId.theme.disabled, false, 'a real, working control - never a backend gap');
  assert.deepEqual(byId.theme.options, ['light', 'dark', 'system']);
  assert.equal(byId.readerSize.value, 'L');
  assert.equal(byId.readerSize.disabled, false);
  assert.equal(byId.autoscroll.value, false);
  assert.equal(byId.autoscroll.disabled, false);
  assert.equal(byId.meaning.value, true);
  assert.equal(byId.meaning.disabled, false);
  assert.equal(byId.wordHighlight.disabled, true, 'no real mechanism exists anywhere in the app');
  assert.equal(byId.wordHighlight.value, false, 'a disabled toggle never shows a fabricated on state');
  assert.equal(byId.autoplay.disabled, true);
  assert.equal(byId.autoplay.value, false);

  /* System is the default (D-089): an unrecognised/absent value never throws and never silently
     picks light or dark - it falls back to 'system', kit/device.js's own normalize shape. */
  assert.equal(learningRows({ theme: undefined }).find((r) => r.id === 'theme').value, 'system');
  assert.equal(learningRows({ theme: 'blue' }).find((r) => r.id === 'theme').value, 'system', 'a corrupted stored value falls back to System, never throws');
  assert.equal(learningRows({ theme: 'light' }).find((r) => r.id === 'theme').value, 'light');
}

/* --- reviewRows: recall-modes.js threaded through, session length is a gap - */
{
  const rows = reviewRows({ modes: { typing: true, cloze: false, dictation: true, listen_choose: true, speak: false } });
  const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
  assert.equal(byId.targetMeaning.value, true);
  assert.equal(byId.sourceAware.value, false);
  assert.equal(byId.audioWord.value, true);
  for (const id of ['targetMeaning', 'sourceAware', 'audioWord']) assert.equal(byId[id].disabled, false);
  assert.equal(byId.sessionLength.disabled, true);
  assert.equal(byId.sessionLength.value, SESSION_LENGTH_FALLBACK, 'the middle option, never an invented one');
  assert.equal(reviewRows({ modes: null }).find((r) => r.id === 'targetMeaning').value, false, 'a missing settings object never throws and never defaults on');
}

/* --- notificationRows: the whole tab is a recorded gap ---------------------- */
{
  const rows = notificationRows();
  assert.equal(rows.length, 4);
  for (const row of rows) {
    assert.equal(row.kind, 'toggle');
    assert.equal(row.disabled, true);
    assert.equal(row.value, false);
  }
}

/* --- planRows: real plan/quota data adapts, gaps stay gaps ------------------ */
{
  const withEvidence = planRows({
    plan: { name: 'Premium', description: 'Deeper feedback.' },
    features: { 'writing.evaluate': { used: 4, monthly_limit: 500 } },
    micOn: true,
    micState: 'granted',
  });
  const byId = Object.fromEntries(withEvidence.map((r) => [r.id, r]));
  assert.equal(byId.plan.disabled, true, 'billing_ready is false everywhere - Manage has no real destination');
  assert.equal(byId.plan.planName, 'Premium');
  assert.equal(byId.messages.disabled, true, 'no entitlement key for AI-tutor messages exists');
  assert.equal(byId.messages.used, 0);
  assert.equal(byId.messages.limit, 0);
  assert.equal(byId.writingReviews.disabled, false, 'writing.evaluate is a real entitlement');
  assert.equal(byId.writingReviews.used, 4);
  assert.equal(byId.writingReviews.limit, 500);
  assert.equal(byId.pronunciation.disabled, true, 'no entitlement key for pronunciation minutes exists');
  assert.equal(byId.mic.value, true);
  assert.equal(byId.mic.disabled, false, 'requesting the permission is a real effect even when it cannot be revoked from script');
  assert.equal(byId.learnerAudio.disabled, true, 'no delete-audio route exists');
  assert.equal(byId.history.disabled, false, 'a real navigation to Progress needs no backend');

  const withoutEvidence = planRows({ plan: null, features: {}, micOn: false, micState: undefined });
  const byId2 = Object.fromEntries(withoutEvidence.map((r) => [r.id, r]));
  assert.equal(byId2.plan.planName, '', 'a missing plan name is empty, never invented');
  assert.equal(byId2.writingReviews.disabled, true, 'a missing entitlement is a gap, not a fabricated 0/0 that looks real');
  assert.equal(byId2.writingReviews.used, 0);
  assert.equal(byId2.writingReviews.limit, 0);
  assert.equal(byId2.mic.state, 'unsupported', 'an unread permission state falls back, never throws');
}

/* --- rowsForTab dispatch ----------------------------------------------------- */
{
  const inputs = {
    languages: { languages: [], supportLanguages: [], targetCode: 'en', supportCode: 'en', interfaceCode: 'en' },
    learning: { sizeBucket: 'M', autoscroll: true, meaning: true, theme: 'system' },
    review: { modes: {} },
    plan: { plan: null, features: {}, micOn: false, micState: 'prompt' },
  };
  assert.equal(rowsForTab('languages', inputs).length, 3);
  assert.equal(rowsForTab('learning', inputs).length, 6);
  assert.equal(rowsForTab('review', inputs).length, 4);
  assert.equal(rowsForTab('notifications', inputs).length, 4);
  assert.equal(rowsForTab('plan', inputs).length, 7);
  assert.deepEqual(rowsForTab('nonsense', inputs), [], 'an unknown tab id is empty, never throws');
}

/* --- kit/device.js: normalize/paint/appearance/setAppearance (P1, independent review) ---------
   The theme feature's actual source of truth has zero coverage anywhere else: every block above
   tests model.js's own independent, redundant appearanceValue() fallback, and the block below only
   stubs matchMedia so importing screen.js doesn't crash under Node - neither asserts kit/device.js's
   exported behaviour directly. Stub document/window/matchMedia/localStorage here, before this file's
   own first import of kit/device.js: it is an ES module singleton (Node caches by resolved file
   path, not by the relative specifier text used to reach it - screen.js's own `'../../kit/device.js'`
   resolves to the same file this block imports as `'../static/orena/kit/device.js'`) and reads
   document/window once at its own top level, so this must run before the copy-specifics block below
   reassigns globalThis.window/document for its own reasons - that reassignment never reaches back
   into an already-imported module. Also exercises APPEARANCES (kit/device.js's own canonical
   three-value list) so it has a real consumer, per the review's "either use it or drop it": model.js
   cannot import it without breaking its own deliberate DOM-free purity (its header says so; every
   block above calls learningRows()/rowsForTab() before any window/document stub exists in this
   file, so a transitive import of a module that touches `document`/`window` at module scope would
   throw ReferenceError and fail this whole gate immediately) - this is the real, minimal consumer. */
{
  const store = new Map();
  let darkMatches = false;
  globalThis.window = {
    localStorage: {
      getItem: (k) => store.get(k) ?? null,
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: (k) => store.delete(k),
    },
    matchMedia: (query) => {
      const media = { media: query, addEventListener: () => {}, removeEventListener: () => {} };
      Object.defineProperty(media, 'matches', { get: () => (query.indexOf('prefers-color-scheme') >= 0 ? darkMatches : false) });
      return media;
    },
  };
  globalThis.document = { documentElement: { dataset: {} } };

  const { appearance, setAppearance, APPEARANCE_KEY, APPEARANCES } = await import('../static/orena/kit/device.js');

  assert.deepEqual(APPEARANCES, ['light', 'dark', 'system'], 'the canonical three-value list device.js exports and this gate now exercises');

  // Round-trip: each explicit choice reads back exactly as stored, under the one key.
  for (const value of ['light', 'dark', 'system']) {
    setAppearance(value);
    assert.equal(appearance(), value, `setAppearance('${value}') round-trips through appearance()`);
    assert.equal(globalThis.window.localStorage.getItem(APPEARANCE_KEY), value, 'the normalized value is what is actually stored');
  }

  // Fallback to System: an unset key, and every corrupted/unknown stored value - never throws.
  globalThis.window.localStorage.removeItem(APPEARANCE_KEY);
  assert.equal(appearance(), 'system', 'an unset key falls back to System, never throws');
  for (const bad of ['blue-cheese', '', 'Light', 'LIGHT', 'null']) {
    globalThis.window.localStorage.setItem(APPEARANCE_KEY, bad);
    assert.equal(appearance(), 'system', `a corrupted stored value (${JSON.stringify(bad)}) falls back to System, never throws or guesses`);
  }

  // paint() derives root.dataset.theme from dark.matches only when the choice normalizes to
  // 'system' - an explicit Light/Dark choice must ignore the OS entirely, in both OS states.
  darkMatches = true;
  setAppearance('light');
  assert.equal(globalThis.document.documentElement.dataset.theme, 'light', 'an explicit Light choice ignores the OS even when it is dark');
  setAppearance('dark');
  assert.equal(globalThis.document.documentElement.dataset.theme, 'dark', 'an explicit Dark choice ignores the OS even when it is dark');
  setAppearance('system');
  assert.equal(globalThis.document.documentElement.dataset.theme, 'dark', 'System resolves from the OS: dark');
  darkMatches = false;
  setAppearance('dark');
  assert.equal(globalThis.document.documentElement.dataset.theme, 'dark', 'an explicit Dark choice ignores the OS even when it is light');
  setAppearance('system');
  assert.equal(globalThis.document.documentElement.dataset.theme, 'light', 'System resolves from the OS: light');

  console.log('kit/device.js: normalize/paint/appearance/setAppearance round-trip, System fallback and OS-only-when-System verified: PASS');
}

/* --- EN/ZH/VI copy specifics -------------------------------------------------- */
{
  const store = new Map();
  globalThis.window = {
    localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) },
    // screen.js now imports kit/device.js (Appearance, D-067) - a real DOM module whose top level
    // calls matchMedia; stub the two queries it makes (theme, phone width) so importing screen.js
    // for its DOM-free __internal helpers below does not throw in Node.
    matchMedia: (query) => ({ matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {} }),
  };
  Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
  globalThis.document = { documentElement: { lang: 'en', dataset: {} } };
  const { t } = await import('../static/orena/screens/settings/copy.js');
  const copy = await import('../static/orena/copy/index.js');
  const table = copy.registeredCopy().get('settings');
  assert.ok(table, 'the settings namespace registered');
  for (const key of Object.keys(table.layers)) assert.equal(table.layers[key], 'interface', `${key} is chrome, per the learner language contract`);
  // A pack that merely repeats the English string for a real sentence (not a proper noun, not a
  // single-letter size code) is the silent-English-fallback rule 26 forbids.
  const invariant = new Set(['sizeS', 'sizeM', 'sizeL']);
  for (const key of Object.keys(table.packs.en)) {
    if (invariant.has(key)) continue;
    assert.notEqual(table.packs.vi[key], table.packs.en[key], `vi.${key} must not silently equal English`);
    assert.notEqual(table.packs.zh[key], table.packs.en[key], `zh.${key} must not silently equal English`);
  }
  assert.match(table.packs.vi.saveError, /[àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]/i, 'Vietnamese keeps its diacritics');
  assert.match(table.packs.zh.saveError, /[一-鿿]/, 'Chinese is Han script, not romanised');
  assert.equal(typeof t('targetLabel'), 'string');

  /* --- screen.js's own DOM-free row-shaping helpers (label/sub key mapping, option labels) --- */
  const { __internal } = await import('../static/orena/screens/settings/screen.js');
  assert.equal(__internal.rowLabel({ id: 'target' }), t('targetLabel'));
  assert.equal(__internal.rowSub({ id: 'target' }), t('targetSub'), 'an ordinary row reads `${id}Sub`');
  assert.equal(__internal.rowSub({ id: 'writingReviews' }), t('thisMonth'), 'writingReviews shares thisMonth, not a duplicate key');
  assert.equal(
    __internal.planSub({ planName: 'Premium', planDescription: 'Deeper feedback.' }),
    'Premium · Deeper feedback.',
    'the Plan row\'s sub is assembled from real data, never a copy key',
  );
  assert.equal(__internal.planSub({ planName: '', planDescription: '' }), '', 'a missing plan is an empty sub, never invented text');
  assert.equal(__internal.rowSub({ id: 'plan', planName: 'Free', planDescription: 'Core.' }), 'Free · Core.', 'rowSub dispatches plan through planSub');

  const targetOpts = __internal.choiceOptions({ id: 'target', value: 'zh', options: [
    { code: 'en', name: 'English', nativeName: 'English' },
    { code: 'zh', name: 'Chinese', nativeName: '中文' },
  ] });
  assert.deepEqual(targetOpts.map((o) => o.label), ['English', 'Chinese · 中文'], 'English\'s own native name is not repeated; Chinese\'s is appended');
  assert.equal(targetOpts.find((o) => o.value === 'zh').selected, true);
  assert.equal(targetOpts.find((o) => o.value === 'en').selected, false);

  /* Regression (P1, independent review): under a Chinese interface, shellCopy('lang_zh') already
     resolves to "中文", so the duplicate-suppression check must compare against that translated
     label, not the backend's raw always-English `opt.name` - otherwise the Chinese option renders
     "中文 · 中文". Exercise the one interface language the assertions above never switch to. */
  copy.chooseInterface('zh');
  try {
    const targetOptsZh = __internal.choiceOptions({ id: 'target', value: 'zh', options: [
      { code: 'en', name: 'English', nativeName: 'English' },
      { code: 'zh', name: 'Chinese', nativeName: '中文' },
    ] });
    assert.deepEqual(
      targetOptsZh.map((o) => o.label),
      ['英语 · English', '中文'],
      'a Chinese interface must not repeat "中文 · 中文" for the Chinese target option (English\'s translated label still differs from its own native name, so it still appends)',
    );
  } finally {
    copy.chooseInterface('en');
  }

  const supportOpts = __internal.choiceOptions({ id: 'support', value: 'vi', options: [{ code: 'vi', label: 'Vietnamese' }, { code: 'ja', label: 'Japanese' }] });
  assert.deepEqual(supportOpts.map((o) => o.label), ['Vietnamese', 'Japanese'], 'support options keep the backend\'s own English label, untranslated (rule 26 governs Orena\'s chrome, not a language\'s own name)');

  const sizeOpts = __internal.choiceOptions({ id: 'readerSize', value: 'M', options: ['S', 'M', 'L'] });
  assert.deepEqual(sizeOpts.map((o) => o.label), [t('sizeS'), t('sizeM'), t('sizeL')]);
  assert.equal(sizeOpts.find((o) => o.value === 'M').selected, true);

  const themeOpts = __internal.choiceOptions({ id: 'theme', value: 'system', options: ['light', 'dark', 'system'] });
  assert.deepEqual(themeOpts.map((o) => o.value), ['light', 'dark', 'system']);
  assert.deepEqual(themeOpts.map((o) => o.label), [t('themeLight'), t('themeDark'), t('themeSystem')]);
  assert.equal(themeOpts.find((o) => o.value === 'system').selected, true, 'System is the default (D-089)');
  assert.equal(themeOpts.find((o) => o.value === 'light').selected, false);
  assert.equal(__internal.rowLabel({ id: 'theme' }), t('themeLabel'));
  assert.equal(__internal.rowSub({ id: 'theme' }), t('themeSub'), 'an ordinary row reads `${id}Sub`, no SUB_KEY override needed');
}

/* D-098: the support language is the frame's segmented control up to 4 options, a picker beyond. */
{
  const opts = (n) => Array.from({ length: n }, (_, i) => ({ code: `l${i}`, label: `L${i}` }));
  assert.equal(SEGMENTED_MAX_OPTIONS, 4);
  assert.equal(usesPicker({ id: 'support', options: opts(4) }), false, 'four languages: the segmented control');
  assert.equal(usesPicker({ id: 'support', options: opts(5) }), true, 'five: the picker');
  assert.equal(usesPicker({ id: 'interface', options: opts(9) }), false, 'only the support language row changes');
  assert.equal(usesPicker(null), false);
}

console.log('Settings: rows built from real data, every backend gap disabled and recorded, EN/VI/ZH covered: PASS');
