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
  'orena.message', 'writing.review', 'pronunciation.audio', 'media.import', 'languages.target',
]);
export const USAGE_ORDER = Object.freeze(['orena.message', 'writing.review', 'pronunciation.audio', 'media.import']);

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

/* The design shows dong to a Vietnamese interface and dollars otherwise (Orena.dc.html `money`). */
export const CYCLES = Object.freeze(['monthly', 'yearly']);
export function currencyFor(locale) {
  return String(locale || '').toLowerCase().startsWith('vi') ? 'VND' : 'USD';
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
    const share = currency === 'VND' ? Math.round(amount / 12 / 1000) * 1000 : amount / 12;
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
