/* Admin cost pages: how an amount is drawn when part of it is free-tier value (D-219, owner decision 2026-10-16).
   An amount is always computed at the public (list) price; the server splits it by the tier stamped on each event
   into real spend (`real`), the list-price value of what a free plan covered (`free`) and events recorded before the
   stamp existed (`unknown`). Real spend is drawn as every amount is; the free value is drawn apart, as the existing
   muted pill and a secondary meta phrase ("Free tier · ~$0.12 at list price"), never added to real spend. The design
   draws no cost page (D-128), so this reuses the kit's pill and row meta and invents no new component. */

const number = (value) => (Number.isFinite(value) ? value : 0);

/* The three parts of one row, from either API shape (the AI report's usd_real / usd_free / usd_unknown, the media
   ledger's real_usd / free_tier_usd / unknown_tier_usd). */
export function tierParts(row) {
  return {
    real: number(row.usd_real ?? row.real_usd),
    free: number(row.usd_free ?? row.free_tier_usd),
    unknown: number(row.usd_unknown ?? row.unknown_tier_usd),
  };
}

/* { right, meta, pills } to merge into a rowList row. `money` formats a number; `t` is the page's copy lookup. */
export function tierRow(row, { money, t }) {
  const { real, free, unknown } = tierParts(row);
  const meta = [];
  const pills = [];
  if (free > 0) {
    meta.push(t('costFreeAt', { amount: money(free) }));
    pills.push({ label: t('costFreeTier'), tone: 'mute' });
  }
  if (unknown > 0) meta.push(t('costUnknownTier', { amount: money(unknown) }));
  let right = money(real);
  if (real === 0 && free > 0 && unknown === 0) right = t('costFreeShort');
  else if (real === 0 && unknown > 0 && free === 0) right = money(unknown);
  return { right, meta, pills };
}
