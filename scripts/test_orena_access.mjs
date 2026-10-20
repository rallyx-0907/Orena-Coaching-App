/* Gate for kit/access.js (D-248 §4-§6, MV2-1): a 403 plan_required and the weekly look-up 429 become typed results,
   a card's access block reads against the plan without computing a tier, and only the client events are sent. */
import assert from 'node:assert/strict';

import {
  cardAccess, mediaToolsExhausted, planRequired, reportAccessEvent, trialStarted, upgradeSheetOpened,
} from '../static/orena/kit/access.js';

function refusal(status, category, context) {
  const error = new Error('refused');
  Object.assign(error, { status, category, context });
  return error;
}

// 403 plan_required -> a typed result, with the preview the Reader keeps.
const locked = planRequired(refusal(403, 'plan_required', {
  required_tier: 'plus', kind: 'reading', item_id: 'a1', plan: 'free', upgrade: '#/plan/pricing',
  trial_available: null, preview: { title: 'Rain', first_paragraph: 'The river rose.' },
}));
assert.equal(locked.type, 'plan_required');
assert.equal(locked.kind, 'reading');
assert.equal(locked.itemId, 'a1');
assert.equal(locked.requiredTier, 'plus');
assert.equal(locked.plan, 'free');
assert.equal(locked.trialAvailable, null, 'an unknown trial is not a no');
assert.equal(locked.preview.first_paragraph, 'The river rose.');
// D-248 §6's names are read too.
const named = planRequired(refusal(403, 'plan_required', { content_kind: 'media_tool', content_id: 'm1',
  required_plan: 'plus', tool: 'dictation', trial_available: true }));
assert.deepEqual([named.kind, named.itemId, named.requiredTier, named.tool, named.trialAvailable],
  ['media_tool', 'm1', 'plus', 'dictation', true]);
// Anything else is not a plan refusal.
assert.equal(planRequired(refusal(403, 'feature_not_in_plan', {})), null);
assert.equal(planRequired(refusal(503, 'quota_unavailable', {})), null, 'an outage never reads as an upgrade');
assert.equal(planRequired(null), null);

// The weekly look-up meter.
const spent = mediaToolsExhausted(refusal(429, 'quota_exhausted', { feature: 'media.tools_weekly', used: 3, limit: 3,
  resets_at: '2026-10-26T00:00:00Z' }));
assert.deepEqual([spent.used, spent.limit, spent.resetsAt], [3, 3, '2026-10-26T00:00:00Z']);
assert.equal(mediaToolsExhausted(refusal(429, 'quota_exhausted', { feature: 'orena.message' })), null);

// A card's access against the plan.
assert.deepEqual({ ...cardAccess({ access: { tier: 'plus', rotation: false } }, 'free') },
  { tier: 'plus', rotation: false, locked: true });
assert.equal(cardAccess({ access: { tier: 'plus' } }, 'plus').locked, false);
assert.equal(cardAccess({ access: { tier: 'plus' } }, 'pro').locked, false);
assert.equal(cardAccess({ access: { tier: 'free', rotation: true } }, 'free').rotation, true);
assert.equal(cardAccess({ access: { tier: 'plus' } }, null).locked, false, 'an unknown plan never locks');
assert.equal(cardAccess({}, 'free').tier, 'free');

// Events: only the client's two, with a short source token.
const sent = [];
const send = async (url, init) => { sent.push([url, JSON.parse(init.body)]); return { ok: true }; };
assert.equal(await upgradeSheetOpened('reader', { send }), true);
assert.equal(await trialStarted('', { send }), true);
assert.equal(await reportAccessEvent('locked_view', 'reading', { send }), false, 'the server counts locked views');
assert.equal(await reportAccessEvent('upgrade_sheet_open', 'Some Title!', { send }), false, 'no content in a source');
assert.deepEqual(sent, [
  ['/api/product/access/events', { event: 'upgrade_sheet_open', source: 'reader' }],
  ['/api/product/access/events', { event: 'trial_start', source: '' }],
]);
assert.equal(await upgradeSheetOpened('reader', { send: async () => { throw new Error('offline'); } }), false);

console.log('test_orena_access OK');
