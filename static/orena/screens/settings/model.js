/* Settings: pure data mapping only, no DOM (scripts/test_orena_screen_settings.mjs). screen.js
   owns the markup, the requests and the events; every row shape a tab needs comes from here as a
   plain descriptor `{ id, kind: 'choice'|'toggle'|'bar'|'action', ..., disabled }`, given the real
   inputs screen.js read from the API, the profile, device memory and the browser.

   `disabled` is the Design Contract rule 40 line: a row the frame draws but Orena has no real
   effect for is never wired to pretend, and never removed either (rule 43) - it is drawn, with its
   control inert. Every disabled row here is named in the report and in
   docs/project/UI_BACKEND_GAPS.md, not silently decided. */
import { INTERFACE_ENDONYMS, INTERFACE_LOCALES, interfaceLanguageOptions as sharedInterfaceLanguageOptions } from '../../kit/lang.js';

export const TABS = Object.freeze(['languages', 'learning', 'review', 'notifications', 'plan']);

export function tabFromQuery(raw) {
  const value = String(raw || '').trim().toLowerCase();
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
   (English language names, not translated per interface - a support language's own name is data,
   not chrome; rule 26 governs Orena's interface strings, not a language's own name). */
export function supportLanguageOptions(supportLanguages) {
  return (Array.isArray(supportLanguages) ? supportLanguages : [])
    .filter((item) => item && item.code && item.label)
    .map((item) => ({ code: item.code, label: item.label }));
}

/* The frame draws the support language as a segmented control, which holds a short list. Past
   this many options it becomes a picker - a button that opens a sheet of rows (D-098). */
export const SEGMENTED_MAX_OPTIONS = 4;

export function usesPicker(row) {
  return row?.id === 'support' && Array.isArray(row.options) && row.options.length > SEGMENTED_MAX_OPTIONS;
}

export function interfaceLanguageOptions(locales = INTERFACE_LOCALES) {
  return sharedInterfaceLanguageOptions(locales);
}

/* A quota bar's fill: 0 whenever the limit is not a real positive number (rule 40 - a metric with
   no measured value is 0, never invented), clamped so a usage figure larger than the limit never
   overflows the track. */
export function barPercent(used, limit) {
  const u = Number(used);
  const l = Number(limit);
  if (!Number.isFinite(u) || !Number.isFinite(l) || l <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((u / l) * 100)));
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

export function learningRows({ sizeBucket, autoscroll, meaning, theme, palette }) {
  return [
    { id: 'theme', kind: 'choice', options: APPEARANCE_VALUES, value: appearanceValue(theme), disabled: false },
    { id: 'palette', kind: 'choice', options: ['indigo', 'orchid', 'blue', 'rose'], value: ['indigo', 'orchid', 'blue', 'rose'].includes(palette) ? palette : 'indigo', disabled: false },
    { id: 'readerSize', kind: 'choice', options: ['S', 'M', 'L'], value: sizeBucket, disabled: false },
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

export function planRows({ plan, features, micOn, micState }) {
  const writingEvaluate = features && typeof features === 'object' ? features['writing.evaluate'] : null;
  return [
    { id: 'plan', kind: 'action', disabled: true, planName: plan?.name || '', planDescription: plan?.description || '' },
    // No entitlement key for AI-tutor messages or for pronunciation minutes exists in the plan
    // catalogue at all - UI_BACKEND_GAPS.md N-29/N-30.
    { id: 'messages', kind: 'bar', disabled: true, used: 0, limit: 0 },
    {
      id: 'writingReviews',
      kind: 'bar',
      disabled: !writingEvaluate,
      used: Number(writingEvaluate?.used) || 0,
      limit: Number(writingEvaluate?.monthly_limit) || 0,
    },
    { id: 'pronunciation', kind: 'bar', disabled: true, used: 0, limit: 0 },
    { id: 'mic', kind: 'toggle', disabled: false, value: micOn === true, state: micState || 'unsupported' },
    // No route deletes a learner's stored audio/media - UI_BACKEND_GAPS.md N-31.
    { id: 'learnerAudio', kind: 'action', disabled: true },
    { id: 'history', kind: 'action', disabled: false },
  ];
}

export function rowsForTab(tab, inputs) {
  if (tab === 'languages') return languageRows(inputs.languages);
  if (tab === 'learning') return learningRows(inputs.learning);
  if (tab === 'review') return reviewRows(inputs.review);
  if (tab === 'notifications') return notificationRows();
  if (tab === 'plan') return planRows(inputs.plan);
  return [];
}
