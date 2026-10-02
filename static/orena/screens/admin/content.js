/* Content, wired: the pages of content-pages.js over the shared rules
   (capabilities/admin-content.js) and the one admin client. Nothing here deletes - taking an item
   back is a state, so a decision can be undone - and a lifecycle action opens the item first, so the
   operator sees what they are about to change. Reading, which keeps its own lifecycle, is
   screens/admin/reading.js; this area routes to it from the home tiles. */
import { html } from '../../kit/html.js';
import { languages } from '../../copy/index.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { applyLifecycle, contentCounts, loadContent, publishCollection } from '../../capabilities/admin-content.js';
import { t } from './copy.js';
import { createHost } from './host.js';
import { explain } from './reading.js';
import { pageHead, skeleton } from './blocks.js';
import { loadFailedBlock } from './reading-pages.js';
import { bookPage, collectionPage, homePage, listPage, mediaPage } from './content-pages.js';

const KIND_OF = { adminBooks: 'book', adminBook: 'book', adminMedia: 'media', adminMediaItem: 'media', adminVocab: 'vocabulary', adminCollection: 'vocabulary' };
const CONFIRM = {
  unpublish: ['ctUnpublishTitle', 'ctUnpublishBody', false],
  archive: ['ctArchiveTitle', 'ctArchiveBody', true],
  republish: ['ctRestoreTitle', 'ctRestoreBody', false],
  restore: ['ctRestoreTitle', 'ctRestoreBody', false],
  reprocess: ['ctReprocessTitle', 'ctReprocessBody', false],
  publish: ['ctPublishTitle', 'ctPublishBody', false],
};
const DONE = { unpublish: 'ctDone_unpublish', archive: 'ctDone_archive', republish: 'ctDone_restore', restore: 'ctDone_restore', reprocess: 'ctDone_reprocess', publish: 'ctDone_publish' };

export async function mountContent(shell, ctx) {
  const routeId = ctx.route.id;
  const kind = KIND_OF[routeId] || '';
  const host = createHost(shell, ctx);
  const api = adminApi;
  const ui = () => languages().ui;
  const view = { loading: true, failed: false, busy: false, error: '', status: 'all', q: '', offset: 0 };
  const data = { counts: null, list: null, detail: null, form: { rights: '', completeness: 'unknown', attested: false } };

  function build() {
    const base = { t, ui: ui(), href: ctx.href, view };
    if (view.loading && !data.list) return { title: t('ctTitle'), markup: html`<section class="a-page">${pageHead({ title: t('ctTitle') })}${skeleton(t('loading'))}</section>` };
    if (view.failed) return { title: t('ctTitle'), markup: html`<section class="a-page">${pageHead({ title: t('ctTitle') })}${loadFailedBlock(t)}</section>` };
    switch (routeId) {
      case 'adminBooks': case 'adminMedia': case 'adminVocab': return { ...listPage({ ...base, kind, data: data.list, loading: view.loading }), filterValue: view.q };
      case 'adminBook': return bookPage({ ...base, detail: data.detail });
      case 'adminMediaItem': return mediaPage({ ...base, detail: data.detail, form: data.form });
      case 'adminCollection': return collectionPage({ ...base, detail: data.detail, form: data.form });
      default: return homePage({ ...base, counts: data.counts });
    }
  }
  host.setBuilder(build, { filter: ['adminBooks', 'adminMedia', 'adminVocab'].includes(routeId) });

  const filters = () => ({ kind, q: view.q, status: view.status === 'all' ? '' : view.status, offset: 0 });

  async function load({ append = false } = {}) {
    view.loading = true;
    view.failed = false;
    if (!append) host.paint();
    try {
      if (['adminBooks', 'adminMedia', 'adminVocab'].includes(routeId)) {
        const page = await loadContent(api, { ...filters(), offset: append ? (data.list?.items.length || 0) : 0 });
        data.list = append ? { ...page, items: [...(data.list?.items || []), ...(page.items || [])] } : page;
      } else if (kind) {
        data.detail = await api.contentDetail(kind, ctx.params.id);
        const admission = data.detail.admission || {};
        if (kind === 'vocabulary') data.form = { rights: admission.rights_status || '', completeness: admission.completeness || 'unknown', attested: false };
        if (kind === 'media') data.form = { rights: data.detail.source?.rights || 'unknown', license: data.detail.source?.license || '', attested: false };
      } else {
        data.counts = await contentCounts(api);
      }
    } catch (error) {
      if (!host.alive() || error?.name === 'AbortError') return;
      view.failed = true;
    }
    if (!host.alive()) return;
    view.loading = false;
    host.paint();
  }

  host.on('go', (control, dataset) => ctx.go(dataset.to));
  host.on('reload', () => load());
  host.on('status', (control, dataset) => { view.status = dataset.value; data.list = null; load(); });
  host.on('more', () => load({ append: true }));
  let timer = 0;
  host.onFilter((value) => {
    view.q = value;
    clearTimeout(timer);
    timer = setTimeout(() => { data.list = null; load(); }, 300);
  });

  host.on('lifecycle', async (control, dataset) => {
    if (view.busy) return;
    const intent = dataset.intent;
    const [title, body, danger] = CONFIRM[intent];
    const answer = await host.confirm({ title: t(kind === 'media' && intent === 'publish' ? 'ctMediaPublishTitle' : title), body: t(kind === 'media' && intent === 'publish' ? 'ctMediaPublishBody' : body), cancel: t('actCancel'), confirm: t(`ctAct_${intent}`), danger });
    if (!answer.confirmed) return;
    view.error = '';
    view.busy = true;
    host.paint();
    try {
      await applyLifecycle(api, kind, ctx.params.id, intent);
      host.toast(t(DONE[intent]));
      data.detail = await api.contentDetail(kind, ctx.params.id);
    } catch (error) {
      view.error = explain(error);
    }
    view.busy = false;
    host.paint();
  });

  host.on('media-rights-save', async () => {
    if (view.busy) return;
    view.busy = true;
    view.error = '';
    host.paint();
    try {
      await api.reviewMediaRights(ctx.params.id, { rights: data.form.rights, license: data.form.license, attested: data.form.attested });
      data.detail = await api.contentDetail(kind, ctx.params.id);
      data.form.attested = false;
      host.toast(t('ctRightsSaved'));
    } catch (error) { view.error = explain(error); }
    view.busy = false;
    host.paint();
  });

  host.on('toggle', () => { data.form.attested = !data.form.attested; host.paint(); });
  host.on('pick', (control, dataset) => { data.form[dataset.field] = dataset.value; host.paint(); });
  host.onInput((id, value) => { if (id in data.form) { data.form[id] = value; host.paint(); } });
  host.on('collection-publish', async () => {
    view.busy = true;
    view.error = '';
    host.paint();
    try {
      const done = await publishCollection(api, ctx.params.id, data.form);
      host.toast((done.warnings || []).length ? t('ctPublishedOver') : t('ctDone_publish'));
      data.detail = await api.contentDetail(kind, ctx.params.id);
    } catch (error) {
      view.error = explain(error);
    }
    view.busy = false;
    host.paint();
  });

  load();
  return () => { clearTimeout(timer); host.cleanup(); };
}
