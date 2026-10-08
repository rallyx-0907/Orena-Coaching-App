/* Marking learning-language text with its own `lang` attribute (WCAG 3.1.2 "Language of Parts";
   language-finish task, findings A). The page's own `html[lang]` always tracks the *interface*
   language (copy/index.js#setLanguages) - never the learner's active learning language. A screen
   that shows real learning-language data (a saved headword, an example sentence, an article/media
   title, a transcript excerpt) marks that one piece of text with the language the DATA declares:
   an item's own field when the API returns one (an article's `language`, a media item's
   `language`, a collection's `language_code`, a saved word's `identity.language`), the content's
   own field, or - when no per-item field exists - the learner's own active learning language the
   screen already read (`ctx.context().language`, product/languages.js#learningLanguage: 'en' | 'zh'
   today). Never a script-sniffing regex here: a regex cannot tell English from Vietnamese, or
   Chinese from Japanese. Where no real language signal exists at all for a piece of text, a screen
   leaves it unmarked (this module renders it bare) rather than guess - safer than a wrong `lang`.

   The one documented exception is Word Detail's own script check (screens/word/model.js's `HAN`
   test): a saved word carries no per-item language field from the backend at all (becoming_
   library.py never returns `language_code`, only uses it to scope the query), so the backend's own
   `POST /api/dictionary/word-detail` answer falls back to the identical Han-range check
   (writing_coach/word_detail.py `script_of`) to tell a Chinese headword from an English one - this
   module's helpers are still used to turn that script into the `lang` attribute value itself, so
   the ad-hoc `? 'zh' : ''` string this build used to repeat per screen lives in one place.

   A second, related concern lives here too: naming the interface language itself. Settings'
   Languages tab and Onboarding's Languages step both draw a three-way interface-language picker
   (English/Tiếng Việt/中文, each in its own script so a learner who cannot yet read a given
   interface language still recognises it - the same choice static/orena/app.js's own preferences
   dialog already makes) and both label a target-learning-language option with its own native name
   appended only when that differs from the translated label (English's native name repeats its
   translated name; Chinese's does not) - the guard against doubling to "中文 · 中文" once a name is
   already in its own script. Two independent screen units each built this once and each had to fix
   the same doubling bug separately (independent review, Wave B) - `INTERFACE_LOCALES`/
   `INTERFACE_ENDONYMS`/`interfaceLanguageOptions`/`appendNativeName` below are the one shared
   implementation both screens' own model.js now import, so a future fix cannot diverge a third
   time. Pure data, no DOM, importable from a model.js's own Node gate with no window/document stub -
   same purity contract as knownLang/langAttr/langSpan above. */
import { html } from './html.js';

/* The three interface locales this build supports (copy/index.js's own LOCALES, identical - kept
   here too since a model.js file stays DOM-free and copy/index.js is not: it reads
   window.localStorage/navigator and writes document.documentElement.lang at import time, which
   would break a model.js's own no-stub Node gate). */
export const INTERFACE_LOCALES = Object.freeze(['en', 'vi', 'zh']);

/* A locale's own endonym - invariant across which interface language is currently active. */
export const INTERFACE_ENDONYMS = Object.freeze({ en: 'English', vi: 'Tiếng Việt', zh: '中文' });

/* A support language's own endonym, by the platform's `support_languages[].code` - invariant across the
   interface language, as INTERFACE_ENDONYMS is. A code this table does not hold keeps the platform's own label. */
export const SUPPORT_ENDONYMS = Object.freeze({
  en: 'English', vi: 'Tiếng Việt', zh: '中文 (简体)', ja: '日本語', ko: '한국어', es: 'Español', fr: 'Français',
  de: 'Deutsch', pt: 'Português', ru: 'Русский', id: 'Bahasa Indonesia', th: 'ไทย',
});

export function supportLanguageLabel(code, fallback = '') {
  return SUPPORT_ENDONYMS[code] || fallback || String(code || '');
}

/* The interface-language picker's options: every supported locale, named in itself. `selected` is
   left for the caller to overlay when it wants one (Onboarding marks the active pick inline;
   Settings computes its own `selected` downstream against the row's live value), so this stays the
   one shared shape both draw from rather than two screens each deciding it separately. */
export function interfaceLanguageOptions(locales = INTERFACE_LOCALES) {
  return locales.map((code) => ({ code, label: INTERFACE_ENDONYMS[code] || code }));
}

/* The doubling guard: append a language's own native name to its translated label only when the
   two differ, so a name already in its own script ("中文") is never repeated ("中文 · 中文"). */
export function appendNativeName(translated, nativeName) {
  return nativeName && nativeName !== translated ? `${translated} · ${nativeName}` : translated;
}

/* Every language code this build's UI ever needs to stamp on learner-facing text: the three
   interface locales (copy/index.js LOCALES) plus 'zh', the one learning language that is not also
   an interface locale (English, the other learning language, already is one). An unrecognised value
   (empty string, `undefined`, a stray guess) renders no `lang` attribute at all - always safer than
   a wrong one. */
const KNOWN = new Set(['en', 'vi', 'zh']);

/* A regional provider tag describes the same learning language. An unknown tag
   uses only the caller's explicit fallback, never a script-based guess. */
export function primaryLanguage(tag, fallback = 'en') {
  const primary = String(tag || '').trim().toLowerCase().split(/[-_]/)[0];
  return !primary || primary === 'und' ? fallback : primary;
}

export function knownLang(code) {
  const value = String(code || '').trim().toLowerCase();
  return KNOWN.has(value) ? value : '';
}

/* For an attribute already on an owning element a screen controls directly, e.g.
   `lang="${langAttr(item.language)}"`. An unknown language renders `lang=""`, which browsers and
   assistive tech already treat as "language not specified" - identical in effect to omitting the
   attribute, never a guessed code. */
export function langAttr(code) {
  return knownLang(code);
}

/* Wraps content that has no element of its own to carry the attribute (a card title handed to a
   shared kit component such as mediaCard()/listRow()/heroMedia(), a plain list item) in a bare
   `<span lang="…">`. `content` may be a plain string (escaped like any other kit/html.js
   interpolation) or already-built Markup (another `html` template, e.g. a highlighted example) -
   both compose the same way they would inside any other `html` template, because this returns the
   same Markup type. Content whose language is not known renders unwrapped. */
export function langSpan(content, code) {
  const lang = knownLang(code);
  return lang ? html`<span lang="${lang}">${content}</span>` : html`${content}`;
}
