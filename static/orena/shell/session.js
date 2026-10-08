/* Signing in and out of the new learner UI. Pure decisions, no DOM and no requests, so the node gate
   (scripts/test_orena_session.mjs) can pin them.

   The server only knows Google (auth_support.py). `/auth/google?next=...` accepts a return target that
   must be `/` or continue with `?` or `#`; anything else it replaces with `/`, so what is built here is
   always inside that allowlist and never a place of its own choosing.

   - A first sign-in from "Get started" returns into onboarding at its Languages step.
   - A sign-in from "I already have an account" returns to the empty address: the entry rule
     (shell/routes.js entryRoute) opens Today for a learner who has a profile and Welcome for one who
     has not, so a returning learner is never sent through setup and a new one is never sent past it.
   - A 401 from any request while the app is running means the session ended: the learner goes to
     Welcome, never to an error. */

export const SIGN_IN_PATH = '/auth/google';
export const SIGN_OUT_PATH = '/auth/logout';
export const SIGN_OUT_NEXT = '/';

const RETURN_TARGET = Object.freeze({
  signup: '/#/welcome?step=languages',
  login: '/#/',
});

/* `mode` is the design's own: 'signup' (Get started, "Create account") or 'login' ("I already have an account", "Log in"). */
export function signInHref(mode) {
  const next = RETURN_TARGET[mode === 'login' ? 'login' : 'signup'];
  return `${SIGN_IN_PATH}?next=${encodeURIComponent(next)}`;
}

export function signOutUrl(next = SIGN_OUT_NEXT) {
  return `${SIGN_OUT_PATH}?next=${encodeURIComponent(next)}`;
}

export function isUnauthorized(error) {
  return Boolean(error) && error.status === 401;
}

/* What boot does with the failure of its first read: a 401 is "nobody is signed in" and draws the
   signed-out Welcome; anything else is the app's own could-not-open notice. */
export function bootOutcome(error) {
  return isUnauthorized(error) ? 'signed-out' : 'failed';
}

/* A 401 while the app runs: leave for Welcome, unless the learner is already on a page that is read
   signed out (Welcome itself, the legal pages). */
export function unauthorizedRoute(hash = '') {
  const path = String(hash).replace(/^#\/?/, '').split('?')[0].replace(/\/+$/, '');
  if (path === 'welcome' || path.startsWith('legal/')) return null;
  return '#/welcome';
}

/* Where Sign out goes. A server that did not name one (an older build) still ends at the learner UI. */
export function signedOutDestination(body) {
  const next = body && typeof body === 'object' ? body.next : '';
  return typeof next === 'string' && /^\/(?:[?#]|$)/.test(next) ? next : SIGN_OUT_NEXT;
}
