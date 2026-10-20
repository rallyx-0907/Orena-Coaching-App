/* The light upgrade sheet (D-248 §5, UI_BACKEND_GAPS "Monetisation v2" G4/G5): what a Free learner meets on a Plus
   Reading card, at the end of a locked article's preview, and on a paid tool around a video. Owner's instruction: a light
   sheet, never a heavy page.

   Built from drawn parts only: the design's sheet with its header and round close (kit/overlay.js `sheetHead`), the
   Coming-soon frame's lock in a well (`.o-coming__icon`: 64px, `--surface2`, `--text3`, Lucide `lock`), Pricing's
   benefit rows (`.s-pricing-card__feat` with its check) and price line (`.s-pricing-card__billed`), and the Mic sheet's
   action buttons (`.s-mic__action`). It says what Plus unlocks (3 rows), the plan's dong prices from the catalogue
   (never a hard-coded figure; no line when the catalogue holds none), a primary "Start 7-day free trial" and a secondary
   "See all plans".

   The trial is a seam: Billing's trial route does not exist yet (D-248 §1, the `promotional_grants` schema gate), so the
   primary button opens Plan & usage, the existing Plan screen. Once the server says the trial was used
   (`trial_available: false`), the primary is "Upgrade to Plus" to the plans and the secondary is not repeated.

   On a media page the caller pauses the player first: the sheet never sits over a playing YouTube player (Required
   Minimum Functionality). Opening counts `upgrade_sheet_open:<source>` through kit/access.js (#466). */
import { openSheet, sheetHead, fillSheet } from '../../kit/overlay.js';
import { html, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { upgradeSheetOpened } from '../../kit/access.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy, planName } from '../../copy/shell.js';
import { href } from '../../shell/routes.js';
import { readAccess } from '../../product/content-access.js';
import { t } from './copy.js';
import { upgradePrice } from './model.js';

export const UPGRADE_KINDS = Object.freeze(['reading', 'tool']);

/* The three things Plus unlocks, the one the learner just met first. */
export function benefitKeys(kind) {
  return kind === 'tool'
    ? ['benefitVideoTools', 'benefitVideoReview', 'benefitReading']
    : ['benefitReading', 'benefitVideoTools', 'benefitVideoReview'];
}

/* The price line: "{monthly} / month · {yearly} / year" from the catalogue, either half alone when the catalogue holds only one. */
export function priceLine(price) {
  if (!price) return '';
  return [price.monthly ? t('pricePerMonth', { amount: price.monthly }) : '', price.yearly ? t('pricePerYear', { amount: price.yearly }) : '']
    .filter(Boolean)
    .join(' · ');
}

export function upgradeSheetMarkup({ kind = 'reading', tier = 'plus', price = null, trialAvailable = null } = {}) {
  const plan = planName({ id: tier }) || tier;
  const trialUsed = trialAvailable === false;
  return html`${sheetHead({ title: t('upgradeTitle', { plan }), closeLabel: shellCopy('close'), flush: true })}
    <div class="o-sheet__body s-upgrade">
      <div class="s-upgrade__top">
        <div class="o-coming__icon">${raw(icon('lock', { size: 28 }))}</div>
        <div class="s-mic__body">${t(kind === 'tool' ? 'upgradeLeadTool' : 'upgradeLeadReading', { plan })}</div>
      </div>
      <div class="s-pricing-card__feats">${benefitKeys(kind).map((key) => html`<div class="s-pricing-card__feat"><span class="s-pricing-card__tick">${raw(icon('check', { size: 17, stroke: 2.4 }))}</span><span>${t(key)}</span></div>`)}</div>
      <div class="s-pricing-card__billed" data-upgrade-price>${priceLine(price)}</div>
      <div class="s-mic__actions s-upgrade__actions">
        <button type="button" class="s-mic__action s-mic__action--primary" data-upgrade-primary autofocus>${trialUsed ? t('ctaUpgrade', { plan }) : t('startTrial')}</button>
        ${trialUsed ? '' : html`<button type="button" class="s-mic__action s-mic__action--secondary" data-upgrade-plans>${t('seePlans')}</button>`}
      </div>
    </div>`;
}

/* Open the sheet. `source` is a short token for the funnel (`reading_card`, `reader`, `listening_translation`, ...);
   `tier` the plan the item needs (`plus` | `pro`). Resolves to the sheet's handle. */
export async function openUpgradeSheet({ source = '', kind = 'reading', tier = 'plus', go = (to) => { location.hash = to; } } = {}) {
  await Promise.all(['screens/plan/plan.css', 'screens/mic/mic.css', 'screens/coming/coming.css', 'screens/plan/upgrade.css'].map((sheet) => useStyles(sheet)));
  const access = await readAccess();
  let alive = true;
  const handle = openSheet({
    label: t('upgradeTitle', { plan: planName({ id: tier }) || tier }),
    className: 's-upgrade-sheet',
    scrim: true,
    render(element, sheet) {
      fillSheet(element, sheet, upgradeSheetMarkup({ kind, tier, trialAvailable: access.trialAvailable }));
      element.querySelector('[data-upgrade-primary]')?.addEventListener('click', () => {
        sheet.close();
        // The trial seam: until Billing's trial route exists, the existing Plan screen; after a used trial, the plans.
        go(href(access.trialAvailable === false ? 'pricing' : 'billing'));
      });
      element.querySelector('[data-upgrade-plans]')?.addEventListener('click', () => {
        sheet.close();
        go(href('pricing'));
      });
      return () => { alive = false; };
    },
  });
  void upgradeSheetOpened(source);
  // The price arrives after the sheet is up: a slow catalogue never holds the sheet back.
  api.productPlans().then((answer) => {
    if (!alive) return;
    const plan = (answer?.plans || []).find((item) => item && item.id === tier);
    const line = priceLine(upgradePrice(plan, languages().ui));
    const slot = handle.element.querySelector('[data-upgrade-price]');
    if (slot) slot.textContent = line;
  }).catch(() => {});
  return handle;
}
