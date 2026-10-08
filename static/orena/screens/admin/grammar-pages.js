/* Grammar in Platform Admin (proposals/ADMIN_GRAMMAR_UI.md, layout approved 2026-10-08): the page builders and the
   pure rules behind them. Composed only from the accepted Admin patterns - the Content packs page for the import
   (G2), the Reading queue for the review queue (G3), the Reading review detail for a point (G4) - and the shared
   blocks; the point preview is the learner's own Grammar Concept page (conceptPreviewMarkup). The wiring is
   grammar.js (G3, G4) and imports.js (G2); scripts/test_orena_screen_admin_grammar.mjs checks the rules. */
import { html } from '../../kit/html.js';
import { dateShort, dateTime, num } from '../../capabilities/admin-format.js';
import { contractText, levelCode } from '../../product/grammar-source.js';
import { banner, block, button, chipRow, formBlock, kv, metrics, pageHead, pill, rowList, searchField, stateBlock, tabs } from './blocks.js';

export const GRAMMAR_TABS = Object.freeze(['review', 'accepted', 'published', 'rejected', 'archived']);
export const GRAMMAR_LANGUAGES = Object.freeze(['en', 'zh']);
export const PLAN_PREVIEW = 20;

const REVIEW_TONE = { imported: 'info', accepted: 'ok', rejected: 'err' };
const RIGHTS_TONE = { cleared: 'ok', unknown: 'warn', restricted: 'err' };
const LIFE_TONE = { published: 'ok', unpublished: 'mute', archived: 'mute' };
const PLAN_TONE = { new: 'info', changed: 'warn', unchanged: 'mute', refused: 'err', unlisted: 'mute' };

/* ---- pure rules ------------------------------------------------------------------------------------------------ */

/* Which queue tab a point belongs to, from its lifecycle and its newest version. */
export function tabOf(point) {
  const latest = point?.latest_version || {};
  if (point?.lifecycle === 'archived') return 'archived';
  if (point?.lifecycle === 'published') return 'published';
  if (latest.review_status === 'imported') return 'review';
  if (latest.review_status === 'rejected') return 'rejected';
  return 'accepted';
}

export function tabCounts(points) {
  const counts = Object.fromEntries(GRAMMAR_TABS.map((tab) => [tab, 0]));
  for (const point of points || []) counts[tabOf(point)] += 1;
  return counts;
}

/* The rows a tab shows, after the level chip and the search needle (native title, title, sub, id). */
export function shownPoints(points, { tab, level = 'all', q = '', ui = 'en' } = {}) {
  const needle = String(q || '').trim().toLowerCase();
  return (points || []).filter((point) => tabOf(point) === tab
    && (level === 'all' || levelCode(point.level) === level)
    && (!needle || [point.id, point.header?.native_title, contractText(point.header?.title, ui), contractText(point.header?.sub, ui)]
      .join(' ').toLowerCase().includes(needle)));
}

/* "Publish accepted": every accepted point of the language, by its newest version - the whole language at once, not
   only the rows a filter shows (decision 2026-10-08: publish per learning language). */
export function publishableItems(points) {
  return (points || []).filter((point) => tabOf(point) === 'accepted' && point.latest_version?.review_status === 'accepted')
    .map((point) => ({ point_id: point.id, version_id: point.latest_version.id }));
}

/* What can be done to a point from its review page. */
export function pointActions(point) {
  const versions = point?.versions || [];
  const latest = versions[versions.length - 1] || {};
  const actions = [];
  if (point?.lifecycle === 'archived') return ['restore'];
  if (latest.review_status === 'imported') actions.push('accept', 'reject');
  if (latest.review_status === 'accepted' && !latest.is_published) actions.push('publish');
  if (point?.lifecycle === 'published') actions.push('unpublish');
  if (point?.lifecycle !== 'published') actions.push('archive');
  if (latest.rights_status === 'cleared') actions.push('restrict');
  else if (latest.rights_status === 'restricted') actions.push('clear');
  return actions;
}

/* Why Publish is not available yet, in the order the server checks it. */
export function publishBlockers(point) {
  const versions = point?.versions || [];
  const latest = versions[versions.length - 1] || {};
  const blockers = [];
  if (latest.review_status !== 'accepted') blockers.push('grNeedsAccept');
  if (latest.rights_status !== 'cleared') blockers.push('grNeedsRights');
  return blockers;
}

/* ---- shared pieces --------------------------------------------------------------------------------------------- */

const reviewPill = (t, status) => ({ label: t(`grReview_${status}`), tone: REVIEW_TONE[status] || 'mute' });
const rightsPill = (t, status) => ({ label: t(`grRights_${status}`), tone: RIGHTS_TONE[status] || 'mute' });
const lifePill = (t, status) => ({ label: t(`grLife_${status}`), tone: LIFE_TONE[status] || 'mute' });
const languageLabel = (t, code) => t(code === 'zh' ? 'langZh' : 'langEn');

function titleOf(point, ui) {
  return point?.header?.native_title || contractText(point?.header?.title, ui) || point?.id || '';
}

/* ---- G2: import a Grammar Lab package (Imports) -------------------------------------------------------------- */

export function importPage({ grammar, t, ui, href }) {
  const check = grammar.check;
  const result = grammar.result;
  const fileBlock = formBlock({
    span: true,
    title: t('grImpPackage'),
    fields: [{ id: 'grammarFile', kind: 'file', label: t('grImpFile'), span: true, fileLabel: grammar.file ? grammar.file.name : t('grImpChoose'), accept: t('grImpAccept'), acceptAttr: '.zip,application/zip' }],
    actions: [{ label: grammar.checking ? t('impChecking') : t('grImpCheck'), kind: check ? '' : 'primary', a: 'grammar-check', disabled: !grammar.file || grammar.checking || grammar.importing }],
  });
  const blocks = [fileBlock];
  if (grammar.error) blocks.push(stateBlock({ span: true, kind: 'error', heading: grammar.error }));
  if (check && !result) {
    const counts = check.diff?.counts || {};
    const passed = Boolean(check.ok && check.validator?.passed);
    if (check.already_imported) {
      blocks.push(html`<div class="a-block a-block--full a-block--flat">${banner({ tone: 'info', title: t('grImpAlready'), text: t('grImpAlreadyText', { when: dateTime(check.already_imported.created_at, ui) }), actions: [{ label: t('grImpReview'), a: 'go', data: { to: href('adminGrammar', {}, { language: check.language }) } }] })}</div>`);
    }
    blocks.push(block({
      span: true,
      title: t('grImpPlan'),
      pills: [{ label: passed ? t('grImpPassed') : t('grImpFailed'), tone: passed ? 'ok' : 'err' }],
      body: html`${kv([
        { key: t('grImpLanguage'), value: languageLabel(t, check.language) },
        { key: t('grImpSet'), value: check.set_version || '—', mono: true },
        { key: t('grImpPoints'), value: num(check.point_count ?? 0, ui) },
        { key: t('grImpHash'), value: String(check.package_hash || '').slice(0, 16), mono: true },
      ])}
      ${metrics(['new', 'changed', 'unchanged', 'refused'].map((state) => ({ label: t(`grImpState_${state}`), value: num(counts[state] ?? 0, ui), tone: state === 'refused' && counts[state] ? 'err' : '' })), { columns: 4 })}
      ${planRows(t, check, grammar.showAll)}`,
    }));
    if (check.problems?.length) {
      blocks.push(block({ span: true, title: t('grImpProblems'), sub: t('grImpProblemsText'), body: rowList(check.problems.slice(0, 50).map((problem) => ({ title: problem.code || String(problem), meta: problem.point_id || problem.path || '', detail: problem.message || '' }))) }));
    }
    if (!check.already_imported && passed) {
      blocks.push(formBlock({
        span: true,
        title: t('grImpRights'),
        fields: [
          { id: 'basis', kind: 'seg', label: t('grImpBasis'), options: ['orena_original', 'licensed', 'other'].map((id) => ({ id, label: t(`grBasis_${id}`), on: grammar.basis === id })) },
          { id: 'attestation', label: t('grImpAttest'), value: grammar.attestation, hint: t('grImpAttestHint'), span: true },
        ],
        actions: [{ label: grammar.importing ? t('impImporting') : t('grImpAction'), kind: 'primary', a: 'grammar-import', disabled: grammar.importing || !grammar.attestation.trim() }],
      }));
    }
  }
  if (result) {
    const counts = result.batch?.counts || {};
    blocks.push(html`<div class="a-block a-block--full a-block--flat">${banner({ tone: 'ok', title: t('grImpDone'), text: t('grImpDoneText', { n: num((counts.new ?? 0) + (counts.changed ?? 0), ui) }), actions: [{ label: t('grImpReview'), kind: 'primary', a: 'go', data: { to: href('adminGrammar', {}, { language: result.batch?.language || 'en' }) } }] })}</div>`);
    blocks.push(block({ span: true, title: t('impPackResult'), body: metrics(['new', 'changed', 'unchanged', 'refused'].map((state) => ({ label: t(`grImpState_${state}`), value: num(counts[state] ?? 0, ui) })), { columns: 4 }) }));
  }
  return {
    title: t('impTitle'),
    markup: html`<section class="a-page" data-screen-label="Grammar packages">
      ${pageHead({ back: { href: href('adminImports'), label: t('impTitle') }, title: t('grImp'), sub: t('grImpSub') })}
      <div class="a-blocks">${blocks}</div>
    </section>`,
  };
}

function planRows(t, check, showAll) {
  const points = check.diff?.points || [];
  if (!points.length) return '';
  const order = { refused: 0, changed: 1, new: 2, unchanged: 3 };
  const sorted = [...points].sort((a, b) => (order[a.state] ?? 4) - (order[b.state] ?? 4));
  const shown = showAll ? sorted : sorted.slice(0, PLAN_PREVIEW);
  return html`${rowList(shown.map((item) => ({ title: item.id, meta: item.reason || item.code || '', pills: [{ label: t(`grImpState_${item.state}`), tone: PLAN_TONE[item.state] || 'mute' }] })))}
    ${sorted.length > PLAN_PREVIEW ? html`<div class="a-more">${button({ label: showAll ? t('grImpShowFewer') : t('grImpShowAll', { n: sorted.length }), a: 'grammar-show-all', size: 'sm' })}</div>` : ''}`;
}

/* ---- G3: the review queue (Content) ------------------------------------------------------------------------- */

function rowActions(t, point, tab, href) {
  const open = { label: t('rdReview'), kind: tab === 'review' || tab === 'accepted' ? 'primary' : '', a: 'go', data: { to: href('adminGrammarPoint', { id: point.id }) } };
  const preview = { label: t('rdPreview'), a: 'grammar-preview', data: { id: point.id } };
  const act = (action, label, kind = '') => ({ label, kind, a: 'grammar-act', data: { id: point.id, action } });
  if (tab === 'review') return [preview, open, act('accept', t('grAccept'))];
  if (tab === 'accepted') return [preview, open, act('publish', t('grPublish'))];
  if (tab === 'published') return [preview, open, act('unpublish', t('grUnpublish'))];
  if (tab === 'rejected') return [preview, open];
  return [preview, act('restore', t('grRestore'), 'primary')];
}

export function queuePage({ points, view, t, ui, href, loading, busy }) {
  const tab = view.tab;
  const counts = tabCounts(points);
  const levels = ['all', ...[...new Set((points || []).filter((point) => tabOf(point) === tab).map((point) => levelCode(point.level)).filter(Boolean))]];
  const shown = shownPoints(points, { tab, level: view.level, q: view.q, ui });
  const publishable = publishableItems(points);
  const batch = tab === 'review' && shown.length
    ? button({ label: t('grAcceptAll', { n: num(shown.length, ui) }), kind: 'primary', size: 'sm', a: 'grammar-accept-all', disabled: Boolean(busy) })
    : tab === 'accepted' && publishable.length
      ? button({ label: t('grPublishAll', { n: num(publishable.length, ui) }), kind: 'primary', size: 'sm', a: 'grammar-publish-all', disabled: Boolean(busy) })
      : '';
  const rows = shown.map((point) => {
    const latest = point.latest_version || {};
    const sub = contractText(point.header?.sub, ui) || contractText(point.header?.title, ui);
    return html`<div class="a-qrow">
      <button type="button" class="a-qrow__main" data-go="${href('adminGrammarPoint', { id: point.id })}"><span class="a-qrow__title" lang="${point.language === 'zh' ? 'zh' : 'en'}">${titleOf(point, ui)}</span><span class="a-qrow__meta">${[sub, point.id].filter(Boolean).join(' · ')}</span></button>
      <span class="a-qrow__c1">${levelCode(point.level) || '—'}</span>
      <span class="a-qrow__c2">${latest.version ? t('grVersion', { n: latest.version }) : '—'}</span>
      <span class="a-qrow__pill">${pill(tab === 'review' || tab === 'accepted' ? rightsPill(t, latest.rights_status) : tab === 'published' ? { label: point.published_at ? dateShort(point.published_at, ui) : t('grLive'), tone: 'ok' } : tab === 'rejected' ? reviewPill(t, 'rejected') : lifePill(t, 'archived'))}</span>
      <div class="a-qrow__acts">${rowActions(t, point, tab, href).map(button)}</div>
    </div>`;
  });
  const empty = view.q || view.level !== 'all' ? { title: t('rdNoMatch'), text: t('rdNoMatchText') } : { title: t(`grEmpty_${tab}`), text: tab === 'review' ? t('grEmptyText') : '' };
  return {
    title: t('ctTitle'),
    crumb: t('grTitle'),
    markup: html`<section class="a-page" data-screen-label="Grammar queue">
      ${pageHead({ back: { href: href('adminContent'), label: t('ctTitle') }, title: t('grTitle'), sub: t('grQSub'), actions: [{ label: `+ ${t('grImportAction')}`, a: 'go', data: { to: href('adminImportGrammar') } }] })}
      ${tabs(GRAMMAR_TABS.map((id) => ({ id, label: t(`grTab_${id}`), count: num(counts[id], ui), selected: id === tab })))}
      <div class="a-filters">
        ${chipRow({ options: GRAMMAR_LANGUAGES.map((id) => ({ id, label: languageLabel(t, id), on: view.language === id })), a: 'grammar-language' })}
        ${searchField({ id: 'q', value: view.q || '', placeholder: t('grSearch') })}
        ${chipRow({ options: levels.map((id) => ({ id, label: id === 'all' ? t('rdAll') : id, on: (view.level || 'all') === id })), a: 'level' })}
        ${batch ? html`<div class="a-filters__batch">${batch}</div>` : ''}
      </div>
      ${busy ? html`<div class="a-status" role="status">${busy}</div>` : ''}
      <div class="a-qtable">
        <div class="a-qhead"><span>${t('grColPoint')}</span><span>${t('grColLevel')}</span><span>${t('grColVersion')}</span><span>${t(tab === 'published' ? 'grColPublished' : tab === 'review' || tab === 'accepted' ? 'grColRights' : 'grColStatus')}</span></div>
        ${loading ? html`<div class="a-loading">${t('loading')}</div>` : rows.length ? rows : html`<div class="a-qempty"><div class="a-qempty__title">${empty.title}</div>${empty.text ? html`<div class="a-qempty__text">${empty.text}</div>` : ''}</div>`}
      </div>
    </section>`,
  };
}

/* ---- G4: one point's review page (Content) ----------------------------------------------------------------- */

const ACTION_BUTTON = {
  accept: ['grAccept', 'primary'], reject: ['grReject', 'danger'], publish: ['grPublish', 'primary'], unpublish: ['grUnpublish', ''],
  archive: ['grArchive', 'danger'], restore: ['grRestore', 'primary'], restrict: ['grRestrict', ''], clear: ['grClear', ''],
};

export function pointPage({ point, preview, summary, t, ui, href, busy }) {
  const versions = point.versions || [];
  const latest = versions[versions.length - 1] || {};
  const blockers = publishBlockers(point);
  const actions = pointActions(point).map((action) => {
    const [label, kind] = ACTION_BUTTON[action];
    const blocked = action === 'publish' && blockers.length > 0;
    return { label: t(label), kind, a: 'grammar-act', data: { id: point.id, action }, disabled: Boolean(busy) || blocked, tip: blocked ? t(blockers[0]) : '' };
  });
  const title = summary?.header?.native_title || point.id;
  const sub = [levelCode(summary?.level), contractText(summary?.header?.sub, ui) || contractText(summary?.header?.title, ui), point.id].filter(Boolean).join(' · ');
  const versionRows = [...versions].reverse().map((version) => ({
    title: t('grVersion', { n: version.version }),
    meta: [t('grVersionMeta', { when: dateTime(version.imported_at, ui) }), version.reviewed_by ? t('grReviewedBy', { who: version.reviewed_by }) : ''].filter(Boolean).join(' · '),
    detail: version.review_note || '',
    pills: [reviewPill(t, version.review_status), rightsPill(t, version.rights_status), ...(version.is_published ? [{ label: t('grLive'), tone: 'ok' }] : [])],
  }));
  const eventRows = [...(point.events || [])].reverse().slice(0, 12).map((event) => ({
    title: t.has(`grEvent_${event.action}`) ? t(`grEvent_${event.action}`) : event.action,
    meta: [event.actor, dateTime(event.created_at, ui)].filter(Boolean).join(' · '),
    detail: event.reason || '',
  }));
  const needsBanner = latest.review_status === 'accepted' && !latest.is_published && blockers.length;
  return {
    title: t('ctTitle'),
    crumb: title,
    markup: html`<section class="a-page" data-screen-label="Grammar point review">
      ${pageHead({
        back: { href: href('adminGrammar', {}, { language: point.language }), label: t('grTitle') },
        pills: [lifePill(t, point.lifecycle), reviewPill(t, latest.review_status), rightsPill(t, latest.rights_status)],
        title: html`<span lang="${point.language === 'zh' ? 'zh' : 'en'}">${title}</span>`,
        sub,
        actions,
      })}
      ${needsBanner ? banner({ tone: 'warn', title: t(blockers[0]) }) : ''}
      ${busy ? html`<div class="a-status" role="status">${busy}</div>` : ''}
      <div class="a-blocks">
        ${block({ span: true, title: t('grLearnerView'), sub: t('grLearnerViewSub'), pills: [{ label: t('grVersion', { n: latest.version || 1 }), tone: 'mute' }], body: preview || html`<div class="a-loading">${t('loading')}</div>` })}
        ${block({ title: t('grVersions'), body: rowList(versionRows) })}
        ${block({ title: t('grActivity'), body: rowList(eventRows, { title: t('grNoEvents'), text: '' }) })}
      </div>
    </section>`,
  };
}
