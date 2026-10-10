/* Why the learner was sent to Plans (D-17Q): the server's own refusal, kept in memory for the one screen that
   explains it. A refusal opens Plans at once (`#/plan/pricing?reason=language`); the figures it carries (limit,
   languages held, plan, and the language the learner tried to take) are the server's `context`, held here until the
   learner dismisses the explanation. Nothing is stored on a device or sent anywhere, and nothing here decides what
   a plan allows: if the page is reloaded the address still says why, and the explanation is then built from the plans
   alone. */
let held = null;

export const REASON_LANGUAGE = 'language';

export function holdLanguageRefusal(error, requested = '') {
  const context = error?.context && typeof error.context === 'object' ? error.context : {};
  held = {
    kind: REASON_LANGUAGE,
    category: String(error?.category || ''),
    limit: context.limit == null ? null : Number(context.limit),
    owned: context.owned == null ? null : Number(context.owned),
    languages: Array.isArray(context.languages) ? context.languages.map(String) : [],
    plan: String(context.plan || ''),
    requested: String(requested || ''),
  };
}

export function heldReason() {
  return held;
}

export function releaseReason() {
  held = null;
}
