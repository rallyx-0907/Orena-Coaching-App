/* Credits and Credits Payment: pure data mapping (Design Contract rule 40). No DOM, no network.

   Every figure here is read from the backend's own answers (product/credit-topup.js): the packs from
   GET /api/billing/offers `credit_packs`, the price and units copied from the pack, never computed. The design's pack
   sizes, bonuses, prices and history rows are sample content (D-068) and are not in this file. A balance, a bonus, a
   "most chosen" tag and a history have no learner endpoint yet, so they are absent (docs/project/UI_BACKEND_GAPS.md
   CT-2, CT-3, CT-5). */
import { formatNumber } from '../plan/model.js';

export { formatNumber };

/* A price as the design writes it: digits grouped with a dot and the dong sign ("49.000 ₫"), whatever the interface
   language; any other currency is formatted by the browser for the interface language. */
export function formatPrice(amountMinor, currency, locale = 'en') {
  const amount = Number(amountMinor) || 0;
  if (String(currency).toUpperCase() === 'VND') return `${new Intl.NumberFormat('vi-VN').format(amount)} ₫`;
  try {
    return new Intl.NumberFormat(locale, { style: 'currency', currency: String(currency).toUpperCase() }).format(amount);
  } catch {
    return `${formatNumber(amount, locale)} ${currency}`;
  }
}

/* The pack the learner picked, else the first (the design always has one selected). */
export function selectedPack(packs, key) {
  const list = Array.isArray(packs) ? packs : [];
  return list.find((pack) => pack.key === key) || list[0] || null;
}

/* The pack cards: a total in Credits and a price, in the order the backend lists them. */
export function packCards(packs, key, locale = 'en') {
  const picked = selectedPack(packs, key);
  return (Array.isArray(packs) ? packs : []).map((pack) => ({
    key: pack.key,
    total: formatNumber(pack.creditUnits, locale),
    price: formatPrice(pack.amountMinor, pack.currency, locale),
    selected: Boolean(picked) && pack.key === picked.key,
  }));
}

/* The strip beside "Credits are separate": the learner's plan name, only when the commerce read gave one. */
export function planStrip(commerce) {
  const plan = commerce && commerce.available !== false ? commerce.plan : null;
  return plan && plan.id ? { id: String(plan.id), name: String(plan.name || '') } : null;
}

/* The five "How Credits work" rows: a Lucide icon (the design's hand-typed paths, identified by name) and copy keys. */
export const HOW_ROWS = Object.freeze([
  { icon: 'loader', title: 'how1Title', text: 'how1Text' },
  { icon: 'expand', title: 'how2Title', text: 'how2Text' },
  { icon: 'clock', title: 'how3Title', text: 'how3Text' },
  { icon: 'pen-line', title: 'how4Title', text: 'how4Text' },
  { icon: 'undo-2', title: 'how5Title', text: 'how5Text' },
]);

/* The three history filters of the design. */
export const FILTERS = Object.freeze([
  { id: 'all', label: 'filterAll' },
  { id: 'in', label: 'filterIn' },
  { id: 'out', label: 'filterOut' },
]);

/* The history rows to show for a filter (rows from product/credit-topup.js historyRows). */
export function filterHistory(rows, filter) {
  const list = Array.isArray(rows) ? rows : [];
  if (filter === 'in') return list.filter((row) => row.change > 0);
  if (filter === 'out') return list.filter((row) => row.change < 0);
  return list;
}

/* The payment sheet's step for the purchase in hand: from the checkout and the backend's order state only. */
export function sheetStep({ order, orderState }) {
  if (!order) return 'confirm';
  if (orderState === 'confirmed') return 'done';
  if (orderState === 'received') return 'received';
  if (['expired', 'cancelled', 'failed', 'refunded'].includes(orderState)) return 'expired';
  return 'qr';
}

/* The QR as one SVG path of horizontal runs ("M x y h n v1 h-n z"), from a module reader. */
export function qrPath(size, isDark) {
  let d = '';
  for (let row = 0; row < size; row += 1) {
    let col = 0;
    while (col < size) {
      if (!isDark(row, col)) { col += 1; continue; }
      let end = col;
      while (end < size && isDark(row, end)) end += 1;
      d += `M${col} ${row}h${end - col}v1h-${end - col}z`;
      col = end;
    }
  }
  return d;
}
