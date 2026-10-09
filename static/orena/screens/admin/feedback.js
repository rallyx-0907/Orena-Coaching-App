/* Admin > Users > Feedback (D-156; the design draws no feedback page, so kit blocks only, by the human's
   request 2026-10-09). Reads GET /api/admin/feedback: the learners' reviews, newest first, with a summary
   (total, average, stars distribution, counts by area, last 7 days). Filters by stars and by area go to
   the server; paging is 25 at a time like the Users list. A review links to its account when it has one. */
import { html } from '../../kit/html.js';
import { languages } from '../../copy/index.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { t } from './copy.js';
import { block, bars, chipRow, kv, metrics, pageHead, rowList, skeleton, stateBlock } from './blocks.js';
import { createHost } from './host.js';

export const PAGE_SIZE = 25;
export const STARS = Object.freeze([1, 2, 3, 4, 5]);
export const AREAS = Object.freeze(['listening', 'speaking', 'reading', 'writing', 'vocabulary', 'orena', 'bugs']);

export const starsText = (stars) => {
  const count = Math.max(0, Math.min(5, Math.round(Number(stars) || 0)));
  return '★'.repeat(count) + '☆'.repeat(5 - count);
};

const share = (count, total) => (total > 0 ? (Number(count) / total) * 100 : 0);

function whenOf(iso, ui) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat(ui, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

const areaLabel = (area) => t(`fbArea_${area}`);

export function feedbackPage({ data, filters = {}, offset = 0, failed = false, ui = 'en', href }) {
  const head = pageHead({ back: { href: href('adminUsers'), label: t('navUsers') }, title: t('fbTitle'), sub: t('fbSub') });
  if (failed) return html`<section class="a-page" data-screen-label="Feedback">${head}${block({ body: t('opUnavailable') })}</section>`;
  if (!data) return html`<section class="a-page" data-screen-label="Feedback">${head}${skeleton(t('loading'))}</section>`;
  if (data.available === false) return html`<section class="a-page" data-screen-label="Feedback">${head}${stateBlock({ kind: 'unavail', heading: t('opUnavailable') })}</section>`;
  const summary = data.summary || {};
  const total = Number(summary.total) || 0;
  const number = new Intl.NumberFormat(ui);
  const average = total > 0 && summary.average != null ? new Intl.NumberFormat(ui, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(summary.average) : '—';
  const items = data.items || [];
  const listed = Number(data.total) || 0;
  const filterRows = html`${chipRow({ label: t('fbStars'), field: 'stars', options: [{ id: '', label: t('opAll'), on: !filters.stars }, ...STARS.map((n) => ({ id: String(n), label: `${n} ★`, on: String(filters.stars || '') === String(n) }))] })}${chipRow({ label: t('fbArea'), field: 'area', options: [{ id: '', label: t('opAll'), on: !filters.area }, ...(data.areas?.length ? data.areas : AREAS).map((area) => ({ id: area, label: areaLabel(area), on: filters.area === area }))] })}`;
  return html`<section class="a-page" data-screen-label="Feedback">
    ${head}
    <div class="a-blocks">
      ${block({ span: true, body: metrics([
        { label: t('fbTotal'), value: number.format(total) },
        { label: t('fbAverage'), value: average },
        { label: t('fbLast7'), value: number.format(Number(summary.last_7_days) || 0) },
      ], { columns: 3 }) })}
      ${block({ title: t('fbByStars'), body: bars([...STARS].reverse().map((n) => ({ label: `${n} ★`, pct: share(summary.by_stars?.[String(n)] || 0, total), value: number.format(summary.by_stars?.[String(n)] || 0) })), { labelWidth: '56px' }) })}
      ${block({ title: t('fbByArea'), body: bars((data.areas?.length ? data.areas : AREAS).map((area) => ({ label: areaLabel(area), pct: share(summary.by_area?.[area] || 0, total), value: number.format(summary.by_area?.[area] || 0) }))) })}
      ${block({ span: true, title: t('fbReviews'), body: html`${filterRows}${rowList(items.map((item) => ({
        title: starsText(item.stars),
        meta: [[item.name, item.email].filter(Boolean).join(' · ') || t('fbAnonymous'), [item.language, item.interface].filter(Boolean).join(' / ')].filter(Boolean).join(' · '),
        detail: item.text || '',
        pills: (item.areas || []).map((area) => ({ label: areaLabel(area) })),
        right: whenOf(item.created_at, ui),
        go: item.account_id ? href('adminUser', { id: item.account_id }) : '',
      })), { title: t('opNone'), text: '' })}` })}
      ${block({ title: t('opCount'), body: kv([{ key: t('opCount'), value: number.format(listed) }]), actions: [
        { label: t('opPrevious'), a: 'previous', disabled: offset === 0 },
        { label: t('opNext'), a: 'next', disabled: offset + items.length >= listed },
      ] })}
    </div>
  </section>`;
}

export async function mountFeedback(shell, ctx) {
  const host = createHost(shell, ctx);
  const view = { data: null, filters: { stars: '', area: '' }, offset: 0, failed: false };
  host.setBuilder(() => ({ title: t('fbTitle'), markup: feedbackPage({ data: view.data, filters: view.filters, offset: view.offset, failed: view.failed, ui: languages().ui, href: ctx.href }) }));
  async function load() {
    view.failed = false;
    try {
      view.data = await adminApi.feedback({ limit: PAGE_SIZE, offset: view.offset, stars: view.filters.stars, area: view.filters.area });
    } catch {
      view.data = null;
      view.failed = true;
    }
    host.paint();
  }
  host.on('go', (control, dataset) => { if (dataset.to) ctx.go(dataset.to); });
  host.on('filter', (control, dataset) => { view.filters[dataset.field] = dataset.value; view.offset = 0; load(); });
  host.on('next', () => { view.offset += PAGE_SIZE; load(); });
  host.on('previous', () => { view.offset = Math.max(0, view.offset - PAGE_SIZE); load(); });
  host.paint();
  await load();
  return () => host.cleanup();
}
