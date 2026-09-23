/* Content: one library over the three catalogs that exist - books, media
   (curated lessons and shared imports) and vocabulary collections - read from
   /api/admin/console/content, which keeps each item's own identity.

   Actions appear only where a backend contract exists: a published book can be
   archived, a vocabulary collection waiting for review can be published after
   its rights are confirmed, and media imported from a link can be read again.
   Every action opens the item first, so the operator sees what they are about
   to change. There is no delete, unpublish or edit, because nothing
   implements them. */
import { adminApi } from './api.js';
import { openDrawer } from './drawer.js';
import { chip, dateShort, dateTime, duration, esc, fill, kv, languageName, notice, num, pager, panel, select, table } from './format.js';
import { safeExternal } from '../ui/html.js';
import { entryIcon } from '../ui/icons.js';

export const PAGE_SIZE = 25;
const KINDS = ['all', 'book', 'media', 'vocabulary'];
const KIND_ICON = { book: 'book', media: 'sound', vocabulary: 'leaf' };
export const RIGHTS = ['public_domain', 'licensed', 'creator_authorized', 'internal_curated'];

export function imageSource(url) {
  const value = String(url || '');
  if (value.startsWith('/api/')) return value;
  return safeExternal(value);
}

function thumb(record) {
  const source = imageSource(record.image);
  return `<span class="ac-thumb" data-kind="${esc(record.kind)}">${source
    ? `<img src="${esc(source)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
    : entryIcon(KIND_ICON[record.kind] || 'folder')}</span>`;
}

function statusLabel(record, t) {
  if (record.kind === 'vocabulary' && record.status === 'draft') return chip('pending_review', t);
  return chip(record.status, t);
}

export function detailsCell(record, t, ui) {
  const facts = record.facts || {};
  if (record.kind === 'book') return esc(fill(t.detailsBook, { chapters: num(facts.chapter_count, ui), words: num(facts.word_count, ui) }));
  if (record.kind === 'media') {
    const length = facts.duration_ms ? esc(duration(facts.duration_ms)) : '';
    const transcript = facts.transcript === 'available'
      ? `<span>${esc(fill(t.detailsTranscript, { count: num(facts.segment_count, ui) }))}</span>`
      : chip('transcript_missing', t);
    return `<div class="ac-cell-stack">${length ? `<span>${length}</span>` : ''}${transcript}</div>`;
  }
  return esc(fill(t.detailsVocabulary, { count: num(facts.item_count, ui) }));
}

function actionButtons(record, t) {
  const buttons = [`<button type="button" class="ac-button" data-ac-open="${esc(record.kind)}:${esc(record.id)}">${esc(t.actionPreview)}</button>`];
  if (record.actions.includes('archive')) buttons.push(`<button type="button" class="ac-button" data-ac-open="${esc(record.kind)}:${esc(record.id)}" data-ac-intent="archive">${esc(t.actionArchive)}</button>`);
  if (record.actions.includes('publish')) buttons.push(`<button type="button" class="ac-button" data-ac-open="${esc(record.kind)}:${esc(record.id)}" data-ac-intent="publish">${esc(t.actionPublish)}</button>`);
  if (record.actions.includes('reprocess')) buttons.push(`<button type="button" class="ac-button" data-ac-open="${esc(record.kind)}:${esc(record.id)}" data-ac-intent="reprocess">${esc(t.actionReprocess)}</button>`);
  return `<div class="ac-actions">${buttons.join('')}</div>`;
}

export function contentTabs(kind, counts, t, ui) {
  return `<div class="ac-segments" role="group" aria-label="${esc(t.colTypeContent)}">${KINDS.map((value) => `<button type="button" class="ac-segment" data-ac-kind="${value}" aria-pressed="${value === kind}">${esc(t[`kind_${value}`])}<span class="ac-segment__count">${esc(num(counts?.[value] ?? 0, ui))}</span></button>`).join('')}</div>`;
}

export function contentToolbar(filters, t) {
  return `<form class="ac-toolbar" data-ac-filters role="search"><label class="ac-field ac-field--search"><span class="sr-only">${esc(t.searchContent)}</span><input type="search" name="q" value="${esc(filters.q || '')}" placeholder="${esc(t.searchContent)}" autocomplete="off"></label>${select({
    name: 'language', label: t.colLanguage, value: filters.language || '',
    options: [['', t.all], ['en', languageName('en', t)], ['zh', languageName('zh', t)]],
  })}${select({
    name: 'status', label: t.filterStatus, value: filters.status || '',
    options: [['', t.all], ['published', t.status_published], ['draft', t.status_draft], ['archived', t.status_archived], ['issues', t.statusIssues]],
  })}${select({
    name: 'sort', label: t.sortLabel, value: filters.sort || 'updated',
    options: [['updated', t.sort_updated], ['created', t.sort_created], ['title', t.sort_title]],
  })}</form>`;
}

export function contentTable(data, t, ui) {
  const sources = Object.entries(data?.sources || {}).filter(([, state]) => state !== 'ok');
  const notices = sources.map(([kind]) => notice(t[`sourceUnavailable_${kind}`] || kind, 'warn')).join('');
  const rows = (data?.items || []).map((record) => ({
    attributes: ` data-content-row="${esc(record.kind)}:${esc(record.id)}"`,
    cells: [
      `<div class="ac-title-cell">${thumb(record)}<div class="ac-cell-stack"><button type="button" class="ac-rowlink" data-ac-open="${esc(record.kind)}:${esc(record.id)}" lang="${esc(record.language)}">${esc(record.title)}</button>${record.subtitle ? `<span class="ac-muted">${esc(record.subtitle)}</span>` : ''}<span class="ac-tag">${esc(t[`origin_${record.origin}`] || record.origin)}</span></div></div>`,
      esc(t[`type_${record.kind}`] || record.kind),
      esc(languageName(record.language, t)),
      statusLabel(record, t),
      detailsCell(record, t, ui),
      record.updated_at ? `<span title="${esc(dateTime(record.updated_at, ui))}">${esc(dateShort(record.updated_at, ui))}</span>` : '<span class="ac-muted">—</span>',
      actionButtons(record, t),
    ],
  }));
  return `${notices}${table({
    head: [t.colTitle, t.colTypeContent, t.colLanguage, t.colStatus, t.colDetails, t.colUpdated, { label: t.colActions, hidden: true }],
    rows,
    empty: t.noContent,
    className: 'ac-table--content',
  })}${pager({ offset: data?.offset || 0, limit: data?.limit || PAGE_SIZE, total: data?.total || 0 }, t, ui)}`;
}

/* Only a route inside this app: the link is built by the server from ids,
   and anything else - another site, a script URL - is not offered at all. */
function learnerLink(detail, t) {
  const link = String(detail.learner_link || '');
  return link.startsWith('#/')
    ? `<p><a class="ac-link" href="${esc(link)}">${esc(t.openAsLearner)}</a> <span class="ac-muted">${esc(t.learnerLinkNote)}</span></p>`
    : '';
}

function confirmBlock({ intent, text, action, t }) {
  return `<div class="ac-confirm" data-ac-confirm="${esc(intent)}"><p>${esc(text)}</p><div class="ac-actions"><button type="button" class="ac-button ac-button--primary" data-ac-do="${esc(intent)}">${esc(action)}</button><button type="button" class="ac-button" data-ac-do="cancel">${esc(t.cancel)}</button></div><p class="ac-editor__status" role="status" data-ac-result></p></div>`;
}

export function publishForm(detail, t) {
  const admission = detail.admission || {};
  return `<form class="ac-editor" data-ac-publish><h3>${esc(t.publishTitle)}</h3><div class="ac-editor__fields">${select({
    name: 'rights_status', label: t.rightsStatus, value: admission.rights_status || '',
    options: [['', t.rights_], ...RIGHTS.map((value) => [value, t[`rights_${value}`]])],
  })}${select({
    name: 'completeness', label: t.completeness, value: admission.completeness || 'unknown',
    options: ['complete', 'partial', 'unknown'].map((value) => [value, t[`completeness_${value}`]]),
  })}</div><label class="ac-check"><input type="checkbox" name="attested"><span>${esc(t.attest)}</span></label><div class="ac-editor__actions"><button type="submit" class="ac-button ac-button--primary">${esc(t.actionPublish)}</button><span class="ac-editor__status" role="status" data-ac-result></span></div></form>`;
}

export function contentDetailView(detail, t, ui, intent = '') {
  const record = detail.record;
  const facts = record.facts || {};
  const head = `<div class="ac-detail-head">${thumb(record)}<div><h3 lang="${esc(record.language)}">${esc(record.title)}</h3>${record.subtitle ? `<p class="ac-muted">${esc(record.subtitle)}</p>` : ''}<p class="ac-chips">${statusLabel(record, t)}<span class="ac-tag">${esc(t[`origin_${record.origin}`] || record.origin)}</span></p></div></div>`;
  if (record.kind === 'book') {
    const book = detail.book || {};
    const chapters = book.chapters || [];
    const shown = chapters.slice(0, 12);
    return `<div class="ac-stack">${head}${kv([
      [t.colLanguage, esc(languageName(record.language, t))],
      [t.chapters, esc(num(facts.chapter_count, ui))],
      [t.wordCount, esc(num(facts.word_count, ui))],
      [t.colCreated, esc(dateTime(record.created_at, ui))],
      [t.importedBy, esc(book.imported_by || '—')],
    ])}${book.description ? `<p class="ac-note">${esc(book.description)}</p>` : ''}<section><h3>${esc(t.chapters)}</h3><ol class="ac-chapters">${shown.map((chapter) => `<li lang="${esc(record.language)}">${esc(chapter.title)}</li>`).join('')}</ol>${chapters.length > shown.length ? `<p class="ac-muted">${esc(fill(t.moreChapters, { count: num(chapters.length - shown.length, ui) }))}</p>` : ''}</section>${learnerLink(detail, t)}${record.actions.includes('archive') ? (intent === 'archive'
      ? confirmBlock({ intent: 'archive', text: t.archiveConfirm, action: t.actionArchive, t })
      : `<div class="ac-actions"><button type="button" class="ac-button" data-ac-intent-open="archive">${esc(t.actionArchive)}</button></div>`) : ''}</div>`;
  }
  if (record.kind === 'media') {
    const transcript = detail.transcript || { segments: [], segment_count: 0 };
    const source = detail.source || {};
    const sourceUrl = safeExternal(source.url || '');
    const lines = transcript.segments?.length
      ? `<ol class="ac-transcript">${transcript.segments.map((segment) => `<li><span class="ac-muted">${esc(duration(segment.start_ms))}</span><span lang="${esc(record.language)}">${esc(segment.text)}</span></li>`).join('')}</ol>${transcript.segment_count > transcript.segments.length ? `<p class="ac-muted">${esc(fill(t.entriesShown, { shown: num(transcript.segments.length, ui), total: num(transcript.segment_count, ui) }))}</p>` : ''}`
      : notice(t.noTranscript, 'warn');
    return `<div class="ac-stack">${head}${kv([
      [t.colLanguage, esc(languageName(record.language, t))],
      [t.duration, esc(facts.duration_ms ? duration(facts.duration_ms) : '—')],
      [t.level, esc(facts.level || '—')],
      [t.topic, esc(facts.topic || '—')],
      [t.segments, esc(num(facts.segment_count, ui))],
      [t.provider, esc(facts.provider || '—')],
    ])}<section><h3>${esc(t.source)}</h3>${kv([
      [t.source, sourceUrl ? `<a class="ac-link" href="${esc(sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(sourceUrl)}</a>` : esc(t.fileUpload)],
      [t.license, esc(source.license || '—')],
      [t.rightsReview, esc(source.review_status || '—')],
      source.imported_by ? [t.importedBy, esc(source.imported_by)] : null,
    ])}</section><section><h3>${esc(t.transcript)}</h3>${lines}</section>${learnerLink(detail, t)}${record.origin === 'curated' ? `<p class="ac-note">${esc(t.curatedNote)}</p>` : ''}${record.actions.includes('reprocess') ? (intent === 'reprocess'
      ? confirmBlock({ intent: 'reprocess', text: t.reprocessConfirm, action: t.actionReprocess, t })
      : `<div class="ac-actions"><button type="button" class="ac-button" data-ac-intent-open="reprocess">${esc(t.actionReprocess)}</button></div>`) : ''}</div>`;
  }
  const entries = table({
    head: [t.colTerm, t.colReading, t.colMeaning, t.level, t.colPos],
    rows: (detail.entries || []).map((entry) => [
      `<strong lang="${esc(record.language)}">${esc(entry.term)}</strong>`,
      esc(entry.reading || '—'),
      esc(entry.meaning || '—'),
      esc(entry.level || '—'),
      esc(entry.part_of_speech || '—'),
    ]),
    empty: t.notAvailable,
  });
  const sources = table({
    head: [t.colFile, t.colCreated, t.colStatus, t.colResult],
    rows: (detail.sources || []).map((row) => [
      esc(row.filename),
      esc(dateShort(row.created_at, ui)),
      chip(row.status === 'imported' ? 'imported' : row.status, t),
      esc(row.status === 'failed' ? row.error : fill(t.vocabResult, { imported: num(row.imported, ui), duplicates: num(row.duplicates, ui), skipped: num(row.skipped, ui) })),
    ]),
    empty: t.none,
  });
  return `<div class="ac-stack">${head}${kv([
    [t.colLanguage, esc(languageName(record.language, t))],
    [t.entries, esc(num(facts.item_count, ui))],
    [t.framework, esc(facts.framework || '—')],
    [t.level, esc(facts.level || '—')],
    [t.topic, esc(facts.topic || '—')],
    [t.rightsStatus, esc(facts.rights_status ? t[`rights_${facts.rights_status}`] || facts.rights_status : t.rights_)],
    [t.completeness, esc(facts.completeness ? t[`completeness_${facts.completeness}`] || facts.completeness : '—')],
  ])}<section><h3>${esc(t.entries)}</h3>${entries}${detail.entry_total > (detail.entries || []).length ? `<p class="ac-muted">${esc(fill(t.entriesShown, { shown: num((detail.entries || []).length, ui), total: num(detail.entry_total, ui) }))}</p>` : ''}</section><section><h3>${esc(t.importSources)}</h3>${sources}</section>${record.actions.includes('publish') ? publishForm(detail, t) : ''}</div>`;
}

export async function renderContent(container, env) {
  const { t, ui, alive } = env;
  const api = env.api || adminApi;
  const params = env.params || {};
  const filters = {
    kind: KINDS.includes(params.kind) ? params.kind : 'all',
    q: '',
    language: '',
    status: ['published', 'draft', 'archived', 'issues'].includes(params.status) ? params.status : '',
    sort: 'updated',
  };
  let offset = 0;
  let data = null;
  let timer = null;

  const request = () => api.content({
    kind: filters.kind === 'all' ? '' : filters.kind,
    q: filters.q,
    language: filters.language,
    status: filters.status,
    sort: filters.sort,
    limit: PAGE_SIZE,
    offset,
  });

  data = await request();
  if (!alive()) return;
  container.innerHTML = panel({
    title: t.section_content,
    body: `<div data-ac-tabs>${contentTabs(filters.kind, data.counts, t, ui)}</div>${contentToolbar(filters, t)}<div data-ac-results>${contentTable(data, t, ui)}</div>`,
  });
  const results = container.querySelector('[data-ac-results]');
  const tabs = container.querySelector('[data-ac-tabs]');

  const reload = async () => {
    results?.setAttribute('aria-busy', 'true');
    try {
      data = await request();
    } catch {
      data = null;
    }
    if (!alive()) return;
    results?.removeAttribute('aria-busy');
    if (results) results.innerHTML = data ? contentTable(data, t, ui) : notice(t.loadFailed, 'bad');
    if (tabs && data) tabs.innerHTML = contentTabs(filters.kind, data.counts, t, ui);
  };

  const open = async (key, intent = '') => {
    const [kind, ...rest] = key.split(':');
    const id = rest.join(':');
    const drawer = openDrawer({ title: t[`type_${kind}`] || kind, body: `<p class="ac-empty">${esc(t.loading)}</p>`, label: t.close });
    let detail = null;
    const paint = (currentIntent) => {
      if (drawer.element.isConnected && detail) drawer.set(contentDetailView(detail, t, ui, currentIntent));
      drawer.element.querySelector('[data-ac-confirm] [data-ac-do]')?.focus();
    };
    const load = async () => {
      detail = await api.contentDetail(kind, id);
    };
    try {
      await load();
      paint(intent);
    } catch (error) {
      if (drawer.element.isConnected) drawer.set(notice(error?.message || t.loadFailed, 'bad'));
      return;
    }
    drawer.element.addEventListener('click', async (event) => {
      const opener = event.target.closest('[data-ac-intent-open]');
      if (opener) {
        paint(opener.dataset.acIntentOpen);
        return;
      }
      const action = event.target.closest('[data-ac-do]');
      if (!action) return;
      if (action.dataset.acDo === 'cancel') {
        paint('');
        return;
      }
      const result = drawer.element.querySelector('[data-ac-result]');
      action.disabled = true;
      try {
        if (action.dataset.acDo === 'archive') {
          await api.archiveBook(id);
          env.notify?.(t.archived);
        } else if (action.dataset.acDo === 'reprocess') {
          const outcome = await api.reprocessMedia(id);
          env.notify?.(fill(t.reprocessDone, { status: t[`status_${outcome.item?.status}`] || outcome.item?.status || '' }));
        }
        await load();
        paint('');
        reload();
      } catch (error) {
        if (result) result.textContent = error?.message || t.loadFailed;
        action.disabled = false;
      }
    });
    drawer.element.addEventListener('submit', async (event) => {
      const form = event.target.closest('[data-ac-publish]');
      if (!form) return;
      event.preventDefault();
      const result = form.querySelector('[data-ac-result]');
      if (!form.elements.attested.checked) {
        if (result) result.textContent = t.validationAttest;
        return;
      }
      const button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;
      try {
        await api.publishCollection(id, {
          rights_status: form.elements.rights_status.value,
          completeness: form.elements.completeness.value,
          attested: true,
        });
        env.notify?.(t.publishedDone);
        await load();
        paint('');
        reload();
      } catch (error) {
        if (result) result.textContent = error?.message || t.loadFailed;
        if (button) button.disabled = false;
      }
    });
  };

  container.addEventListener('click', (event) => {
    const kindButton = event.target.closest('[data-ac-kind]');
    if (kindButton) {
      filters.kind = kindButton.dataset.acKind;
      offset = 0;
      reload();
      return;
    }
    const page = event.target.closest('[data-page]');
    if (page) {
      offset = Math.max(0, offset + (page.dataset.page === 'next' ? PAGE_SIZE : -PAGE_SIZE));
      reload();
      return;
    }
    const opener = event.target.closest('[data-ac-open]');
    if (opener) open(opener.dataset.acOpen, opener.dataset.acIntent || '');
  });
  const form = container.querySelector('[data-ac-filters]');
  form?.addEventListener('submit', (event) => event.preventDefault());
  form?.addEventListener('input', (event) => {
    if (event.target.name !== 'q') return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      filters.q = event.target.value.trim();
      offset = 0;
      reload();
    }, 300);
  });
  form?.addEventListener('change', (event) => {
    if (!['language', 'status', 'sort'].includes(event.target.name)) return;
    filters[event.target.name] = event.target.value;
    offset = 0;
    reload();
  });
  return () => clearTimeout(timer);
}

