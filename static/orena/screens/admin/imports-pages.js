/* Imports, drawn as the pinned design draws it (Orena-Admin.dc.html A28 hub, Import books, Import
   media, Import vocabulary, Register source, Reading jobs, A29 job detail, A30 history). Pure builders
   over the data the shared rules loaded (capabilities/admin-imports.js); the wiring is imports.js.

   Left out rather than invented (UI_BACKEND_GAPS "Admin: Imports"): one unified feed across domains
   (the design marks it Future: each domain keeps its own history), a job's title and source (the
   job list carries neither), the design's sample-file shortcuts. */
import { html, raw } from '../../kit/html.js';
import { loadingMarkup, processingProgressMarkup } from '../../kit/states.js';
import { icon } from '../../kit/icons.js';
import { bytes, dateTime, latency, num, relative } from '../../capabilities/admin-format.js';
import { HISTORY_PAGE, MEDIA_LEVELS, PRIMARY_FIELDS, RIGHTS_STATUSES, VOCABULARY_FIELDS } from '../../capabilities/admin-imports.js';
import { STAGES } from '../../capabilities/admin-tray.js';
import { banner, block, button, chipRow, formBlock, futureCard, kv, metrics, pageHead, pill, rowList, stateBlock, stepsBlock, tabs } from './blocks.js';

const OUTCOME = {
  to_import: ['impQueued', 'mute'], queued: ['impQueued', 'mute'], processing: ['impRunning', 'info'], ready: ['impReady', 'info'],
  published: ['impDone', 'ok'], duplicate: ['impDuplicate', 'mute'], failed: ['impFailed', 'err'],
  review: ['ctStatusReview', 'info'], unpublished: ['ctStatusUnpublished', 'mute'],
  archived: ['impArchived', 'mute'],
};
const outcome = (t, state) => { const [label, tone] = OUTCOME[state] || OUTCOME.queued; return { label: t(label), tone }; };

/* A failure in words: the stage it stopped at and what happened, ours for a known category. */
export function failureText(t, item) {
  const reason = t.has(`impErr_${item.code}`) ? t(`impErr_${item.code}`) : item.message ? t('impServerReason', { detail: item.message }) : t('impErr_unknown');
  const stage = item.stage && t.has(`impStage_${item.stage}`) ? t('impFailedAt', { stage: t(`impStage_${item.stage}`) }) : '';
  return [stage, reason].filter(Boolean).join(' · ');
}

/* ---- A28 hub ------------------------------------------------------------------------------------ */

export function hubPage({ recent, failedJobs, t, href }) {
  const row = (title, meta, to, count, warn) => ({
    title, meta, go: to,
    pills: [...(count != null ? [{ label: t('impRecent', { n: count }), tone: 'mute' }] : []), ...(warn ? [{ label: warn, tone: 'err' }] : [])],
  });
  return {
    title: t('impTitle'),
    markup: html`<section class="a-page" data-screen-label="A28 Imports">
      ${pageHead({ title: t('impTitle'), sub: t('impSub') })}
      <div class="a-blocks">
        ${block({ title: t('impImport'), body: rowList([
          row(t('impBooks'), t('impBooksNote'), href('adminImportBooks'), recent.book),
          row(t('impMedia'), t('impMediaNote'), href('adminImportMedia'), recent.media),
          row(t('impVocab'), t('impVocabNote'), href('adminImportVocab'), recent.vocabulary),
          row(t('impReading'), t('impReadingNote'), href('adminAdd')),
          row(t('impSources'), t('impSourcesNote'), href('adminImportSource')),
        ]) })}
        ${block({ title: t('impFollow'), body: rowList([
          row(t('impJobs'), t('impJobsNote'), href('adminJobs'), null, failedJobs ? t('impFailedCount', { n: failedJobs }) : ''),
          row(t('impHistory'), t('impHistoryNote'), href('adminHistory'), recent.total),
        ]) })}
      </div>
    </section>`,
  };
}

function queueRows(t, ui, items, describe) {
  return rowList(items.map((item) => ({
    title: item.name || item.title || item.url,
    meta: [item.size !== undefined ? bytes(item.size, ui) : '', item.state === 'failed' ? failureText(t, item) : describe(item)].filter(Boolean).join(' · '),
    pills: [outcome(t, item.state)],
    actions: item.contentId && item.state !== 'failed' ? [{ label: t('impOpen'), size: 'xs', a: 'go', data: { to: item.openTo || '' } }] : [],
  })), { title: t('impNothingQueued'), text: t('impChooseAbove') });
}

/* ---- books -------------------------------------------------------------------------------------- */

export function booksPage({ books, t, ui, href }) {
  const pending = books.items.filter((item) => item.state === 'to_import').length;
  const done = books.items.length && books.items.every((item) => ['published', 'duplicate', 'failed'].includes(item.state));
  const items = books.items.map((item) => ({ ...item, openTo: item.contentId ? href('adminBook', { id: item.contentId }) : '' }));
  return {
    title: t('impTitle'),
    markup: html`<section class="a-page" data-screen-label="Import books">
      ${pageHead({ back: { href: href('adminImports'), label: t('impTitle') }, title: t('impBooksTitle'), sub: t('impBooksSub') })}
      <div class="a-blocks">
        ${formBlock({ span: true,
          fields: [
            { id: 'files', kind: 'file', label: t('impEpub'), span: true, fileLabel: books.items.length ? t('impFilesChosen', { n: books.items.length }) : t('impChooseEpub'), accept: t('impEpubAccept'), acceptAttr: '.epub,application/epub+zip', multiple: true },
            { id: 'language', kind: 'seg', label: t('impLanguage'), options: ['en', 'zh'].map((code) => ({ id: code, label: t(code === 'en' ? 'langEn' : 'langZh'), on: books.language === code })) },
          ],
          actions: [{ label: books.running ? t('impImporting') : t('impImportN', { n: pending }), kind: 'primary', a: 'books-import', disabled: !pending || books.running }] })}
        ${block({ span: true, title: t('impQueue'), sub: t('impQueueNote'), body: queueRows(t, ui, items, (item) => (item.state === 'published' ? t('impBookOk', { title: item.title || '', n: num(item.chapters, ui) }) : item.state === 'duplicate' ? t('impBookDuplicate', { title: item.title || '' }) : '')) })}
        ${done ? stateBlock({ span: true, kind: 'ok', heading: t('impDoneSummary', { ok: books.items.filter((item) => item.state === 'published').length, total: books.items.length }), text: '', actions: [{ label: t('impViewBooks'), kind: 'primary', size: 'sm', a: 'go', data: { to: href('adminBooks') } }] }) : ''}
      </div>
    </section>`,
  };
}

/* ---- media -------------------------------------------------------------------------------------- */

function mediaMeta(t, ui, item) {
  if (item.state === 'failed') return failureText(t, item);
  const parts = [item.source_label, item.duration_ms ? latency(item.duration_ms, ui) : ''];
  if (item.state === 'processing') parts.push(t('impMediaProcessing'), t.has(`impMediaStage_${item.stage}`) ? t(`impMediaStage_${item.stage}`) : '');
  if (['review', 'unpublished'].includes(item.state)) parts.push(item.has_transcript ? t('ctTranscriptReady') : t('impNoTranscript'));
  if (item.state === 'published') parts.push(item.has_transcript === false ? t('impNoTranscript') : item.segment_count > 0 ? t('impLines', { n: num(item.segment_count, ui) }) : '');
  else if (item.state === 'ready') parts.push(item.has_transcript ? t('impTranscriptAtImport') : t('impNoTranscript'));
  if (item.state === 'duplicate') parts.push(t('impMediaDuplicate'));
  return parts.filter(Boolean).join(' · ');
}

export function mediaPage({ media, t, ui, href }) {
  const tab = media.tab || 'url';
  const importable = media.items.filter((item) => item.state === 'ready' || (item.file && item.state === 'to_import')).length;
  const done = media.items.length && media.items.every((item) => ['published', 'duplicate', 'failed', 'review', 'unpublished', 'archived'].includes(item.state));
  const entries = media.items.map((item, index) => ({ item, index })).filter(({ item }) => (tab === 'file' ? item.file : !item.file));
  const fields = tab === 'url'
    ? [{ id: 'urls', kind: 'area', label: t('impMediaUrls'), span: true, rows: 3, value: media.urls || '', placeholder: 'https://…' }]
    : [{ id: 'mediaFiles', kind: 'file', label: t('impMediaFile'), span: true, fileLabel: entries.length ? t('impFilesChosen', { n: entries.length }) : t('impChooseMedia'), accept: t('impMediaAccept'), acceptAttr: 'video/*,audio/*', multiple: true }];
  fields.push({ id: 'language', kind: 'seg', label: t('impLanguage'), options: ['en', 'zh'].map((code) => ({ id: code, label: t(code === 'en' ? 'langEn' : 'langZh'), on: media.language === code })) });
  const rowsBlock = entries.length ? block({ span: true, title: t('impQueue'), body: rowList(entries.map(({ item, index }) => ({
    title: item.title || item.name || item.url,
    meta: mediaMeta(t, ui, item),
    detail: item.state === 'processing' ? processingProgressMarkup(item.stage, Object.fromEntries(['fetch', 'transcribe', 'segment', 'translate', 'ready'].map((stage) => [stage, t(`impMediaStage_${stage}`)]))) : '',
    pills: [outcome(t, item.state)],
    actions: [
      ...(item.state === 'ready' && !media.running ? [{ label: item.level ? t('impLevelValue', { level: item.level }) : t('impLevelNone'), size: 'xs', a: 'media-level', data: { index } }] : []),
      ...(item.contentId ? [{ label: t('impOpen'), size: 'xs', a: 'go', data: { to: href('adminMediaItem', { id: item.contentId }) } }] : []),
      ...(!media.running && ['ready', 'to_import', 'failed'].includes(item.state) ? [{ label: t('impRemove'), size: 'xs', a: 'media-remove', data: { index } }] : []),
    ],
  }))) }) : '';
  return {
    title: t('impTitle'),
    markup: html`<section class="a-page" data-screen-label="Import media">
      ${pageHead({ back: { href: href('adminImports'), label: t('impTitle') }, title: t('impMediaTitle'), sub: t('impMediaSub') })}
      ${tabs([{ id: 'url', label: t('impFromUrl'), selected: tab === 'url' }, { id: 'file', label: t('impUploadFile'), selected: tab === 'file' }])}
      <div class="a-blocks">
        ${formBlock({ span: true, fields, actions: tab === 'url' ? [{ label: media.checking ? t('impChecking') : t('impPreview'), kind: 'primary', a: 'media-check', disabled: media.checking || media.running || !String(media.urls || '').trim() }] : [] })}
        ${media.checking || media.running ? loadingMarkup(t(media.checking ? 'impChecking' : 'impImporting')) : ''}
        ${rowsBlock}
        ${entries.length ? formBlock({ span: true, fields: [], actions: [{ label: media.running ? t('impImporting') : t('impImportN', { n: importable }), kind: 'primary', a: 'media-import', disabled: !importable || media.running }] }) : ''}
        ${done ? stateBlock({ span: true, kind: 'ok', heading: t('impDoneSummary', { ok: media.items.filter((item) => ['published', 'review', 'unpublished', 'archived'].includes(item.state)).length, total: media.items.length }), actions: [{ label: t('impViewMedia'), kind: 'primary', size: 'sm', a: 'go', data: { to: href('adminMedia') } }] }) : ''}
      </div>
    </section>`,
  };
}

/* ---- vocabulary --------------------------------------------------------------------------------- */

export function vocabularyPage({ vocab, t, ui, href }) {
  const step = vocab.results ? 3 : vocab.previews.length ? (vocab.step === 2 ? 2 : 1) : 0;
  const meta = vocab.metadata;
  const stages = [t('impVStepChoose'), t('impVStepMap'), t('impVStepPreview'), t('impVStepImport')].map((label, index) => ({ label, state: index < step ? 'done' : index === step ? 'active' : 'todo' }));
  const blocks = [stepsBlock({ span: true, items: stages })];
  if (step === 0) {
    blocks.push(formBlock({ span: true, fields: [
      { id: 'vfiles', kind: 'file', label: t('impWordList'), span: true, fileLabel: vocab.files.length ? vocab.files.map((file) => file.name).join(', ') : t('impChooseList'), accept: t('impListAccept'), acceptAttr: '.csv,.tsv,.json,.txt,.xlsx', multiple: true },
    ], error: vocab.errors.join(' '), actions: [{ label: vocab.previewing ? t('impChecking') : t('impPreviewFile'), kind: 'primary', a: 'vocab-preview', disabled: !vocab.files.length || vocab.previewing }] }));
  }
  if (step >= 1 && !vocab.results) {
    vocab.previews.forEach((preview, index) => {
      if (preview.error) {
        blocks.push(stateBlock({ span: true, title: preview.filename, kind: 'error', heading: t('impPreviewFailed'), text: preview.error }));
        return;
      }
      const headers = preview.headers || [];
      const mapping = vocab.mappings[preview.filename] || {};
      const fieldItems = VOCABULARY_FIELDS.slice(0, vocab.showAll ? VOCABULARY_FIELDS.length : PRIMARY_FIELDS).map((field) => ({
        id: `map:${index}:${field}`, kind: 'select', label: t(`impField_${field}`),
        options: [{ id: '', label: t('impNotMapped'), on: !mapping[field] }, ...headers.map((header) => ({ id: header, label: header, on: mapping[field] === header }))],
      }));
      blocks.push(formBlock({ span: true, title: t('impWhichColumn'), sub: `${preview.filename} · ${t('impRows', { n: num(preview.row_count, ui) })}`, fields: fieldItems,
        error: mapping.term ? '' : t('validationTerm', { file: preview.filename }),
        actions: [{ label: vocab.showAll ? t('impFewerFields') : t('impMoreFields'), a: 'vocab-more' }] }));
      if ((preview.sample || []).length) {
        blocks.push(block({ span: true, title: t('impSample'), body: rowList((preview.sample || []).slice(0, 3).map((row) => ({ title: String(row?.[mapping.term] ?? Object.values(row || {})[0] ?? ''), meta: headers.filter((h) => h !== mapping.term).map((h) => `${h}: ${row?.[h] ?? ''}`).join(' · ') }))) }));
      }
      for (const warning of preview.warnings || []) blocks.push(banner({ tone: 'warn', title: warning }));
    });
    blocks.push(formBlock({ span: true, title: t('impCollection'), fields: [
      { id: 'meta:title', kind: 'text', label: t('impCollectionTitle'), span: true, value: meta.title },
      { id: 'meta:language', kind: 'seg', label: t('impLanguage'), options: ['en', 'zh'].map((code) => ({ id: code, label: t(code === 'en' ? 'langEn' : 'langZh'), on: meta.language === code })) },
      { id: 'meta:meaning_language', kind: 'text', label: t('impMeaningLanguage'), value: meta.meaning_language },
      { id: 'meta:framework', kind: 'text', label: t('impFramework'), value: meta.framework },
      { id: 'meta:level', kind: 'text', label: t('impCollectionLevel'), value: meta.level },
      { id: 'meta:topic', kind: 'text', label: t('impCollectionTopic'), value: meta.topic },
      { id: 'meta:rights_status', kind: 'select', label: t('ctRightsStatus'), options: [{ id: '', label: t('ctRights_'), on: !meta.rights_status }, ...RIGHTS_STATUSES.map((value) => ({ id: value, label: t(`ctRights_${value}`), on: meta.rights_status === value }))] },
      { id: 'meta:completeness', kind: 'seg', label: t('ctCompleteness'), options: ['complete', 'partial', 'unknown'].map((value) => ({ id: value, label: t(`ctCompleteness_${value}`), on: meta.completeness === value })) },
      { id: 'meta:publish', kind: 'toggle', label: t('impPublishAfter'), span: true, on: Boolean(meta.publish), toggleLabel: meta.publish ? t('impPublishOn') : t('impPublishOff'), hint: t('impPublishHint') },
      ...(meta.publish ? [{ id: 'meta:attested', kind: 'toggle', label: t('ctConfirmation'), span: true, on: Boolean(meta.attested), toggleLabel: t('ctAttest') }] : []),
    ], error: vocab.errors.join(' '), status: vocab.running ? t('impImporting') : '', actions: [{ label: t('actCancel'), a: 'vocab-reset' }, { label: vocab.running ? t('impImporting') : t('impImport'), kind: 'primary', a: 'vocab-import', disabled: vocab.running }] }));
  }
  if (vocab.results) {
    const rows = (vocab.results.items || []).map((row) => ({
      title: row.filename || '',
      meta: row.status === 'failed' ? (row.failure_reason ? t('impServerReason', { detail: row.failure_reason }) : t('impErr_unknown')) : t('impVocabResult', { imported: num(row.imported, ui), duplicates: num(row.duplicates, ui), skipped: num(row.skipped, ui) }),
      pills: [{ label: row.status === 'imported' ? t('impDone') : row.status === 'skipped' ? t('impSkipped') : t('impFailed'), tone: row.status === 'imported' ? 'ok' : row.status === 'skipped' ? 'mute' : 'err' }],
    }));
    const collection = vocab.results.collection || {};
    blocks.push(block({ span: true, title: t('impResult'), actions: [
      ...(collection.collection_id || collection.id ? [{ label: t('impOpenCollection'), kind: 'primary', size: 'sm', a: 'go', data: { to: href('adminCollection', { id: collection.collection_id || collection.id }) } }] : []),
      { label: t('impAnother'), size: 'sm', a: 'vocab-reset' },
    ], body: rowList(rows, { title: t('impNothingQueued'), text: '' }) }));
  }
  return {
    title: t('impTitle'),
    markup: html`<section class="a-page" data-screen-label="Import vocabulary">
      ${pageHead({ back: { href: href('adminImports'), label: t('impTitle') }, title: t('impVocabTitle'), sub: t('impVocabSub') })}
      <div class="a-blocks">${blocks}</div>
    </section>`,
  };
}

/* ---- register a source -------------------------------------------------------------------------- */

export function sourceFormPage({ form, t, href }) {
  return {
    title: t('impTitle'),
    markup: html`<section class="a-page" data-screen-label="Register source">
      ${pageHead({ back: { href: href('adminImports'), label: t('impTitle') }, title: t('impSourceTitle'), sub: t('impSourceSub') })}
      <div class="a-blocks">${formBlock({ span: true,
        fields: [
          { id: 'name', kind: 'text', label: t('impSourceName'), value: form.name, placeholder: t('impSourceNameHint') },
          { id: 'url', kind: 'text', label: t('impSourceHome'), value: form.url, placeholder: 'https://' },
          { id: 'type', kind: 'select', label: t('impSourceType'), options: ['direct_url', 'rss', 'feed', 'api', 'manual', 'file'].map((kind) => ({ id: kind, label: t(`srcType_${kind}`), on: form.type === kind })) },
          { id: 'language', kind: 'seg', label: t('impLanguage'), options: ['en', 'zh'].map((code) => ({ id: code, label: t(code === 'en' ? 'langEn' : 'langZh'), on: form.language === code })) },
          { id: 'can_republish', kind: 'toggle', label: t('rdQ_can_republish'), on: form.can_republish, toggleLabel: t('impRepublishOn'), span: true },
          { id: 'can_adapt', kind: 'toggle', label: t('rdQ_can_adapt'), on: form.can_adapt, toggleLabel: t('impAdaptOn'), span: true },
          { id: 'attribution_required', kind: 'toggle', label: t('rdQ_attribution_required'), on: form.attribution_required, toggleLabel: t('impAttributionOn'), span: true },
          { id: 'license', kind: 'text', label: t('addLicense'), span: true, value: form.license, placeholder: t('impOptional') },
          { id: 'polling', kind: 'toggle', label: t('srcPolling'), on: false, toggleLabel: t('impPollingOff'), span: true, hint: t('srcPollingText'), disabledToggle: true, tag: t('pillFuture') },
        ],
        error: form.error, status: form.running ? t('saving') : '',
        actions: [{ label: t('actCancel'), a: 'go', data: { to: href('adminImports') } }, { label: t('impRegister'), kind: 'primary', a: 'source-create', disabled: form.running }] })}</div>
    </section>`,
  };
}

/* ---- jobs --------------------------------------------------------------------------------------- */

const JOB_PILL = { queued: ['jobQueued', 'mute'], running: ['jobRunning', 'info'], completed: ['jobCompleted', 'ok'], failed: ['jobFailed', 'err'] };
export const jobPill = (t, status) => { const [label, tone] = JOB_PILL[status] || JOB_PILL.running; return { label: t(label), tone }; };

const jobKind = (t, job) => (t.has(`jobType_${job.job_type}`) ? t(`jobType_${job.job_type}`) : job.job_type);
const errorLabel = (t, code) => (t.has(`jobErr_${code}`) ? t(`jobErr_${code}`) : code);

export function jobsPage({ jobs, cursor, filter, t, ui, href }) {
  const filters = ['all', 'running', 'failed', 'completed'];
  return {
    title: t('impTitle'),
    markup: html`<section class="a-page" data-screen-label="Reading jobs">
      ${pageHead({ back: { href: href('adminImports'), label: t('impTitle') }, title: t('impJobs'), sub: t('impJobsSub'), actions: [{ label: t('rdAdd'), kind: 'primary', a: 'go', data: { to: href('adminAdd') } }] })}
      ${chipRow({ label: t('impFilterStatus'), options: filters.map((id) => ({ id, label: t(`jobFilter_${id}`), on: (filter || 'all') === id })), a: 'job-filter' })}
      <div class="a-blocks">${block({ span: true, flat: true, body: rowList(jobs.map((job) => ({
        title: jobKind(t, job),
        meta: [t.has(`impStage_${job.stage}`) ? t(`impStage_${job.stage}`) : job.stage, relative(job.created_at, ui), t('jobAttempt', { n: job.attempt, max: job.max_attempts })].join(' · '),
        detail: job.last_error_code ? errorLabel(t, job.last_error_code) : '',
        pills: [jobPill(t, job.status)],
        actions: job.status === 'failed' ? [{ label: t('jobRetry'), kind: 'primary', size: 'xs', a: 'job-retry', data: { id: job.id } }] : [],
        go: href('adminJob', { id: job.id }),
      })), { title: t('jobNone'), text: '' }) })}</div>
      ${cursor ? html`<div class="a-more">${button({ label: t('rdMore'), a: 'more', size: 'sm' })}</div>` : ''}
    </section>`,
  };
}

export function jobPage({ job, t, ui, href }) {
  const reached = STAGES.indexOf(job.stage);
  const failedAt = job.status === 'failed' ? Math.max(reached, 0) : -1;
  const items = STAGES.map((stage, index) => ({
    label: t.has(`impStage_${stage}`) ? t(`impStage_${stage}`) : stage,
    state: job.status === 'completed' ? 'done' : failedAt === index ? 'fail' : index < reached ? 'done' : index === reached ? 'active' : 'todo',
  }));
  return {
    title: t('impTitle'),
    crumb: jobKind(t, job),
    markup: html`<section class="a-page" data-screen-label="A29 Job detail">
      ${pageHead({ back: { href: href('adminJobs'), label: t('impJobs') }, title: jobKind(t, job), sub: t('jobSubmitted', { when: relative(job.created_at, ui), attempt: job.attempt }), pills: [jobPill(t, job.status)],
        actions: [
          ...(job.result_article_id ? [{ label: t('jobOpenReview'), kind: 'primary', a: 'go', data: { to: href('adminArticle', { id: job.result_article_id }) } }] : []),
          ...(job.status === 'failed' ? [{ label: t('jobRetry'), kind: 'primary', a: 'job-retry', data: { id: job.id } }] : []),
        ] })}
      ${job.status === 'failed' ? banner({ tone: 'err', title: errorLabel(t, job.last_error_code || 'unknown'), text: `${job.last_error || ''} ${t('jobAttempt', { n: job.attempt, max: job.max_attempts })}`.trim() }) : ''}
      <div class="a-blocks">
        ${stepsBlock({ title: t('jobStages'), items })}
        ${block({ title: t('jobDetails'), body: kv([
          { key: t('jobColType'), value: jobKind(t, job) },
          { key: t('jobColSubmittedBy'), value: job.submitted_by || '—' },
          { key: t('jobColCreated'), value: dateTime(job.created_at, ui) },
          { key: t('jobColFinished'), value: job.finished_at ? dateTime(job.finished_at, ui) : '—' },
          { key: t('jobColResult'), value: job.result_kind || '—' },
        ]) })}
        ${block({ span: true, title: t('jobTechnical'), body: kv([
          { key: t('jobColId'), value: job.id, mono: true },
          { key: t('jobColWorker'), value: job.claimed_by || '—' },
          { key: t('jobColHeartbeat'), value: job.heartbeat_at ? dateTime(job.heartbeat_at, ui) : '—' },
          { key: t('jobColNextRetry'), value: job.next_retry_at ? dateTime(job.next_retry_at, ui) : '—' },
        ]) })}
      </div>
    </section>`,
  };
}

/* ---- history ------------------------------------------------------------------------------------ */

const HISTORY_PILL = { published: ['impDone', 'ok'], ready: ['impDone', 'ok'], duplicate: ['impDuplicate', 'mute'], skipped: ['impSkipped', 'mute'], failed: ['impFailed', 'err'], archived: ['impArchived', 'mute'] };

export function historyPage({ data, filters, t, ui, href }) {
  const rows = (data?.items || []).map((row) => {
    const result = row.result || {};
    const [label, tone] = HISTORY_PILL[row.status] || ['impDone', 'ok'];
    const detail = row.error
      ? failureText(t, { code: row.error.code, stage: row.error.stage, message: row.error.message })
      : row.kind === 'vocabulary' ? [result.title, t('impVocabResult', { imported: num(result.imported, ui), duplicates: num(result.duplicates, ui), skipped: num(result.skipped, ui) })].filter(Boolean).join(' · ')
      : [result.title, row.kind === 'book' && result.chapter_count != null ? t('impBookOk', { title: '', n: num(result.chapter_count, ui) }).trim() : ''].filter(Boolean).join(' · ');
    return { title: row.source || '—', meta: `${t(`impKind_${row.kind}`)} · ${row.created_at ? relative(row.created_at, ui) : '—'}${detail ? ` · ${detail}` : ''}`, pills: [{ label: t(label), tone }] };
  });
  const offset = data?.offset || 0;
  const total = data?.total || 0;
  return {
    title: t('impTitle'),
    markup: html`<section class="a-page" data-screen-label="A30 Import history">
      ${pageHead({ back: { href: href('adminImports'), label: t('impTitle') }, title: t('impHistory') })}
      ${chipRow({ label: t('impFilterDomain'), options: ['all', 'book', 'media', 'vocabulary'].map((id) => ({ id, label: t(`impDomain_${id}`), on: (filters.kind || 'all') === id })), a: 'history-filter', field: 'kind' })}
      ${chipRow({ label: t('impFilterStatus'), options: ['all', 'failed'].map((id) => ({ id, label: t(`impStatus_${id}`), on: (filters.status || 'all') === id })), a: 'history-filter', field: 'status' })}
      ${banner({ tone: 'info', title: t('impUnifiedTitle'), text: t('impUnifiedText'), actions: [{ label: t('impJobs'), size: 'sm', a: 'go', data: { to: href('adminJobs') } }] })}
      ${data?.available === false ? stateBlock({ kind: 'unavail', heading: t('impHistoryUnavailable'), text: '' }) : ''}
      <div class="a-blocks">${block({ span: true, flat: true, body: rowList(rows, { title: t('impHistoryEmpty'), text: '' }) })}</div>
      ${total > HISTORY_PAGE ? html`<div class="a-more">${button({ label: t('impPrev'), size: 'sm', a: 'history-page', data: { dir: '-1' }, disabled: offset <= 0 })}<span class="a-more__range">${t('impRange', { from: offset + 1, to: Math.min(offset + HISTORY_PAGE, total), total })}</span>${button({ label: t('impNext'), size: 'sm', a: 'history-page', data: { dir: '1' }, disabled: offset + HISTORY_PAGE >= total })}</div>` : ''}
    </section>`,
  };
}

export { futureCard, metrics, raw, icon, pill, kv };
