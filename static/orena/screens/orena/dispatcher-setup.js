/* The one seam Orena Home (home-session.js) and the Contextual panel (panel.js) both build their
   action dispatcher and their turn requests' locale through - so the two surfaces cannot drift
   into two different answers for "what can this client do right now" or "what language is the
   learner using" (independent review, 2026-09-29: both were previously copy-pasted per file, and
   the locale copy silently broke on the very first line that differed between the two shapes it
   was fed). */
import { createDispatcher } from '../../agent/dispatcher.js';
import { SCREENS } from '../../shell/screens.js';
import { byId } from '../../shell/routes.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { context as shellContext } from '../../shell/context.js';

export function go(target) {
  location.hash = target.startsWith('#') ? target : `#${target}`;
}

/* No confirmation UI is drawn anywhere in the pinned design for a CONFIRM-risk action (E5's six
   frames never draw one - the mock's own canonical streams never emit `unsave_word` either); the
   browser's own confirm() is the one primitive available that invents no app chrome. */
export async function confirmAction(action) {
  try {
    return window.confirm(action?.label ? String(action.label) : 'Continue?');
  } catch {
    return false;
  }
}

export function builtScreens() {
  return new Set(Object.keys(SCREENS));
}

export function createOrenaDispatcher() {
  return createDispatcher({
    api,
    go,
    learningLanguage: () => shellContext().language,
    confirm: confirmAction,
    hasRoute: (id) => Boolean(byId(id)),
  });
}

/* The one mapping from copy/index.js#languages() (its own `{ui, support}` shape) to
   session.js#buildRequest's `{interface, support, target}` (AGENT_CONTRACT §3 locale). Passing
   `languages()` straight into `buildRequest` reads `languages.interface`/`languages.target` -
   fields that do not exist on that object - and silently defaulted both to English on every turn
   (independent review P1, 2026-09-29). `target` is the learner's active learning language, which
   copy/index.js never carries; `shellContext().language` is the same read the dispatcher above
   already uses for `learningLanguage`. */
export function requestLanguages() {
  const { ui, support } = languages();
  return { interface: ui, support, target: shellContext().language };
}
