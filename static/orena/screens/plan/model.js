/* Plan & usage, Plans and the Billing sheet: pure data mapping (Design Contract rule 40). No DOM,
   no network.

   The design draws three tiers (Free / Plus / Pro), two billing cycles, prices, a 14-day message
   chart, a card, invoices and a payment flow. The backend serves the three tiers with their monthly and
   yearly prices in USD and VND and the design's meters with their limits, all editable in Platform Admin
   (D-153, D-161), and each enforced meter's use in its current window (GET /api/product/commerce,
   /api/product/plans), `billing_ready: false`. Every figure
   here is read from those two answers;
   what they cannot supply is not drawn or is drawn at its honest zero/unavailable state - see
   docs/project/UI_BACKEND_GAPS.md "New export frames: Plan, Pricing, Billing, Feedback". */

/* The catalogue's meters (writing_coach/product/catalog.py METERS, catalogue v2 - D-161: the design's Pricing
   meters), in the order the design lists them. `languages.target` is a count cap, not a windowed meter, so
   it has no usage row. */
export const FEATURE_ORDER = Object.freeze([
  'orena.message', 'orena.voice', 'writing.review', 'pronunciation.audio', 'media.import', 'languages.target',
]);
/* `orena.voice` is a daily meter in seconds shown in minutes (D-237): a usage row like the others. */
export const USAGE_ORDER = Object.freeze(['orena.message', 'orena.voice', 'writing.review', 'pronunciation.audio', 'media.import']);

/* An entitlement's limit (catalogue v2 `limit`, in its stored unit; v1 answers carried `monthly_limit`). */
function limitOf(item) {
  const value = item?.limit ?? item?.monthly_limit;
  return value == null ? null : Number(value);
}

/* Stored units per displayed unit (60 seconds are one minute). */
function scaleOf(item) {
  const value = Number(item?.scale);
  return Number.isFinite(value) && value > 0 ? value : 1;
}

/* A stored amount in the unit a learner reads: whole when it is whole, otherwise one decimal. */
export function displayAmount(value, scale = 1) {
  const amount = (Number(value) || 0) / (Number(scale) || 1);
  return Number.isInteger(amount) ? amount : Math.round(amount * 10) / 10;
}

/* A feature key is copy-keyed as `feature_<key with . as _>`. */
export function featureCopyKey(key) {
  return `feature_${String(key).replace(/\./g, '_')}`;
}

/* The subscription states the commerce read can name (writing_coach/product/commerce.py). */
export const SUBSCRIPTION_STATES = Object.freeze(['none', 'pending', 'trialing', 'active', 'past_due', 'paused', 'ended', 'unknown']);

export function statusCopyKey(commerce) {
  const state = String(commerce?.subscription?.state || '');
  if (!commerce || commerce.available === false) return 'status_unknown';
  if (state === 'none' || state === 'inactive' || state === '') return 'status_free';
  return SUBSCRIPTION_STATES.includes(state) ? `status_${state}` : 'status_unknown';
}

/* A bar's fill, 0-100; a missing or zero limit fills nothing. */
export function usagePercent(used, limit) {
  const total = Number(limit);
  if (!Number.isFinite(total) || total <= 0) return 0;
  const value = Number(used);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.min(100, Math.round((value / total) * 100));
}

/* The design's three tones for a meter: ordinary, "almost at limit" (80%), "limit reached" (100%). */
export function usageTone(percent) {
  if (percent >= 100) return 'red';
  if (percent >= 80) return 'amber';
  return 'ok';
}

/* The current plan card. `known` is false when the commerce read failed. */
export function planView(commerce) {
  const plan = commerce && commerce.available !== false ? commerce.plan : null;
  return {
    known: Boolean(plan),
    plan: plan ? { id: String(plan.id || ''), name: String(plan.name || ''), description: String(plan.description || '') } : null,
    isFree: plan ? String(plan.id) === 'free' : false,
    statusKey: statusCopyKey(commerce),
  };
}

/* Usage rows: every windowed meter of the current plan, with this window's use read from the quota
   buckets enforcement writes (GET /api/product/commerce, D-161). `unknown` marks a meter whose use is not
   known: the store could not be read (`unavailable`), or nothing counts it on this deployment
   (`not_metered`) - never drawn as 0 used. Amounts are in the unit a learner reads (minutes, not seconds). */
export function usageRows(commerce) {
  const features = commerce && commerce.features && typeof commerce.features === 'object' ? commerce.features : {};
  return USAGE_ORDER.filter((key) => {
    const item = features[key];
    return item && limitOf(item) != null && limitOf(item) > 0;
  }).map((key) => {
    const item = features[key];
    const scale = scaleOf(item);
    const unknown = item.entitlement_state === 'unknown' || item.usage_state !== 'known';
    const rawUsed = unknown ? 0 : Math.max(0, Number(item.used) || 0);
    const rawLimit = limitOf(item);
    const percent = unknown ? 0 : usagePercent(rawUsed, rawLimit);
    return {
      key,
      used: displayAmount(rawUsed, scale),
      limit: displayAmount(rawLimit, scale),
      percent,
      tone: unknown ? 'ok' : usageTone(percent),
      unknown,
      left: displayAmount(Math.max(0, rawLimit - rawUsed), scale),
      unit: String(item.display_unit || ''),
      window: item.window || null,
      resetsAt: unknown ? null : (item.resets_at || null),
    };
  });
}

/* Plans for the Plans screen and the compare table, from GET /api/product/plans. */
export function pricingPlans({ plans, commerce } = {}) {
  const currentId = commerce && commerce.available !== false && commerce.plan ? String(commerce.plan.id) : '';
  return (Array.isArray(plans) ? plans : []).filter((plan) => plan && plan.id).map((plan) => {
    const entitlements = Array.isArray(plan.entitlements) ? plan.entitlements : [];
    const byKey = Object.fromEntries(entitlements.map((item) => [item.key, item]));
    return {
      id: String(plan.id),
      name: String(plan.name || ''),
      description: String(plan.description || ''),
      priceLabel: String(plan.price_label || ''),
      isFree: String(plan.id) === 'free',
      isCurrent: String(plan.id) === currentId,
      rank: Number(plan.rank) || 0,
      prices: plan.prices && typeof plan.prices === 'object' ? plan.prices : {},
      /* What the plan includes: every enabled meter with its limit, in the unit a learner reads. */
      features: FEATURE_ORDER.filter((key) => byKey[key] && byKey[key].enabled).map((key) => ({
        key,
        limit: limitOf(byKey[key]) == null ? null : displayAmount(limitOf(byKey[key]), scaleOf(byKey[key])),
      })),
      byKey,
    };
  });
}

/* Why a refused language opens Plans (D-171): the facts of the explanation, from the server's refusal (`reason`, what
   reason.js holds - absent after a reload) and the catalogue's plans (`list`, pricingPlans()). Nothing is decided here: the
   limit is the server's own, and the plan to upgrade to is the lowest one above the learner's whose catalogue entry
   lets them hold more languages than they do. `included` is false when the plan has no target-language entitlement at all. */
export function languageReasonFacts({ reason, list } = {}) {
  const plans = Array.isArray(list) ? list : [];
  const current = plans.find((plan) => plan.isCurrent) || null;
  const plan = plans.find((item) => item.id === reason?.plan) || current;
  const entry = plan ? plan.byKey['languages.target'] : null;
  const refusedAsNotInPlan = reason?.category === 'feature_not_in_plan';
  const limit = reason?.limit != null && Number.isFinite(reason.limit)
    ? reason.limit
    : (entry && entry.enabled ? limitOf(entry) : null);
  const included = !refusedAsNotInPlan && (reason?.limit != null ? Number.isFinite(reason.limit) : Boolean(entry && entry.enabled));
  const held = Array.isArray(reason?.languages) ? reason.languages : [];
  const owned = reason?.owned != null && Number.isFinite(reason.owned) ? reason.owned : held.length;
  const holds = Math.max(owned, included && limit != null ? limit : 0);
  const upgrade = plan
    ? plans
      .filter((item) => item.rank > plan.rank && item.byKey['languages.target']?.enabled)
      .filter((item) => limitOf(item.byKey['languages.target']) == null || limitOf(item.byKey['languages.target']) > holds)
      .sort((a, b) => a.rank - b.rank)[0] || null
    : null;
  return { plan, included, limit: included ? limit : null, held, requested: String(reason?.requested || ''), upgrade };
}

/* One row of the compare table per feature any plan lists; a cell is a limit, a tick or a dash. */
export function compareRows(plans) {
  const keys = FEATURE_ORDER.filter((key) => plans.some((plan) => plan.byKey[key]));
  return keys.map((key) => ({
    key,
    cells: plans.map((plan) => {
      const item = plan.byKey[key];
      if (!item || !item.enabled) return { kind: 'no' };
      if (limitOf(item) == null) return { kind: 'yes' };
      return { kind: 'limit', value: displayAmount(limitOf(item), scaleOf(item)), unit: String(item.display_unit || '') };
    }),
  }));
}

/* The Billing sheet's CTA wording by relation to the current plan: a higher rank is an upgrade. */
export function changeKind(target, current) {
  if (!target || target.isCurrent) return 'current';
  if (!current || (Number(target.rank) || 0) > (Number(current.rank) || 0)) return 'upgrade';
  return 'switch';
}

/* D-MON-034 (owner, 2026-10-17): plans are sold by Polar in US dollars only, so a plan's price is shown in dollars in
   every interface language - the amount the learner is charged, formatted in the interface's own way. Dong stay with
   Credits (SePay). This replaces D-153's dong-for-Vietnamese plan display. */
export const CYCLES = Object.freeze(['monthly', 'yearly']);
export const PLAN_CURRENCY = 'USD';
export function currencyFor() {
  return PLAN_CURRENCY;
}

export function formatMoney(amount, currency, locale = 'en') {
  const value = Number(amount);
  if (!Number.isFinite(value)) return '—';
  const whole = currency === 'VND';
  return new Intl.NumberFormat(locale, { style: 'currency', currency, minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: whole ? 0 : 2 }).format(value);
}

/* A plan's price for a cycle: what the card shows large (a yearly plan as its monthly share, as the design
   does), and the line under it. `null` amount: the catalogue has no price for this currency and cycle. */
export function priceView(plan, cycle, locale = 'en') {
  if (!plan || plan.isFree) return { free: true, price: '', billedKey: 'freeForever', billedAmount: '' };
  const currency = currencyFor(locale);
  const amount = Number(plan.prices?.[cycle]?.[currency]);
  if (!Number.isFinite(amount)) return { free: false, price: '—', billedKey: '', billedAmount: '' };
  if (cycle === 'yearly') {
    const share = amount / 12;
    return { free: false, price: formatMoney(share, currency, locale), billedKey: 'billedYearly', billedAmount: formatMoney(amount, currency, locale) };
  }
  return { free: false, price: formatMoney(amount, currency, locale), billedKey: 'billedMonthly', billedAmount: '' };
}

/* What paying yearly saves against twelve months, in whole percent - the smallest across the paid plans,
   so the switch never promises more than every plan gives. 0 when nothing is saved or a price is missing. */
export function yearlySaving(plans, locale = 'en') {
  const currency = currencyFor(locale);
  const savings = (plans || []).filter((plan) => !plan.isFree).map((plan) => {
    const month = Number(plan.prices?.monthly?.[currency]);
    const year = Number(plan.prices?.yearly?.[currency]);
    return month > 0 && year > 0 ? Math.floor((1 - year / (12 * month)) * 100) : 0;
  });
  return savings.length ? Math.max(0, Math.min(...savings)) : 0;
}

/* Payments: the commerce read says so itself (`billing_ready`). */
export function billingReady(commerce) {
  return Boolean(commerce && commerce.billing_ready === true);
}

/* A count in the interface language's digits and grouping. */
export function formatNumber(value, locale = 'en') {
  return new Intl.NumberFormat(locale).format(Number(value) || 0);
}

/* ---- PR-MON-9: buying and managing a plan through Polar --------------------------------------------------- */

const PERIOD_OF = Object.freeze({ monthly: 'month', yearly: 'year' });
const CYCLE_OF = Object.freeze({ month: 'monthly', year: 'yearly' });
export const periodOf = (cycle) => PERIOD_OF[cycle] || 'month';
export const cycleOf = (period) => CYCLE_OF[period] || 'monthly';

/* The server's price key for a plan and cycle (`plan:period:polar`, PR-MON-8 §14: only Polar sells plans). */
export function offerKey(planId, cycle) {
  return `${planId}:${periodOf(cycle)}:polar`;
}

/* The offer the server sells for that key, with its own amount and currency - the only price a checkout confirms. */
export function offerFor(offers, planId, cycle) {
  const key = offerKey(planId, cycle);
  return (Array.isArray(offers) ? offers : []).find((offer) => offer && offer.key === key) || null;
}

/* PR-MON-9 §3.5, mirrored for wording only (the server classifies for itself and its answer wins): the feature tier
   wins over the billing period. `rank` is the catalogue's tier order. */
export function classifyChange(current, target) {
  const from = Number(current?.rank) || 0;
  const to = Number(target?.rank) || 0;
  if (to > from) return 'upgrade';
  if (to < from) return 'downgrade';
  const fromPeriod = current?.period === 'year' ? 1 : 0;
  const toPeriod = target?.period === 'year' ? 1 : 0;
  if (toPeriod > fromPeriod) return 'period_up';
  if (toPeriod < fromPeriod) return 'period_down';
  return 'none';
}

/* Scheduled changes are off in v1 (PR-MON-9 §3.6.1, proved 2026-10-18): a downgrade or a period-down is not sold. */
export const SCHEDULED_CHANGES = false;
export const changeIsImmediate = (kind) => kind === 'upgrade' || kind === 'period_up';

/* What GET /api/billing/subscription says about the learner's card subscription, for the plan card and the banner. */
export function subscriptionView(subscription) {
  if (!subscription || subscription.provider !== 'polar') return { polar: false };
  const live = ['active', 'trialing', 'past_due'].includes(subscription.status);
  return {
    polar: true,
    live,
    period: subscription.period || null,
    cancelling: live && Boolean(subscription.cancel_at_period_end),
    renewsAt: subscription.renews_at ? new Date(subscription.renews_at) : null,
    card: subscription.payment_method && subscription.payment_method.last4 ? subscription.payment_method : null,
    email: subscription.billing_email || '',
  };
}

/* A card's brand as written on it; Polar sends the processor's lowercase key. */
const BRANDS = Object.freeze({ visa: 'Visa', mastercard: 'Mastercard', amex: 'American Express', discover: 'Discover',
  jcb: 'JCB', unionpay: 'UnionPay', diners: 'Diners Club' });
export const cardBrand = (brand) => BRANDS[String(brand || '').toLowerCase()] || String(brand || '');

export function formatDate(value, locale = 'en', { year = true } = {}) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric', ...(year ? { year: 'numeric' } : {}) }).format(date);
}

/* An invoice's amount: Polar's minor units in its own currency. */
export function invoiceAmount(item, locale = 'en') {
  const minor = Number(item?.amount_minor);
  const currency = String(item?.currency || PLAN_CURRENCY).toUpperCase();
  if (!Number.isFinite(minor)) return '—';
  return formatMoney(currency === 'VND' ? minor : minor / 100, currency, locale);
}

/* What the cancel sheet lists as lost (the design's "Orena messages 200 → 20 a day"): each metered feature whose
   limit drops from the current plan to Free, from the catalogue. Kept (saved words, notes, progress) is a fixed row. */
export function cancelLosses(current, free) {
  const limits = (plan) => Object.fromEntries((plan?.features || []).map((feature) => [feature.key, feature]));
  const now = limits(current);
  const after = limits(free);
  return USAGE_ORDER.filter((key) => now[key] && after[key] && now[key].limit != null && after[key].limit != null
    && Number(after[key].limit) < Number(now[key].limit))
    .map((key) => ({ key, from: now[key].limit, to: after[key].limit,
      unit: String(current?.byKey?.[key]?.display_unit || '') }));
}
