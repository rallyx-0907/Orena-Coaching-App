/* Imports: one place to bring content in - books, media, vocabulary - and one
   history of what came in and what failed.

   Each flow is the existing importer, used as it was built: EPUBs through the
   reading library importer, links and files through the media source
   importer, vocabulary sources through the admission-checked vocabulary
   importer. The console sends books and media one item per request, so every
   item shows its own progress and one failure never holds up the rest; a
   vocabulary batch is one request because publication is decided for the
   collection as a whole. Book and media attempts are recorded server-side, so
   history lists failures too, with the stage where each one stopped. */
import { adminApi } from './api.js';
import { jobRows } from './reading.js';
import { emptyBlock, errorBlock, failureDetail, gapNote, loadingBlock } from './states.js';
import { bytes, chip, dateTime, duration, esc, fill, languageName, notice, num, pager, panel, relative, select, table } from './format.js';
import { safeExternal } from '../ui/html.js';

export const HISTORY_PAGE = 20;
export const VOCABULARY_FIELDS = [
  'term', 'short_meaning', 'reading', 'pronunciation', 'part_of_speech', 'example', 'level',
  'detailed_definition', 'usage', 'framework', 'topic', 'meaning_language', 'target_language', 'orthography', 'sense_key',
];
const PRIMARY_FIELDS = 7;
/* The level scales the media library accepts per learning language
   (media_library_store.validate_entry); any other value is refused there. */
export const MEDIA_LEVELS = {
  en: ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'],
  zh: ['HSK1', 'HSK2', 'HSK3', 'HSK4', 'HSK5', 'HSK6', 'HSK7-9'],
};

/* Run `worker` over `items` one at a time. Each item moves queued ->
   processing -> its outcome, and a thrown error is that item's failure, never
   the queue's. */
export async function runQueue(items, worker, onUpdate = () => {}) {
  for (const item of items) item.state = 'queued';
  onUpdate(items);
  for (const item of items) {
    item.state = 'processing';
    onUpdate(items);
    try {
      Object.assign(item, await worker(item));
    } catch (error) {
      Object.assign(item, { state: 'failed', code: error?.category || 'unknown', message: error?.message || '' });
    }
    onUpdate(items);
  }
  return items;
}

export function bookOutcome(row) {
  if (row?.status === 'ok') return { state: 'published', title: row.title, chapters: row.chapter_count, contentId: row.book_id };
  if (row?.status === 'duplicate') return { state: 'duplicate', title: row.title, contentId: row.book_id };
  return { state: 'failed', code: row?.category || 'unknown', stage: row?.stage || 'parse' };
}

export function mediaOutcome(row) {
  // The server keys an uploaded file by its content: the same bytes again are
  // the item already in the library, not a failure and not a second copy.
  if (row?.status === 'duplicate') return { state: 'duplicate', contentId: row.media_id };
  if (row?.status === 'ok') {
    return { state: 'published', contentId: row.media_id, has_transcript: row.has_transcript ?? null, segment_count: row.segment_count ?? null };
  }
  return { state: 'failed', code: 'source', stage: 'source', message: row?.detail || '' };
}

/* A known failure has words in both languages; otherwise the server's own
   detail is shown, marked as quoted where the interface is not English. */
export function failureText(item, t) {
  const reason = t[`error_${item.code}`] || (item.message ? fill(t.serverReason, { detail: item.message }) : t.error_unknown);
  const stage = item.stage ? fill(t.failedAt, { stage: t[`stage_${item.stage}`] || item.stage }) : '';
  return [stage, reason].filter(Boolean).join(t.pairSep);
}

export function defaultCollectionTitle(filename) {
  const stem = String(filename || '').replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
  return stem ? stem[0].toLocaleUpperCase() + stem.slice(1) : '';
}

export function validateVocabulary({ files = [], previews = [], mappings = {}, metadata = {} }, t) {
  const errors = [];
  if (!files.length) errors.push(t.validationFiles);
  if (!String(metadata.title || '').trim()) errors.push(t.validationTitle);
  for (const preview of previews) {
    if (preview.error) continue;
    if (!mappings[preview.filename]?.term) errors.push(fill(t.validationTerm, { file: preview.filename }));
  }
  if (metadata.publish && !metadata.attested) errors.push(t.validationAttest);
  return errors;
}

function queueTable(items, t, ui, describe) {
  return table({
    head: [t.colFile, { label: t.colSize, numeric: true }, t.colState, t.colResult],
    rows: items.map((item) => [
      esc(item.name),
      esc(item.size !== undefined ? bytes(item.size, ui) : '—'),
      chip(item.state, t),
      item.state === 'failed' ? `<span class="ac-error">${esc(failureText(item, t))}</span>` : describe(item),
    ]),
    empty: '',
    className: 'ac-table--queue',
  });
}

function languageSelect(name, value, t) {
  return select({ name, label: t.learningLanguage, value, options: [['en', languageName('en', t)], ['zh', languageName('zh', t)]] });
}

/* The native file input forgets its selection whenever the flow repaints, and
   would then say "no file chosen" beside a list of chosen files. So the input
   is kept for what it does - opening the picker, taking focus - and the
   control states the count from the flow's own state. */
function fileControl({ label, accept, count, disabled }, t, ui) {
  return `<label class="ac-field ac-field--file"><span>${esc(label)}</span><span class="ac-file"><input type="file" name="files" accept="${esc(accept)}" multiple${disabled ? ' disabled' : ''}><span class="ac-button">${esc(t.chooseFiles)}</span><span class="ac-file__chosen">${esc(count ? fill(t.filesChosen, { count: num(count, ui) }) : t.noFilesChosen)}</span></span></label>`;
}

export function chooserView(flow, t) {
  return `<div class="ac-chooser" role="group" aria-label="${esc(t.newImport)}">${['books', 'media', 'vocabulary']
    .map((kind) => `<button type="button" class="ac-choice" data-ac-flow="${kind}" aria-pressed="${flow === kind}"><strong>${esc(t[`choose_${kind}`])}</strong><span>${esc(t[`choose_${kind}Note`])}</span></button>`)
    .join('')}</div>`;
}

export function booksView(state, t, ui) {
  const items = state.items;
  const done = items.filter((item) => ['published', 'duplicate', 'failed'].includes(item.state));
  const ok = items.filter((item) => item.state === 'published').length;
  return `<form class="ac-flow" data-ac-books><div class="ac-flow__fields">${fileControl({ label: t.choose_booksNote, accept: '.epub,application/epub+zip', count: items.length, disabled: state.running }, t, ui)}${languageSelect('language', state.language, t)}</div>${items.length ? queueTable(items, t, ui, (item) => (item.state === 'published'
    ? esc(fill(t.bookResult_ok, { title: item.title, chapters: num(item.chapters, ui) }))
    : item.state === 'duplicate' ? esc(fill(t.bookResult_duplicate, { title: item.title })) : '')) : ''}<div class="ac-flow__actions"><button type="submit" class="ac-button ac-button--primary"${!items.length || state.running || done.length === items.length ? ' disabled' : ''}>${esc(state.running ? t.importing : fill(t.importBooks, { count: num(items.filter((item) => item.state === 'to_import').length, ui) }))}</button>${done.length && done.length === items.length ? `<span role="status">${esc(fill(t.doneSummary, { ok: num(ok, ui), total: num(items.length, ui) }))}</span> <a class="ac-link" href="#/admin?id=content&amp;kind=book">${esc(t.viewInContent)}</a>` : ''}</div></form>`;
}

function mediaLevelOptions(language, value, t) {
  return [['', t.levelNone], ...(MEDIA_LEVELS[language] || []).map((level) => [level, level])].map(
    ([optionValue, label]) => `<option value="${esc(optionValue)}"${optionValue === value ? ' selected' : ''}>${esc(label)}</option>`,
  ).join('');
}

/* What is known about a source's transcript. A provider preview can know a
   transcript exists without having counted it, so a preview never shows it
   as zero; after the import the server answers with what was stored. */
function transcriptCell(item, t, ui) {
  if (item.state === 'failed') return '—';
  if (item.segment_count > 0) return esc(fill(t.transcriptLines, { count: num(item.segment_count, ui) }));
  if (item.state === 'published') return item.has_transcript === false ? chip('transcript_missing', t) : '—';
  if (item.file) return '—';
  if (item.has_transcript) return `<span class="ac-muted">${esc(t.transcriptAtImport)}</span>`;
  return chip('transcript_missing', t);
}

export function mediaView(state, t, ui) {
  const rows = state.items.map((item, index) => {
    const thumbnail = item.thumbnail_url ? (item.thumbnail_url.startsWith('/api/') ? item.thumbnail_url : safeExternal(item.thumbnail_url)) : '';
    const editable = item.state === 'ready' && !state.running;
    const failed = item.state === 'failed';
    const meta = [item.source_label, item.duration_ms ? duration(item.duration_ms) : ''].filter(Boolean).join(t.sep);
    const heading = editable
      ? `<label class="ac-field ac-field--inline"><span class="sr-only">${esc(t.titleField)}</span><input type="text" data-ac-media-field="title" data-index="${index}" value="${esc(item.title || '')}" maxlength="240"></label>`
      : `<strong>${esc(item.title || item.url)}</strong>`;
    const source = item.file
      ? `<div class="ac-cell-stack"><strong>${esc(item.name)}</strong><span class="ac-muted">${esc(t.fileUpload)}, ${esc(bytes(item.size, ui))}</span></div>`
      : `<div class="ac-title-cell"><span class="ac-thumb" data-kind="media">${thumbnail ? `<img src="${esc(thumbnail)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ''}</span><div class="ac-cell-stack">${heading}${meta ? `<span class="ac-muted">${esc(meta)}</span>` : ''}${editable || item.title ? `<span class="ac-url">${esc(item.url)}</span>` : ''}</div></div>`;
    const transcript = transcriptCell(item, t, ui);
    const level = item.file || failed ? '—' : editable
      ? `<label class="ac-field ac-field--inline"><span class="sr-only">${esc(t.level)}</span><select data-ac-media-field="level" data-index="${index}">${mediaLevelOptions(state.language, item.level || '', t)}</select></label>`
      : esc(item.level || '—');
    const advanced = state.advanced && !item.file && !failed
      ? editable
        ? `<div class="ac-inline-fields"><label class="ac-field ac-field--inline"><span>${esc(t.topic)}</span><input type="text" data-ac-media-field="topic" data-index="${index}" value="${esc(item.topic || '')}" maxlength="64"></label><label class="ac-field ac-field--inline"><span>${esc(t.tags)}</span><input type="text" data-ac-media-field="tags" data-index="${index}" value="${esc((item.tags || []).join(', '))}"></label></div>`
        : `<span class="ac-muted">${esc([item.topic, (item.tags || []).join(t.enumSep)].filter(Boolean).join(' / ') || '—')}</span>`
      : '';
    const stateCell = item.state === 'failed'
      ? `${chip('failed', t)}<span class="ac-error">${esc(failureText(item, t))}</span>`
      : item.state === 'duplicate'
        ? `${chip('duplicate', t)}<span class="ac-muted">${esc(t.mediaDuplicate)}</span>`
        : chip(item.state, t);
    const remove = editable || (!state.running && (item.state === 'to_import' || failed))
      ? `<button type="button" class="ac-button ac-button--quiet" data-ac-remove="${index}">${esc(t.removeItem)}</button>`
      : '';
    return [source, transcript, advanced ? `<div class="ac-cell-stack">${level}${advanced}</div>` : level, `<div class="ac-cell-stack">${stateCell}</div>`, remove];
  });
  const importable = state.items.filter((item) => item.state === 'ready' || (item.file && item.state === 'to_import')).length;
  const done = state.items.length && state.items.every((item) => ['published', 'duplicate', 'failed'].includes(item.state));
  const ok = state.items.filter((item) => item.state === 'published').length;
  return `<form class="ac-flow" data-ac-media><div class="ac-flow__fields"><label class="ac-field ac-field--wide"><span>${esc(t.mediaUrls)}</span><textarea name="urls" rows="3"${state.running ? ' disabled' : ''}>${esc(state.urls)}</textarea></label>${fileControl({ label: t.mediaFiles, accept: 'video/*,audio/*', count: state.items.filter((item) => item.file).length, disabled: state.running }, t, ui)}${languageSelect('language', state.language, t)}</div><div class="ac-flow__actions"><button type="button" class="ac-button" data-ac-media-check${state.running || state.checking ? ' disabled' : ''}>${esc(state.checking ? t.checking : t.checkSources)}</button><label class="ac-check"><input type="checkbox" name="advanced"${state.advanced ? ' checked' : ''}><span>${esc(t.advancedFields)}</span></label></div>${rows.length ? table({
    head: [t.colSource, t.transcript, t.level, t.colState, { label: t.colActions, hidden: true }],
    rows,
    className: 'ac-table--queue',
  }) : `<p class="ac-empty">${esc(t.mediaNoItems)}</p>`}<div class="ac-flow__actions"><button type="submit" class="ac-button ac-button--primary"${!importable || state.running ? ' disabled' : ''}>${esc(state.running ? t.importing : fill(t.importMedia, { count: num(importable, ui) }))}</button>${done ? `<span role="status">${esc(fill(t.doneSummary, { ok: num(ok, ui), total: num(state.items.length, ui) }))}</span> <a class="ac-link" href="#/admin?id=content&amp;kind=media">${esc(t.viewInContent)}</a>` : ''}</div></form>`;
}

function mappingSelect(preview, field, value, index, t) {
  const headerOptions = (preview.headers || []).map((header) => `<option value="${esc(header)}"${header === value ? ' selected' : ''}>${esc(header)}</option>`).join('');
  return `<label class="ac-field"><span>${esc(t[`field_${field}`] || field)}</span><select data-ac-map data-file="${index}" data-field="${esc(field)}"><option value="">${esc(t.notMapped)}</option>${headerOptions}</select></label>`;
}

export function vocabularyPreviewView(preview, index, mapping, t, ui) {
  if (preview.error) return `<article class="ac-source" data-tone="bad"><h3>${esc(preview.filename)}</h3>${notice(preview.error, 'bad')}</article>`;
  const primary = VOCABULARY_FIELDS.slice(0, PRIMARY_FIELDS).map((field) => mappingSelect(preview, field, mapping?.[field] || '', index, t)).join('');
  const more = VOCABULARY_FIELDS.slice(PRIMARY_FIELDS).map((field) => mappingSelect(preview, field, mapping?.[field] || '', index, t)).join('');
  const headers = preview.headers || [];
  const sample = table({
    head: headers,
    rows: (preview.sample || []).slice(0, 3).map((row) => headers.map((header) => esc(String(row?.[header] ?? '')))),
    className: 'ac-table--compact',
  });
  return `<article class="ac-source"><header class="ac-source__head"><h3>${esc(preview.filename)}</h3><span class="ac-muted">${esc(fill(t.rows, { count: num(preview.row_count, ui) }))}, ${esc(String(preview.format || '').toUpperCase())}</span>${mapping?.term ? chip('ready', t) : chip('failed', t, { label: fill(t.validationTerm, { file: preview.filename }) })}</header><div class="ac-mapping">${primary}</div><details><summary>${esc(t.moreFields)}</summary><div class="ac-mapping">${more}</div></details>${(preview.warnings || []).length ? `<ul class="ac-warnings">${preview.warnings.map((warning) => `<li>${esc(warning)}</li>`).join('')}</ul>` : ''}<details><summary>${esc(t.sampleRows)}</summary>${sample}</details></article>`;
}

export function vocabularyView(state, t, ui) {
  const metadata = state.metadata;
  const previews = state.previews.map((preview, index) => vocabularyPreviewView(preview, index, state.mappings[preview.filename], t, ui)).join('');
  const fields = `<div class="ac-flow__fields"><label class="ac-field ac-field--wide"><span>${esc(t.collectionTitle)}</span><input type="text" data-ac-meta="title" value="${esc(metadata.title)}" maxlength="255" required></label>${select({
    name: 'meta-language', label: t.learningLanguage, value: metadata.language, attributes: ' data-ac-meta="language"',
    options: [['en', languageName('en', t)], ['zh', languageName('zh', t)]],
  })}<label class="ac-field"><span>${esc(t.meaningLanguage)}</span><input type="text" data-ac-meta="meaning_language" value="${esc(metadata.meaning_language)}" maxlength="20"></label><label class="ac-field"><span>${esc(t.framework)}</span><input type="text" data-ac-meta="framework" value="${esc(metadata.framework)}" maxlength="80"></label><label class="ac-field"><span>${esc(t.collectionLevel)}</span><input type="text" data-ac-meta="level" value="${esc(metadata.level)}" maxlength="80"></label><label class="ac-field"><span>${esc(t.collectionTopic)}</span><input type="text" data-ac-meta="topic" value="${esc(metadata.topic)}" maxlength="160"></label></div>`;
  const advanced = `<details class="ac-advanced"${metadata.publish ? ' open' : ''}><summary>${esc(t.advanced)}</summary><div class="ac-flow__fields"><label class="ac-field"><span>${esc(t.collectionId)}</span><input type="text" data-ac-meta="collection_id" value="${esc(metadata.collection_id)}" placeholder="${esc(t.collectionIdHint)}" maxlength="160"></label>${select({
    name: 'meta-rights', label: t.rightsStatus, value: metadata.rights_status, attributes: ' data-ac-meta="rights_status"',
    options: [['', t.rights_], ['public_domain', t.rights_public_domain], ['licensed', t.rights_licensed], ['creator_authorized', t.rights_creator_authorized], ['internal_curated', t.rights_internal_curated]],
  })}${select({
    name: 'meta-completeness', label: t.completeness, value: metadata.completeness, attributes: ' data-ac-meta="completeness"',
    options: ['complete', 'partial', 'unknown'].map((value) => [value, t[`completeness_${value}`]]),
  })}</div><label class="ac-check"><input type="checkbox" data-ac-meta="publish"${metadata.publish ? ' checked' : ''}><span>${esc(t.publishAfterImport)}</span></label>${metadata.publish ? `<label class="ac-check"><input type="checkbox" data-ac-meta="attested"${metadata.attested ? ' checked' : ''}><span>${esc(t.attest)}</span></label>` : ''}</details>`;
  const errors = state.errors.length ? `<ul class="ac-errors" role="alert">${state.errors.map((error) => `<li>${esc(error)}</li>`).join('')}</ul>` : '';
  const results = state.results ? `<section class="ac-results"><h3>${esc(t.colResult)}</h3>${table({
    head: [t.colFile, t.colState, t.colResult],
    rows: (state.results.items || []).map((row) => [
      esc(row.filename || ''),
      chip(row.status === 'imported' ? 'imported' : row.status === 'skipped' ? 'skipped' : 'failed', t),
      row.status === 'failed'
        ? `<span class="ac-error">${esc(row.failure_reason ? fill(t.serverReason, { detail: row.failure_reason }) : t.error_unknown)}</span>`
        : esc(fill(t.vocabResult, { imported: num(row.imported, ui), duplicates: num(row.duplicates, ui), skipped: num(row.skipped, ui) })),
    ]),
  })}<p>${esc(fill(t.collectionStatus, { status: t[`collection_${state.results.collection?.catalog_status}`] || state.results.collection?.catalog_status || '' }))} <a class="ac-link" href="#/admin?id=content&amp;kind=vocabulary">${esc(t.viewInContent)}</a></p></section>` : '';
  return `<form class="ac-flow" data-ac-vocabulary><div class="ac-flow__fields">${fileControl({ label: t.choose_vocabularyNote, accept: '.csv,.tsv,.json,.txt,.xlsx', count: state.files.length, disabled: state.running }, t, ui)}</div>${state.files.length ? `<p class="ac-muted">${esc(state.files.map((file) => file.name).join(', '))}</p>` : ''}<div class="ac-flow__actions"><button type="button" class="ac-button" data-ac-vocabulary-preview${!state.files.length || state.previewing || state.running ? ' disabled' : ''}>${esc(state.previewing ? t.previewing : t.vocabularyPreview)}</button></div>${previews}${state.previews.length ? `${fields}${advanced}${errors}<div class="ac-flow__actions"><button type="submit" class="ac-button ac-button--primary"${state.running || state.results ? ' disabled' : ''}>${esc(state.running ? t.importing : t.importVocabulary)}</button></div>` : ''}${results}</form>`;
}

export function historyResult(row, t, ui) {
  const result = row.result || {};
  if (row.kind === 'book') {
    if (row.status === 'duplicate') return esc(fill(t.bookResult_duplicate, { title: result.title || '' }));
    if (row.status === 'failed') return '';
    return esc(fill(t.bookResult_ok, { title: result.title || '', chapters: num(result.chapter_count, ui) }));
  }
  if (row.kind === 'media') {
    if (row.status === 'failed') return '';
    return esc([result.title, fill(t.resultTranscript, { value: t[`transcript_${result.transcript}`] || result.transcript || '—' })].filter(Boolean).join(t.sep));
  }
  if (row.status === 'failed') return esc(result.title || '');
  return esc([result.title, fill(t.vocabResult, { imported: num(result.imported, ui), duplicates: num(result.duplicates, ui), skipped: num(result.skipped, ui) })].filter(Boolean).join(t.pairSep));
}


/* The Reading engine's queue, in the area an operator already looks for an
   import. Its own feed and its own cursor: the catalogue history counts rows
   it owns, and merging two paginations into one table would mean a page that
   silently skips work. */
export function readingJobsView(page, filters, t, ui) {
  const items = (page?.items || []).filter((job) => filters.status !== 'failed' || job.status === 'failed');
  return panel({
    title: t.readingJobsTitle,
    note: t.importsReadingNote,
    body: `${table({
      head: [t.readingColJob, t.colStatus, t.readingColStage, t.readingColAttempt, t.colError, t.colDate,
             { label: t.colActions, hidden: true }],
      rows: jobRows(items, t, ui),
      empty: t.readingNoJobs,
      className: 'ac-table--history',
    })}${page?.next_cursor ? `<div class="ac-pager"><span class="ac-pager__buttons"><button type="button" class="ac-button" data-ac-jobs-more>${esc(t.next)}</button></span></div>` : ''}`,
  });
}

export function historyView(data, filters, t, ui) {
  if (!data?.available) return notice(t.historyUnavailable, 'neutral');
  const rows = (data.items || []).map((row) => [
    `<div class="ac-cell-stack"><span class="ac-url">${esc(row.source || '—')}</span>${row.origin === 'catalog' ? `<span class="ac-muted">${esc(t.beforeHistory)}</span>` : ''}</div>`,
    chip(row.status, t),
    esc(t[`type_${row.kind === 'book' ? 'book' : row.kind === 'media' ? 'media' : 'vocabulary'}`]),
    `<span title="${esc(dateTime(row.created_at, ui))}">${esc(row.created_at ? relative(row.created_at, ui) : '—')}</span>`,
    historyResult(row, t, ui),
    row.error ? `<span class="ac-error">${esc(failureText({ code: row.error.code, stage: row.error.stage, message: row.error.message }, t))}</span>` : '',
  ]);
  const summary = data.summary ? `<p class="ac-muted">${esc(fill(t.historySummary, { total: num(data.summary.total, ui), failed: num(data.summary.failed, ui) }))}</p>` : '';
  const errorsOnly = filters.status === 'failed';
  return `<form class="ac-toolbar" data-ac-history-filters>${select({
    name: 'kind', label: t.colTypeContent, value: filters.kind,
    options: [['', t.all], ['book', t.kind_book], ['media', t.kind_media], ['vocabulary', t.kind_vocabulary]],
  })}${select({
    name: 'status', label: t.colStatus, value: filters.status,
    options: [['', t.all], ['failed', t.status_failed], ['published', t.status_published], ['ready', t.status_ready], ['duplicate', t.status_duplicate], ['skipped', t.status_skipped], ['archived', t.status_archived]],
  })}</form>${summary}${table({
    head: [t.colSource, t.colStatus, t.colTypeContent, t.colCreated, t.colResult, t.colError],
    rows,
    empty: t.historyEmpty,
    className: 'ac-table--history',
  })}${pager({ offset: data.offset || 0, limit: data.limit || HISTORY_PAGE, total: data.total || 0 }, t, ui)}${
    errorsOnly ? '' : gapNote(t, t.importsFeedGap)
  }`;
}

export async function renderImports(container, env) {
  const { t, ui, alive, ctx } = env;
  const api = env.api || adminApi;
  const params = env.params || {};
  const learning = ctx?.language === 'zh' ? 'zh' : 'en';
  const state = {
    flow: ['books', 'media', 'vocabulary'].includes(params.flow) ? params.flow : '',
    books: { items: [], language: learning, running: false },
    media: { urls: '', items: [], language: learning, running: false, checking: false, advanced: false },
    vocabulary: {
      files: [], previews: [], mappings: {}, running: false, previewing: false, errors: [], results: null,
      metadata: {
        title: '', language: learning, meaning_language: ctx?.support || '', framework: '', level: '', topic: '',
        collection_id: '', rights_status: '', completeness: 'unknown', publish: false, attested: false,
      },
    },
    history: { filters: { kind: '', status: ['failed'].includes(params.status) ? params.status : '' }, offset: 0, data: null },
    jobs: { page: null, cursor: null },
  };

  container.innerHTML = `<div class="ac-stack">${panel({ title: t.newImport, body: '<div data-ac-chooser></div><div data-ac-flow-host></div>' })}${panel({ title: t.historyTitle, body: '<div class="ac-stack ac-stack--tight" data-ac-history></div>' })}</div>`;
  const chooser = container.querySelector('[data-ac-chooser]');
  const flowHost = container.querySelector('[data-ac-flow-host]');
  const historyHost = container.querySelector('[data-ac-history]');

  const paintFlow = () => {
    if (!alive()) return;
    if (chooser) chooser.innerHTML = chooserView(state.flow, t);
    if (!flowHost) return;
    flowHost.innerHTML = state.flow === 'books'
      ? booksView(state.books, t, ui)
      : state.flow === 'media'
        ? mediaView(state.media, t, ui)
        : state.flow === 'vocabulary'
          ? vocabularyView(state.vocabulary, t, ui)
          : '';
  };
  /* Two feeds, one filter: the catalogue history the server paginates, and the
     Reading engine's own job queue. A runtime without the engine answers 503,
     which is a missing table rather than a broken page. */
  const loadHistory = async () => {
    if (historyHost && !state.history.data) historyHost.innerHTML = loadingBlock(t, { rows: 5 });
    const [history, jobs] = await Promise.allSettled([
      api.history({ ...state.history.filters, limit: HISTORY_PAGE, offset: state.history.offset }),
      api.readingJobs?.({ limit: 10, cursor: state.jobs.cursor || '' }) ?? Promise.resolve(null),
    ]);
    state.history.data = history.status === 'fulfilled' ? history.value : null;
    state.jobs.page = jobs.status === 'fulfilled' ? jobs.value : null;
    if (!alive() || !historyHost) return;
    if (!state.history.data) {
      const failure = failureDetail(history.reason, t);
      historyHost.innerHTML = errorBlock(t, { detail: failure.detail, reference: failure.reference });
      historyHost.querySelector('[data-ac-retry]')?.addEventListener('click', loadHistory, { once: true });
      return;
    }
    historyHost.innerHTML = `${historyView(state.history.data, state.history.filters, t, ui)}${
      state.jobs.page ? readingJobsView(state.jobs.page, state.history.filters, t, ui) : ''
    }`;
  };

  paintFlow();
  await loadHistory();

  const importBooks = async () => {
    const books = state.books;
    const pending = books.items.filter((item) => item.state === 'to_import');
    books.running = true;
    await runQueue(pending, async (item) => {
      const response = await api.importBook(item.file, books.language);
      return bookOutcome((response.results || [])[0]);
    }, paintFlow);
    books.running = false;
    paintFlow();
    loadHistory();
  };

  const checkMedia = async () => {
    const media = state.media;
    const urls = media.urls.split(/[\n,]/).map((line) => line.trim()).filter(Boolean);
    const files = media.items.filter((item) => item.file);
    if (!urls.length) {
      media.items = files;
      paintFlow();
      return;
    }
    media.checking = true;
    paintFlow();
    try {
      const response = await api.mediaPreview(urls, media.language);
      media.items = [
        ...(response.items || []).map((row) => (row.status === 'ok'
          ? { ...row, name: row.url, state: 'ready', tags: [] }
          : { url: row.url, name: row.url, state: 'failed', code: 'source', stage: 'source', message: row.detail })),
        ...files,
      ];
    } catch (error) {
      media.items = [...urls.map((url) => ({ url, name: url, state: 'failed', code: error?.category || 'unknown', message: error?.message || '' })), ...files];
    }
    media.checking = false;
    paintFlow();
  };

  const importMedia = async () => {
    const media = state.media;
    const pending = media.items.filter((item) => item.state === 'ready' || (item.file && item.state === 'to_import'));
    media.running = true;
    await runQueue(pending, async (item) => {
      if (item.file) {
        const response = await api.importMediaFile(item.file, media.language);
        return mediaOutcome((response.items || [])[0]);
      }
      const response = await api.importMediaUrl({
        url: item.url,
        title: item.title || null,
        level: item.level || null,
        topic: item.topic || null,
        tags: item.tags || [],
      }, media.language);
      return mediaOutcome((response.items || [])[0]);
    }, paintFlow);
    media.running = false;
    paintFlow();
    loadHistory();
  };

  const previewVocabulary = async () => {
    const vocabulary = state.vocabulary;
    vocabulary.previewing = true;
    vocabulary.errors = [];
    vocabulary.results = null;
    paintFlow();
    try {
      const response = await api.vocabularyPreview(vocabulary.files);
      vocabulary.previews = response.items || [];
      vocabulary.mappings = {};
      for (const preview of vocabulary.previews) {
        if (!preview.error) vocabulary.mappings[preview.filename] = { ...(preview.detected_mapping || {}) };
      }
      if (!vocabulary.metadata.title) vocabulary.metadata.title = defaultCollectionTitle(vocabulary.files[0]?.name);
    } catch (error) {
      vocabulary.errors = [error?.message || t.loadFailed];
    }
    vocabulary.previewing = false;
    paintFlow();
  };

  const importVocabulary = async () => {
    const vocabulary = state.vocabulary;
    vocabulary.errors = validateVocabulary(vocabulary, t);
    if (vocabulary.errors.length) {
      paintFlow();
      return;
    }
    vocabulary.running = true;
    paintFlow();
    const meta = vocabulary.metadata;
    try {
      vocabulary.results = await api.vocabularyImport(vocabulary.files, {
        title: meta.title.trim(),
        language_code: meta.language,
        meaning_language: meta.meaning_language,
        framework: meta.framework,
        level: meta.level,
        topic: meta.topic,
        collection_id: meta.collection_id,
        rights_status: meta.rights_status,
        completeness: meta.completeness,
        publish: meta.publish,
        publication_attested: meta.publish && meta.attested,
      }, vocabulary.mappings);
    } catch (error) {
      vocabulary.errors = [error?.message || t.loadFailed];
    }
    vocabulary.running = false;
    paintFlow();
    loadHistory();
  };

  const onClick = (event) => {
    const jobsMore = event.target.closest?.('[data-ac-jobs-more]');
    if (jobsMore) {
      state.jobs.cursor = state.jobs.page?.next_cursor || null;
      loadHistory();
      return;
    }
    const retryJob = event.target.closest?.('[data-ac-retry]')?.dataset?.acRetry
      ? event.target.closest('[data-ac-retry]')
      : null;
    if (retryJob) {
      (api.readingRetryJob?.(retryJob.dataset.acRetry) ?? Promise.resolve()).then(loadHistory).catch(() => loadHistory());
      return;
    }
    const choice = event.target.closest('button[data-ac-flow]');
    if (choice) {
      state.flow = choice.dataset.acFlow;
      paintFlow();
      flowHost?.querySelector('input, textarea, select')?.focus();
      return;
    }
    if (event.target.closest('[data-ac-media-check]')) {
      checkMedia();
      return;
    }
    const remove = event.target.closest('[data-ac-remove]');
    if (remove) {
      state.media.items.splice(Number(remove.dataset.acRemove), 1);
      paintFlow();
      return;
    }
    if (event.target.closest('[data-ac-vocabulary-preview]')) {
      previewVocabulary();
      return;
    }
    const page = event.target.closest('[data-page]');
    if (page && historyHost?.contains(page)) {
      state.history.offset = Math.max(0, state.history.offset + (page.dataset.page === 'next' ? HISTORY_PAGE : -HISTORY_PAGE));
      loadHistory();
    }
  };

  const onChange = (event) => {
    const target = event.target;
    if (target.closest('[data-ac-books]')) {
      if (target.name === 'files') {
        state.books.items = [...(target.files || [])].map((file) => ({ file, name: file.name, size: file.size, state: 'to_import' }));
        paintFlow();
      } else if (target.name === 'language') {
        state.books.language = target.value;
      }
      return;
    }
    if (target.closest('[data-ac-media]')) {
      if (target.name === 'files') {
        const kept = state.media.items.filter((item) => !item.file);
        state.media.items = [...kept, ...[...(target.files || [])].map((file) => ({ file, name: file.name, size: file.size, state: 'to_import' }))];
        paintFlow();
      } else if (target.name === 'language') {
        state.media.language = target.value;
        state.media.items = state.media.items.map((item) => ({ ...item, level: '' }));
        paintFlow();
      } else if (target.name === 'advanced') {
        state.media.advanced = target.checked;
        paintFlow();
      } else if (target.dataset.acMediaField) {
        const item = state.media.items[Number(target.dataset.index)];
        if (item) item[target.dataset.acMediaField] = target.dataset.acMediaField === 'tags'
          ? target.value.split(',').map((tag) => tag.trim()).filter(Boolean)
          : target.value;
      }
      return;
    }
    if (target.closest('[data-ac-vocabulary]')) {
      const vocabulary = state.vocabulary;
      if (target.name === 'files') {
        vocabulary.files = [...(target.files || [])];
        vocabulary.previews = [];
        vocabulary.mappings = {};
        vocabulary.results = null;
        vocabulary.errors = [];
        paintFlow();
      } else if (target.dataset.acMap !== undefined) {
        const preview = vocabulary.previews[Number(target.dataset.file)];
        if (preview) {
          vocabulary.mappings[preview.filename] ||= {};
          vocabulary.mappings[preview.filename][target.dataset.field] = target.value || null;
          paintFlow();
        }
      } else if (target.dataset.acMeta) {
        const key = target.dataset.acMeta;
        vocabulary.metadata[key] = target.type === 'checkbox' ? target.checked : target.value;
        if (key === 'publish') paintFlow();
      }
      return;
    }
    if (target.closest('[data-ac-history-filters]')) {
      state.history.filters[target.name] = target.value;
      state.history.offset = 0;
      // The filter applies to both feeds, so the job page restarts with it.
      state.jobs.cursor = null;
      loadHistory();
    }
  };

  const onInput = (event) => {
    const target = event.target;
    if (target.closest('[data-ac-media]') && target.name === 'urls') state.media.urls = target.value;
    if (target.closest('[data-ac-media]') && target.dataset.acMediaField && target.tagName === 'INPUT') {
      const item = state.media.items[Number(target.dataset.index)];
      if (item) item[target.dataset.acMediaField] = target.dataset.acMediaField === 'tags'
        ? target.value.split(',').map((tag) => tag.trim()).filter(Boolean)
        : target.value;
    }
    if (target.closest('[data-ac-vocabulary]') && target.dataset.acMeta && target.type !== 'checkbox') {
      state.vocabulary.metadata[target.dataset.acMeta] = target.value;
    }
  };

  const onSubmit = (event) => {
    event.preventDefault();
    if (event.target.closest('[data-ac-books]')) importBooks();
    else if (event.target.closest('[data-ac-media]')) importMedia();
    else if (event.target.closest('[data-ac-vocabulary]')) importVocabulary();
  };

  container.addEventListener('click', onClick);
  container.addEventListener('change', onChange);
  container.addEventListener('input', onInput);
  container.addEventListener('submit', onSubmit);
  return () => {
    container.removeEventListener('click', onClick);
    container.removeEventListener('change', onChange);
    container.removeEventListener('input', onInput);
    container.removeEventListener('submit', onSubmit);
  };
}
