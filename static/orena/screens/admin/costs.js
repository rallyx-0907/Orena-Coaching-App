/* Admin > AI & Models > AI cost (D-128: the design draws no cost page; existing kit blocks only, by the
   human's decision 2026-10-04). Reads GET /api/admin/ai/costs: the shared AI ledger by UTC day and by
   feature x provider x model, with a unit cost per call or per audio minute. Totals only - the ledger is
   anonymous. Cost per account (AC-2) is a second read, GET /api/admin/ai/costs/accounts, an administrator's
   only; before its table exists the block says so. The report's own gaps are shown as the server states
   them, never hidden. */
import { html } from '../../kit/html.js';
import { languages } from '../../copy/index.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { t } from './copy.js';
import { block, formBlock, metrics, pageHead, rowList, skeleton } from './blocks.js';
import { createHost } from './host.js';
import { tierParts, tierRequests, tierRow } from './cost-tier.js';

const DAYS = [7, 30, 90];

function usd(value, ui) {
  if (value == null) return '—';
  // One precision for every amount on the page, so a real, a free and a per-call amount compare at a glance.
  return new Intl.NumberFormat(ui, { style: 'currency', currency: 'USD', minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(value);
}

function capabilityLabel(key) {
  const label = t(`cap_${key}`);
  return label && label !== `cap_${key}` ? label : key;
}

export function costsPage({ report, accounts, days, failed, ui, href }) {
  const head = pageHead({ back: { href: href('adminAi'), label: t('aiTitle') }, title: t('costTitle'), sub: t('costSub'), actions: [{ label: t('polTitle'), size: 'sm', a: 'go', data: { to: href('adminPolicies') } }] });
  if (failed) return html`<section class="a-page" data-screen-label="AI cost">${head}${block({ body: t('opUnavailable') })}</section>`;
  if (!report) return html`<section class="a-page" data-screen-label="AI cost">${head}${skeleton(t('loading'))}</section>`;
  const totals = report.totals || {};
  const real = totals.usd_real ?? 0;
  const free = totals.usd_free ?? 0;
  const unknown = totals.usd_unknown ?? 0;
  const calls = (report.by_day || []).reduce((sum, day) => sum + (day.calls || 0), 0);
  const unpriced = (report.by_day || []).reduce((sum, day) => sum + (day.unpriced_calls || 0), 0);
  const money = (value) => usd(value, ui);
  const tier = (row) => tierRow(row, { money, t });
  const range = formBlock({ span: true, fields: [{ id: 'days', kind: 'seg', label: t('costRange'), options: DAYS.map((n) => ({ id: String(n), label: t('costDays', { n }), on: days === n })) }] });
  return html`<section class="a-page" data-screen-label="AI cost">
    ${head}
    <div class="a-blocks">
      ${range}
      ${block({ span: true, body: metrics([
        { label: t('costReal'), value: money(real), note: unknown > 0 ? t('costUnknownTier', { amount: money(unknown) }) : '' },
        { label: t('costFreeValue'), value: money(free), note: t('costFreeValueNote'), tone: 'ok' },
        { label: t('costCalls'), value: new Intl.NumberFormat(ui).format(calls) },
        { label: t('costUnpriced'), value: new Intl.NumberFormat(ui).format(unpriced), tone: unpriced ? 'warn' : '' },
      ], { columns: 4 }) })}
      ${block({ span: true, title: t('costByFeature'), body: rowList((report.by_feature || []).map((row) => {
        const view = tier(row);
        return {
          title: capabilityLabel(row.capability),
          meta: [row.provider, row.model].filter(Boolean).join(' · ') || t('costNoProvider'),
          detail: view.detail,
          right: view.right,
          pills: [{ label: row.usd_per_unit == null ? t('costNoUnit') : t(row.unit === 'audio_minute' ? 'costPerMinute' : 'costPerCall', { amount: usd(row.usd_per_unit, ui) }), tone: 'mute' }],
        };
      }), { title: t('opNone'), text: '' }) })}
      ${block({ span: true, title: t('costByDay'), body: rowList((report.by_day || []).map((day) => {
        const view = tier(day);
        return { title: day.day, meta: t('costDayMeta', { calls: day.calls, unpriced: day.unpriced_calls }), detail: view.detail, right: view.right };
      }), { title: t('opNone'), text: '' }) })}
      ${report.media ? block({ span: true, title: t('costMedia'), sub: t('costMediaSub'), body: rowList((report.media.by_provider || []).map((row) => {
        const amounts = tierParts(row);
        const credits = row.requests > 0 && amounts.real + amounts.free + amounts.unknown === 0;
        const view = credits ? { right: '', detail: tierRequests(row, { t }) } : tier(row);
        return { title: row.provider, meta: t('costMediaEvents', { n: row.events }), detail: view.detail, right: view.right };
      }), { title: t('opNone'), text: '' }) }) : ''}
      ${accounts ? block({ span: true, title: t('costByAccount'), body: accounts.available
        ? rowList([
          ...(accounts.accounts || []).map((row) => {
            const view = tier(row);
            return { title: row.name || row.email, meta: [row.email, t('costAccountMeta', { calls: row.calls })].filter(Boolean).join(' · '), detail: view.detail, right: view.right };
          }),
          ...(accounts.truncated ? [{ title: t('costAccountsTop') }] : []),
        ], { title: t('opNone'), text: '' })
        : t('costAccountsOff') }) : ''}
      ${block({ span: true, title: t('costGaps'), body: rowList((report.gaps || []).map((gap) => ({ title: t(`costGap_${gap.code}`) }))) })}
    </div>
  </section>`;
}

export async function mountCosts(shell, ctx) {
  const host = createHost(shell, ctx);
  const view = { days: 30, report: null, accounts: null, failed: false };
  const ui = () => languages().ui;
  host.setBuilder(() => ({ title: t('costTitle'), markup: costsPage({ report: view.report, accounts: view.accounts, days: view.days, failed: view.failed, ui: ui(), href: ctx.href }) }));
  async function load() {
    view.report = null;
    view.accounts = null;
    view.failed = false;
    host.paint();
    try {
      view.report = await adminApi.aiCosts(view.days);
    } catch {
      view.failed = true;
    }
    try {
      view.accounts = await adminApi.aiCostsByAccount(view.days);
    } catch {
      view.accounts = null;
    }
    host.paint();
  }
  host.on('go', (control, dataset) => { if (dataset.to) ctx.go(dataset.to); });
  host.on('pick', (control, dataset) => { if (dataset.field === 'days') { view.days = Number(dataset.value) || 30; load(); } });
  await load();
  return () => host.cleanup();
}
