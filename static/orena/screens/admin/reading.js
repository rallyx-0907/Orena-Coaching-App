/* The Reading pipeline, wired: the pages of reading-pages.js over the shared rules
   (capabilities/admin-reading.js) and the one admin client. Every action is a call to a route that
   already exists; publishing is one of them, always an administrator's act, and rights advice
   warns before it and never disables it (D-082). */
import { languages } from '../../copy/index.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { watch as watchJob } from '../../capabilities/admin-tray.js';
import {
  changeArticle, loadQueue, publicationAdvice, publicationBlockers, rightsChanges, saveArticle, submissionFrom, submissionProblem, submitContent, tabFrom,
} from '../../capabilities/admin-reading.js';
import { t } from './copy.js';
import { createHost } from './host.js';
import { loadFailedBlock, addPage, articlePage, overviewPage, previewBody, queuePage, setPage, sourcePage, sourcesPage } from './reading-pages.js';
import { html } from '../../kit/html.js';
import { pageHead, skeleton } from './blocks.js';

/* What a failed request says: our words for the errors an operator meets, the server's own sentence
   for the rest. */
export function explain(error) {
  const category = error?.category || error?.context?.category || '';
  if (category && t.has(`err_${category}`)) return t(`err_${category}`);
  return error?.message || t('healthError_unknown');
}

export async function mountReading(shell, ctx) {
  const routeId = ctx.route.id;
  const host = createHost(shell, ctx);
  const api = adminApi;
  const ui = () => languages().ui;
  const view = {
    loading: true, failed: false, busy: false,
    tab: tabFrom(ctx.query.get('tab')), q: '', level: 'all',
    dtab: 'article', evOpen: false, edit: {}, dirty: false, editError: '', actionError: '', newTarget: { text: '', type: 'word', meaning: '' }, targetError: '',
    support: languages().support === 'vi' || languages().support === 'zh' ? languages().support : 'en', generating: false, setError: '',
    error: '', mode: ctx.query.get('mode') === 'text' ? 'text' : ctx.query.get('mode') === 'file' ? 'file' : 'url', rights: '', language: 'auto', last: null, file: null,
  };
  const data = { ops: null, sources: [], next: [], items: [], cursor: null, article: null, sets: [], set: null };

  /* ---- builders ---- */
  function build() {
    const base = { t, ui: ui(), href: ctx.href, now: Date.now(), view };
    if (view.loading) return { title: t('rdTitle'), markup: html`<section class="a-page">${pageHead({ title: t('rdTitle') })}${skeleton(t('loading'))}</section>` };
    if (view.failed) return { title: t('rdTitle'), markup: html`<section class="a-page">${pageHead({ title: t('rdTitle') })}${loadFailedBlock(t)}</section>` };
    switch (routeId) {
      case 'adminQueue': return { ...queuePage({ ...base, tab: view.tab, items: data.items, next: data.cursor, counts: counts() }), filterValue: view.q };
      case 'adminArticle': return articlePage({ ...base, article: data.article, sets: data.sets });
      case 'adminSet': return setPage({ ...base, set: data.set, article: data.article });
      case 'adminAdd': return addPage({ ...base, sources: data.sources });
      case 'adminSources': return { ...sourcesPage({ ...base, sources: data.sources }), filterValue: view.q };
      case 'adminSource': {
        const source = data.sources.find((item) => item.id === ctx.params.id);
        return source ? sourcePage({ ...base, source }) : sourcesPage({ ...base, sources: data.sources });
      }
      default: return overviewPage({ ...base, ops: data.ops, sources: data.sources, next: data.next, failedJobs: Number(data.ops?.queue?.failed || 0) });
    }
  }
  host.setBuilder(build, { filter: routeId === 'adminQueue' || routeId === 'adminSources' });

  function counts() {
    const articles = data.ops?.articles || {};
    const sum = (...keys) => keys.reduce((total, key) => total + Number(articles[key] || 0), 0);
    return { review: sum('draft', 'needs_review', 'ready', 'processing'), published: sum('published'), rejected: sum('rejected'), archived: sum('archived', 'unpublished') };
  }

  /* ---- loading ---- */
  async function load() {
    view.loading = true;
    view.failed = false;
    host.paint();
    try {
      if (routeId === 'adminQueue') {
        const [ops, page] = await Promise.all([api.readingOperations().catch(() => null), loadQueue(api, { tab: view.tab })]);
        data.ops = ops;
        data.items = page.items || [];
        data.cursor = page.next_cursor || null;
      } else if (routeId === 'adminArticle') {
        const [article, sets] = await Promise.all([api.readingArticle(ctx.params.id), api.readingSets(ctx.params.id).catch(() => ({ items: [] }))]);
        data.article = article;
        data.sets = sets.items || [];
      } else if (routeId === 'adminSet') {
        data.set = await api.readingSet(ctx.params.id);
        data.article = await api.readingArticle(data.set.article_id).catch(() => null);
      } else if (routeId === 'adminSources' || routeId === 'adminSource' || routeId === 'adminAdd') {
        data.sources = (await api.readingSources()).items || [];
      } else if (routeId === 'adminReading') {
        const [ops, sources, review] = await Promise.all([
          api.readingOperations().catch(() => null),
          api.readingSources().catch(() => ({ items: [] })),
          api.readingQueue({ status: 'draft,needs_review,ready', limit: 3 }).catch(() => ({ items: [] })),
        ]);
        data.ops = ops;
        data.sources = sources.items || [];
        data.next = review.items || [];
      }
    } catch (error) {
      if (!host.alive() || error?.name === 'AbortError') return;
      view.failed = true;
    }
    if (!host.alive()) return;
    view.loading = false;
    host.paint();
  }

  /* ---- handlers ---- */
  host.on('reload', () => load());
  host.on('tab', (control, dataset) => ctx.replace(ctx.href('adminQueue', {}, { tab: dataset.tab })));
  host.on('level', (control, dataset) => { view.level = dataset.value; host.paint(); });
  host.on('dtab', (control, dataset) => { view.dtab = dataset.value; host.paint(); });
  host.on('toggle-evidence', () => { view.evOpen = !view.evOpen; host.paint(); });
  host.onFilter((value) => { view.q = value; host.paint(); });

  host.on('more', async () => {
    if (!data.cursor) return;
    try {
      const page = await loadQueue(api, { tab: view.tab, cursor: data.cursor });
      data.items = [...data.items, ...(page.items || [])];
      data.cursor = page.next_cursor || null;
    } catch (error) {
      host.toast(explain(error));
    }
    host.paint();
  });

  host.on('preview', async (control, dataset) => {
    try {
      const article = await api.readingArticle(dataset.id);
      host.showPanel({
        kicker: t('rdPreviewKicker'), title: article.title, meta: `${article.effective_level || ''} · ${t('rdMinutes', { n: Math.max(1, Math.round((article.reading_time_seconds || 0) / 60)) })}`,
        body: previewBody(article),
        actions: [{ label: t('rdReview'), kind: 'primary', a: 'go', data: { to: ctx.href('adminArticle', { id: article.id }) } }],
      });
    } catch (error) {
      host.toast(explain(error));
    }
  });
  host.on('go', (control, dataset) => { host.closePanel(); ctx.go(dataset.to); });

  /* Publish, unpublish, reject, archive, restore - each an administrator's own act. */
  async function runAction(id, action, known = null) {
    let article = known;
    try {
      if (action === 'publish') {
        article = article || await api.readingArticle(id);
        if (publicationBlockers(article).length) {
          /* Copyright is a hard gate: say why, and take the operator to where the questions are answered. */
          if (routeId === 'adminArticle') {
            view.actionError = t('rdBlockedText');
            host.paint();
          } else {
            host.toast(t('rdBlockedToast'));
            ctx.go(ctx.href('adminArticle', { id }));
          }
          return;
        }
        const advice = publicationAdvice(article);
        if (advice.length) {
          const answer = await host.confirm({
            title: t('rdPublishTitle', { title: article.title }),
            body: t('rdPublishRisk'),
            list: advice.map((warning) => t(`rdWarn_${warning.code}`)),
            cancel: t('actCancel'), confirm: t('rdPublishAnyway'), danger: false,
          });
          if (!answer.confirmed) return;
        }
        const done = await changeArticle(api, id, 'publish');
        host.toast(done.publication_warnings?.length ? t('rdPublishedOver') : t('rdPublished'));
      } else if (action === 'reject') {
        const answer = await host.confirm({
          title: t('rdRejectTitle'), body: t('rdRejectBody'), reason: { label: t('rdReasonLabel'), placeholder: t('rdReasonHint'), required: true },
          cancel: t('actCancel'), confirm: t('rdReject'),
        });
        if (!answer.confirmed) return;
        await changeArticle(api, id, 'reject', answer.reason);
        host.toast(t('rdRejected'));
      } else if (action === 'unpublish' || action === 'archive') {
        const answer = await host.confirm({
          title: t(action === 'unpublish' ? 'rdUnpublishTitle' : 'rdArchiveTitle'), body: t(action === 'unpublish' ? 'rdUnpublishBody' : 'rdArchiveBody'),
          cancel: t('actCancel'), confirm: t(action === 'unpublish' ? 'rdUnpublish' : 'rdArchive'), danger: action === 'archive',
        });
        if (!answer.confirmed) return;
        await changeArticle(api, id, action);
        host.toast(t(action === 'unpublish' ? 'rdUnpublished' : 'rdArchived'));
      } else {
        await changeArticle(api, id, action);
        host.toast(t('rdRestored'));
      }
    } catch (error) {
      view.actionError = explain(error);
      host.toast(view.actionError);
      host.paint();
      return;
    }
    view.actionError = '';
    await load();
  }
  host.on('article-act', (control, dataset) => runAction(dataset.id, dataset.action, routeId === 'adminArticle' ? data.article : null));

  /* ---- the review pane ---- */
  host.onInput((id, value) => {
    if (routeId === 'adminAdd') { view[id] = value; if (id === 'registeredSource') host.paint(); return; }
    if (['title', 'topic', 'body'].includes(id)) { view.edit[id] = value; view.dirty = true; view.editError = ''; }
    if (id.startsWith('nt_')) {
      view.newTarget = { ...view.newTarget, [id.slice(3)]: value };
      if (id === 'nt_text') host.paint();
    }
  });
  host.on('rights-pick', (control, dataset) => {
    view.rightsDraft = { ...(view.rightsDraft || {}), [dataset.field]: dataset.value };
    view.rightsDirty = Object.keys(rightsChanges(data.article?.source?.rights_state, view.rightsDraft, data.article?.automation)).length > 0;
    view.rightsError = '';
    host.paint();
  });
  host.on('rights-save', async () => {
    const body = rightsChanges(data.article?.source?.rights_state, view.rightsDraft || {}, data.article?.automation);
    if (!Object.keys(body).length) return;
    view.busy = true;
    view.rightsError = '';
    host.paint();
    try {
      data.article = { ...data.article, ...await api.readingSetRights(data.article.id, body) };
      view.rightsDraft = {};
      view.rightsDirty = false;
      view.actionError = '';
      host.toast(t('rdRightsSavedToast'));
    } catch (error) {
      view.rightsError = explain(error);
    }
    view.busy = false;
    host.paint();
  });
  host.on('edit-pick', (control, dataset) => {
    view.edit.reviewed_level = dataset.value;
    view.dirty = true;
    host.paint();
  });
  host.on('save-article', async () => {
    view.busy = true;
    view.editError = '';
    host.paint();
    try {
      data.article = { ...data.article, ...await saveArticle(api, data.article.id, data.article, view.edit) };
      view.edit = {};
      view.dirty = false;
      host.toast(t('rdSavedToast'));
    } catch (error) {
      view.editError = explain(error);
    }
    view.busy = false;
    host.paint();
  });
  host.on('target-decide', async (control, dataset) => {
    try {
      await api.readingDecideTarget(data.article.id, dataset.id, dataset.approved === '1');
      data.article = await api.readingArticle(data.article.id);
    } catch (error) {
      host.toast(explain(error));
    }
    host.paint();
  });
  host.on('target-move', async (control, dataset) => {
    const ids = data.article.targets.map((target) => target.id);
    const from = ids.indexOf(dataset.id);
    const to = from + Number(dataset.dir);
    if (from < 0 || to < 0 || to >= ids.length) return;
    [ids[from], ids[to]] = [ids[to], ids[from]];
    try {
      await api.readingReorderTargets(data.article.id, ids);
      data.article = await api.readingArticle(data.article.id);
    } catch (error) {
      host.toast(explain(error));
    }
    host.paint();
  });
  host.on('target-add', async () => {
    const { text, type, meaning } = view.newTarget;
    try {
      await api.readingAddTarget(data.article.id, { text: text.trim(), target_type: type, meaning: meaning.trim() });
      data.article = await api.readingArticle(data.article.id);
      view.newTarget = { text: '', type: 'word', meaning: '' };
      view.targetError = '';
    } catch (error) {
      view.targetError = explain(error);
    }
    host.paint();
  });

  /* ---- comprehension sets ---- */
  host.on('pick', (control, dataset) => {
    if (dataset.field === 'support') view.support = dataset.value;
    else view[dataset.field] = dataset.value;
    host.paint();
  });
  async function generate() {
    view.generating = true;
    view.setError = '';
    host.paint();
    try {
      const created = await api.readingGenerateSet(data.article.id, view.support);
      host.toast(t('csGenerated'));
      view.generating = false;
      ctx.go(ctx.href('adminSet', { id: created.id }));
      return;
    } catch (error) {
      view.setError = explain(error);
    }
    view.generating = false;
    host.paint();
  }
  host.on('set-generate', () => generate());
  host.on('set-regenerate', async () => {
    data.article = data.article || await api.readingArticle(data.set.article_id);
    view.support = data.set.support_language;
    await generate();
  });
  host.on('question-decide', async (control, dataset) => {
    view.busy = true;
    view.error = '';
    host.paint();
    try {
      data.set = await api.readingDecideQuestion(data.set.id, dataset.id, dataset.decision);
    } catch (error) {
      view.error = explain(error);
    }
    view.busy = false;
    host.paint();
  });
  host.on('set-transition', async (control, dataset) => {
    let reason = '';
    if (dataset.reason === '1') {
      const answer = await host.confirm({ title: t('csRejectTitle'), body: t('csRejectBody'), reason: { label: t('rdReasonLabel'), placeholder: t('rdReasonHint'), required: true }, cancel: t('actCancel'), confirm: t('csAct_reject') });
      if (!answer.confirmed) return;
      reason = answer.reason;
    }
    view.busy = true;
    view.error = '';
    host.paint();
    try {
      data.set = await api.readingSetTransition(data.set.id, dataset.status, reason);
      host.toast(t(`csDone_${dataset.status}`));
    } catch (error) {
      view.error = explain(error);
    }
    view.busy = false;
    host.paint();
  });
  host.on('set-discard', async () => {
    const answer = await host.confirm({ title: t('csDiscardTitle'), body: t('csDiscardBody'), cancel: t('actCancel'), confirm: t('csAct_discard') });
    if (!answer.confirmed) return;
    try {
      await api.readingDiscardSet(data.set.id);
      host.toast(t('csDiscarded'));
      ctx.go(ctx.href('adminArticle', { id: data.set.article_id }));
    } catch (error) {
      view.error = explain(error);
      host.paint();
    }
  });

  /* ---- add content ---- */
  host.on('add-mode', (control, dataset) => { view.mode = dataset.value; view.error = ''; host.paint(); });
  host.onFile((id, files) => { view.file = files[0] || null; view.error = ''; host.paint(); });
  host.on('add-another', () => { Object.assign(view, { last: null, url: '', title: '', body: '', file: null, error: '' }); host.paint(); });
  host.on('add-submit', async () => {
    const submitted = submissionFrom({ mode: view.mode, title: view.title || '', body: view.body || '', url: view.url || '', language: view.language, source: view.source || '', registeredSource: view.registeredSource || '', author: view.author || '', sourceUrl: view.sourceUrl || '', rights: view.rights, adapt: view.adapt || '', attribution: view.attribution || '', license: view.license || '' });
    const problem = submissionProblem(submitted, view.file);
    if (problem) { view.error = t(problem); host.paint(); return; }
    view.busy = true;
    view.error = '';
    host.paint();
    try {
      const job = await submitContent(api, submitted, view.mode === 'file' ? view.file : null);
      const label = (submitted.title || submitted.url || view.file?.name || t('addUntitled')).slice(0, 120);
      watchJob({ id: job.id, label });
      view.last = { id: job.id, title: label, duplicate: job.duplicate };
      Object.assign(view, { url: '', title: '', body: '', file: null });
    } catch (error) {
      view.error = explain(error);
    }
    view.busy = false;
    host.paint();
  });

  /* ---- sources ---- */
  host.on('source-state', async (control, dataset) => {
    const source = data.sources.find((item) => item.id === dataset.id);
    if (['blocked', 'archived'].includes(dataset.state)) {
      const answer = await host.confirm({
        title: t(dataset.state === 'blocked' ? 'srcBlockTitle' : 'srcArchiveTitle'), body: t(dataset.state === 'blocked' ? 'srcBlockBody' : 'srcArchiveBody', { name: source?.name || '' }),
        cancel: t('actCancel'), confirm: t(dataset.state === 'blocked' ? 'srcBlock' : 'srcArchive'),
      });
      if (!answer.confirmed) return;
    }
    try {
      await api.readingSetSourceState(dataset.id, dataset.state);
      data.sources = (await api.readingSources()).items || [];
      view.error = '';
      host.toast(t('srcUpdated'));
    } catch (error) {
      view.error = explain(error);
    }
    host.paint();
  });

  load();
  return () => host.cleanup();
}
