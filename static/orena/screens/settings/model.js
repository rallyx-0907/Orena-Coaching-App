/* Settings: pure data mapping only, no DOM (scripts/test_orena_screen_settings.mjs). screen.js
   owns the markup, the requests and the events; every row shape a tab needs comes from here as a
   plain descriptor `{ id, kind: 'choice'|'toggle'|'bar'|'action', ..., disabled }`, given the real
   inputs screen.js read from the API, the profile, device memory and the browser.

   `disabled` is the Design Contract rule 40 line: a row the frame draws but Orena has no real
   effect for is never wired to pretend, and never removed either (rule 43) - it is drawn, with its
   control inert. Every disabled row here is named in the report and in
   docs/project/UI_BACKEND_GAPS.md, not silently decided. */
import { INTERFACE_ENDONYMS, INTERFACE_LOCALES, interfaceLanguageOptions as sharedInterfaceLanguageOptions } from '../../kit/lang.js';

/* Appearance and Accent are how Orena looks on this device, not how a learner studies, so they have their own
   tab (LEX-079); the frame draws neither, so no frame tab holds them. */
/* The 2026-10-09 design replaced "Plan & privacy" with "Privacy": the plan and its usage live on Plan & usage
   (screens/plan, reached from Profile), so this tab keeps only the microphone, learner audio and History. */
export const TABS = Object.freeze(['languages', 'appearance', 'learning', 'review', 'notifications', 'privacy']);
/* Old links (`?tab=plan`) land on the tab that replaced it. */
const TAB_ALIASES = Object.freeze({ plan: 'privacy' });
const APPEARANCE_ROW_IDS = Object.freeze(['theme', 'palette']);

export function tabFromQuery(raw) {
  const raw2 = String(raw || '').trim().toLowerCase();
  const value = TAB_ALIASES[raw2] || raw2;
  return TABS.includes(value) ? value : TABS[0];
}

/* A language's own endonym, invariant across every interface language - the same choice
   static/orena/app.js's own preferences dialog already makes (INTERFACE_NAMES), so a learner who
   cannot yet read English still recognises "English" as the option that means English. Shared with
   Onboarding's own Languages step (kit/lang.js), which draws the identical picker, so the two
   screens cannot independently diverge on it. */
export { INTERFACE_ENDONYMS, INTERFACE_LOCALES };

/* Target language: the two enabled learning languages the platform actually has
   (GET /api/platform/languages `languages[]`), each labelled with the interface's own translated
   name plus the language's real native_name when that differs from its English name (Chinese only
   - English's native_name is "English" too, so the design's "Chinese · 中文" shape, not a second
   "English · English"). */
export function targetLanguageOptions(languages) {
  return (Array.isArray(languages) ? languages : [])
    .filter((item) => item && item.enabled && item.code)
    .map((item) => ({ code: item.code, name: item.name || item.code, nativeName: item.native_name || '' }));
}

/* Support language: every one the platform lists (`support_languages[]`), labelled with the
   backend's own label exactly as static/orena/app.js's preferences dialog already renders it
   (shown by endonym, kit/lang.js SUPPORT_ENDONYMS - a language's own name, the same in every interface language). */
export function supportLanguageOptions(supportLanguages) {
  return (Array.isArray(supportLanguages) ? supportLanguages : [])
    .filter((item) => item && item.code && item.label)
    .map((item) => ({ code: item.code, label: item.label }));
}

/* The frame draws the support language as a segmented control, which holds a short list. Past
   this many options it becomes a picker - a button that opens a sheet of rows (D-098). */
export const SEGMENTED_MAX_OPTIONS = 4;

/* The Languages tab's three choices are always the picker, the way Support language looks (human, 2026-10-09). */
const ALWAYS_PICKER = Object.freeze(['target', 'support', 'interface']);

export function usesPicker(row) {
  if (ALWAYS_PICKER.includes(row?.id)) return true;
  return ['orenaVoice'].includes(row?.id) && Array.isArray(row.options) && row.options.length > SEGMENTED_MAX_OPTIONS;
}

export function interfaceLanguageOptions(locales = INTERFACE_LOCALES) {
  return sharedInterfaceLanguageOptions(locales);
}

export function languageRows({ languages, supportLanguages, targetCode, supportCode, interfaceCode }) {
  return [
    { id: 'target', kind: 'choice', options: targetLanguageOptions(languages), value: targetCode, disabled: false },
    { id: 'support', kind: 'choice', options: supportLanguageOptions(supportLanguages), value: supportCode, disabled: false },
    { id: 'interface', kind: 'choice', options: interfaceLanguageOptions(), value: interfaceCode, disabled: false },
  ];
}

/* Appearance (D-067 review item): Light / Dark / System, System the default (D-089). The design
   draws no appearance/theme group anywhere in Settings (docs/design/canonical-ui, frame 26 - every
   row across all five tabs is accounted for in the inventory and none is a theme control), so this
   row goes in the most fitting existing group rather than inventing one: Learning is the only tab
   that already holds a pure, device-only *display* preference with no language and no account
   effect - Reader text size - the same shape Appearance is. It leads the tab, since it is the most
   general of the group (it affects the whole app, not only the Reader). `theme` is already
   normalized by kit/device.js's `appearance()` (light/dark/system, an invalid value read back as
   system) - `appearanceValue` here is a second, independent fallback so this pure module never
   trusts its caller and never throws on an unexpected value either (the same defensive shape
   `sizeBucketOf` already gives Reader text size). */
const APPEARANCE_VALUES = Object.freeze(['light', 'dark', 'system']);
function appearanceValue(value) {
  return APPEARANCE_VALUES.includes(value) ? value : 'system';
}

/* Orena's voice (human request 2026-10-06, R29): offered only when the server's live voice is on and lists its
   voices; the value is the learner's stored choice, else the server's default. */
function voiceRow(voices) {
  const list = Array.isArray(voices?.voices) ? voices.voices.filter((v) => v && v.id) : [];
  if (!list.length) return [];
  const value = list.some((v) => v.id === voices.chosen) ? voices.chosen : (voices.default || list[0].id);
  return [{ id: 'orenaVoice', kind: 'choice', options: list, value, disabled: false }];
}

export function learningRows({ sizeBucket, autoscroll, meaning, theme, palette, voices = null }) {
  return [
    { id: 'theme', kind: 'choice', options: APPEARANCE_VALUES, value: appearanceValue(theme), disabled: false },
    { id: 'palette', kind: 'choice', options: ['indigo', 'orchid', 'blue', 'rose'], value: ['indigo', 'orchid', 'blue', 'rose'].includes(palette) ? palette : 'indigo', disabled: false },
    { id: 'readerSize', kind: 'choice', options: ['S', 'M', 'L'], value: sizeBucket, disabled: false },
    ...voiceRow(voices),
    { id: 'autoscroll', kind: 'toggle', value: Boolean(autoscroll), disabled: false },
    { id: 'meaning', kind: 'toggle', value: Boolean(meaning), disabled: false },
    // No real mechanism anywhere in the app measures or drives either of these two (grepped
    // capabilities/, product/ and every screen/ui module - UI_BACKEND_GAPS.md N-25/N-26).
    { id: 'wordHighlight', kind: 'toggle', value: false, disabled: true },
    { id: 'autoplay', kind: 'toggle', value: false, disabled: true },
  ];
}

/* Session length's own fallback when it is disabled - the middle of the design's three options,
   never a first/invented one, matching how every other clamped preference in this app (recall-
   modes.js's own newPerDay/limitPerDay) already resolves an absent value. */
export const SESSION_LENGTH_FALLBACK = '10';

export function reviewRows({ modes }) {
  const m = modes && typeof modes === 'object' ? modes : {};
  return [
    { id: 'targetMeaning', kind: 'toggle', value: Boolean(m.typing), disabled: false },
    { id: 'sourceAware', kind: 'toggle', value: Boolean(m.cloze), disabled: false },
    { id: 'audioWord', kind: 'toggle', value: Boolean(m.dictation), disabled: false },
    // No stored field means "items per sitting" anywhere (recall-modes.js has newPerDay/
    // limitPerDay, neither is this) - UI_BACKEND_GAPS.md N-27.
    { id: 'sessionLength', kind: 'choice', options: ['5', '10', '20'], value: SESSION_LENGTH_FALLBACK, disabled: true },
  ];
}

export function notificationRows() {
  // No notification-preference storage exists anywhere in the app at all (grepped the whole
  // repository); every row is a recorded gap - UI_BACKEND_GAPS.md N-28.
  return ['dueReview', 'writingReview', 'mediaReady', 'system'].map((id) => ({ id, kind: 'toggle', value: false, disabled: true }));
}

/* The public legal pages (D-161). They know the languages en and vi; a Chinese interface reads them in English,
   which is what the page itself does for `?lang=zh`, so the address says so. */
export function legalHref(path, lang) {
  return `${path}?lang=${lang === 'vi' ? 'vi' : lang === 'zh' ? 'zh' : 'en'}`;
}

export function privacyRows({ micOn, micState, lang } = {}) {
  return [
    { id: 'mic', kind: 'toggle', disabled: false, value: micOn === true, state: micState || 'unsupported' },
    // No route deletes a learner's stored audio/media - UI_BACKEND_GAPS.md N-31.
    { id: 'learnerAudio', kind: 'action', disabled: true },
    { id: 'history', kind: 'action', disabled: false },
    // Who made the dictionaries, recordings and texts, and under which licence (D-124).
    { id: 'licences', kind: 'action', disabled: false },
    // Pointers to the public pages, in the Licences link's own pattern: the privacy policy, the terms, and the
    // way to ask for the account to be deleted (there is no in-app deletion yet, so a link to the request page).
    { id: 'privacyPolicy', kind: 'link', href: legalHref('/privacy', lang) },
    { id: 'termsOfService', kind: 'link', href: legalHref('/terms', lang) },
    { id: 'deleteAccount', kind: 'link', href: legalHref('/account-deletion', lang) },
  ];
}

export function rowsForTab(tab, inputs) {
  if (tab === 'languages') return languageRows(inputs.languages);
  if (tab === 'appearance') return learningRows(inputs.learning).filter((row) => APPEARANCE_ROW_IDS.includes(row.id));
  if (tab === 'learning') return learningRows(inputs.learning).filter((row) => !APPEARANCE_ROW_IDS.includes(row.id));
  if (tab === 'review') return reviewRows(inputs.review);
  if (tab === 'notifications') return notificationRows();
  if (tab === 'privacy') return privacyRows(inputs.privacy);
  return [];
}
