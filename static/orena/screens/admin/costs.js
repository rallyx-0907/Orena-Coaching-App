/* Admin > AI & Models > AI cost (D-128: the design draws no cost page; existing kit blocks only, by the
   human's decision 2026-10-04). Reads GET /api/admin/ai/costs: the shared AI ledger by UTC day and by
   feature x provider x model, with a unit cost per call or per audio minute. Totals only - the ledger is
   anonymous; cost per learner arrives with the per-account cost record (AC-2). The report's own gaps are
   shown as the server states them, never hidden. */
import { html } from '../../kit/html.js';
import { languages } from '../../copy/index.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { t } from './copy.js';
import { block, formBlock, metrics, pageHead, rowList, skeleton } from './blocks.js';
import { createHost } from './host.js';

const DAYS = [7, 30, 90];

function usd(value, ui) {
  if (value == null) return '—';
  return new Intl.NumberFormat(ui, { style: 'currency', currency: 'USD', minimumFractionDigits: value < 1 ? 4 : 2, maximumFractionDigits: value < 1 ? 4 : 2 }).format(value);
}

function capabilityLabel(key) {
  const label = t(`cap_${key}`);
  return label && label !== `cap_${key}` ? label : key;
}

export function costsPage({ report, days, failed, ui, href }) {
  const head = pageHead({ back: { href: href('adminAi'), label: t('aiTitle') }, title: t('costTitle'), sub: t('costSub') });
  if (failed) return html`<section class="a-page" data-screen-label="AI cost">${head}${block({ body: t('opUnavailable') })}</section>`;
  if (!report) return html`<section class="a-page" data-screen-label="AI cost">${head}${skeleton(t('loading'))}</section>`;
  const total = (report.by_day || []).reduce((sum, day) => sum + (day.usd || 0), 0);
  const calls = (report.by_day || []).reduce((sum, day) => sum + (day.calls || 0), 0);
  const unpriced = (report.by_day || []).reduce((sum, day) => sum + (day.unpriced_calls || 0), 0);
  const range = formBlock({ span: true, fields: [{ id: 'days', kind: 'seg', label: t('costRange'), options: DAYS.map((n) => ({ id: String(n), label: t('costDays', { n }), on: days === n })) }] });
  return html`<section class="a-page" data-screen-label="AI cost">
    ${head}
    <div class="a-blocks">
      ${range}
      ${block({ span: true, body: metrics([
        { label: t('costTotal'), value: usd(total, ui) },
        { label: t('costCalls'), value: new Intl.NumberFormat(ui).format(calls) },
        { label: t('costUnpriced'), value: new Intl.NumberFormat(ui).format(unpriced), tone: unpriced ? 'warn' : '' },
      ], { columns: 3 }) })}
      ${block({ span: true, title: t('costByFeature'), body: rowList((report.by_feature || []).map((row) => ({
        title: capabilityLabel(row.capability),
        meta: [row.provider, row.model].filter(Boolean).join(' · ') || t('costNoProvider'),
        right: usd(row.usd, ui),
        pills: [{ label: row.usd_per_unit == null ? t('costNoUnit') : t(row.unit === 'audio_minute' ? 'costPerMinute' : 'costPerCall', { amount: usd(row.usd_per_unit, ui) }), tone: 'mute' }],
      })), { title: t('opNone'), text: '' }) })}
      ${block({ span: true, title: t('costByDay'), body: rowList((report.by_day || []).map((day) => ({
        title: day.day, meta: t('costDayMeta', { calls: day.calls, unpriced: day.unpriced_calls }), right: usd(day.usd, ui),
      })), { title: t('opNone'), text: '' }) })}
      ${block({ span: true, title: t('costGaps'), body: rowList((report.gaps || []).map((gap) => ({ title: t(`costGap_${gap.code}`) }))) })}
    </div>
  </section>`;
}

export async function mountCosts(shell, ctx) {
  const host = createHost(shell, ctx);
  const view = { days: 30, report: null, failed: false };
  const ui = () => languages().ui;
  host.setBuilder(() => ({ title: t('costTitle'), markup: costsPage({ report: view.report, days: view.days, failed: view.failed, ui: ui(), href: ctx.href }) }));
  async function load() {
    view.report = null;
    view.failed = false;
    host.paint();
    try {
      view.report = await adminApi.aiCosts(view.days);
    } catch {
      view.failed = true;
    }
    host.paint();
  }
  host.on('go', (control, dataset) => { if (dataset.to) ctx.go(dataset.to); });
  host.on('pick', (control, dataset) => { if (dataset.field === 'days') { view.days = Number(dataset.value) || 30; load(); } });
  await load();
  return () => host.cleanup();
}
