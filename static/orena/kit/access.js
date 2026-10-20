/* Content access (D-248 §4-§6, MV2-1): what a refused or gated read means, as data the later UI PRs draw (the
   upgrade sheet, a locked Reader, a tool lock). No DOM and no visual change here, and the client never computes a tier:
   the server decides (writing_coach/product/content_access.py) and this module only reads its answers.

   - `planRequired(error)`: a 403 `plan_required` (infrastructure/api.js sets `status`, `category` and `context` from the
     contract's error envelope) as a typed result, else null.
   - `mediaToolsExhausted(error)`: the 429 `quota_exhausted` of the weekly look-up meter (`media.tools_weekly`), else null.
   - `cardAccess(card, planId)`: a Reading card's `access` block against the learner's plan (from /api/product/commerce).
   - `reportAccessEvent(event, source)`: the `upgrade_sheet_open` hook and the `trial_start` seam, counted on the server
     (`POST /api/product/access/events`). `locked_view` is counted by the server where it refuses. */

export const TIERS = Object.freeze(['free', 'plus', 'pro']);
export const MEDIA_TOOLS_METER = 'media.tools_weekly';
export const CLIENT_EVENTS = Object.freeze(['upgrade_sheet_open', 'trial_start']);
const SOURCE = /^[a-z][a-z0-9_]{0,31}$/;

const rank = (tier) => TIERS.indexOf(String(tier || ''));
const text = (value) => (value == null ? '' : String(value));

/* A 403 `plan_required` as `{kind, itemId, requiredTier, plan, upgrade, trialAvailable, tool, preview}`; null for
   anything else. The D-248 §6 names (`content_kind`, `content_id`, `required_plan`) are read when the others are absent. */
export function planRequired(error) {
  if (!error || error.status !== 403 || error.category !== 'plan_required') return null;
  const context = error.context && typeof error.context === 'object' ? error.context : {};
  const requiredTier = text(context.required_tier || context.required_plan);
  return Object.freeze({
    type: 'plan_required',
    kind: text(context.kind || context.content_kind),
    itemId: text(context.item_id || context.content_id),
    requiredTier: rank(requiredTier) > 0 ? requiredTier : 'plus',
    plan: context.plan == null ? null : text(context.plan),
    upgrade: text(context.upgrade) || '#/plan/pricing',
    trialAvailable: typeof context.trial_available === 'boolean' ? context.trial_available : null,
    tool: context.tool == null ? null : text(context.tool),
    preview: context.preview && typeof context.preview === 'object' ? context.preview : {},
  });
}

/* The weekly look-up meter spent (429 `quota_exhausted`, `context.feature` `media.tools_weekly`): `{used, limit,
   resetsAt}`; null for anything else. The video still plays: only Orena's tools wait for the next week. */
export function mediaToolsExhausted(error) {
  if (!error || error.status !== 429 || error.category !== 'quota_exhausted') return null;
  const context = error.context && typeof error.context === 'object' ? error.context : {};
  if (context.feature !== MEDIA_TOOLS_METER) return null;
  return Object.freeze({
    type: 'media_tools_exhausted',
    used: Number(context.used) || 0,
    limit: context.limit == null ? null : Number(context.limit),
    resetsAt: context.resets_at == null ? null : text(context.resets_at),
    upgrade: text(context.upgrade) || '#/plan/pricing',
  });
}

/* What a Reading card's `access` block means for this learner: `{tier, rotation, locked}`. An unknown plan (the
   commerce read failed) is never locked - no upgrade prompt over an outage. A card without a block is free. */
export function cardAccess(card, planId) {
  const access = card && typeof card.access === 'object' && card.access ? card.access : {};
  const tier = rank(access.tier) >= 0 ? access.tier : 'free';
  const have = rank(planId);
  return Object.freeze({
    tier,
    rotation: access.rotation === true,
    locked: have >= 0 && rank(tier) > have,
  });
}

/* Count one access event on the server. `send(url, init)` defaults to `fetch`; analytics never throw at a caller. */
export async function reportAccessEvent(event, source = '', { send = globalThis.fetch } = {}) {
  if (!CLIENT_EVENTS.includes(event)) return false;
  const token = text(source).trim().toLowerCase();
  if (token && !SOURCE.test(token)) return false;
  if (typeof send !== 'function') return false;
  try {
    const response = await send('/api/product/access/events', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, source: token }),
    });
    return Boolean(response && response.ok);
  } catch {
    return false;
  }
}

/* The hook the upgrade sheet (MV2-3) calls when it opens; `source` names where (e.g. `reader`, `listening_tool`). */
export const upgradeSheetOpened = (source, options) => reportAccessEvent('upgrade_sheet_open', source, options);
/* The seam the trial button calls once Billing's trial route answers (D-248 §1). */
export const trialStarted = (source, options) => reportAccessEvent('trial_start', source, options);
