/* What the learner UI draws for content access (D-248 §4-§5, MV2-3): a Plus/Pro badge on a Reading card, a lock on a
   paid tool, and whether a tap opens the upgrade sheet. The server decides every tier (writing_coach/product/
   content_access.py); this module only reads its answers:

   - the commerce read's `content_access` block (GET /api/product/commerce): `{enforced, tier, trial_available}`;
   - a Reading card's `access` block (`{tier, rotation}`, the list and the Today recommendation);
   - a media payload's `access.tools` (present only while enforcement is on).

   Nothing is drawn and nothing locks while `access.enforced` is off (the documented choice for MV2-3: a badge before the
   switch would advertise a paywall that does not exist yet). An unknown tier (the plan could not be read) never locks:
   no upgrade prompt over an outage. A rotation pick shows no badge that week (G7). */
import { api } from '../infrastructure/api.js';
import { cardAccess } from '../kit/access.js';

const TTL_MS = 60 * 1000;
let cached = null;

const OFF = Object.freeze({ enforced: false, tier: null, trialAvailable: null });

/* The commerce read's block as `{enforced, tier, trialAvailable}`; OFF when it is missing. */
export function accessFrom(commerce) {
  const block = commerce && typeof commerce === 'object' ? commerce.content_access : null;
  if (!block || typeof block !== 'object') return OFF;
  return Object.freeze({
    enforced: block.enforced === true,
    tier: typeof block.tier === 'string' && block.tier ? block.tier : null,
    trialAvailable: typeof block.trial_available === 'boolean' ? block.trial_available : null,
  });
}

/* The learner's access, read once a minute at most (every card and room asks; one request answers them). A failed read is
   OFF: nothing is badged or locked, and the server still refuses on its own. */
export function readAccess({ fresh = false, now = Date.now() } = {}) {
  if (!fresh && cached && cached.expires > now) return cached.promise;
  const promise = Promise.resolve()
    .then(() => api.productCommerce())
    .then(accessFrom)
    .catch(() => OFF);
  cached = { promise, expires: now + TTL_MS };
  return promise;
}

/* After a plan change (the Billing sheet's Done), the next read asks again. */
export function forgetAccess() {
  cached = null;
}

/* A Reading card for this learner: `{badge, locked}`. `badge` is 'plus' | 'pro' | null - the corner tag and the tier wash
   (G1/G2); `locked` opens the upgrade sheet instead of the room. */
export function cardView(card, access = OFF) {
  if (!access?.enforced) return Object.freeze({ badge: null, locked: false });
  const read = cardAccess(card, access.tier);
  return Object.freeze({ badge: read.tier === 'free' || read.rotation ? null : read.tier, locked: read.locked });
}

/* An item of an own set (a word of a vocabulary set, a grammar point; D-248 §4, MV2-5) or a row of a list (My Library,
   Search): `{badge, locked}` as for a card. When the server says `locked` itself (a set's detail read), its answer wins
   over the comparison. */
export function itemView(item, access = OFF) {
  const view = cardView(item, access);
  if (!access?.enforced) return view;
  const server = item?.access && typeof item.access.locked === 'boolean' ? item.access.locked : null;
  return server == null ? view : Object.freeze({ badge: view.badge, locked: server });
}

/* The wash class of a paid row (G2: a fill, never an outline), '' for none. */
export function tierClass(badge) {
  return badge === 'plus' || badge === 'pro' ? `o-tier--${badge}` : '';
}

/* Whether a media payload's tool is locked for this learner (`translation`, `shadowing_score`, `dictation`,
   `save_to_review`). The server adds `access` only while enforcement is on; the player and the captions are never a tool. */
export function toolLocked(payload, tool) {
  return payload?.access?.tools?.[tool]?.locked === true;
}

export const __internal = { reset: () => { cached = null; }, OFF };
