/* The three language layers, resolved in one place (docs/product/ORENA_LANGUAGE_COHERENCE.md).

   - interface: what the chrome speaks - navigation, buttons, menus, Settings, system labels.
   - support:   what explains - translations, hints, instructions, feedback, guidance.
   - language:  what is being learned - the line, the word, the transcript, the exercise.

   None is inferred from another, ever. Each has its own source:

   - interface  the learner's own choice of interface language. The account cannot keep it yet
                (`account_profile.py`: `interface_language` is declared, `stored=False`; its column is
                a gated migration), so the device keeps it, under INTERFACE_KEY. Unchosen, it is the
                browser's language when Orena speaks it, else English. Never the support language.
   - support    the account's support language (`support_language`, else `native_language`).
   - language   the learning language the server says is active.

   Anything else a device may hold (an older `orena.support` cache, a profile read before a change
   elsewhere) is not a source and is never read to decide a layer. */

export const INTERFACE_KEY = 'orena.interface';

const tag = (value) => String(value || '').trim().toLowerCase();

/* A code Orena has an interface for, from a stored value or a browser tag ("zh-Hans", "vi-VN"). */
export function matchLocale(value, supported) {
  const code = tag(value);
  if (!code) return '';
  if (supported.includes(code)) return code;
  const base = code.split(/[-_]/)[0];
  return supported.includes(base) ? base : '';
}

export function interfaceLanguage({ stored = '', browser = [], supported = ['en'] } = {}) {
  return (
    matchLocale(stored, supported) ||
    [...(browser || [])].map((value) => matchLocale(value, supported)).find(Boolean) ||
    (supported.includes('en') ? 'en' : supported[0])
  );
}

export function supportLanguage(profile) {
  return tag(profile?.support_language) || tag(profile?.native_language) || 'en';
}

export function learningLanguage(active) {
  return tag(active) || 'en';
}

/* All three at once, each from its own source. */
export function resolveLanguages({ stored, browser, supported, profile, active } = {}) {
  return {
    ui: interfaceLanguage({ stored, browser, supported }),
    support: supportLanguage(profile),
    language: learningLanguage(active),
  };
}

/* Which of Orena's written packs carries guidance for a support language. Twelve support languages
   exist and three packs are written (en, vi, zh); a support language without one reads its guidance
   in English - the documented fallback - and never in the interface language instead. */
export function guidanceLocale(support, packs) {
  const code = matchLocale(support, packs);
  return code || 'en';
}
