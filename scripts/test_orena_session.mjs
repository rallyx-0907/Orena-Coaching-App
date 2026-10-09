/* Signing in to and out of the new learner UI: the pure decisions (shell/session.js), the 401 handler of
   infrastructure/api.js, and the signed-out Welcome/Account markup contract of the onboarding screen.
   The server half (the / allowlist, the callback, the logout) is tests/test_next_sign_in.py. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  SIGN_IN_PATH, SIGN_OUT_NEXT, signInHref, signOutUrl, isUnauthorized, bootOutcome, unauthorizedRoute, signedOutDestination,
} from '../static/orena/shell/session.js';
import { entryRoute, match } from '../static/orena/shell/routes.js';

const source = (path) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8');

/* --- the return target is always inside the server's allowlist (/, then ? or #) ---------------- */
{
  for (const mode of ['signup', 'login', undefined, 'anything']) {
    const href = signInHref(mode);
    assert.ok(href.startsWith(`${SIGN_IN_PATH}?next=`), 'the Google start, with a return target');
    const next = decodeURIComponent(href.slice(href.indexOf('=') + 1));
    assert.match(next, /^\/([?#]|$)/, `next stays at /: ${next}`);
    assert.ok(!next.includes('//') && !next.includes('\\') && !/\s/.test(next), 'no scheme, host, backslash or whitespace');
    assert.ok(!href.includes('#'), 'the fragment is encoded, so it reaches the server as part of next');
  }
  assert.equal(decodeURIComponent(signInHref('signup').split('=')[1]), '/#/welcome?step=languages', 'a new learner returns into setup at Languages');
  assert.equal(decodeURIComponent(signInHref('login').split('=')[1]), '/#/', 'a returning learner returns to the entry rule');
  assert.equal(signInHref(), signInHref('signup'), 'an unknown mode is the first-visit one');
  assert.equal(signOutUrl(), '/auth/logout?next=%2F');
  assert.equal(SIGN_OUT_NEXT, '/');
}

/* --- the entry decision after returning ---------------------------------------------------------- */
{
  // '#/' is the empty address: the router asks entryRoute. A returning learner opens Today, a new one Welcome.
  assert.equal(entryRoute({ profile: { exists: true, language: 'en' }, activeLanguage: 'en' }), 'today');
  assert.equal(entryRoute({ profile: { exists: false }, activeLanguage: 'en' }), 'welcome');
  // '#/welcome?step=languages' is the welcome route with the step as a query.
  const found = match('#/welcome?step=languages');
  assert.equal(found.route.id, 'welcome');
  assert.equal(found.query.get('step'), 'languages');
}

/* --- boot and the running app on a 401 ----------------------------------------------------------- */
{
  assert.equal(isUnauthorized({ status: 401 }), true);
  assert.equal(isUnauthorized({ status: 403 }), false, 'a refused learner is not a signed-out one');
  assert.equal(isUnauthorized(null), false);
  assert.equal(isUnauthorized(new Error('x')), false);
  assert.equal(bootOutcome({ status: 401 }), 'signed-out', 'the first read answering 401 draws the signed-out Welcome');
  assert.equal(bootOutcome({ status: 500 }), 'failed');
  assert.equal(bootOutcome(new TypeError('Failed to fetch')), 'failed', 'offline is the could-not-open notice, not Welcome');
  assert.equal(unauthorizedRoute('#/today'), '#/welcome');
  assert.equal(unauthorizedRoute('#/read/abc?tab=x'), '#/welcome');
  assert.equal(unauthorizedRoute(''), '#/welcome');
  assert.equal(unauthorizedRoute('#/welcome'), null, 'already there: no loop');
  assert.equal(unauthorizedRoute('#/welcome?step=languages'), null);
  assert.equal(unauthorizedRoute('#/legal/terms'), null, 'the legal pages are read signed out');
  assert.equal(signedOutDestination({ ok: true, next: '/#/welcome' }), '/#/welcome');
  assert.equal(signedOutDestination({ ok: true }), '/');
  assert.equal(signedOutDestination({ next: 'https://evil.example' }), '/', 'only a / target is followed');
  assert.equal(signedOutDestination({ next: '//evil.example' }), '/', 'a protocol-relative target is not followed');
  assert.equal(signedOutDestination({ next: '/admin-x' }), '/', 'a path other than / is not followed');
  assert.equal(signedOutDestination(null), '/');
}

/* --- infrastructure/api.js: 401 calls the installed handler; before one is installed, Welcome ------ */
{
  const location = { href: '' };
  globalThis.location = location;
  globalThis.window = globalThis;
  let status = 401;
  globalThis.fetch = async () => ({
    ok: status < 400,
    status,
    headers: { get: () => 'application/json' },
    json: async () => ({ detail: 'Authentication required' }),
  });
  const { request, setUnauthorizedHandler } = await import('../static/orena/infrastructure/api.js');

  await assert.rejects(() => request('/api/me'), (error) => error.status === 401);
  assert.equal(location.href, '/#/welcome', 'by default a 401 goes to Welcome (there is no /login page)');

  location.href = '';
  let calls = 0;
  setUnauthorizedHandler(() => { calls += 1; });
  await assert.rejects(() => request('/api/me'), (error) => error.status === 401, 'the error still reaches the caller');
  assert.equal(calls, 1, 'the new UI handler runs once per 401');
  assert.equal(location.href, '', 'and the default is not used');

  status = 500;
  await assert.rejects(() => request('/api/me'));
  assert.equal(calls, 1, 'only a 401 is a signed-out learner');
  setUnauthorizedHandler(null);
  status = 401;
  await assert.rejects(() => request('/api/me'));
  assert.equal(location.href, '', 'a non-function handler is a no-op, never a throw');
}

/* --- what the screens wire up ---------------------------------------------------------------------- */
{
  const main = source('../static/orena/main.js');
  assert.match(main, /bootOutcome\(error\) === 'signed-out'/, 'boot reads a 401 as signed out');
  assert.match(main, /setUnauthorizedHandler\(\(\) => \{\}\);/, 'the handler is silent while booting');
  assert.match(main, /unauthorizedRoute\(location\.hash\)/, 'a 401 in the running app goes to Welcome');

  const screen = source('../static/orena/screens/onboarding/screen.js');
  assert.match(screen, /data-action="welcome-login"/, 'Welcome draws "I already have an account" (O-01)');
  assert.match(screen, /signedOut\s*\? html`<div class="s-onboarding__cta s-onboarding__cta--welcome s-onboarding__cta--pair">/, 'only when signed out');
  assert.match(screen, /window\.location\.assign\(signInHref\(state\.mode\)\)/, 'Google is the one way in');
  assert.ok(!/type="(email|password)"/.test(screen), 'no email or password field is built (UI_BACKEND_GAPS: Email sign-in)');

  const profile = source('../static/orena/screens/profile/screen.js');
  assert.match(profile, /api\.logout\(SIGN_OUT_NEXT\)/, 'Sign out asks the server to return to /');
  assert.ok(!profile.includes("'/login'"), 'the learner UI never sends a learner to the retired sign-in page');

  // Every copy key the signed-out frames use exists in all three languages.
  const keys = ['haveAccount', 'signupTitle', 'signupSub', 'loginTitle', 'loginSub', 'tabSignup', 'tabLogin', 'googleCta', 'googleBusy', 'terms'];
  const copy = source('../static/orena/screens/onboarding/copy.js');
  for (const key of keys) {
    assert.equal(copy.split(`${key}:`).length - 1, 3, `${key} is written in English, Vietnamese and Chinese`);
  }
}

/* --- a signed-in learner is never gated by admin status; /account is retired --------------------------- */
{
  const fs2 = await import('node:fs');
  const path2 = await import('node:path');
  const main = source('../static/orena/main.js');
  const gate = main.slice(main.indexOf('const router = createRouter') - 900, main.indexOf('const router = createRouter'));
  assert.ok(!/shellCopy|t\('limited'\)|t\('account'\)/.test(gate), 'no limited notice is drawn before the router');
  assert.match(main, /if \(!learner\.isAdmin && isAdminHash\(location\.hash\)\)/, 'a non-admin is stopped only at an admin address');
  assert.ok(!/if \(!learner\.isAdmin\) \{/.test(main), 'no blanket non-admin gate');
  assert.ok(!/internal review/i.test(source('../static/orena/copy/shell.js')), 'the internal-review notice copy is gone');

  const walk = (dir) => fs2.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path2.join(dir, entry.name);
    return entry.isDirectory() ? (entry.name === 'vendor' ? [] : walk(full)) : /\.(js|css|html)$/.test(entry.name) ? [full] : [];
  });
  const root = new URL('../static/orena/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
  for (const file of walk(decodeURIComponent(root))) {
    const text = fs2.readFileSync(file, 'utf8');
    assert.ok(!/href=["']\/account["']|location\.(assign|replace)\(["']\/account/.test(text), `${file} links to the retired /account`);
  }

  // New / incomplete account -> Welcome (onboarding); completed -> Today; a reload with an address keeps it.
  assert.equal(entryRoute({ profile: { exists: false }, activeLanguage: 'en' }), 'welcome', 'a new account starts onboarding');
  assert.equal(entryRoute({ profile: { exists: true, language: '' }, activeLanguage: '' }), 'welcome', 'an account with no learning language starts onboarding');
  assert.equal(entryRoute({ profile: { exists: true, language: 'en' }, activeLanguage: 'en' }), 'today', 'a completed account opens Today');
  assert.equal(match('#/progress').route.id, 'progress', 'a reload keeps the place in the address');
  assert.equal(decodeURIComponent(signInHref('login').split('=')[1]), '/#/', 'the OAuth return target is honoured');
}

console.log('test_orena_session: ok');
