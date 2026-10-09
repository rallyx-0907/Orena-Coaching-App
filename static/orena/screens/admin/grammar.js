/* Grammar in Platform Admin, wired: the review queue (G3) and a point's review page (G4) of
   proposals/ADMIN_GRAMMAR_UI.md over the Grammar Store's Admin API (writing_coach/grammar_admin_api.py). The pages are
   grammar-pages.js; the import page (G2) lives in Imports (imports.js). Every decision is the administrator's own act:
   accept, reject, rights, publish and status each go through the server's own rules, and each refusal is said in words. */
import { html } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { languages } from '../../copy/index.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { conceptPreviewMarkup } from '../grammar-concept/screen.js';
import { t } from './copy.js';
import { createHost } from './host.js';
import { explain } from './reading.js';
import { pageHead, skeleton } from './blocks.js';
import { loadFailedBlock } from './reading-pages.js';
import { GRAMMAR_LANGUAGES, GRAMMAR_TABS, pointPage, publishableItems, queuePage, shownPoints } from './grammar-pages.js';

const languageName = (code) => t(code === 'zh' ? 'langZh' : 'langEn');

export async function mountGrammar(shell, ctx) {
  await useStyles('screens/grammar-concept/grammar-concept.css');
  const routeId = ctx.route.id;
  const host = createHost(shell, ctx);
  const api = adminApi;
  const ui = () => languages().ui;
  const support = () => languages().support || 'en';
  const fromQuery = (key, allowed, fallback) => (allowed.includes(ctx.query.get(key)) ? ctx.query.get(key) : fallback);
  const view = {
    loading: true, failed: false, busy: '',
    tab: fromQuery('tab', GRAMMAR_TABS, 'review'),
    language: fromQuery('language', GRAMMAR_LANGUAGES, ctx.context?.language === 'zh' ? 'zh' : 'en'),
    level: 'all', q: '',
  };
  const data = { points: [], point: null, summary: null, preview: '' };

  function build() {
    const base = { t, ui: ui(), href: ctx.href };
    if (view.loading && routeId === 'adminGrammarPoint') return { title: t('ctTitle'), markup: html`<section class="a-page">${pageHead({ title: t('grTitle') })}${skeleton(t('loading'))}</section>` };
    if (view.failed) return { title: t('ctTitle'), markup: html`<section class="a-page">${pageHead({ title: t('grTitle') })}${loadFailedBlock(t)}</section>` };
    if (routeId === 'adminGrammarPoint') return pointPage({ ...base, point: data.point, summary: data.summary, preview: data.preview, busy: view.busy });
    return queuePage({ ...base, points: data.points, view, loading: view.loading, busy: view.busy });
  }
  host.setBuilder(build);

  async function loadQueue() {
    view.loading = true;
    view.failed = false;
    host.paint();
    try {
      data.points = (await api.grammarPoints({ language: view.language })).points || [];
    } catch (error) {
      if (!host.alive() || error?.name === 'AbortError') return;
      view.failed = true;
    }
    if (!host.alive()) return;
    view.loading = false;
    host.paint();
  }

  async function loadPoint() {
    view.loading = true;
    view.failed = false;
    host.paint();
    try {
      data.point = await api.grammarPoint(ctx.params.id);
      const summaries = (await api.grammarPoints({ language: data.point.language })).points || [];
      data.summary = summaries.find((row) => row.id === data.point.id) || null;
      const latest = data.point.versions[data.point.versions.length - 1];
      const shown = latest ? await api.grammarPreview(latest.id) : null;
      data.preview = shown?.point ? conceptPreviewMarkup(shown.point, { support: support(), native: ctx.context?.profile?.native_language }) : '';
    } catch (error) {
      if (!host.alive() || error?.name === 'AbortError') return;
      view.failed = true;
    }
    if (!host.alive()) return;
    view.loading = false;
    host.paint();
  }

  const load = () => (routeId === 'adminGrammarPoint' ? loadPoint() : loadQueue());

  /* ---- navigation, filters ---- */
  host.on('go', (control, dataset) => { host.closePanel(); if (dataset.to) ctx.go(dataset.to); });
  host.on('tab', (control, dataset) => {
    view.tab = dataset.tab;
    view.level = 'all';
    ctx.replace(ctx.href('adminGrammar', {}, { language: view.language, tab: view.tab }));
  });
  host.on('grammar-language', (control, dataset) => {
    if (dataset.value === view.language) return;
    ctx.replace(ctx.href('adminGrammar', {}, { language: dataset.value, tab: view.tab }));
  });
  host.on('level', (control, dataset) => { view.level = dataset.value; host.paint(); });
  host.onInput((id, value) => { if (id === 'q') { view.q = value; host.paint(); } });

  /* ---- the learner preview, from a queue row ---- */
  host.on('grammar-preview', async (control, dataset) => {
    try {
      const point = await api.grammarPoint(dataset.id);
      const latest = point.versions[point.versions.length - 1];
      const shown = await api.grammarPreview(latest.id);
      const row = data.points.find((item) => item.id === dataset.id);
      host.showPanel({
        kicker: t('grLearnerView'),
        title: row?.header?.native_title || point.id,
        meta: t('grVersion', { n: latest.version }),
        body: conceptPreviewMarkup(shown.point, { support: support(), native: ctx.context?.profile?.native_language }),
        actions: [{ label: t('rdReview'), kind: 'primary', a: 'go', data: { to: ctx.href('adminGrammarPoint', { id: point.id }) } }],
      });
    } catch (error) {
      host.toast(explain(error));
    }
  });

  /* ---- one point's decisions ---- */
  const CONFIRM = {
    reject: { title: 'grRejectTitle', body: 'grRejectBody', confirm: 'grReject', danger: true, reason: true },
    publish: { title: 'grPublishTitle', body: 'grPublishBody', confirm: 'grPublish', danger: false },
    unpublish: { title: 'grUnpublishTitle', body: 'grUnpublishBody', confirm: 'grUnpublish', danger: true },
    archive: { title: 'grArchiveTitle', body: 'grArchiveBody', confirm: 'grArchive', danger: true },
    restrict: { title: 'grRestrictTitle', body: 'grRestrictBody', confirm: 'grRestrict', danger: true, reason: true },
    clear: { title: 'grClearTitle', body: 'grClearBody', confirm: 'grClear', danger: false, reason: true },
  };

  async function newestVersion(id) {
    const point = routeId === 'adminGrammarPoint' && data.point?.id === id ? data.point : await api.grammarPoint(id);
    return { point, latest: point.versions[point.versions.length - 1] };
  }

  host.on('grammar-act', async (control, dataset) => {
    const { id, action } = dataset;
    let point;
    let latest;
    try {
      ({ point, latest } = await newestVersion(id));
    } catch (error) {
      host.toast(explain(error));
      return;
    }
    const spec = CONFIRM[action];
    let reason = t('grReasonDefault');
    if (spec) {
      const answer = await host.confirm({
        title: t(spec.title), body: t(spec.body, { language: languageName(point.language) }), cancel: t('actCancel'), confirm: t(spec.confirm), danger: spec.danger,
        reason: spec.reason ? { label: t('grReasonLabel'), required: true } : null,
      });
      if (!answer.confirmed) return;
      if (spec.reason) reason = answer.reason;
    }
    try {
      if (action === 'accept') await api.grammarReview(latest.id, 'accept', reason);
      else if (action === 'reject') await api.grammarReview(latest.id, 'reject', reason);
      else if (action === 'publish') await api.grammarPublishPoint(id, latest.id, reason);
      else if (action === 'restrict') await api.grammarVersionRights(latest.id, 'restricted', reason);
      else if (action === 'clear') await api.grammarVersionRights(latest.id, 'cleared', reason);
      else await api.grammarStatus(id, action, reason);
      host.toast(t('grDone'));
    } catch (error) {
      host.toast(explain(error));
    }
    await load();
  });

  /* ---- the batch acts of the queue ---- */
  host.on('grammar-accept-all', async () => {
    const targets = shownPoints(data.points, { tab: 'review', level: view.level, q: view.q, ui: ui() });
    if (!targets.length) return;
    const answer = await host.confirm({ title: t('grAcceptAllTitle', { n: targets.length }), body: t('grAcceptAllBody'), cancel: t('actCancel'), confirm: t('grAccept'), danger: false });
    if (!answer.confirmed) return;
    let done = 0;
    let failed = null;
    for (const point of targets) {
      if (!host.alive()) return;
      view.busy = `${t('grAccept')} · ${done} / ${targets.length}`;
      host.paint();
      try {
        await api.grammarReview(point.latest_version.id, 'accept', t('grReasonDefault'));
        done += 1;
      } catch (error) {
        failed = failed || error;
      }
    }
    view.busy = '';
    host.toast(failed ? explain(failed) : t('grAccepted', { n: done }));
    await loadQueue();
  });

  host.on('grammar-publish-all', async () => {
    const items = publishableItems(data.points);
    if (!items.length) return;
    const language = languageName(view.language);
    const answer = await host.confirm({ title: t('grPublishAllTitle', { n: items.length, language }), body: t('grPublishAllBody', { language }), cancel: t('actCancel'), confirm: t('grPublishAllConfirm'), danger: false });
    if (!answer.confirmed) return;
    view.busy = `${t('grPublish')} · ${items.length}`;
    host.paint();
    try {
      const result = await api.grammarPublish(items, t('grReasonDefault'));
      host.toast(t('grPublished', { n: (result.published || []).length }));
    } catch (error) {
      host.toast(explain(error));
    }
    view.busy = '';
    await loadQueue();
  });

  host.on('reload', () => load());
  await load();
  return () => host.cleanup();
}
