/* Imports, wired: the pages of imports-pages.js over the shared importer rules
   (capabilities/admin-imports.js) and the one admin client. Books and media go one item per request
   so a failure never holds up the rest; a vocabulary batch is one request because publication is
   decided for the collection as a whole. */
import { html } from '../../kit/html.js';
import { languages } from '../../copy/index.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { watch as watchJob } from '../../capabilities/admin-tray.js';
import {
  MEDIA_LEVELS, checkMediaUrls, defaultCollectionTitle, importBooks, importMedia, importVocabulary, loadHistory, loadJobs,
  previewVocabulary, sourceBody, vocabularyProblems, mediaProcessingOutcome,
} from '../../capabilities/admin-imports.js';
import { t } from './copy.js';
import { createHost } from './host.js';
import { explain } from './reading.js';
import { pageHead, skeleton } from './blocks.js';
import { loadFailedBlock } from './reading-pages.js';
import { booksPage, historyPage, hubPage, jobPage, jobsPage, mediaPage, sourceFormPage, vocabularyPage } from './imports-pages.js';

export async function mountImports(shell, ctx) {
  const routeId = ctx.route.id;
  const host = createHost(shell, ctx);
  const api = adminApi;
  const ui = () => languages().ui;
  const learning = ctx.context?.language === 'zh' ? 'zh' : 'en';
  const view = {
    loading: true, failed: false,
    books: { items: [], language: learning, running: false },
    media: { tab: 'url', urls: '', items: [], language: learning, checking: false, running: false },
    vocab: {
      files: [], previews: [], mappings: {}, step: 0, showAll: false, running: false, previewing: false, errors: [], results: null,
      metadata: { title: '', language: learning, meaning_language: languages().support || '', framework: '', level: '', topic: '', collection_id: '', rights_status: '', completeness: 'unknown', publish: false, attested: false },
    },
    source: { name: '', url: '', type: 'direct_url', language: learning, can_republish: false, can_adapt: false, attribution_required: true, license: '', error: '', running: false },
    jobFilter: ctx.query.get('status') === 'failed' ? 'failed' : 'all',
    history: { kind: 'all', status: ctx.query.get('status') === 'failed' ? 'failed' : 'all', offset: 0 },
  };
  const data = { recent: { book: 0, media: 0, vocabulary: 0, total: 0 }, failedJobs: 0, jobs: [], cursor: null, job: null, history: null };
  let mediaTimer = 0;
  async function refreshMedia() {
    clearTimeout(mediaTimer);
    const entries = view.media.items.filter((item) => item.contentId && item.state !== 'failed');
    await Promise.all(entries.map(async (item) => {
      try {
        const detail = await api.contentDetail('media', item.contentId);
        if (host.alive() && view.media.items.includes(item)) Object.assign(item, mediaProcessingOutcome(detail));
      } catch {
        // Retain the last known state on a transient read failure; the content
        // detail remains reachable and a pending item will be checked again.
      }
    }));
    if (!host.alive()) return;
    host.paint();
    if (view.media.items.some((item) => item.contentId && item.state === 'processing')) mediaTimer = setTimeout(refreshMedia, 2500);
  }

  function build() {
    const base = { t, ui: ui(), href: ctx.href };
    if (view.loading) return { title: t('impTitle'), markup: html`<section class="a-page">${pageHead({ title: t('impTitle') })}${skeleton(t('loading'))}</section>` };
    if (view.failed) return { title: t('impTitle'), markup: html`<section class="a-page">${pageHead({ title: t('impTitle') })}${loadFailedBlock(t)}</section>` };
    switch (routeId) {
      case 'adminImportBooks': return booksPage({ ...base, books: view.books });
      case 'adminImportMedia': return mediaPage({ ...base, media: view.media });
      case 'adminImportVocab': return vocabularyPage({ ...base, vocab: view.vocab });
      case 'adminImportSource': return sourceFormPage({ ...base, form: view.source });
      case 'adminJobs': return jobsPage({ ...base, jobs: data.jobs, cursor: data.cursor, filter: view.jobFilter });
      case 'adminJob': return jobPage({ ...base, job: data.job });
      case 'adminHistory': return historyPage({ ...base, data: data.history, filters: view.history });
      default: return hubPage({ ...base, recent: data.recent, failedJobs: data.failedJobs });
    }
  }
  host.setBuilder(build);

  const jobStatus = () => ({ all: '', running: 'running', failed: 'failed', completed: 'completed' }[view.jobFilter] || '');

  async function load() {
    view.loading = true;
    view.failed = false;
    host.paint();
    try {
      if (routeId === 'adminImports') {
        const [history, failed] = await Promise.all([loadHistory(api).catch(() => null), loadJobs(api, { status: 'failed', limit: 25 }).catch(() => ({ items: [] }))]);
        const rows = history?.items || [];
        data.recent = { book: rows.filter((row) => row.kind === 'book').length, media: rows.filter((row) => row.kind === 'media').length, vocabulary: rows.filter((row) => row.kind === 'vocabulary').length, total: history?.total || rows.length };
        data.failedJobs = (failed.items || []).length;
      } else if (routeId === 'adminJobs') {
        const page = await loadJobs(api, { status: jobStatus() });
        data.jobs = page.items || [];
        data.cursor = page.next_cursor || null;
      } else if (routeId === 'adminJob') {
        data.job = await api.readingJob(ctx.params.id);
      } else if (routeId === 'adminHistory') {
        data.history = await loadHistory(api, { kind: view.history.kind === 'all' ? '' : view.history.kind, status: view.history.status === 'all' ? '' : view.history.status, offset: view.history.offset });
      }
    } catch (error) {
      if (!host.alive() || error?.name === 'AbortError') return;
      view.failed = true;
    }
    if (!host.alive()) return;
    view.loading = false;
    host.paint();
  }

  host.on('go', (control, dataset) => { if (dataset.to) ctx.go(dataset.to); });
  host.on('reload', () => load());
  host.on('more', async () => {
    try {
      const page = await loadJobs(api, { status: jobStatus(), cursor: data.cursor || '' });
      data.jobs = [...data.jobs, ...(page.items || [])];
      data.cursor = page.next_cursor || null;
    } catch (error) {
      host.toast(explain(error));
    }
    host.paint();
  });
  host.on('job-filter', (control, dataset) => { view.jobFilter = dataset.value; load(); });
  host.on('job-retry', async (control, dataset) => {
    try {
      const retried = await api.readingRetryJob(dataset.id);
      watchJob({ id: retried.id, label: '' });
      host.toast(t('jobRetried'));
      await load();
    } catch (error) {
      host.toast(explain(error));
    }
  });
  host.on('history-filter', (control, dataset) => { view.history[dataset.field] = dataset.value; view.history.offset = 0; load(); });
  host.on('history-page', (control, dataset) => { view.history.offset = Math.max(0, view.history.offset + Number(dataset.dir) * 20); load(); });

  /* ---- books ---- */
  host.onFile((id, files) => {
    if (id === 'files') view.books.items = files.map((file) => ({ file, name: file.name, size: file.size, state: 'to_import' }));
    if (id === 'mediaFiles') view.media.items = [...view.media.items.filter((item) => !item.file), ...files.map((file) => ({ file, name: file.name, size: file.size, state: 'to_import' }))];
    if (id === 'vfiles') { view.vocab.files = files; view.vocab.errors = []; }
    host.paint();
  });
  host.on('books-import', async () => {
    view.books.running = true;
    host.paint();
    await importBooks(api, view.books.items, view.books.language, () => host.paint());
    view.books.running = false;
    host.paint();
  });

  /* ---- media ---- */
  host.on('tab', (control, dataset) => { view.media.tab = dataset.tab; host.paint(); });
  host.on('media-check', async () => {
    const urls = view.media.urls.split(/[\n,]/).map((line) => line.trim()).filter(Boolean);
    const files = view.media.items.filter((item) => item.file);
    view.media.checking = true;
    host.paint();
    view.media.items = [...await checkMediaUrls(api, urls, view.media.language), ...files];
    view.media.checking = false;
    host.paint();
  });
  host.on('media-level', (control, dataset) => {
    const item = view.media.items[Number(dataset.index)];
    const levels = ['', ...(MEDIA_LEVELS[view.media.language] || [])];
    item.level = levels[(levels.indexOf(item.level || '') + 1) % levels.length];
    host.paint();
  });
  host.on('media-remove', (control, dataset) => { view.media.items.splice(Number(dataset.index), 1); host.paint(); });
  host.on('media-import', async () => {
    view.media.running = true;
    host.paint();
    await importMedia(api, view.media.items, view.media.language, () => host.paint());
    view.media.running = false;
    for (const item of view.media.items) if (item.contentId && item.state !== 'failed') item.state = 'processing';
    await refreshMedia();
  });

  /* ---- vocabulary ---- */
  host.on('vocab-preview', async () => {
    const vocab = view.vocab;
    vocab.previewing = true;
    vocab.errors = [];
    host.paint();
    try {
      const found = await previewVocabulary(api, vocab.files);
      vocab.previews = found.previews;
      vocab.mappings = found.mappings;
      if (!vocab.metadata.title) vocab.metadata.title = found.title || defaultCollectionTitle(vocab.files[0]?.name);
      vocab.step = 1;
    } catch (error) {
      vocab.errors = [explain(error)];
    }
    vocab.previewing = false;
    host.paint();
  });
  host.on('vocab-more', () => { view.vocab.showAll = !view.vocab.showAll; host.paint(); });
  host.on('vocab-reset', () => {
    Object.assign(view.vocab, { files: [], previews: [], mappings: {}, step: 0, results: null, errors: [], showAll: false });
    view.vocab.metadata = { ...view.vocab.metadata, title: '', publish: false, attested: false };
    host.paint();
  });
  host.on('vocab-import', async () => {
    const vocab = view.vocab;
    const problems = vocabularyProblems(vocab);
    if (problems.length) {
      vocab.errors = problems.map((problem) => t(problem.key, { file: problem.file || '' }));
      host.paint();
      return;
    }
    vocab.running = true;
    vocab.errors = [];
    host.paint();
    try {
      vocab.results = await importVocabulary(api, { files: vocab.files, metadata: vocab.metadata, mappings: vocab.mappings });
    } catch (error) {
      vocab.errors = [explain(error)];
    }
    vocab.running = false;
    host.paint();
  });
  host.on('toggle', (control, dataset) => {
    if (dataset.field === 'meta:publish') view.vocab.metadata.publish = !view.vocab.metadata.publish;
    else if (dataset.field === 'meta:attested') view.vocab.metadata.attested = !view.vocab.metadata.attested;
    else if (routeId === 'adminImportSource') view.source[dataset.field] = !view.source[dataset.field];
    host.paint();
  });

  /* ---- shared fields ---- */
  host.on('pick', (control, dataset) => {
    const { field, value } = dataset;
    if (routeId === 'adminImportBooks') view.books[field] = value;
    else if (routeId === 'adminImportMedia') {
      view.media[field] = value;
      view.media.items = view.media.items.map((item) => ({ ...item, level: '' }));
    } else if (routeId === 'adminImportVocab' && field.startsWith('meta:')) view.vocab.metadata[field.slice(5)] = value;
    else if (routeId === 'adminImportSource') view.source[field] = value;
    host.paint();
  });
  host.onInput((id, value) => {
    if (routeId === 'adminImportMedia' && id === 'urls') view.media.urls = value;
    else if (routeId === 'adminImportVocab') {
      if (id.startsWith('meta:')) view.vocab.metadata[id.slice(5)] = value;
      else if (id.startsWith('map:')) {
        const [, index, field] = id.split(':');
        const preview = view.vocab.previews[Number(index)];
        if (preview) {
          view.vocab.mappings[preview.filename] = { ...(view.vocab.mappings[preview.filename] || {}), [field]: value || undefined };
          host.paint();
        }
      }
    } else if (routeId === 'adminImportSource' && id in view.source) view.source[id] = value;
    if (routeId === 'adminImportMedia' && id === 'urls') host.paint();
  });

  /* ---- register a source ---- */
  host.on('source-create', async () => {
    const form = view.source;
    if (!form.name.trim() || !/^https?:\/\//i.test(form.url.trim())) { form.error = t('impSourceRequired'); host.paint(); return; }
    form.running = true;
    form.error = '';
    host.paint();
    try {
      const created = await api.readingCreateSource(sourceBody({ name: form.name, url: form.url, type: form.type, language: form.language, rights: form, license: form.license }));
      host.toast(t('impSourceRegistered'));
      ctx.go(ctx.href('adminSource', { id: created.id }));
      return;
    } catch (error) {
      form.error = explain(error);
    }
    form.running = false;
    host.paint();
  });

  if (['adminImportBooks', 'adminImportMedia', 'adminImportVocab', 'adminImportSource'].includes(routeId)) {
    view.loading = false;
    host.paint();
  } else {
    load();
  }
  return () => { clearTimeout(mediaTimer); host.cleanup(); };
}
