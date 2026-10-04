/* A word's meaning in the learner's support language (D-124).

   A vocabulary sense exists once; what a learner reads is that sense's localization for their
   current support language. The server already hands every saved word and catalogue card the
   sense's localizations, each tagged with its language (`short_meanings[]` from the corpus or the
   dictionary, `support_translations{}` from curated packs), so the choice is made here, once, for
   every surface - never by naming a language in a screen. Adding a support language adds rows of
   data; nothing in this file changes.

   `translation_vi` is a learner record's older copy of one localization (Vietnamese). It is read
   only as that language's localization, after the sense's own, and only for a Vietnamese support
   language - it is never a meaning model. A learner's own `definition` (what they were shown or
   typed when they saved the word) comes after the sense's localization: it is the learner's note,
   not the sense's meaning in this language. Pure: no I/O, no provider. */

const clean = (value) => String(value ?? '').trim();
const lower = (value) => clean(value).toLowerCase();

function listed(list, language) {
  for (const entry of Array.isArray(list) ? list : []) {
    if (entry && lower(entry.language) === language && clean(entry.text)) return clean(entry.text);
  }
  return '';
}

/* The sense's localization for exactly this support language, or null. */
export function localizedMeaning(item, supportLanguage) {
  const language = lower(supportLanguage);
  if (!item || !language) return null;
  const fromSense = listed(item.short_meanings, language) || clean(item.support_translations?.[language]);
  if (fromSense) return { text: fromSense, language, source: 'localization' };
  if (language === 'vi' && clean(item.translation_vi)) {
    return { text: clean(item.translation_vi), language, source: 'saved' };
  }
  return null;
}

/* The label a meaning carries when it is not in the learner's support language (D-124): the
   language's own name in the interface language ("Tiếng Anh", "English", "英语"), from the
   browser's language data - no table to keep. Empty when the meaning is in the support language
   or its language is unknown, so a label is never shown for nothing. */
export function meaningLanguageLabel(language, supportLanguage, ui = 'en') {
  const code = lower(language);
  if (!code || code === lower(supportLanguage)) return '';
  try {
    return new Intl.DisplayNames([ui || 'en'], { type: 'language' }).of(code) || code;
  } catch {
    return code;
  }
}

/* The meaning to show: this language's localization, else the learner's own note, else the
   sense's localization in another language (tagged with that language so a caller can say so),
   else null. The sense's own-language definition is not a localization and is not chosen here. */
export function vocabularyMeaning(item, supportLanguage) {
  const localized = localizedMeaning(item, supportLanguage);
  if (localized) return localized;
  const note = clean(item?.definition);
  if (note) return { text: note, language: '', source: 'note' };
  const own = lower(item?.language_code || item?.identity?.language);
  for (const entry of Array.isArray(item?.short_meanings) ? item.short_meanings : []) {
    const language = lower(entry?.language);
    if (language && language !== own && clean(entry?.text)) {
      return { text: clean(entry.text), language, source: 'other_language' };
    }
  }
  return null;
}
