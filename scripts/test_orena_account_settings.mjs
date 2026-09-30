/* Account-wide settings client (product/account-settings.js; D4 I2/I3/I3b/I13, D-104 H-17).
   The token is opaque: echoed verbatim, one re-read and re-apply on a 409, never parsed, and
   nothing is sent (or claimed) for an account with no row to hold settings. A stub fetch stands in
   for the network only. */
import assert from 'node:assert/strict';

globalThis.location = { href: '' };
const calls = [];
let script = [];
globalThis.fetch = async (url, options = {}) => {
  calls.push({ url, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : null });
  const next = script.shift();
  if (!next) throw new Error(`unscripted call ${url}`);
  return {
    ok: next.status < 400,
    status: next.status,
    headers: { get: () => 'application/json' },
    json: async () => next.body,
  };
};
const { selectLearningLanguage, saveAccountSettings, reconcileInterface, reviewFromProfile, saveReviewSettings } =
  await import('../static/orena/product/account-settings.js');

const reset = (...steps) => { calls.length = 0; script = steps; };
const account = (version, extra = {}) => ({ status: 200, body: { stored: true, settings_version: version, interface_language: '', learning_language: '', weekly_goal_days: null, ...extra } });

/* The learning language is switched against the token just read, echoed verbatim. */
reset(account('2026-09-30T10:00:00.123456+00:00'), { status: 200, body: { ok: true, active: 'zh', stored: true, settings_version: 'v2' } });
await selectLearningLanguage('zh');
assert.deepEqual(calls[1].body, { language: 'zh', settings_version: '2026-09-30T10:00:00.123456+00:00' }, 'the microseconds survive');

/* A 409 re-reads and re-applies once; a second 409 is given up on. */
reset(account('a'), { status: 409, body: { detail: { reason: 'version_conflict' } } }, account('b'), { status: 200, body: { ok: true } });
await selectLearningLanguage('en');
assert.equal(calls[3].body.settings_version, 'b', 'the retry carries the fresh token');
reset(account('a'), { status: 409, body: {} }, account('b'), { status: 409, body: {} });
await assert.rejects(() => selectLearningLanguage('en'), (error) => error.status === 409);

/* An account with no row: the session still switches, no token is sent. */
reset({ status: 200, body: { stored: false, settings_version: '' } }, { status: 200, body: { ok: true } });
await selectLearningLanguage('en');
assert.deepEqual(calls[1].body, { language: 'en' });
reset({ status: 200, body: { stored: false, settings_version: '' } });
assert.equal(await saveAccountSettings({ interface_language: 'vi' }), null);
assert.equal(calls.length, 1, 'nothing written for an account with nowhere to keep it');

/* Scalars are written against the token; an empty token is the never-written state. */
reset(account(''), { status: 200, body: { stored: true, settings_version: 'n' } });
await saveAccountSettings({ interface_language: 'vi' });
assert.deepEqual(calls[1].body, { expected_settings_version: '', interface_language: 'vi' });

/* The interface language: the account seeds a device that has none; a device value seeds the account. */
assert.equal(await reconcileInterface({ stored: true, interface_language: 'vi' }, ''), 'vi');
assert.equal(await reconcileInterface({ stored: true, interface_language: 'vi' }, 'zh'), '', 'the device that chose keeps its choice');
assert.equal(await reconcileInterface({ stored: false, interface_language: 'vi' }, ''), '');
reset(account(''), { status: 200, body: { stored: true } });
assert.equal(await reconcileInterface({ stored: true, interface_language: '' }, 'zh'), '');
await new Promise((resolve) => setTimeout(resolve, 20));
assert.equal(calls.at(-1)?.body?.interface_language, 'zh', 'the first save comes from the device value');

/* Review settings: the server shape, only registered modes, retried once on a stale profile. */
assert.equal(reviewFromProfile({ review_new_per_day: null, review_limit_per_day: null, review_modes: null }), null);
assert.deepEqual(reviewFromProfile({ review_new_per_day: 5, review_limit_per_day: null, review_modes: { cloze: false } }), { newPerDay: 5, modes: { cloze: false } });
reset({ status: 409, body: {} }, { status: 200, body: { version: 'p2' } }, { status: 200, body: { version: 'p3' } });
const seen = [];
await saveReviewSettings({ newPerDay: 5, limitPerDay: 100, modes: { typing: true, cloze: false, speak: true, listen_choose: true } }, 'p1', (profile) => seen.push(profile.version));
assert.deepEqual(calls[0].body.review_modes, { typing: true, cloze: false }, 'unregistered modes never leave the device');
assert.equal(calls[2].body.expected_version, 'p2');
assert.deepEqual(seen, ['p2', 'p3']);

console.log('Account settings client: token echo, one retry on 409, no-row account, interface reconcile and review settings: PASS');
