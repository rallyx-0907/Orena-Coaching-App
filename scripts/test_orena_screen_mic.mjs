/* Gate for the Mic state sheet's pure data (static/orena/screens/mic/model.js), frame 62 / E2 §11.
   No DOM - imports only the DOM-free module. Checks the six states match the source's own `MS`
   object (orena-script.js) exactly: icon tokens, which copy key each uses, the `blocked` state's
   real `textOK` branch, and `noisy`'s real button order (secondary drawn before primary). */
import assert from 'node:assert/strict';
import { MIC_STATES, micStateSpec, gateStateFor, micUnavailableReason } from '../static/orena/screens/mic/model.js';

assert.deepEqual(MIC_STATES, ['permission', 'blocked', 'notheard', 'noisy', 'provider', 'offline']);
assert.equal(micStateSpec('bogus'), null, 'no 7th state exists - never invent one');

/* --- permission --- */
{
  const spec = micStateSpec('permission');
  assert.equal(spec.iconBg, 'var(--accent-soft)');
  assert.equal(spec.iconColor, 'var(--accent)');
  assert.equal(spec.titleKey, 'permissionTitle');
  assert.equal(spec.bodyKey, 'permissionBody');
  assert.equal(spec.stepsKey, '', 'only "blocked" has a steps box');
  assert.deepEqual(spec.actions.map((a) => a.key), ['allow', 'dismiss']);
  assert.equal(spec.actions[0].variant, 'primary');
  assert.equal(spec.actions[1].variant, 'secondary');
}

/* --- blocked: the real textOK branch, not a static string --- */
{
  const withFallback = micStateSpec('blocked', { textFallback: true });
  assert.equal(withFallback.bodyKey, 'blockedBodyFallback');
  assert.deepEqual(withFallback.actions.map((a) => a.key), ['retry', 'typeInstead']);
  const noFallback = micStateSpec('blocked', { textFallback: false });
  assert.equal(noFallback.bodyKey, 'blockedBodyNoFallback');
  assert.deepEqual(noFallback.actions.map((a) => a.key), ['retry', 'close']);
  assert.equal(withFallback.iconBg, 'var(--red-soft)');
  assert.equal(withFallback.iconColor, 'var(--red)');
  assert.equal(withFallback.stepsKey, 'blockedSteps');
  // default textFallback is true (most callers offer a text alternative)
  assert.equal(micStateSpec('blocked').bodyKey, 'blockedBodyFallback');
}

/* --- notheard / provider: primary then secondary, amber / neutral --- */
{
  const notheard = micStateSpec('notheard');
  assert.equal(notheard.iconBg, 'var(--amber-soft)');
  assert.deepEqual(notheard.actions.map((a) => a.key), ['tryagain', 'cancel']);
  const provider = micStateSpec('provider');
  assert.equal(provider.iconBg, 'var(--surface2)');
  assert.equal(provider.iconColor, 'var(--muted)');
  assert.deepEqual(provider.actions.map((a) => a.key), ['retry', 'continue']);
}

/* --- noisy: the source's own order is secondary first, primary second --- */
{
  const noisy = micStateSpec('noisy');
  assert.deepEqual(noisy.actions.map((a) => a.key), ['keep', 'recordagain']);
  assert.equal(noisy.actions[0].variant, 'secondary');
  assert.equal(noisy.actions[1].variant, 'primary');
}

/* --- offline: one action only --- */
{
  const offline = micStateSpec('offline');
  assert.equal(offline.actions.length, 1);
  assert.equal(offline.actions[0].key, 'ok');
  assert.equal(offline.iconBg, 'var(--surface2)');
}

/* --- gateStateFor: only micGate's own two states, from the real readiness signal --- */
assert.equal(gateStateFor('ready'), null, 'ready: go ahead, no sheet');
assert.equal(gateStateFor('denied'), 'blocked');
assert.equal(gateStateFor('no_device'), 'blocked');
assert.equal(gateStateFor('unsupported'), 'blocked');
assert.equal(gateStateFor('checking'), null, 'still checking is not a failure to report yet');

console.log('test_orena_screen_mic.mjs: Mic state sheet - the source\'s 6 states, real textOK/order, gate mapping: PASS');

// BUG-01 (mobile QA): a page that cannot record says why, and offers no Retry or Allow that cannot work.
{
  assert.equal(micUnavailableReason({ secure: false, mediaDevices: undefined }), 'insecure');
  assert.equal(micUnavailableReason({ secure: true, mediaDevices: undefined }), 'unsupported');
  assert.equal(micUnavailableReason({ secure: true, mediaDevices: { getUserMedia() {} } }), null);
  const insecure = micStateSpec('blocked', { reason: 'insecure' });
  assert.equal(insecure.titleKey, 'unavailableTitle');
  assert.equal(insecure.bodyKey, 'insecureBody');
  assert.deepEqual(insecure.actions.map((a) => a.key), ['typeInstead'], 'no Retry when retrying cannot work');
  assert.deepEqual(micStateSpec('blocked', { reason: 'unsupported', textFallback: false }).actions.map((a) => a.key), ['close']);
}

