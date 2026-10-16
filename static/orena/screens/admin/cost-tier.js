/* Admin cost pages: how an amount is drawn when part of it is free-tier value (D-219, owner decision 2026-10-16).
   An amount is always computed at the public (list) price; the server splits it by the tier stamped on each event
   into real spend (`real`), the list-price value of what a free plan covered (`free`) and events recorded before the
   stamp existed (`unknown`). Real spend is the amount on the right of a row, drawn as every amount is. The free value
   is never added to it: it sits on its own line under the row, "Free tier" in the kit's `ok` (green) pill followed by
   "~$X at list price", so the words carry the meaning and the colour only sets it apart. An amount recorded before
   the tier was stamped has its own muted "Before tier recording" pill and is never shown as real spend. The design
   draws no cost page (D-128), so this reuses the kit's pill, row detail and metric tones and invents no component. */
import { html } from '../../kit/html.js';
import { pill } from './blocks.js';

const number = (value) => (Number.isFinite(value) ? value : 0);
const PART_KEYS = ['usd_real', 'usd_free', 'usd_unknown', 'real_usd', 'free_tier_usd', 'unknown_tier_usd'];

/* The three parts of one row, from either API shape (the AI report's usd_real / usd_free / usd_unknown, the media
   ledger's real_usd / free_tier_usd / unknown_tier_usd). */
export function tierParts(row) {
  return {
    real: number(row.usd_real ?? row.real_usd),
    free: number(row.usd_free ?? row.free_tier_usd),
    unknown: number(row.usd_unknown ?? row.unknown_tier_usd),
  };
}

const lines = (list) => (list.length ? html`${list.map((line) => html`<div>${line}</div>`)}` : '');

/* { right, detail } to merge into a rowList row. `money` formats a number; `t` is the page's copy lookup. A row with no
   tier fields at all (an older server) shows its plain amount. */
export function tierRow(row, { money, t }) {
  if (!PART_KEYS.some((key) => row[key] !== undefined && row[key] !== null)) return { right: money(number(row.usd)), detail: '' };
  const { real, free, unknown } = tierParts(row);
  const detail = [];
  if (free > 0) detail.push(html`${pill({ label: t('costFreeTier'), tone: 'ok' })} ${t('costListAt', { amount: money(free) })}`);
  if (unknown > 0) detail.push(html`${pill({ label: t('costUnknownShort'), tone: 'mute' })} ${money(unknown)}`);
  return { right: real > 0 || (!free && !unknown) ? money(real) : '', detail: lines(detail) };
}

/* The same for a credit-billed provider (Supadata): requests, not dollars, with the tier each was made under. */
export function tierRequests(row, { t }) {
  const by = row.requests_by_tier || {};
  const detail = [];
  if (by.free > 0) detail.push(html`${pill({ label: t('costFreeTier'), tone: 'ok' })} ${t('costMediaRequests', { n: by.free })}`);
  if (by.real > 0) detail.push(html`${t('costMediaRequests', { n: by.real })}`);
  if (by.unknown > 0) detail.push(html`${pill({ label: t('costUnknownShort'), tone: 'mute' })} ${t('costMediaRequests', { n: by.unknown })}`);
  return lines(detail);
}
