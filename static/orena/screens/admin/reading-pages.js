/* The Reading pipeline, drawn as the pinned design draws it (Orena-Admin.dc.html A15 overview, A16
   queue, A17 review detail, A21 add content, A22-A23 sources, Comprehension set review). Pure: each
   builder takes the data the shared rules loaded (capabilities/admin-reading.js), the page's own
   view state and the copy function, and returns markup - so scripts/test_orena_screen_admin.mjs
   renders every page from a fixture without a browser.

   The queue carries source, rights and target count per row (D-105 c), and copyright is a hard gate
   at Publish (D-105 a): the review page states the refusal and lets the administrator answer the
   rights questions, which the server records without rewriting the ingested snapshot. */
import { html, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { dateShort, dateTime, num, relative } from '../../capabilities/admin-format.js';
import {
  RIGHTS_EDIT, QUEUE_TABS, automationChoice, articleActions, isEditable, levelOptions, publicationBlockers, questionState,
  questionsEditable, readingMinutes, setActions, setIsStale, setProgress, tabOf,
} from '../../capabilities/admin-reading.js';
import { learnerAddress } from '../../capabilities/admin-reading.js';
import { banner, block, button, chipRow, formBlock, futureCard, kv, metrics, pageHead, pill, rowList, searchField, stateBlock, tabs, tiles, textBlock } from './blocks.js';

const STATUS_PILL = {
  published: ['rdStatusPublished', 'ok'],
  needs_review: ['rdStatusReview', 'info'],
  ready: ['rdStatusReview', 'info'],
  draft: ['rdStatusReview', 'info'],
  processing: ['rdStatusProcessing', 'info'],
  rejected: ['rdStatusRejected', 'err'],
  archived: ['rdStatusArchived', 'mute'],
  unpublished: ['rdStatusUnpublished', 'mute'],
};

export function statusPill(t, status) {
  const [label, tone] = STATUS_PILL[status] || ['rdStatusReview', 'info'];
  return { label: t(label), tone };
}

const RIGHTS_PILL = { allowed: ['rdRightsAllow', 'ok'], denied: ['rdRightsDeny', 'err'], unknown: ['rdRightsUnknown', 'warn'] };

export function rightsPill(t, level) {
  const [label, tone] = RIGHTS_PILL[level] || RIGHTS_PILL.unknown;
  return { label: t(label), tone };
}

const SET_PILL = {
  draft: ['csStatusDraft', 'mute'],
  needs_review: ['csStatusReview', 'info'],
  approved: ['csStatusApproved', 'ok'],
  rejected: ['csStatusRejected', 'err'],
  stale: ['csStatusStale', 'warn'],
  archived: ['csStatusArchived', 'mute'],
};

export function setPill(t, status) {
  const [label, tone] = SET_PILL[status] || SET_PILL.draft;
  return { label: t(label), tone };
}

const LANGS = { en: 'langEn', vi: 'langVi', zh: 'langZh' };
const langName = (t, code) => (LANGS[code] ? t(LANGS[code]) : String(code || '').toUpperCase());

/* ---- A15 overview ------------------------------------------------------------------------------ */

export function overviewPage({ ops, sources, next, failedJobs, t, ui, href }) {
  const articles = ops?.articles || {};
  const count = (...keys) => keys.reduce((sum, key) => sum + Number(articles[key] || 0), 0);
  const active = (sources || []).filter((source) => source.state === 'active');
  const withError = (sources || []).filter((source) => source.last_error);
  const review = count('draft', 'needs_review', 'ready');
  const items = [
    { label: t('rdStatusPublished'), value: num(count('published'), ui), tone: 'ok', note: t('rdNoteLive'), go: href('adminQueue', {}, { tab: 'published' }) },
    { label: t('rdStatusReview'), value: num(review, ui), tone: 'accent', note: t('rdNoteWaiting'), go: href('adminQueue', {}, { tab: 'review' }) },
    { label: t('rdStatusProcessing'), value: num(count('processing'), ui), tone: 'warn', note: t('rdNotePipeline'), go: '' },
    { label: t('rdStatusRejected'), value: num(count('rejected'), ui), note: t('rdNoteKept'), go: href('adminQueue', {}, { tab: 'rejected' }) },
    { label: t('rdStatusArchived'), value: num(count('archived', 'unpublished'), ui), note: t('rdNoteHidden'), go: href('adminQueue', {}, { tab: 'archived' }) },
    { label: t('rdFailedJobs'), value: failedJobs == null ? '—' : num(failedJobs, ui), tone: failedJobs ? 'err' : '', note: t('rdNoteImports'), go: href('adminJobs', {}, { status: 'failed' }) },
    { label: t('rdActiveSources'), value: num(active.length, ui), note: t('rdNoteOfSources', { n: num((sources || []).length, ui) }), go: href('adminSources') },
    { label: t('rdSourceErrors'), value: num(withError.length, ui), tone: withError.length ? 'err' : '', note: t('rdNoteSourceErrors'), go: href('adminSources') },
  ];
  const nextRows = (next || []).map((item) => ({
    title: item.title || t('rdUntitled'),
    meta: [item.source_name, langName(t, item.language), item.topic, item.level, t('rdMinutes', { n: readingMinutes(item.reading_time_seconds) })].filter(Boolean).join(' · '),
    pills: [rightsPill(t, item.rights_level)],
    right: t('rdReview'),
    go: href('adminArticle', { id: item.id }),
  }));
  return {
    title: t('rdTitle'),
    markup: html`<section class="a-page" data-screen-label="A15 Reading overview">
      ${pageHead({ back: { href: href('adminContent'), label: t('ctTitle') }, title: t('rdTitle'), sub: t('rdSub'),
        actions: [
          { label: `+ ${t('rdAdd')}`, kind: 'primary', a: 'go', data: { to: href('adminAdd') } },
          { label: t('rdQueue'), a: 'go', data: { to: href('adminQueue') } },
          { label: t('rdSources'), a: 'go', data: { to: href('adminSources') } },
          { label: t('rdJobs'), a: 'go', data: { to: href('adminJobs') } },
        ] })}
      ${tiles(items)}
      <div class="a-blocks">${block({ span: true, title: t('rdNext'), actions: [{ label: `${t('rdOpenQueue')} →`, size: 'sm', a: 'go', data: { to: href('adminQueue') } }],
        body: rowList(nextRows, { title: t('rdQueueClear'), text: '' }) })}</div>
      ${futureCard({ title: t('rdCoverage'), pill: t('pillFuture'), text: t('rdCoverageText') })}
    </section>`,
  };
}

/* ---- A16 queue --------------------------------------------------------------------------------- */

const TAB_TITLE = {
  review: ['rdQTitleReview', 'rdQSubReview'],
  published: ['rdQTitlePublished', 'rdQSubPublished'],
  rejected: ['rdQTitleRejected', 'rdQSubRejected'],
  archived: ['rdQTitleArchived', 'rdQSubArchived'],
};

function queueActions(t, item, tab, href) {
  const open = { label: t('rdReview'), kind: 'primary', a: 'go', data: { to: href('adminArticle', { id: item.id }) } };
  const preview = { label: t('rdPreview'), a: 'preview', data: { id: item.id } };
  const act = (action, label, kind = '') => ({ label, kind, a: 'article-act', data: { id: item.id, action } });
  if (tab === 'review') return [preview, open, act('publish', t('rdPublish')), act('reject', t('rdReject'), 'danger')];
  if (tab === 'published') return [preview, { label: t('rdEditMeta'), a: 'go', data: { to: href('adminArticle', { id: item.id }) } }, act('unpublish', t('rdUnpublish')), act('archive', t('rdArchive'), 'danger')];
  if (tab === 'rejected') return [preview, act('restore', t('rdRestoreReview'), 'primary'), act('archive', t('rdArchive'))];
  return [preview, act('restore', t('rdRestore'), 'primary')];
}

export function queuePage({ tab, items, next, counts, view, t, ui, href, loading }) {
  const [titleKey, subKey] = TAB_TITLE[tab];
  const needle = String(view.q || '').trim().toLowerCase();
  const shown = (items || []).filter((item) => (!view.level || view.level === 'all' || item.level === view.level)
    && (!needle || `${item.title} ${item.topic}`.toLowerCase().includes(needle)));
  /* The levels on offer are the ones the list holds (the design offers the learner levels; the engine grades both scales). */
  const order = [...levelOptions('en'), ...levelOptions('zh')];
  const levels = ['all', ...[...new Set((items || []).map((item) => item.level).filter(Boolean))].sort((a, b) => order.indexOf(a) - order.indexOf(b))];
  const head = { review: ['rdColLevel', 'rdColTargets', 'rdColRights'], published: ['rdColLevel', 'rdColWords', 'rdColAdded'], rejected: ['rdColLevel', 'rdColWords', 'rdColAdded'], archived: ['rdColLevel', 'rdColWords', 'rdColAdded'] }[tab];
  const rows = shown.map((item) => {
    const pillInfo = tab === 'review' ? rightsPill(t, item.rights_level) : { label: dateShort(item.created_at, ui), tone: 'mute' };
    return html`<div class="a-qrow">
      <button type="button" class="a-qrow__main" data-go="${href('adminArticle', { id: item.id })}"><span class="a-qrow__title">${item.title || t('rdUntitled')}</span><span class="a-qrow__meta">${[item.source_name, langName(t, item.language), item.topic || t('rdNoTopic'), t('rdMinutes', { n: readingMinutes(item.reading_time_seconds) })].filter(Boolean).join(' · ')}</span></button>
      <span class="a-qrow__c1">${item.level || '—'}${item.reviewed_level ? html`<small>${t('rdReviewedMark')}</small>` : ''}</span>
      <span class="a-qrow__c2">${num(tab === 'review' ? item.target_count : item.word_count, ui)}</span>
      <span class="a-qrow__pill">${pill(pillInfo)}</span>
      <div class="a-qrow__acts">${queueActions(t, item, tab, href).map(button)}</div>
    </div>`;
  });
  const empty = needle || (view.level && view.level !== 'all')
    ? { title: t('rdNoMatch'), text: t('rdNoMatchText') }
    : { title: tab === 'review' ? t('rdQueueClear') : t('rdNothingYet'), text: tab === 'review' ? t('rdQueueClearText') : '' };
  return {
    title: t('rdTitle'),
    markup: html`<section class="a-page" data-screen-label="A16 Reading queue">
      ${pageHead({ back: { href: href('adminReading'), label: t('rdTitle') }, title: t(titleKey), sub: t(subKey), actions: [{ label: `+ ${t('rdAdd')}`, kind: 'primary', a: 'go', data: { to: href('adminAdd') } }] })}
      ${tabs(QUEUE_TABS.map((id) => ({ id, label: t(TAB_TITLE[id][0].replace('rdQTitle', 'rdTab')), count: counts ? num(counts[id] ?? 0, ui) : null, selected: id === tab })))}
      <div class="a-filters">${searchField({ id: 'q', value: view.q || '', placeholder: t('rdSearch') })}${chipRow({ options: levels.map((id) => ({ id, label: id === 'all' ? t('rdAll') : id, on: (view.level || 'all') === id })), a: 'level' })}</div>
      <div class="a-qtable">
        <div class="a-qhead"><span>${t('rdColArticle')}</span>${head.map((key) => html`<span>${t(key)}</span>`)}</div>
        ${loading ? html`<div class="a-loading">${t('loading')}</div>` : rows.length ? rows : html`<div class="a-qempty"><div class="a-qempty__title">${empty.title}</div>${empty.text ? html`<div class="a-qempty__text">${empty.text}</div>` : ''}</div>`}
      </div>
      ${next ? html`<div class="a-more">${button({ label: t('rdMore'), a: 'more', size: 'sm' })}</div>` : ''}
    </section>`,
  };
}

/* ---- A17 review detail -------------------------------------------------------------------------- */

function rightsAdviceKey(blockers) {
  if (blockers.some((blocker) => blocker.code.endsWith('not_cleared'))) return 'rdRightsAdviceDenied';
  if (blockers.length) return 'rdRightsAdviceUnknown';
  return 'rdRightsAdviceAllowed';
}

/* The three rights questions as editable choices: the server's held answer unless the operator has
   picked another. An unanswered question is its own choice, because "unknown" is an answer the
   gate treats as a refusal. */
function rightsEditor(t, state, draft, automation) {
  return RIGHTS_EDIT.map((question) => {
    const held = question.override ? automationChoice(automation) : state[question.id] === undefined || state[question.id] === 'unknown' ? '' : state[question.id];
    const chosen = draft[question.id] !== undefined ? draft[question.id] : held;
    const defaultLabel = question.override ? t('rdAutoDefault', { value: t(automation?.source_default ? 'rdAnswerAllowed' : 'rdAnswerDenied') }) : null;
    const options = [['', question.override ? '' : 'rdAnswerUnknown'], [question.yes, question.yes === 'required' ? 'rdAnswerRequired' : 'rdAnswerAllowed'], [question.no, question.no === 'not_required' ? 'rdAnswerNotRequired' : 'rdAnswerDenied']];
    return html`<div class="a-field"><div class="a-field__label"><span>${t(`rdQ_${question.id}`)}</span></div><div class="a-seg" role="group" aria-label="${t(`rdQ_${question.id}`)}">${options.map(([id, key]) => html`<button type="button" class="a-seg__option" data-a="rights-pick" data-field="${question.id}" data-value="${id}" aria-pressed="${chosen === id ? 'true' : 'false'}"><span>${key === '' ? defaultLabel : t(key)}</span></button>`)}</div></div>`;
  });
}

const RIGHT_ANSWER = { allowed: 'rdAnswerAllowed', denied: 'rdAnswerDenied', unknown: 'rdAnswerUnknown', required: 'rdAnswerRequired', not_required: 'rdAnswerNotRequired' };
const RIGHT_TONE = { allowed: 'ok', denied: 'err', unknown: 'warn', required: 'info', not_required: 'ok' };

function evidenceFields(t, article, ui) {
  const analysis = article.analysis || {};
  const source = article.source || {};
  const meta = source.metadata || {};
  const rows = [
    [t('rdEvLang'), analysis.detected_language || meta.detected_language ? `${analysis.detected_language || meta.detected_language}${meta.detected_language_confidence != null ? ` (${meta.detected_language_confidence})` : ''}` : '—'],
    [t('rdEvLevel'), article.estimated_level ? `${article.estimated_level}${article.estimated_level_confidence != null ? ` (${article.estimated_level_confidence})` : ''}` : '—'],
    [t('rdEvSentences'), analysis.sentence_count != null ? `${num(analysis.sentence_count, ui)} · ${t('rdEvAvgLength', { n: analysis.average_sentence_length })}` : '—'],
    [t('rdEvTargets'), num((article.targets || []).length, ui)],
    [t('rdEvIssues'), (analysis.quality_issues || []).length ? analysis.quality_issues.map((code) => (t.has(`rdIssue_${code}`) ? t(`rdIssue_${code}`) : code)).join(', ') : t('rdEvNoIssues')],
    [t('rdEvInput'), meta.input_kind || '—'],
    [t('rdEvHash'), String(source.content_hash || '').slice(0, 12) || '—'],
    [t('rdEvRevision'), num(article.content_revision, ui)],
  ];
  return rows;
}

export function articlePage({ article, sets, view, t, ui, href, now }) {
  const source = article.source || {};
  const state = source.rights_state || {};
  const blockers = publicationBlockers(article);
  const isLive = article.status === 'published';
  const editable = isEditable(article.status);
  const actions = articleActions(article.status);
  const status = statusPill(t, article.status);
  const targets = article.targets || [];
  const dtab = view.dtab || 'article';
  const kinds = ['word', 'phrase', 'collocation', 'grammar'];
  const actionButtons = actions.map((action) => ({
    label: t({ publish: 'rdPublish', unpublish: 'rdUnpublish', reject: 'rdReject', archive: 'rdArchive', restore: 'rdRestoreReview' }[action]),
    disabled: action === 'publish' && blockers.length > 0,
    tip: action === 'publish' && blockers.length ? t('rdPublishNeedsRights') : '',
    kind: action === 'publish' ? 'primary' : action === 'reject' || (action === 'archive' && article.status === 'published') ? 'danger' : '',
    a: 'article-act', data: { id: article.id, action },
  }));
  const dupes = article.duplicates || [];
  const draft = view.edit || {};
  const value = (key) => (draft[key] !== undefined ? draft[key] : article[key] ?? '');
  const reviewed = draft.reviewed_level !== undefined ? draft.reviewed_level : article.reviewed_level || '';

  const processed = block({
    title: t('rdProcessed'),
    pills: [],
    actions: [],
    body: html`<div class="a-form">
      ${formFields([
        { id: 'title', kind: 'text', label: t('rdFieldTitle'), span: true, value: value('title'), readOnly: !editable },
        { id: 'topic', kind: 'text', label: t('rdFieldTopic'), value: value('topic'), placeholder: t('rdTopicHint'), readOnly: !editable },
      ])}
      <div class="a-field"><div class="a-field__label"><span>${t('rdFieldEstimated')}</span></div><div class="a-fact">${article.estimated_level || '—'}<small>${article.estimated_level_confidence != null ? t('rdConfidence', { n: Math.round(article.estimated_level_confidence * 100) }) : ''}</small></div></div>
      <div class="a-field"><div class="a-field__label"><span>${t('rdFieldTime')}</span></div><div class="a-fact">${t('rdMinutes', { n: readingMinutes(article.reading_time_seconds) })}<small>${t('rdWords', { n: num(article.word_count, ui) })}</small></div></div>
      ${formFields([
        { id: 'reviewed_level', kind: 'seg', label: t('rdFieldReviewed'), span: true, options: [{ id: '', label: t('rdKeepEstimate'), on: reviewed === '' }, ...levelOptions(article.language).map((level) => ({ id: level, label: level, on: reviewed === level, disabled: !editable }))], disabledAll: !editable },
        { id: 'body', kind: 'area', label: t('rdFieldBody'), span: true, rows: 12, value: value('body'), readOnly: !editable },
      ])}
    </div>
    <div class="a-attribution">${t('rdAttribution')} · ${source.author || '—'}${source.rights?.license_note ? ` · ${source.rights.license_note}` : ''}</div>
    ${editable ? html`<div class="a-actions a-actions--end">${button({ label: view.dirty ? t('rdSaveChanges') : t('rdSaved'), kind: 'primary', a: 'save-article', disabled: !view.dirty || view.busy })}</div>` : ''}
    ${view.editError ? html`<div class="a-error" role="alert">${view.editError}</div>` : ''}`,
  });

  const targetRows = targets.map((target, index) => html`<div class="a-target" data-state="${target.admin_rejected ? 'dropped' : target.admin_approved ? 'kept' : 'suggested'}">
    <div class="a-target__order"><button type="button" class="a-iconbtn" data-a="target-move" data-id="${target.id}" data-dir="-1" aria-label="${t('rdMoveUp')}"${raw(!editable || index === 0 ? ' disabled' : '')}>${raw(icon('chevron-up', { size: 16 }))}</button><button type="button" class="a-iconbtn" data-a="target-move" data-id="${target.id}" data-dir="1" aria-label="${t('rdMoveDown')}"${raw(!editable || index === targets.length - 1 ? ' disabled' : '')}>${raw(icon('chevron-down', { size: 16 }))}</button></div>
    <div class="a-target__body"><div class="a-target__head"><span class="a-target__text">${target.text}</span>${pill({ label: t.has(`rdKind_${target.target_type}`) ? t(`rdKind_${target.target_type}`) : target.target_type, tone: 'mute' })}${pill(target.admin_rejected ? { label: t('rdTargetDropped'), tone: 'err' } : target.admin_approved ? { label: t('rdTargetKept'), tone: 'ok' } : { label: t('rdTargetSuggested'), tone: 'info' })}</div>${target.context ? html`<div class="a-target__ctx">“${target.context}”</div>` : ''}${target.meaning ? html`<div class="a-target__meaning">${target.meaning}</div>` : ''}</div>
    <div class="a-target__acts">${target.admin_rejected
      ? button({ label: t('rdTargetRestore'), size: 'xs', a: 'target-decide', data: { id: target.id, approved: '1' }, disabled: !editable })
      : [button({ label: target.admin_approved ? t('rdTargetKept') : t('rdTargetKeep'), size: 'xs', a: 'target-decide', data: { id: target.id, approved: '1' }, disabled: !editable || target.admin_approved }), button({ label: t('rdTargetDrop'), size: 'xs', a: 'target-decide', data: { id: target.id, approved: '0' }, disabled: !editable })]}</div>
  </div>`);
  const nt = view.newTarget || { text: '', type: 'word', meaning: '' };
  const targetsBlock = block({
    title: t('rdTargets'),
    pills: [{ label: t('rdTargetSummary', { kept: targets.filter((x) => !x.admin_rejected).length, dropped: targets.filter((x) => x.admin_rejected).length }), tone: 'mute' }],
    body: html`${targets.length ? html`<div class="a-targets">${targetRows}</div>` : html`<div class="a-qempty"><div class="a-qempty__title">${t('rdNoTargets')}</div></div>`}
      ${editable ? html`<div class="a-addtarget"><input class="a-input" name="nt_text" value="${nt.text}" placeholder="${t('rdNtWord')}" data-a-input="nt_text" aria-label="${t('rdNtWord')}"><select class="a-input" name="nt_type" data-a-input="nt_type" aria-label="${t('rdFieldKind')}">${kinds.map((kind) => html`<option value="${kind}"${raw(nt.type === kind ? ' selected' : '')}>${t(`rdKind_${kind}`)}</option>`)}</select><input class="a-input" name="nt_meaning" value="${nt.meaning}" placeholder="${t('rdNtMeaning')}" data-a-input="nt_meaning" aria-label="${t('rdNtMeaning')}">${button({ label: `+ ${t('rdNtAdd')}`, a: 'target-add', size: 'sm', disabled: !nt.text.trim() })}</div>${view.targetError ? html`<div class="a-error" role="alert">${view.targetError}</div>` : ''}` : ''}`,
  });

  const published = article.status === 'published';
  const supportOptions = ['en', 'vi', 'zh'].map((code) => ({ id: code, label: langName(t, code), on: (view.support || 'en') === code }));
  const setsBlock = block({
    title: t('csTitle'),
    sub: t('csSub'),
    actions: [{ label: view.generating ? t('csGenerating') : t('csGenerate'), kind: 'primary', size: 'sm', a: 'set-generate', disabled: !published || view.generating, tip: published ? '' : t('csNeedsPublished') }],
    body: html`${published ? html`<div class="a-field"><div class="a-field__label"><span>${t('csSupport')}</span></div><div class="a-seg" role="group">${supportOptions.map((option) => html`<button type="button" class="a-seg__option" data-a="pick" data-field="support" data-value="${option.id}" aria-pressed="${option.on ? 'true' : 'false'}"${raw(view.generating ? ' disabled' : '')}><span>${option.label}</span></button>`)}</div></div>` : html`<div class="a-hint">${t('csNeedsPublished')}</div>`}
      ${view.setError ? html`<div class="a-error" role="alert">${view.setError}</div>` : ''}
      ${view.generating ? html`<div class="a-status" role="status">${t('csGeneratingText')}</div>` : ''}
      ${rowList((sets || []).map((set) => ({
        title: t('csName', { language: langName(t, set.support_language) }),
        meta: t('csMeta', { n: set.questions.length, model: set.model || '—', when: relative(set.created_at, ui, now) }),
        pills: [...(setIsStale(set) && set.status !== 'stale' ? [{ label: t('csArticleChanged'), tone: 'warn' }] : []), setPill(t, set.status)],
        go: href('adminSet', { id: set.id }),
      })), { title: t('csNone'), text: '' })}`,
  });

  const originalBlock = block({
    title: t('rdOriginal'),
    pills: [{ label: t('rdReadOnly'), tone: 'mute' }],
    body: html`<div class="a-original__title">${source.title || '—'}</div>
      ${kv([
        { key: t('rdFieldAuthor'), value: source.author || '—' },
        { key: t('rdFieldUrl'), value: source.canonical_url || t('rdPasted'), mono: Boolean(source.canonical_url) },
        { key: t('rdFieldDate'), value: source.published_at ? dateShort(source.published_at, ui) : '—' },
        { key: t('rdFieldSourceName'), value: source.metadata?.source_name || '—' },
        { key: t('rdFieldLicense'), value: source.rights?.license_note || '—' },
      ])}
      <div class="a-text a-text--original">${source.body || ''}</div>`,
  });
  const evOpen = Boolean(view.evOpen);
  const evidenceBlock = block({
    body: html`<button type="button" class="a-disclose" data-a="toggle-evidence" aria-expanded="${evOpen ? 'true' : 'false'}"><span class="a-disclose__title">${t('rdEvidence')}</span><span class="a-disclose__sum">${(article.analysis?.quality_issues || []).length ? t('rdEvIssuesCount', { n: article.analysis.quality_issues.length }) : t('rdEvClean')}${raw(icon(evOpen ? 'chevron-up' : 'chevron-down', { size: 16 }))}</span></button>
      ${evOpen ? kv(evidenceFields(t, article, ui).map(([key, val]) => ({ key, value: val }))) : ''}
      ${evOpen ? rowList((article.events || []).slice(0, 8).map((event) => ({ title: t.has(`rdEvent_${event.action}`) ? t(`rdEvent_${event.action}`) : event.action, meta: `${event.actor || '—'} · ${dateTime(event.created_at, ui)}`, detail: event.reason || '' })), { title: t('rdNoEvents'), text: '' }) : ''}`,
  });

  const dtabs = ['article', 'targets', 'original', 'evidence'];
  return {
    title: t('rdTitle'),
    crumb: article.title,
    markup: html`<section class="a-page a-detail" data-screen-label="A17 Reading review detail" data-dtab="${dtab}">
      ${html`<button type="button" class="a-back" data-go="${href('adminQueue', {}, { tab: tabOf(article.status) })}">${raw(icon('chevron-left', { size: 18 }))}${t(TAB_TITLE[tabOf(article.status)][0].replace('rdQTitle', 'rdTab'))}</button>`}
      <div class="a-sticky"><div class="a-sticky__text"><div class="a-pills">${pill(status)}${article.status === 'published' ? html`<a class="a-learnerlink" href="${learnerAddress('reading', article.id)}">${t('rdOpenAsLearner')}</a>` : ''}</div><h1 class="a-detail__title">${article.title}</h1></div><div class="a-sticky__acts">${actionButtons.map(button)}</div></div>
      ${view.actionError ? html`<div class="a-error" role="alert">${view.actionError}</div>` : ''}
      ${blockers.length && !isLive ? banner({ tone: 'err', title: t('rdBlockedTitle'), text: t('rdBlockedText'), }) : ''}
      <div class="a-rights"><div class="a-rights__text"><div class="a-rights__label">${t('rdRights')}</div><div class="a-rights__note">${t(rightsAdviceKey(blockers))}</div>${blockers.length ? html`<ul class="a-rights__list">${blockers.map((blocker) => html`<li>${t(`rdWarn_${blocker.code}`)}</li>`)}</ul>` : ''}${article.automation ? html`<div class="a-rights__note">${t('rdAutoEffective', { value: t(article.automation.allowed ? 'rdAnswerAllowed' : 'rdAnswerDenied'), origin: t(article.automation.origin === 'article' ? 'rdAutoFromArticle' : 'rdAutoFromSource') })}</div>` : ''}${article.rights_review ? html`<div class="a-rights__note">${t('rdRightsAnsweredBy', { who: article.rights_review.actor || '—', when: dateShort(article.rights_review.at, ui) })}</div>` : ''}</div>
        <div class="a-rights__edit">${rightsEditor(t, state, view.rightsDraft || {}, article.automation)}${view.rightsError ? html`<div class="a-error" role="alert">${view.rightsError}</div>` : ''}<div class="a-actions a-actions--end">${button({ label: view.rightsDirty ? t('rdRightsSave') : t('rdRightsSaved'), kind: 'primary', size: 'sm', a: 'rights-save', disabled: !view.rightsDirty || view.busy })}</div></div></div>
      ${dupes.length ? banner({ tone: 'warn', title: t('rdDupTitle'), text: t('rdDupText', { sources: dupes.map((copy) => copy.source_name || copy.source_slug || copy.source_id).join(', ') }) }) : ''}
      <div class="a-dtabs">${chipRow({ options: dtabs.map((id) => ({ id, label: id === 'targets' ? `${t('rdDtab_targets')} · ${targets.length}` : t(`rdDtab_${id}`), on: dtab === id })), a: 'dtab' })}</div>
      <div class="a-detail__grid">
        <div class="a-detail__col"><div data-part="processed">${processed}</div><div data-part="targets">${targetsBlock}</div><div data-part="sets">${setsBlock}</div></div>
        <div class="a-detail__col"><div data-part="original">${originalBlock}</div><div data-part="evidence">${evidenceBlock}</div></div>
      </div>
      <div class="a-detail__foot">${actionButtons.map(button)}</div>
    </section>`,
  };
}

/* A field grid entry with the page's own controls (the blocks' `field` is private to blocks.js). */
function formFields(items) {
  return items.map((item) => {
    if (item.kind === 'seg') {
      return html`<div class="a-field a-field--full"><div class="a-field__label"><span>${item.label}</span></div><div class="a-seg" role="group" aria-label="${item.label}">${item.options.map((option) => html`<button type="button" class="a-seg__option" data-a="edit-pick" data-field="${item.id}" data-value="${option.id}" aria-pressed="${option.on ? 'true' : 'false'}"${raw(option.disabled || item.disabledAll ? ' disabled' : '')}><span>${option.label}</span></button>`)}</div></div>`;
    }
    if (item.kind === 'area') {
      return html`<div class="a-field a-field--full"><div class="a-field__label"><span>${item.label}</span></div><textarea class="a-input a-input--area" name="${item.id}" rows="${item.rows}" data-a-input="${item.id}" aria-label="${item.label}"${raw(item.readOnly ? ' readonly' : '')}>${item.value}</textarea></div>`;
    }
    return html`<div class="a-field${item.span ? ' a-field--full' : ''}"><div class="a-field__label"><span>${item.label}</span></div><input class="a-input" name="${item.id}" value="${item.value}" placeholder="${item.placeholder || ''}" data-a-input="${item.id}" aria-label="${item.label}" autocomplete="off"${raw(item.readOnly ? ' readonly' : '')}></div>`;
  });
}

/* ---- Comprehension set review ------------------------------------------------------------------ */

export function setPage({ set, article, view, t, ui, href }) {
  const progress = setProgress(set);
  const editable = questionsEditable(set);
  const stale = setIsStale(set);
  const actions = setActions(set);
  const decided = progress.approved + progress.rejected;
  const percent = progress.total ? Math.round((decided / progress.total) * 100) : 0;
  const whyKey = { stale: 'csWhyStale', undecided: 'csWhyUndecided', none: 'csWhyNone' };
  const buttons = actions.map((action) => ({
    label: t(`csAct_${action.id}`),
    kind: action.primary ? 'primary' : action.id === 'reject' || action.id === 'discard' ? 'danger' : '',
    a: action.discard ? 'set-discard' : 'set-transition',
    data: action.discard ? {} : { status: action.status, reason: action.reason ? '1' : '' },
    disabled: action.enabled === false || view.busy,
    tip: action.enabled === false ? t(whyKey[action.why] || 'csWhyNone') : '',
  }));
  const visibility = set.status === 'approved' ? t('csLive') : t('csHidden');
  const questions = set.questions.map((question, index) => {
    const state = questionState(question);
    const stateInfo = { approved: { label: t('csQApproved'), tone: 'ok' }, rejected: { label: t('csQRejected'), tone: 'err' }, undecided: { label: t('csQUndecided'), tone: 'mute' } }[state];
    return html`<article class="a-question" data-state="${state}">
      <div class="a-question__head"><div class="a-pills"><span class="a-question__n">Q${index + 1}</span>${pill({ label: t.has(`csType_${question.question_type}`) ? t(`csType_${question.question_type}`) : question.question_type, tone: 'mute' })}</div>${pill(stateInfo)}</div>
      <div class="a-question__prompt">${question.prompt}</div>
      <div class="a-options">${question.options.map((option, optionIndex) => html`<div class="a-option" data-correct="${optionIndex === question.correct_index ? '1' : '0'}"><span class="a-option__mark">${String.fromCharCode(65 + optionIndex)}</span><span class="a-option__text">${option}</span>${optionIndex === question.correct_index ? html`<span class="a-option__tag">${t('csCorrect')}</span>` : ''}</div>`)}</div>
      ${question.explanation ? html`<div class="a-question__why"><b>${t('csExplanation')}</b> ${question.explanation}</div>` : ''}
      ${question.evidence_text ? html`<div class="a-question__evidence"><b>${t('csEvidence')}</b> “${question.evidence_text}”</div>` : ''}
      <div class="a-actions">${[
        button({ label: state === 'approved' ? t('csQApproved') : t('csQApprove'), size: 'xs', kind: state === 'approved' ? 'primary' : '', a: 'question-decide', data: { id: question.id, decision: 'approve' }, disabled: !editable || view.busy || state === 'approved' }),
        button({ label: state === 'rejected' ? t('csQRejected') : t('csQReject'), size: 'xs', kind: state === 'rejected' ? 'danger' : '', a: 'question-decide', data: { id: question.id, decision: 'reject' }, disabled: !editable || view.busy || state === 'rejected' }),
        state !== 'undecided' ? button({ label: t('csQUndo'), size: 'xs', a: 'question-decide', data: { id: question.id, decision: 'undecided' }, disabled: !editable || view.busy }) : '',
      ]}</div>
    </article>`;
  });
  return {
    title: t('rdTitle'),
    crumb: t('csTitle'),
    markup: html`<section class="a-page" data-screen-label="Comprehension set review">
      <button type="button" class="a-back" data-go="${href('adminArticle', { id: set.article_id })}">${raw(icon('chevron-left', { size: 18 }))}${article?.title || t('rdTitle')}</button>
      <div class="a-sticky"><div class="a-sticky__text"><div class="a-pills">${pill(setPill(t, set.status))}<span class="a-sticky__meta">${t('csMeta', { n: set.questions.length, model: set.model || '—', when: '' }).replace(/ · $/, '')}</span></div><h1 class="a-detail__title">${t('csName', { language: langName(t, set.support_language) })}</h1><p class="a-sub">${visibility}</p></div><div class="a-sticky__acts">${buttons.map(button)}</div></div>
      ${view.error ? html`<div class="a-error" role="alert">${view.error}</div>` : ''}
      ${stale ? banner({ tone: 'warn', title: t('csStaleTitle'), text: t('csStaleText'), actions: [{ label: t('csRegenerate'), size: 'sm', a: 'set-regenerate' }] }) : ''}
      <div class="a-progress"><div class="a-progress__bar"><span style="width:${percent}%"></span></div><span class="a-progress__text">${t('csProgress', { done: decided, total: progress.total, approved: progress.approved })}</span></div>
      <div class="a-questions">${questions}</div>
    </section>`,
  };
}

/* ---- A21 add content --------------------------------------------------------------------------- */

export function addPage({ view, t, href }) {
  const mode = view.mode || 'url';
  const modes = ['url', 'text', 'file'];
  const rights = view.rights || '';
  const risky = rights !== 'allowed';
  const adapt = view.adapt || '';
  const attribution = view.attribution || '';
  const fields = [];
  if (mode === 'url') fields.push({ id: 'url', kind: 'text', label: t('addUrl'), span: true, value: view.url || '', placeholder: 'https://…' });
  if (mode === 'text') {
    fields.push({ id: 'title', kind: 'text', label: t('rdFieldTitle'), span: true, value: view.title || '' });
    fields.push({ id: 'body', kind: 'area', label: t('rdFieldBody'), span: true, rows: 10, value: view.body || '' });
  }
  if (mode === 'file') {
    fields.push({ id: 'file', kind: 'file', label: t('addFile'), span: true, fileLabel: view.file ? view.file.name : t('addChooseFile'), accept: t('addFileAccept'), acceptAttr: '.txt,.md,.html,.htm' });
    fields.push({ id: 'title', kind: 'text', label: t('rdFieldTitle'), span: true, value: view.title || '' });
  }
  fields.push({ id: 'language', kind: 'seg', label: t('addLanguage'), options: [{ id: 'auto', label: t('addAuto'), on: (view.language || 'auto') === 'auto' }, { id: 'en', label: t('langEn'), on: view.language === 'en' }, { id: 'zh', label: t('langZh'), on: view.language === 'zh' }] });
  fields.push({ id: 'source', kind: 'text', label: mode === 'url' ? t('addSourceOptional') : t('rdFieldSourceName'), value: view.source || '', placeholder: t('addSourceHint') });
  fields.push({ id: 'author', kind: 'text', label: t('rdFieldAuthor'), value: view.author || '' });
  if (mode === 'text') fields.push({ id: 'sourceUrl', kind: 'text', label: t('addSourceUrl'), value: view.sourceUrl || '' });
  fields.push({ id: 'rights', kind: 'seg', label: t('rdRights'), span: true, options: [{ id: '', label: t('addRightsUnknown'), on: rights === '' }, { id: 'allowed', label: t('rdAnswerAllowed'), on: rights === 'allowed' }, { id: 'denied', label: t('rdAnswerDenied'), on: rights === 'denied' }], hint: risky ? t('addRiskNote') : '', hintTone: risky ? 'warn' : '' });
  fields.push({ id: 'adapt', kind: 'seg', label: t('rdQ_can_adapt'), options: [{ id: '', label: t('addRightsUnknown'), on: adapt === '' }, { id: 'allowed', label: t('rdAnswerAllowed'), on: adapt === 'allowed' }, { id: 'denied', label: t('rdAnswerDenied'), on: adapt === 'denied' }] });
  fields.push({ id: 'attribution', kind: 'seg', label: t('rdQ_attribution_required'), options: [{ id: '', label: t('addRightsUnknown'), on: attribution === '' }, { id: 'required', label: t('rdAnswerRequired'), on: attribution === 'required' }, { id: 'not_required', label: t('rdAnswerNotRequired'), on: attribution === 'not_required' }] });
  fields.push({ id: 'license', kind: 'text', label: t('addLicense'), span: true, value: view.license || '', placeholder: t('addLicenseHint') });
  const last = view.last;
  return {
    title: t('addTitle'),
    markup: html`<section class="a-page a-page--narrow" data-screen-label="A21 Add reading content">
      ${pageHead({ back: { href: href('adminReading'), label: t('rdTitle') }, title: t('addTitle'), sub: t('addSub') })}
      ${chipRow({ options: modes.map((id) => ({ id, label: t(`addMode_${id}`), on: mode === id })), a: 'add-mode' })}
      <div class="a-blocks a-blocks--one">${formBlock({ span: true, fields, error: view.error || '', status: view.busy ? t('saving') : '', actions: [{ label: t('addSubmit'), kind: 'primary', a: 'add-submit', disabled: view.busy }] })}</div>
      ${last ? html`<div class="a-success" role="status"><span class="a-success__icon" aria-hidden="true">${raw(icon('check', { size: 18 }))}</span><div class="a-success__text"><div class="a-success__title">${t('addSubmitted', { title: last.title })}</div><div class="a-success__body">${t('addSubmittedText')}</div></div><div class="a-actions">${[
        button({ label: t('addAnother'), size: 'sm', a: 'add-another' }),
        button({ label: t('addViewJob'), size: 'sm', a: 'go', data: { to: href('adminJob', { id: last.id }) } }),
        button({ label: t('addClose'), size: 'sm', a: 'go', data: { to: href('adminReading') } }),
      ]}</div></div>` : ''}
    </section>`,
  };
}

/* ---- A22-A23 sources ---------------------------------------------------------------------------- */

const SOURCE_PILL = {
  active: ['srcActive', 'ok'], approved: ['srcApproved', 'ok'], paused: ['srcPaused', 'warn'], blocked: ['srcBlocked', 'err'],
  archived: ['srcArchived', 'mute'], needs_review: ['srcNeedsReview', 'info'], rejected: ['srcRejected', 'err'],
};
const sourcePill = (t, state) => { const [label, tone] = SOURCE_PILL[state] || SOURCE_PILL.needs_review; return { label: t(label), tone }; };

function sourceActions(t, source, detail = false) {
  const id = source.id;
  const act = (state, label, kind = '') => ({ label, kind, size: detail ? 'md' : 'xs', a: 'source-state', data: { id, state } });
  switch (source.state) {
    case 'active': return [act('paused', t('srcPause')), ...(detail ? [act('blocked', t('srcBlock'), 'danger'), act('archived', t('srcArchive'), 'danger')] : [])];
    case 'paused': case 'approved': return [act('active', t('srcResume')), ...(detail ? [act('blocked', t('srcBlock'), 'danger'), act('archived', t('srcArchive'), 'danger')] : [])];
    case 'needs_review': return [act('active', t('srcApprove'), 'primary')];
    case 'blocked': return [act('paused', t('srcUnblock'))];
    case 'archived': return [act('paused', t('srcRestore'))];
    default: return [];
  }
}

export function sourcesPage({ sources, view, t, ui, href }) {
  const needle = String(view.q || '').trim().toLowerCase();
  const shown = (sources || []).filter((source) => !needle || `${source.name} ${source.base_url} ${source.slug}`.toLowerCase().includes(needle));
  return {
    title: t('rdTitle'),
    markup: html`<section class="a-page" data-screen-label="A22 Reading sources">
      ${pageHead({ back: { href: href('adminReading'), label: t('rdTitle') }, title: t('srcTitle'), sub: t('srcSub'), actions: [{ label: t('srcRegister'), kind: 'primary', a: 'go', data: { to: href('adminImportSource') } }] })}
      <div class="a-blocks">${block({ span: true, flat: true, body: rowList(shown.map((source) => ({
        tile: (source.name || '?')[0].toUpperCase(),
        title: source.name,
        meta: [source.base_url || source.slug, t.has(`srcType_${source.source_type}`) ? t(`srcType_${source.source_type}`) : source.source_type, source.last_checked_at ? t('srcChecked', { when: relative(source.last_checked_at, ui) }) : t('srcNeverChecked')].join(' · '),
        pills: [rightsPill(t, source.rights?.can_republish ? 'allowed' : 'unknown'), sourcePill(t, source.state)],
        actions: sourceActions(t, source),
        go: href('adminSource', { id: source.id }),
      })), { title: t('srcNone'), text: '' }) })}</div>
    </section>`,
  };
}

export function sourcePage({ source, view, t, ui, href }) {
  const rights = source.rights || {};
  const answer = (value) => (value ? 'allowed' : 'unknown');
  return {
    title: t('rdTitle'),
    crumb: source.name,
    markup: html`<section class="a-page" data-screen-label="A23 Source detail">
      ${pageHead({ back: { href: href('adminSources'), label: t('srcTitle') }, title: source.name, sub: source.base_url || source.slug, pills: [rightsPill(t, rights.can_republish ? 'allowed' : 'unknown'), sourcePill(t, source.state)], actions: sourceActions(t, source, true) })}
      ${view.error ? html`<div class="a-error" role="alert">${view.error}</div>` : ''}
      <div class="a-blocks">
        ${block({ span: true, title: t('srcFacts'), body: metrics([
          { label: t('srcFactType'), value: t.has(`srcType_${source.source_type}`) ? t(`srcType_${source.source_type}`) : source.source_type },
          { label: t('srcFactLanguages'), value: (source.languages || []).map((code) => langName(t, code)).join(', ') || '—' },
          { label: t('srcFactChecked'), value: source.last_checked_at ? relative(source.last_checked_at, ui) : '—' },
          { label: t('srcFactSuccess'), value: source.last_success_at ? relative(source.last_success_at, ui) : '—' },
        ], { columns: 4 }) })}
        ${block({ title: t('srcRights'), sub: t('srcRightsSub'), body: kv([
          { key: t('rdQ_can_republish'), value: t(RIGHT_ANSWER[answer(rights.can_republish)]), tone: rights.can_republish ? 'ok' : 'warn' },
          { key: t('rdQ_can_adapt'), value: t(RIGHT_ANSWER[answer(rights.can_adapt)]), tone: rights.can_adapt ? 'ok' : 'warn' },
          { key: t('rdQ_automation_allowed'), value: t(RIGHT_ANSWER[answer(rights.automation_allowed)]), tone: rights.automation_allowed ? 'ok' : 'warn' },
          { key: t('rdQ_attribution_required'), value: t(rights.attribution_required ? 'rdAnswerRequired' : 'rdAnswerNotRequired') },
          { key: t('rdFieldLicense'), value: rights.license_note || '—' },
        ]) })}
        ${block({ title: t('srcPolling'), pills: [{ label: t('pillFuture'), tone: 'fut' }], body: html`<div class="a-hint">${t('srcPollingText')}</div>` })}
        ${source.last_error ? block({ title: t('srcLastError'), body: html`<div class="a-text a-text--mono">${source.last_error}</div>` }) : ''}
      </div>
    </section>`,
  };
}

/* ---- the learner preview panel -------------------------------------------------------------------- */

export function previewBody(article) {
  return html`<div class="a-serif">${String(article.body || '').split('\n\n').map((paragraph) => html`<p>${paragraph}</p>`)}</div>`;
}

export function loadFailedBlock(t) {
  return html`<div class="a-blocks">${stateBlock({ span: true, kind: 'error', heading: t('loadFailedTitle'), text: t('loadFailedText'), actions: [{ label: t('retry'), kind: 'primary', size: 'sm', a: 'reload' }] })}</div>`;
}

export { textBlock };
