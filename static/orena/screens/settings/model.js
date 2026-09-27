/* Settings: pure data mapping only, no DOM (scripts/test_orena_screen_settings.mjs). screen.js
   owns the markup, the requests and the events; every row shape a tab needs comes from here as a
   plain descriptor `{ id, kind: 'choice'|'toggle'|'bar'|'action', ..., disabled }`, given the real
   inputs screen.js read from the API, the profile, device memory and the browser.

   `disabled` is the Design Contract rule 40 line: a row the frame draws but Orena has no real
   effect for is never wired to pretend, and never removed either (rule 43) - it is drawn, with its
   control inert. Every disabled row here is named in the report and in
   docs/project/UI_BACKEND_GAPS.md, not silently decided. */

export const TABS = Object.freeze(['languages', 'learning', 'review', 'notifications', 'plan']);

export function tabFromQuery(raw) {
  const value = String(raw || '').trim().toLowerCase();
  return TABS.includes(value) ? value : TABS[0];
}

/* A language's own endonym, invariant across every interface language - the same choice
   static/orena/app.js's own preferences dialog already makes (INTERFACE_NAMES), so a learner who
   cannot yet read English still recognises "English" as the option that means English. */
export const INTERFACE_ENDONYMS = Object.freeze({ en: 'English', vi: 'Tiếng Việt', zh: '中文' });
export const INTERFACE_LOCALES = Object.freeze(['en', 'vi', 'zh']);

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

export function interfaceLanguageOptions(locales = INTERFACE_LOCALES) {
  return locales.map((code) => ({ code, label: INTERFACE_ENDONYMS[code] || code }));
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

export function learningRows({ sizeBucket, autoscroll, meaning }) {
  return [
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
