/* Plan & usage, Plans and the Billing sheet: pure data mapping (Design Contract rule 40). No DOM,
   no network.

   The design draws three tiers (Free / Plus / Pro), two billing cycles, prices, a 14-day message
   chart, a card, invoices and a payment flow. The backend serves the three tiers with their monthly and
   yearly prices in USD and VND and per-feature monthly limits, all editable in Platform Admin (D-153), and
   this month's use (GET /api/product/commerce, /api/product/plans), `billing_ready: false`. Every figure
   here is read from those two answers;
   what they cannot supply is not drawn or is drawn at its honest zero/unavailable state - see
   docs/project/UI_BACKEND_GAPS.md "New export frames: Plan, Pricing, Billing, Feedback". */

/* The catalogue's feature keys (writing_coach/product/catalog.py), in the order they are listed. */
export const FEATURE_ORDER = Object.freeze([
  'writing.evaluate', 'writing.improve', 'dictionary.lookup', 'vocabulary.save',
  'library.grammar', 'analytics.basic', 'analytics.advanced', 'practice.personalized', 'export.report',
]);

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

/* Usage rows: every metered feature of the current plan (a feature with a monthly limit), with the
   month's use. `unknown` marks a feature whose use the server could not read. */
export function usageRows(commerce) {
  const features = commerce && commerce.features && typeof commerce.features === 'object' ? commerce.features : {};
  return FEATURE_ORDER.filter((key) => {
    const item = features[key];
    return item && item.monthly_limit != null && Number(item.monthly_limit) > 0;
  }).map((key) => {
    const item = features[key];
    const unknown = item.entitlement_state === 'unknown' || item.usage_state === 'unavailable';
    const used = unknown ? 0 : Math.max(0, Number(item.used) || 0);
    const limit = Number(item.monthly_limit);
    const percent = unknown ? 0 : usagePercent(used, limit);
    return { key, used, limit, percent, tone: unknown ? 'ok' : usageTone(percent), unknown, left: Math.max(0, limit - used) };
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
      /* What the plan includes: every enabled feature, a metered one with its monthly limit. */
      features: FEATURE_ORDER.filter((key) => byKey[key] && byKey[key].enabled).map((key) => ({
        key,
        limit: byKey[key].monthly_limit == null ? null : Number(byKey[key].monthly_limit),
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
      if (item.monthly_limit == null) return { kind: 'yes' };
      return { kind: 'limit', value: Number(item.monthly_limit) };
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
