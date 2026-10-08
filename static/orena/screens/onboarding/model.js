/* Onboarding: pure data mapping only, no DOM (scripts/test_orena_screen_onboarding.mjs). screen.js
   owns the markup, the requests and the events; every shape a step needs comes from here, given the
   real inputs screen.js already has (shell/context.js's context, GET /api/platform/languages).

   Five steps (Onboarding.dc.html frames 01-05), recomposed against real product truth rather than
   the prototype script's own fake-timer/local-state behaviour (CLAUDE.md "The UI" rule 1; the
   surface brief's Wave B note: "canned scores, demo attempts ... are NOT behaviour to copy"):

   - 02 Account: the app requires auth before /next is ever reached (main.js boot), so there is no
     separate signup/login to build (a human/architecture gate - AGENTS.md §1 "Architecture review
     authority", account/auth changes need independent review). The step shows the identity already
     established, not a credential form. Frame 01 Welcome's two buttons ("Get started" /
     "I already have an account") led to that same now-removed form with only a local `mode` flag
     difference; with no second destination behind either, only one continues (rule 44 - no live
     destination, no interaction) - "welcomeCta" below.
   - 04 Level: the frame's 5-question placement check (`QS` in the prototype script) is invented
     grammar-quiz content with no backend source (no placement-test API exists anywhere in this
     app - grepped) - keeping it would ship fabricated pedagogical content as real (rule 40). Only
     the self-pick path (the frame's `noScore` branch) is built: CEFR/HSK are real, standard
     frameworks, not invented data.
   - 05 Meet Orena: the frame's scripted chat (starter chips, a free-text composer, a local
     regex-matched fake-AI `answer()`) is prototype-only; no chat capability exists yet anywhere in
     this build (the `orena` route itself is still Coming Soon) and `shell/agent-bridge.js`'s
     `askOrena()` only navigates away when no agent panel is registered. Built to the task brief's
     own instruction: "the agent's mark and an opening line from the mock at most." */
import { INTERFACE_LOCALES, INTERFACE_ENDONYMS, interfaceLanguageOptions, appendNativeName, primaryLanguage } from '../../kit/lang.js';

export const STEP_COUNT = 5;
export const STEPS = Object.freeze(['welcome', 'account', 'languages', 'level', 'orena']);

/* The step position: clamped to a real step, never NaN/negative/overflowing - the same zero-
   fallback shape kit/device.js's own `normalize()` uses. Read back from sessionStorage (session,
   not learner, state - the same non-learner-owned convenience shell/router.js's own ORIGIN_KEY/
   DEPTH_KEY already use) so a full remount (an interface-language change on step 2 re-runs the
   router - copy/index.js's onLanguageChange) does not drop the learner back to Welcome. */
export function clampStep(value) {
  const n = Math.round(Number(value));
  if (!Number.isFinite(n)) return 0;
  return Math.min(STEP_COUNT - 1, Math.max(0, n));
}

/* The aside/top-bar step list: a filled dot up to the current step, the current step lit, later
   steps outlined - Onboarding.dc.html's own `stepList` shape (`glyph`, `done`, `current`). */
export function stepDots(step, labels) {
  return labels.map((label, i) => ({ label, done: i < step, current: i === step }));
}

/* ---- 02 Account: the identity already established (GET /api/me, held on shell/context.js's own
   `user`) ------------------------------------------------------------------------------------- */
export function identityOf(user) {
  const u = user && typeof user === 'object' ? user : {};
  // A local (no sign-in) session has no name of its own: the server answers a fixed placeholder
  // ("Local user") there, which is never shown (mobile QA BUG-06; O-11).
  const name = u.mode === 'local' ? '' : String(u.name || '').trim();
  const email = String(u.email || '').trim();
  const picture = typeof u.picture === 'string' && /^https:\/\//.test(u.picture) ? u.picture : '';
  return {
    name,
    initial: name ? name.charAt(0).toLocaleUpperCase() : '',
    email,
    picture,
    google: u.mode === 'google',
  };
}

/* ---- 03 Languages ---------------------------------------------------------------------------- */

/* Target-language tile presentation (glyph/tint/font): the design's own per-language look
   (Onboarding.dc.html `targets`), kept as data here so the gate can check it never drifts to a raw
   hex - every tint is one of kit/tokens.css's own skill hues (rule: colour has one owner), the
   closest existing tokens to the frame's literal #4867EC/#EE4F6C (both confirmed identical to
   --skill-grammar/--skill-speak - see the report's "kit requests"). */
const TARGET_TILE = Object.freeze({
  en: { glyph: 'En', font: 'inherit', tint: 'var(--skill-grammar)' },
  zh: { glyph: '中', font: "'Noto Sans SC', sans-serif", tint: 'var(--skill-speak)' },
});

/* shell/context.js's own `languageOptions` (GET /api/session/bootstrap `language.options`) - the
   learning languages the platform actually has enabled, already resolved by the server (no client-
   side enabled filter needed, unlike settings/model.js's separate GET /api/platform/languages read
   - this screen reuses what boot already fetched rather than asking again). */
export function targetOptions(languageOptions, activeCode) {
  return (Array.isArray(languageOptions) ? languageOptions : [])
    .filter((item) => item && item.code)
    .map((item) => ({
      code: item.code,
      name: item.name || item.code,
      nativeName: item.native_name || '',
      selected: item.code === activeCode,
      ...(TARGET_TILE[item.code] || TARGET_TILE.en),
    }));
}

/* A target tile's label: the interface's own translated language name (shellCopy `lang_en`/
   `lang_zh`, passed in as `langLabel`). The frame appends the language's own name only in English
   ("Chinese · 中文", where the script is unfamiliar) and draws the bare translated name in
   Vietnamese ("Tiếng Trung"). The doubling guard itself - never repeat a name already in its own
   script ("中文 · 中文") - is shared with settings/screen.js's own `targetOptionLabel`
   (kit/lang.js's `appendNativeName`, the same P1 fix both screens once had to make independently);
   only the extra "English interface only" gate around it is this step's own. */
export function targetLabel(option, langLabel, uiLocale = 'en') {
  return uiLocale === 'en' ? appendNativeName(langLabel, option.nativeName) : langLabel;
}

/* A language written in itself ("Tiếng Việt", "中文", "Español"): the frame draws the support
   languages as endonyms in every interface language, so a learner finds their own language by its
   name whichever language the buttons are in. From the platform's own CLDR names, never a hand-kept
   table; an unknown code or a platform without display names falls back to `fallback` (the
   backend's own label), then the code. */
export function endonym(code, fallback = '') {
  const key = String(code || '').trim();
  if (!key) return fallback;
  try {
    const name = new Intl.DisplayNames([key], { type: 'language' }).of(key);
    if (name && name !== key) return name.charAt(0).toLocaleUpperCase(key) + name.slice(1);
  } catch {
    /* an invalid code or a platform without display names - the fallback below */
  }
  return fallback || key;
}

/* GET /api/platform/languages `support_languages[]` ({code,label}) - every support language the
   backend lists, each named in itself (`endonym`, the backend's English `label` only when the
   platform has no name for it). When that list could not be read, the learner's current support
   language - real state from the profile - is the one pill shown (selected), so the group never
   draws empty. */
export function supportOptions(list, current) {
  const options = (Array.isArray(list) ? list : [])
    .filter((item) => item && item.code && item.label)
    .map((item) => ({ code: item.code, label: endonym(item.code, item.label), selected: item.code === current }));
  if (!options.length && current) return [{ code: current, label: endonym(current), selected: true }];
  return options;
}

/* The support-language pills the step draws (the frame draws two, HO-6 A): the languages a learner is
   most likely to want - the current one, the interface locales and the browser's own languages - in
   the backend's order, each only if the platform lists it as a support language. Every other language
   is reached through the "More" picker (the one Settings uses, endonym rows), which lists them all.
   `rest` is true when the pills leave any listed language out. */
export function supportShortlist(options, { current = '', interfaceCodes = INTERFACE_LOCALES, browser = [] } = {}) {
  const list = Array.isArray(options) ? options : [];
  const likely = new Set([current, ...interfaceCodes, ...(Array.isArray(browser) ? browser : []).map((tag) => primaryLanguage(tag, ''))].filter(Boolean));
  const pills = list.filter((option) => likely.has(option.code));
  const shown = pills.length ? pills : list.slice(0, 2);
  return { pills: shown, rest: shown.length < list.length };
}

/* Shared with settings/model.js's own identical picker (kit/lang.js) - only the `selected` overlay
   below (this step marks the active pick inline; Settings computes its own downstream) is this
   screen's own. */
export { INTERFACE_LOCALES, INTERFACE_ENDONYMS };

export function interfaceOptions(current, locales = INTERFACE_LOCALES) {
  return interfaceLanguageOptions(locales).map((option) => ({ ...option, selected: option.code === current }));
}

/* ---- 04 Level: CEFR for English, HSK for Chinese (real, standard frameworks - not invented) ---
   A row's `code` is the platform's own code (GET /api/platform/languages `languages[].levels`:
   "B1", "HSK3") - the value the shell's level and the profile's `declared_level` carry - and its
   `label` is what the cell draws ("HSK 3", the frame's spacing). The names and descriptions are the
   frame's, in three languages. The frame's HSK word counts are the older HSK's, while the platform
   lists the newer scale (HSK7-9 exists), so no count is claimed. */

const levelEntry = (code, label, copyKey) => Object.freeze({ code, label, nameKey: `level${copyKey}Name`, descKey: `level${copyKey}Desc` });

export const LEVELS = Object.freeze({
  en: Object.freeze([
    levelEntry('A1', 'A1', 'A1'), levelEntry('A2', 'A2', 'A2'), levelEntry('B1', 'B1', 'B1'),
    levelEntry('B2', 'B2', 'B2'), levelEntry('C1', 'C1', 'C1'), levelEntry('C2', 'C2', 'C2'),
  ]),
  zh: Object.freeze([
    levelEntry('HSK1', 'HSK 1', 'H1'), levelEntry('HSK2', 'HSK 2', 'H2'), levelEntry('HSK3', 'HSK 3', 'H3'),
    levelEntry('HSK4', 'HSK 4', 'H4'), levelEntry('HSK5', 'HSK 5', 'H5'), levelEntry('HSK6', 'HSK 6', 'H6'),
    // One band after HSK 6, as the server's registry holds it (human decision, 2026-09-30).
    levelEntry('HSK7-9', 'HSK 7–9', 'H79'),
  ]),
});

/* The grid for a learning language: the frame's levels the platform lists for it (`listed`, the
   language's `levels` from GET /api/platform/languages), in the frame's order. HSK 7-9 is one cell
   after HSK 6, never three; when the platform's list cannot be read, or names none of these, the
   whole table stands. */
export function levelsFor(language, listed) {
  const table = LEVELS[language === 'zh' ? 'zh' : 'en'];
  const codes = Array.isArray(listed) ? listed.map(String) : [];
  const rows = table.filter((entry) => codes.includes(entry.code));
  return rows.length ? rows : table;
}

/* The middle of the grid (index 2 of 0-5: B1/HSK 3, the prototype script's own `zh?"HSK 3":"B1"`
   fallback) - never a first/invented pick, the same fallback shape settings/model.js's
   SESSION_LENGTH_FALLBACK already uses for a value nothing has measured yet. The HSK 7-9 band extends
   the top of the scale, not its middle, so the middle is taken over the frame's six. */
const FRAME_CELLS = 6;
function middleIndex(levels) {
  return Math.floor((Math.min(levels.length, FRAME_CELLS) - 1) / 2);
}

export function defaultLevelCode(levels) {
  return levels[middleIndex(levels)].code;
}

export function levelRow(levels, code) {
  return levels.find((entry) => entry.code === code) || levels[middleIndex(levels)];
}

/* The learner's pick is stored as `declared_level` (D4 I1, migration 0017): the code of the scope
   language's own list, validated by the server against the language registry (HSK7-9 is one band, not
   three). Only a code the frame draws a cell for, or one the platform lists for the language
   (`listed`, GET /api/platform/languages `languages[].levels`), is ever sent; anything else is null,
   and a failed or skipped save never blocks the flow and never claims a save that did not happen
   (rule 40). HSK7-9 is offered as one band after HSK 6 (human decision, 2026-09-30). */
export function declaredLevelPatch(code, listed, language = '') {
  const value = String(code || '');
  if (!value) return null;
  const framed = LEVELS[language === 'zh' ? 'zh' : 'en'].map((entry) => entry.code);
  const offered = Array.isArray(listed) && listed.length ? listed.map(String) : framed;
  return offered.includes(value) ? { declared_level: value } : null;
}

/* ---- 05 Meet Orena: a template greeting from real, already-known state - no AI call, no chat --- */

/* A language's name written in `locale` (the language the sentence around it renders in), from the
   platform's own CLDR names - never a hand-kept table, so it covers every support language the
   backend lists in every interface language. Vietnamese names its languages with a leading common
   noun ("tiếng Anh"), which mid-sentence takes a lower-case first letter (the one place a
   language's own grammar changes the string, so the one place this branches). An unknown code or a
   platform without the names falls back to `fallback` (the backend's own label), then the code. */
export function languageName(code, locale, fallback = '') {
  const key = String(code || '').trim();
  if (!key) return fallback;
  try {
    const name = new Intl.DisplayNames([locale || 'en'], { type: 'language' }).of(key);
    if (name && name !== key) return locale === 'vi' ? name.charAt(0).toLocaleLowerCase('vi') + name.slice(1) : name;
  } catch {
    /* an invalid code or a platform without display names - the fallback below */
  }
  return fallback || key;
}

/* `target` and `support` are language codes (the learning language and the support language); the
   caller names them in the greeting's own language with languageName(). `level` is the label of the
   learner's pick (`picked`, a code from `levels`; the context's own level when there is no pick).
   `name` is the signed-in name as the account gives it, or '' (a device with no sign-in, a name-less
   account) - the copy has a separate line for a learner with none, never "Hi !". The frame greets
   the first word of the name; which word of a name is the given one depends on the culture (a
   Vietnamese name ends with it), so the whole name is used, as Today's own greeting does. */
export function greetingParams(context, supportCode = '', { levels, picked } = {}) {
  const target = context?.language === 'zh' ? 'zh' : 'en';
  // A level in the other framework (a stored CEFR level while learning Chinese) is not this
  // learner's level in this language - the same middle default the Level step itself opens on.
  const grid = levels || levelsFor(target);
  const level = levelRow(grid, picked ?? context?.level).label;
  // A local (no sign-in) device has no name of its own - GET /api/me answers a fixed placeholder
  // there - so only an account that supplies one is greeted by it.
  const name = context?.user?.mode === 'local' ? '' : String(context?.name || '').trim().replace(/\s+/g, ' ');
  return { name, level, target, support: String(supportCode || '').trim().toLowerCase() || 'en', zh: target === 'zh' };
}
