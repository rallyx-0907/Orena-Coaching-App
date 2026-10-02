/* Content, drawn as the pinned design draws it (Orena-Admin.dc.html A8 home, A9-A10 Books, A11-A12
   Media, A13-A14 Vocabulary). Pure builders over the data the shared rules loaded
   (capabilities/admin-content.js); the wiring is content.js.

   Left out rather than invented (UI_BACKEND_GAPS "Admin: Content"): a book's opening text (the detail
   carries chapter titles only), per-item reader and play counts (the design's "readers", "plays"), a
   media item's pipeline steps (the server keeps a transcript state, not the stages), and the Practice
   generator (no backend). Vocabulary publishing follows the server: rights and completeness warn and
   are recorded, the attestation is the one thing it will not go without. */
import { html, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { dateShort, dateTime, latency, num } from '../../capabilities/admin-format.js';
import { COMPLETENESS, KIND_TILE, PAGE_SIZE, RIGHTS, learnerLink, lifecycleIntents, publishChecks } from '../../capabilities/admin-content.js';
import { block, button, chipRow, formBlock, kv, pageHead, pill, rowList, stateBlock, textBlock } from './blocks.js';

const STATUS_PILL = {
  published: ['ctStatusPublished', 'ok'], draft: ['ctStatusDraft', 'mute'], unpublished: ['ctStatusUnpublished', 'mute'], archived: ['ctStatusArchived', 'mute'],
  review: ['ctStatusReview', 'info'], processing: ['ctStatusProcessing', 'info'],
};
const statusPill = (t, record) => {
  const [label, tone] = STATUS_PILL[record.status] || ['ctStatusDraft', 'mute'];
  return { label: t(label), tone };
};

/* ---- A8 home ------------------------------------------------------------------------------------ */

export function homePage({ counts, t, ui, href }) {
  const tile = (kind, label, to, stats, meta, alert) => html`<button type="button" class="a-hometile" data-go="${to}"><span class="a-hometile__top"><span class="a-row__tile" aria-hidden="true">${KIND_TILE[kind]}</span><span class="a-hometile__text"><span class="a-hometile__label">${label}</span><span class="a-hometile__meta">${meta}</span></span></span><span class="a-hometile__stats">${stats.map(([key, value]) => html`<span><b>${value}</b> ${key}</span>`)}${alert ? html`<span class="a-hometile__alert">${pill({ label: alert, tone: 'info' })}</span>` : ''}</span></button>`;
  const value = (key) => (counts ? num(counts.counts[key] ?? 0, ui) : '—');
  const status = (key) => num(counts?.statusCounts?.[key] ?? 0, ui);
  return {
    title: t('ctTitle'),
    markup: html`<section class="a-page a-page--home" data-screen-label="A8 Content">
      ${pageHead({ title: t('ctTitle'), sub: t('ctSub') })}
      <div class="a-hometiles">
        ${tile('reading', t('rdTitle'), href('adminReading'), [[t('ctPublished'), num(counts?.counts?.reading_published ?? 0, ui)], [t('ctInReview'), num(counts?.counts?.reading_review ?? 0, ui)]], t('ctReadingMeta'), (counts?.counts?.reading_review || 0) ? t('ctToReview', { n: counts.counts.reading_review }) : '')}
        ${tile('book', t('ctBooks'), href('adminBooks'), [[t('ctBooksUnit'), value('book')]], t('ctBooksMeta'))}
        ${tile('media', t('ctMedia'), href('adminMedia'), [[t('ctMediaUnit'), value('media')]], t('ctMediaMeta'))}
        ${tile('vocabulary', t('ctVocab'), href('adminVocab'), [[t('ctVocabUnit'), value('vocabulary')]], t('ctVocabMeta'))}
      </div>
    </section>`,
  };
}

/* ---- lists -------------------------------------------------------------------------------------- */

const LIST = {
  book: { title: 'ctBooksTitle', sub: 'ctBooksSub', back: 'adminContent', importTo: 'adminImportBooks', importLabel: 'ctImportEpub', detail: 'adminBook', label: 'ctBooks', screen: 'A9 Books' },
  media: { title: 'ctMediaTitle', sub: 'ctMediaSub', importTo: 'adminImportMedia', importLabel: 'ctImportMedia', detail: 'adminMediaItem', label: 'ctMedia', screen: 'A11 Media' },
  vocabulary: { title: 'ctVocabTitle', sub: 'ctVocabSub', importTo: 'adminImportVocab', importLabel: 'ctImportList', detail: 'adminCollection', label: 'ctVocab', screen: 'A13 Vocabulary' },
};

function recordMeta(t, ui, record) {
  const facts = record.facts || {};
  const lang = t(record.language === 'zh' ? 'langZh' : 'langEn');
  if (record.kind === 'book') return [record.subtitle, lang, t('ctChaptersN', { n: num(facts.chapter_count, ui) }), t('ctWordsN', { n: num(facts.word_count, ui) })].filter(Boolean).join(' · ');
  if (record.kind === 'media') return [record.subtitle, lang, facts.duration_ms ? latency(facts.duration_ms, ui) : '', facts.level].filter(Boolean).join(' · ');
  return [record.subtitle, lang, facts.level, t('ctEntriesN', { n: num(facts.item_count, ui) })].filter(Boolean).join(' · ');
}

export function listPage({ kind, data, view, t, ui, href, loading }) {
  const spec = LIST[kind];
  const filters = kind === 'media' ? ['all', 'published', 'review', 'processing', 'archived', 'issues'] : ['all', 'published', 'draft', 'archived', 'issues'];
  const items = data?.items || [];
  const total = data?.total ?? items.length;
  return {
    title: t('ctTitle'),
    markup: html`<section class="a-page" data-screen-label="${spec.screen}">
      ${pageHead({ back: { href: href('adminContent'), label: t('ctTitle') }, title: t(spec.title), sub: t(spec.sub), actions: [{ label: t(spec.importLabel), kind: 'primary', a: 'go', data: { to: href(spec.importTo) } }] })}
      ${chipRow({ label: t('ctFilterStatus'), options: filters.map((id) => ({ id, label: t(`ctFilter_${id}`), on: (view.status || 'all') === id })), a: 'status' })}
      ${Object.entries(data?.sources || {}).filter(([, state]) => state !== 'ok').map(([source]) => html`<div class="a-hint" role="status">${t.has(`ctSourceDown_${source}`) ? t(`ctSourceDown_${source}`) : source}</div>`)}
      <div class="a-blocks">${block({ span: true, flat: true, body: loading ? html`<div class="a-loading">${t('loading')}</div>` : rowList(items.map((record) => ({
        tile: KIND_TILE[record.kind],
        title: record.title,
        meta: recordMeta(t, ui, record),
        pills: [statusPill(t, record), ...(record.kind === 'media' && record.facts?.transcript !== 'available' ? [{ label: t('ctTranscriptMissing'), tone: 'warn' }] : [])],
        go: href(spec.detail, { id: record.id }),
      })), { title: view.q || view.status ? t('rdNoMatch') : t('ctNone'), text: '' }) })}</div>
      ${items.length < total ? html`<div class="a-more">${button({ label: t('rdMore'), a: 'more', size: 'sm' })}</div>` : ''}
    </section>`,
    pageSize: PAGE_SIZE,
  };
}

/* ---- details ------------------------------------------------------------------------------------ */

function lifecycleButtons(t, record, kind) {
  return lifecycleIntents(record).map((intent) => ({
    label: t(`ctAct_${intent}`),
    kind: ['publish', 'republish', 'restore'].includes(intent) ? 'primary' : intent === 'archive' ? 'danger' : '',
    a: 'lifecycle', data: { intent },
  })).filter((action) => !(kind === 'vocabulary' && action.data.intent === 'publish'));
}

export function bookPage({ detail, view, t, ui, href }) {
  const record = detail.record;
  const facts = record.facts || {};
  const book = detail.book || {};
  const chapters = book.chapters || [];
  const link = learnerLink(record, detail);
  return {
    title: t('ctTitle'),
    crumb: record.title,
    markup: html`<section class="a-page" data-screen-label="A10 Book detail">
      ${pageHead({ back: { href: href('adminBooks'), label: t('ctBooks') }, title: record.title, sub: record.subtitle || '', pills: [statusPill(t, record)], actions: lifecycleButtons(t, record, 'book') })}
      ${view.error ? html`<div class="a-error" role="alert">${view.error}</div>` : ''}
      <div class="a-blocks">
        ${block({ title: t('ctDetails'), body: kv([
          { key: t('ctFactChapters'), value: num(facts.chapter_count, ui) },
          { key: t('ctFactWords'), value: num(facts.word_count, ui) },
          { key: t('ctFactLanguage'), value: t(record.language === 'zh' ? 'langZh' : 'langEn') },
          { key: t('ctFactImported'), value: dateTime(record.created_at, ui) },
          { key: t('ctFactImportedBy'), value: book.imported_by || '—' },
        ]) })}
        ${block({ title: t('ctLearnerView'), body: html`${book.description ? html`<p class="a-sub">${book.description}</p>` : ''}${link ? html`<a class="a-btn a-btn--md" href="${link}">${t('ctOpenAsLearner')}</a>` : html`<div class="a-hint">${t('ctNotLive')}</div>`}<div class="a-hint">${t('ctReadersGap')}</div>` })}
        ${block({ span: true, title: t('ctChapters'), body: rowList(chapters.slice(0, 40).map((chapter) => ({ title: chapter.title })), { title: t('ctNone'), text: '' }) })}
      </div>
    </section>`,
  };
}

export function mediaPage({ detail, view, t, ui, href, form = {} }) {
  const record = detail.record;
  const facts = record.facts || {};
  const source = detail.source || {};
  const transcript = detail.transcript || { segments: [], segment_count: 0 };
  const missing = facts.transcript !== 'available';
  const link = learnerLink(record, detail);
  const reprocess = (record.actions || []).includes('reprocess');
  return {
    title: t('ctTitle'),
    crumb: record.title,
    markup: html`<section class="a-page" data-screen-label="A12 Media detail">
      ${pageHead({ back: { href: href('adminMedia'), label: t('ctMedia') }, title: record.title, sub: record.subtitle || '', pills: [statusPill(t, record), missing ? { label: t('ctTranscriptMissing'), tone: 'warn' } : { label: t('ctTranscriptReady'), tone: 'ok' }], actions: lifecycleButtons(t, record, 'media').filter((action) => action.data.intent !== 'reprocess').map((action) => ({ ...action, disabled: view.busy })) })}
      ${view.error ? html`<div class="a-error" role="alert">${view.error}</div>` : ''}
      ${missing ? html`<div class="a-banner" data-tone="warn"><div class="a-banner__text"><div class="a-banner__title">${t('ctMissingTitle')}</div><div class="a-banner__body">${t('ctMissingText')}</div></div></div>` : ''}
      <div class="a-blocks">
        ${block({ title: t('ctDetails'), body: kv([
          { key: t('ctFactSource'), value: source.url || t('ctUpload'), mono: Boolean(source.url) },
          { key: t('ctFactSegments'), value: num(facts.segment_count, ui) },
          { key: t('ctFactDuration'), value: facts.duration_ms ? latency(facts.duration_ms, ui) : '—' },
          { key: t('ctFactLanguage'), value: t(record.language === 'zh' ? 'langZh' : 'langEn') },
          { key: t('ctFactLevel'), value: facts.level || '—' },
          { key: t('ctFactTopic'), value: facts.topic || '—' },
          { key: t('ctFactProvider'), value: facts.provider || '—' },
          { key: t('ctFactLicense'), value: source.license || '—' },
        ]) })}
        ${block({ title: t('ctLearnerView'), body: html`${link ? html`<a class="a-btn a-btn--md" href="${link}">${t('ctOpenAsLearner')}</a>` : html`<div class="a-hint">${t('ctNotLive')}</div>`}<div class="a-hint">${t('ctPlaysGap')}</div>` })}
        ${record.origin === 'imported' ? formBlock({ span: true, title: t('ctRightsOrigin'), sub: t('ctMediaRightsHelp'), fields: [
          { id: 'rights', kind: 'seg', label: t('ctRightsStatus'), span: true, options: ['unknown', 'cleared', 'denied'].map((id) => ({ id, label: t(`ctMediaRights_${id}`), on: (form.rights || source.rights || 'unknown') === id })) },
          { id: 'license', label: t('ctFactLicense'), value: form.license ?? source.license ?? '', span: true },
          { id: 'attested', kind: 'toggle', label: t('ctConfirmation'), toggleLabel: t('ctMediaAttest'), on: Boolean(form.attested), span: true },
        ], actions: [{ label: t('ctRightsSave'), a: 'media-rights-save', kind: 'primary', disabled: view.busy || (form.rights === 'cleared' && (['queued', 'running'].includes(record.processing?.state) || !form.attested || !String(form.license || '').trim())) }] }) : ''}
        ${formBlock({ span: true, title: t('ctReprocess'), sub: t('ctReprocessSub'), fields: [
          { id: 'reprocessOpt', kind: 'seg', label: t('ctRedo'), span: true, hint: t('ctRedoGap'), options: [
            { id: 'all', label: t('ctRedoAll'), sub: t('ctRedoAllSub'), on: true },
            { id: 'keep', label: t('ctRedoKeep'), sub: '', on: false, disabled: true, tip: t('ctRedoUnsupported') },
          ] },
        ], actions: reprocess ? [{ label: t('ctAct_reprocess'), a: 'lifecycle', data: { intent: 'reprocess' } }] : [] })}
        ${block({ span: true, title: t('ctTranscript'), body: transcript.segments?.length ? html`${rowList(transcript.segments.map((segment) => ({ title: segment.text, meta: latency(segment.start_ms, ui) })))}${transcript.segment_count > transcript.segments.length ? html`<div class="a-hint">${t('ctSegmentsShown', { shown: transcript.segments.length, total: num(transcript.segment_count, ui) })}</div>` : ''}` : html`<div class="a-hint">${t('ctNoTranscript')}</div>` })}
      </div>
    </section>`,
  };
}

export function collectionPage({ detail, form, view, t, ui, href }) {
  const record = detail.record;
  const facts = record.facts || {};
  const checks = publishChecks(form);
  const failing = checks.filter((check) => !check.pass);
  const canPublish = (record.actions || []).includes('publish');
  const entries = detail.entries || [];
  const strong = checks.find((check) => check.id === 'rights')?.level === 'strong' && !checks[0].pass;
  return {
    title: t('ctTitle'),
    crumb: record.title,
    markup: html`<section class="a-page" data-screen-label="A14 Vocabulary detail">
      ${pageHead({ back: { href: href('adminVocab'), label: t('ctVocab') }, title: record.title, sub: [t(record.language === 'zh' ? 'langZh' : 'langEn'), facts.level, t('ctEntriesN', { n: num(facts.item_count, ui) })].filter(Boolean).join(' · '), pills: [statusPill(t, record)], actions: lifecycleButtons(t, record, 'vocabulary') })}
      ${view.error ? html`<div class="a-error" role="alert">${view.error}</div>` : ''}
      ${canPublish ? html`<div class="a-banner" data-tone="${strong ? 'err' : failing.length > 1 ? 'warn' : 'info'}"><div class="a-banner__text"><div class="a-banner__title">${t('ctGateTitle')}</div><div class="a-banner__body">${t('ctGateText')}</div></div></div>` : ''}
      <div class="a-blocks">
        ${canPublish ? block({ title: t('ctChecks'), pills: [{ label: failing.length ? t('ctChecksFailing', { n: failing.length }) : t('ctChecksPassed'), tone: failing.length ? 'warn' : 'ok' }], body: rowList(checks.map((check) => ({
          title: t(`ctCheck_${check.id}`),
          meta: check.pass ? '' : t(`ctCheckWhy_${check.id}`),
          pills: [{ label: check.pass ? t('ctPass') : check.level === 'required' ? t('ctRequired') : t('ctWarns'), tone: check.pass ? 'ok' : check.level === 'required' ? 'err' : 'warn' }],
        }))) }) : ''}
        ${canPublish ? formBlock({ title: t('ctRightsOrigin'), fields: [
          { id: 'rights', kind: 'select', label: t('ctRightsStatus'), options: [{ id: '', label: t('ctRights_'), on: !form.rights }, ...RIGHTS.map((value) => ({ id: value, label: t(`ctRights_${value}`), on: form.rights === value }))] },
          { id: 'completeness', kind: 'seg', label: t('ctCompleteness'), options: COMPLETENESS.map((value) => ({ id: value, label: t(`ctCompleteness_${value}`), on: form.completeness === value })) },
          { id: 'attested', kind: 'toggle', label: t('ctConfirmation'), span: true, on: form.attested, toggleLabel: t('ctAttest') },
        ], actions: [{ label: t('ctAct_publish'), kind: 'primary', a: 'collection-publish', disabled: !form.attested || view.busy }] }) : block({ title: t('ctRightsOrigin'), body: kv([
          { key: t('ctRightsStatus'), value: facts.rights_status ? t(`ctRights_${facts.rights_status}`) : t('ctRights_') },
          { key: t('ctCompleteness'), value: facts.completeness ? t(`ctCompleteness_${facts.completeness}`) : '—' },
        ]) })}
        ${block({ title: t('ctDetails'), body: kv([
          { key: t('ctFactEntries'), value: num(facts.item_count, ui) },
          { key: t('ctFactFramework'), value: facts.framework || '—' },
          { key: t('ctFactLevel'), value: facts.level || '—' },
          { key: t('ctFactTopic'), value: facts.topic || '—' },
        ]) })}
        ${block({ title: t('ctImportSources'), body: rowList((detail.sources || []).map((row) => ({
          title: row.filename,
          meta: `${dateShort(row.created_at, ui)} · ${row.status === 'failed' ? row.error : t('impVocabResult', { imported: num(row.imported, ui), duplicates: num(row.duplicates, ui), skipped: num(row.skipped, ui) })}`,
          pills: [{ label: row.status === 'failed' ? t('impFailed') : t('impDone'), tone: row.status === 'failed' ? 'err' : 'ok' }],
        })), { title: t('ctNone'), text: '' }) })}
        ${block({ span: true, title: t('ctEntries'), body: html`${rowList(entries.map((entry) => ({
          title: entry.term,
          meta: [entry.part_of_speech, entry.meaning].filter(Boolean).join(' · '),
        })), { title: t('ctNone'), text: '' })}${detail.entry_total > entries.length ? html`<div class="a-hint">${t('ctSegmentsShown', { shown: entries.length, total: num(detail.entry_total, ui) })}</div>` : ''}` })}
      </div>
    </section>`,
  };
}

export { stateBlock, textBlock, raw, icon };
