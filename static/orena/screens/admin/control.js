import { html } from '../../kit/html.js';
import { loadingMarkup } from '../../kit/states.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { createHost } from './host.js';
import { controlPage } from './control-pages.js';
import { pageHead, stateBlock } from './blocks.js';
import { t } from './copy.js';

export async function mountControl(shell, ctx) {
  const host = createHost(shell, ctx);
  const route = ctx.route.id;
  const filters = { q: '', role: '', language: '', activity: '' };
  let offset = 0;
  let data = {};
  let loading = true;
  let failed = false;
  let generation = 0;
  let timer = 0;
  host.setBuilder(() => loading || failed ? {
    title: t(route === 'adminOverview' ? 'navOverview' : route.startsWith('adminUser') ? 'navUsers' : 'navOperations'),
    filterValue: filters.q,
    markup: html`<section class="a-page">${pageHead({ title: failed ? t('loadFailedTitle') : t('loading') })}${failed ? stateBlock({ kind: 'error', heading: t('loadFailedTitle'), text: t('loadFailedText'), actions: [{ label: t('retry'), a: 'reload' }] }) : loadingMarkup(t('loading'))}</section>`,
  } : controlPage(route, data, { href: ctx.href, filters, offset }), { filter: route === 'adminUsers' });

  async function load() {
    const request = ++generation;
    loading = true;
    failed = false;
    host.paint();
    try {
      if (route === 'adminOverview') data = { overview: await adminApi.overview() };
      else if (route === 'adminUser') data = { detail: await adminApi.user(ctx.params.id) };
      else if (route === 'adminUsers') {
        const [summary, list] = await Promise.all([adminApi.usersSummary(), adminApi.users({ ...filters, offset, limit: 25 })]);
        if (request !== generation) return;
        data = { summary, list };
      } else if (route === 'adminPolling') data = { sources: await adminApi.readingSources() };
      else {
        const results = await Promise.allSettled([adminApi.runtime(), adminApi.aiOperations(), adminApi.overview(), adminApi.readingOperations()]);
        if (request !== generation) return;
        data = Object.fromEntries(['runtime', 'telemetry', 'overview', 'reading'].map((name, index) => [name, results[index].status === 'fulfilled' ? results[index].value : { available: false }]));
      }
    } catch {
      if (request !== generation) return;
      failed = true;
    }
    if (!host.alive() || request !== generation) return;
    loading = false;
    host.paint();
  }
  host.on('reload', load);
  host.on('go', (_, dataset) => ctx.go(dataset.to));
  host.on('next', () => { offset += 25; load(); });
  host.on('previous', () => { offset = Math.max(0, offset - 25); load(); });
  host.onInput((field, next) => { if (!(field in filters)) return; filters[field] = next; offset = 0; load(); });
  host.onFilter((next) => { filters.q = next; offset = 0; clearTimeout(timer); timer = setTimeout(load, 250); });
  await load();
  return () => { generation += 1; clearTimeout(timer); host.cleanup(); };
}
