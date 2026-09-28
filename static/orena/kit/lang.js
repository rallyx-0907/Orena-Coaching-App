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
   the ad-hoc `? 'zh' : ''` string this build used to repeat per screen lives in one place. */
import { html } from './html.js';

/* Every language code this build's UI ever needs to stamp on learner-facing text: the three
   interface locales (copy/index.js LOCALES) plus 'zh', the one learning language that is not also
   an interface locale (English, the other learning language, already is one). An unrecognised value
   (empty string, `undefined`, a stray guess) renders no `lang` attribute at all - always safer than
   a wrong one. */
const KNOWN = new Set(['en', 'vi', 'zh']);

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
