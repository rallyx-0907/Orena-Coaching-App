/* Progress (17-Progress.html, D-091). Six tabs (Overview, Trends, Knowing -> Using, Evidence,
   Rank, History) as local UI state on one route, matching the design's own `pgTab`/`pgIsOverview`
   family - not six routes. Not a focus route (shell/routes.js): a normal scrolling hub page.
   Opens on the tab Profile's own `?tab=history` action link names (model.js `tabFromQuery`,
   case-insensitive), defaulting to Overview otherwise - the same `?tab=` pattern Settings already
   establishes for its own five tabs.

   Real data only (Design Contract rule 40 - see model.js's doc comment for exactly which slots
   have no backend source and why): GET /api/learner-summary for per-domain activity, GET
   /api/library/vocabulary/summary (via product/rank.js) for the rank ladder, and
   essays()/practiceOutcomes()/readingEvidence()/speakingAttempts() plus learner-summary's own
   listening observations for Evidence and History, and GET /api/cross-skill-cue with the due count
   for Overview's "Next" rows (model.js `buildNextRows`). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { emptyMarkup, errorMarkup } from '../../kit/states.js';
import { listRow, segmentedControl } from '../../kit/components.js';
import { langSpan } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { rankSummary } from '../../product/rank.js';
import { t } from './copy.js';
import {
  TABS,
  tabFromQuery,
  buildSkillRows,
  buildKuStages,
  storyFacts,
  buildRank,
  buildWritingEvidence,
  buildReadingEvidence,
  buildSpeakingEvidence,
  buildListeningEvidence,
  mergeEvidence,
  filterEvidence,
  historyGroups,
  resolveMediaEvidence,
  buildNextRows,
} from './model.js';

const TAB_COPY_KEY = { Overview: 'tabOverview', Trends: 'tabTrends', KU: 'tabKU', Evidence: 'tabEvidence', Rank: 'tabRank', History: 'tabHistory' };
const RANGES = ['7d', '30d', '90d'];
const RANGE_COPY_KEY = { '7d': 'range7d', '30d': 'range30d', '90d': 'range90d' };
const EV_FILTERS = ['All', 'listening', 'speaking', 'reading', 'writing', 'review']; // D-152 skill order
const EV_FILTER_COPY_KEY = { All: 'evFilter_All', listening: 'evFilter_listening', speaking: 'evFilter_speaking', review: 'evFilter_review', reading: 'evFilter_reading', writing: 'evFilter_writing' };
/* Badge fill under white ink (--accent-ink): D-093 forbids --accent under white text, so
   "recognized" uses --accent-fill like every other filled control. The other four are not
   --accent and are unaffected. */
const KU_COLOR = { recognized: 'var(--accent-fill)', recalled: 'var(--accent-text)', used: 'var(--skill-listen)', transferred: 'var(--skill-read)', fastRetrieval: 'var(--muted)' };
const KU_LABEL_KEY = { recognized: 'ku_recognized', recalled: 'ku_recalled', used: 'ku_used', transferred: 'ku_transferred', fastRetrieval: 'ku_fastRetrieval' };
const KU_DESC_KEY = { recognized: 'ku_desc_recognized', recalled: 'ku_desc_recalled', used: 'ku_desc_used', transferred: 'ku_desc_transferred', fastRetrieval: 'ku_desc_fastRetrieval' };

function locale() {
  const ui = languages().ui;
  return ui === 'zh' ? 'zh-CN' : ui === 'vi' ? 'vi-VN' : 'en-GB';
}
function formatDate(at) {
  if (!at) return '';
  return new Intl.DateTimeFormat(locale(), { day: 'numeric', month: 'short' }).format(new Date(at));
}
function formatTime(at) {
  if (!at) return '';
  return new Intl.DateTimeFormat(locale(), { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(at));
}

export default async function progressScreen(element, ctx) {
  await useStyles('screens/progress/progress.css');
  const context = ctx.context;
  const state = { tab: tabFromQuery(ctx.query.get('tab')), range: '30d', evFilter: 'All' };
  const cache = { summaries: new Map(), evidence: null, evidenceAll: null, rank: null, activity: null };

  function getSummary(range) {
    if (!cache.summaries.has(range)) cache.summaries.set(range, api.learnerSummary(range));
    return cache.summaries.get(range);
  }
  function getEvidenceAllSummary() {
    if (!cache.evidenceAll) cache.evidenceAll = api.learnerSummary('all');
    return cache.evidenceAll;
  }
  function getEvidenceSources() {
    if (!cache.evidence) {
      cache.evidence = Promise.all([
        api.essays(),
        api.practiceOutcomes(30).then((r) => r?.items || []),
        api.readingEvidence(30).then((r) => r?.items || []),
        api.speakingAttempts(100).then((r) => r?.items || []),
        api.listeningLibrary(context.language),
      ]).then(([essays, outcomes, reading, speaking, library]) => ({ essays, outcomes, reading, speaking, library }));
    }
    return cache.evidence;
  }
  function getActivity() {
    if (!cache.activity) {
      const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
      cache.activity = api.learnerActivity(zone);
    }
    return cache.activity;
  }
  function getRank() {
    if (!cache.rank) cache.rank = api.libraryVocabularySummary();
    return cache.rank;
  }

  async function evidenceItems() {
    const [{ essays, outcomes, reading, speaking, library }, summary] = await Promise.all([getEvidenceSources(), getEvidenceAllSummary()]);
    return resolveMediaEvidence(mergeEvidence({
      writing: buildWritingEvidence(essays, outcomes),
      reading: buildReadingEvidence(reading),
      speaking: buildSpeakingEvidence(speaking),
      listening: buildListeningEvidence(summary),
    }), library);
  }

  function openRoute(item) {
    if (item.domain === 'writing' && item.essayId != null) return ctx.href('writingDraft', { id: item.essayId });
    if (item.domain === 'reading' && item.articleId) return ctx.href('reader', { id: item.articleId.startsWith('article:') ? item.articleId : `article:${item.articleId}` });
    if (item.domain === 'speaking' && item.lessonId) return ctx.href('attempts', { id: `media:${item.lessonId}` }, item.segmentId ? { segment: item.segmentId } : {});
    if (item.domain === 'listening' && item.lessonId) return ctx.href('dictation', { id: item.lessonId }, item.segmentId ? { segment: item.segmentId } : {});
    return '';
  }

  function skillChip(domain) {
    const key = { writing: 'skill_writing', reading: 'skill_reading', speaking: 'skill_speaking', listening: 'skill_listening', language: 'skill_vocabulary' }[domain] || domain;
    return html`<span class="o-tag">${t(key)}</span>`;
  }

  // languages-5 / finding A: a writing prompt/draft, a read article's title and a spoken attempt's
  // transcript are all real target-language content, in the learner's active learning language
  // (`context.language`) - the language every one of these domains produces or reads in. Reading's
  // own `responseText` (a correct/total count) and Listening's rows (interface labels only, no
  // real per-event text this build can show, model.js's own comment) are never marked. Writing's
  // response excerpt marks from the essay's own `responseLanguage` (N-36 point 1, model.js) - a
  // real per-item field, not the screen's generic active learning language - falling back to it
  // only when the essay carries no language of its own (kit/lang.js already renders an unknown
  // code unmarked, so this fallback never produces a wrong `lang`).
  function evidenceRowMarkup(item) {
    const href = openRoute(item);
    const language = context.language;
    let sourceText = '';
    let responseText = '';
    let sourceLang = '';
    let responseLang = '';
    let resultText = '';
    let resultColor = 'var(--muted)';
    if (item.domain === 'writing') {
      sourceText = item.sourceText || t('skill_writing');
      sourceLang = item.sourceText ? language : '';
      responseText = item.responseText;
      responseLang = item.responseLanguage || language;
      resultText = item.score != null ? String(item.score) : '';
    } else if (item.domain === 'reading') {
      sourceText = item.sourceText || t('skill_reading');
      sourceLang = item.sourceText ? language : '';
      responseText = `${item.correct} / ${item.total}`;
      resultText = item.total ? `${Math.round((item.correct / item.total) * 100)}%` : '';
      resultColor = item.total && item.correct === item.total ? 'var(--green)' : item.correct === 0 ? 'var(--red)' : 'var(--muted)';
    } else if (item.domain === 'speaking') {
      sourceText = t('skill_speaking');
      responseText = item.responseText;
      responseLang = language;
      resultText = item.score != null ? String(item.score) : '';
      resultColor = item.score != null ? (item.score >= 80 ? 'var(--green)' : 'var(--muted)') : 'var(--muted)';
    } else if (item.domain === 'listening') {
      sourceText = t('sourceListening');
      responseText = item.assisted ? t('assistedLabel') : t('unassistedLabel');
      resultText = item.score != null ? String(item.score) : '';
      resultColor = item.score != null ? (item.score >= 80 ? 'var(--green)' : 'var(--muted)') : 'var(--muted)';
    }
    const lead = html`<span class="s-progress-ev__lead"><span class="s-progress-ev__date">${formatDate(item.at)}</span>${skillChip(item.domain)}</span>`;
    const trailing = resultText ? html`<span class="s-progress-ev__result" style="color:${resultColor}">${resultText}</span>` : null;
    const sub = html`${responseText ? langSpan(responseText, responseLang) : ''}${!href ? html`<span> · ${t('sourceUnavailable')}</span>` : ''}`;
    const rowMarkup = listRow({ tag: href ? 'button' : 'div', variant: 'outline', radius: 16, pad: '14px 18px', leading: lead, title: langSpan(sourceText, sourceLang), sub, trailing, dataset: href ? { go: href } : {} });
    return rowMarkup;
  }

  function historyRowMarkup(item) {
    const href = openRoute(item);
    const language = context.language;
    const kindKey = { writing: 'skill_writing', reading: 'skill_reading', speaking: 'skill_speaking', listening: 'skill_listening' }[item.domain] || item.domain;
    let title = '';
    let titleLang = '';
    let meta = '';
    if (item.domain === 'writing') {
      title = item.sourceText || t('skill_writing');
      titleLang = item.sourceText ? language : '';
      meta = item.score != null ? String(item.score) : '';
    } else if (item.domain === 'reading') {
      title = item.sourceText || t('skill_reading');
      titleLang = item.sourceText ? language : '';
      meta = item.total ? `${item.correct}/${item.total}` : '';
    } else if (item.domain === 'speaking') {
      title = t('skill_speaking');
      meta = item.score != null ? String(item.score) : '';
    } else if (item.domain === 'listening') {
      title = t('sourceListening');
      meta = item.score != null ? String(item.score) : '';
    }
    const lead = html`<span class="s-progress-hi__lead"><span class="s-progress-hi__time">${formatTime(item.at)}</span><span class="o-tag">${t(kindKey)}</span></span>`;
    return listRow({ tag: href ? 'button' : 'div', variant: 'outline', radius: 14, pad: '13px 18px', leading: lead, title: langSpan(title, titleLang), sub: !href ? t('sourceUnavailable') : '', trailing: meta ? html`<span class="o-muted" style="font-size:13px">${meta}</span>` : null, dataset: href ? { go: href } : {} });
  }

  async function renderOverview() {
    const [summary, rankPayload, activity, sources, cue] = await Promise.all([getSummary(state.range), getRank(), getActivity(), getEvidenceSources(), api.crossSkillCue().catch(() => null)]);
    const days = state.range === '7d' ? 7 : state.range === '30d' ? 30 : 90;
    const speaking = days == null ? sources.speaking : sources.speaking.filter(row => Date.parse(row.created_at) >= Date.now() - days * 86400000);
    const skills = buildSkillRows(summary, speaking);
    const rank = buildRank(rankSummary(rankPayload));
    const facts = storyFacts(activity, skills);
    const hero = html`<div class="s-progress-hero">
      ${segmentedControl({ variant: 'hero', equalWidth: true, name: 'range', options: RANGES.map((r) => ({ value: r, label: t(RANGE_COPY_KEY[r]), selected: r === state.range })) })}
      <div class="o-muted" style="font-size:13px">${t('timeUnmeasured')}</div>
    </div>`;
    const level = context.level ? html`<span><b>${context.level}</b>${rank.known && rank.rankName ? html` · ${rank.rankName}` : ''}</span>` : '';
    const stats = [
      facts.streak != null ? html`<span><b>${facts.streak}</b> ${t('streakSuffix')}</span>` : '',
      level,
    ].filter(Boolean);
    const story = html`<div class="s-progress-story">
      <div class="s-progress-story__eyebrow">${t('storyEyebrow')}</div>
      ${stats.length ? '' : html`<div class="s-progress-story__empty">${t('storyEmpty')}</div>`}
      ${stats.length ? html`<div class="s-progress-story__stats">${stats}</div>` : ''}
    </div>`;
    const skillsCard = html`<div class="s-progress-card">
      <div class="s-progress-card__title">${t('skillsTitle')}</div>
      ${skills.map((row) => html`<button type="button" class="s-progress-skill" data-action="skill-open" data-domain="${row.domain}">
        <span class="s-progress-skill__label">${t(`skill_${row.key}`)}</span>
        <span class="o-progress s-progress-skill__track"><span style="width:${row.pct}%"></span></span>
        <span class="s-progress-skill__delta" ${row.score == null ? raw(`aria-label="${t('notMeasured')}"`) : ''}>${row.score != null ? row.score : '—'}</span>
      </button>`)}
    </div>`;
    const ku = buildKuStages(summary);
    const kuMax = Math.max(...ku.map((s) => s.count ?? 0), 1);
    const kuCard = html`<div class="s-progress-card">
      <div class="s-progress-card__head"><div class="s-progress-card__title">${t('tabKU')}</div><button type="button" class="s-progress-card__link" data-action="goto-tab" data-tab="KU">${t('kuDetails')}${raw(icon('chevron-right', { size: 16 }))}</button></div>
      <div class="s-progress-ku-mini">
        ${ku.map((stage) => html`<button type="button" class="s-progress-ku-mini__col" data-action="goto-tab" data-tab="Evidence">
          <b>${stage.countLabel ?? '—'}</b>
          <span class="s-progress-ku-mini__bar" style="background:${KU_COLOR[stage.key]};height:${Math.max(8, ((stage.count ?? 0) / kuMax) * 60)}px"></span>
          <span class="s-progress-ku-mini__label">${t(KU_LABEL_KEY[stage.key])}</span>
        </button>`)}
      </div>
    </div>`;
    const next = buildNextRows(rankPayload, cue, sources.library);
    const nextRows = next.map((row) => html`<button type="button" class="s-progress-next" data-go="${ctx.href(row.route, row.params, row.query)}">
      <span class="s-progress-next__body">
        <span class="s-progress-next__title">${t(`next_${row.key}`)}</span>
        <span class="s-progress-next__reason">${row.key === 'review' ? t('nextDueReason', { count: row.count }) : langSpan(row.text, context.language)}</span>
      </span>
    </button>`);
    const nextCard = html`<div class="s-progress-card">
      <div class="s-progress-card__title">${t('nextTitle')}</div>
      ${next.length ? nextRows : emptyMarkup({ text: t('nextEmpty'), iconName: 'lightbulb' })}
    </div>`;
    return html`${hero}<div class="s-progress-grid2">${story}${skillsCard}</div><div class="s-progress-grid2">${kuCard}${nextCard}</div>`;
  }

  function renderTrends() {
    return html`<div class="s-progress-card">${emptyMarkup({ text: t('trendsUnavailable'), iconName: 'zap' })}</div>`;
  }

  async function renderKU() {
    const ku = buildKuStages(await getSummary(state.range));
    const rows = ku.map((stage) => listRow({
      variant: 'shadow', radius: 18, pad: '18px 20px', chevron: true,
      leading: html`<span class="s-progress-ku-badge" style="background:${KU_COLOR[stage.key]}">${stage.countLabel ?? '—'}</span>`,
      title: t(KU_LABEL_KEY[stage.key]),
      sub: t(KU_DESC_KEY[stage.key]),
      dataset: { action: 'goto-tab', tab: 'Evidence' },
    }));
    return html`<div class="s-progress-ku-list">${rows}<div class="s-progress-ku-footer">${t('kuFooterNote')}</div></div>`;
  }

  async function renderEvidence() {
    const items = filterEvidence(await evidenceItems(), state.evFilter);
    const filters = EV_FILTERS.map((f) => html`<button type="button" class="o-chip s-progress-filter" aria-pressed="${f === state.evFilter ? 'true' : 'false'}" data-action="set-filter" data-filter="${f}">${t(EV_FILTER_COPY_KEY[f])}</button>`);
    const body = items.length
      ? html`<div class="s-progress-list">${items.map((item) => evidenceRowMarkup(item))}</div>`
      : emptyMarkup({ text: t(state.evFilter === 'review' ? 'reviewHistoryUnavailable' : 'evidenceEmpty'), iconName: 'inbox' });
    return html`<div class="s-progress-filters">${filters}</div>${body}`;
  }

  async function renderRank() {
    const rankPayload = await getRank();
    const rank = buildRank(rankSummary(rankPayload));
    const card = rank.known
      ? html`<div class="s-progress-rank">
          <span class="s-progress-rank__badge">${context.level || ''}</span>
          <div><div class="s-progress-rank__name">${rank.rankName}</div><div class="s-progress-rank__sub">${rank.band}${rank.nextRankWords != null ? html` · ${rank.mastered} / ${rank.nextRankWords} — ${rank.nextRankName}` : ''}</div></div>
          <div class="s-progress-rank__bar"><span style="width:${rank.progressPct}%"></span></div>
          <div class="s-progress-rank__note">${t('rankDisclaimer')}</div>
        </div>`
      : html`<div class="s-progress-rank">${emptyMarkup({ text: t('rankUnknown'), iconName: 'crown' })}</div>`;
    const milestones = html`<div class="s-progress-milestones"><div class="s-progress-card__title">${t('milestonesTitle')}</div>${emptyMarkup({ text: t('milestonesEmpty'), iconName: 'crown' })}</div>`;
    return html`<div class="s-progress-grid2">${card}${milestones}</div>`;
  }

  async function renderHistory() {
    const items = await evidenceItems();
    const groups = historyGroups(items, 30);
    if (!groups.length) return emptyMarkup({ text: t('historyEmptyState'), iconName: 'clock' });
    return html`<div class="s-progress-history">${groups.map((group) => html`<div>
      <div class="s-progress-history__day">${group.key === 'today' ? shellCopy('today') : group.key === 'yesterday' ? t('historyYesterday') : formatDate(group.items[0].at)}</div>
      <div class="s-progress-history__items">${group.items.map((item) => historyRowMarkup(item))}</div>
    </div>`)}</div>`;
  }

  const RENDER = { Overview: renderOverview, Trends: renderTrends, KU: renderKU, Evidence: renderEvidence, Rank: renderRank, History: renderHistory };

  function paintShell() {
    mount(
      element,
      html`<div class="s-progress">
        <button type="button" class="s-progress-back" data-go="${ctx.href('profile')}">${raw(icon('chevron-left', { size: 18 }))}${shellCopy('profile')}</button>
        <div><h1 class="o-h1">${shellCopy('progress')}</h1></div>
        <div class="o-tabs" role="tablist">${TABS.map((tab) => html`<button type="button" class="o-tab" role="tab" aria-selected="${tab === state.tab ? 'true' : 'false'}" data-action="goto-tab" data-tab="${tab}"><span>${t(TAB_COPY_KEY[tab])}</span><span class="o-tab__bar"></span></button>`)}</div>
        <div class="s-progress-panel" data-content></div>
      </div>`,
    );
  }

  let paintGeneration = 0;
  async function paintTab() {
    const generation = ++paintGeneration;
    const content = element.querySelector('[data-content]');
    if (!content) return;
    const tab = state.tab;
    try {
      const markup = await RENDER[tab]();
      if (!ctx.isCurrent() || !element.isConnected || generation !== paintGeneration) return;
      mount(content, markup);
    } catch (error) {
      if (!ctx.isCurrent() || !element.isConnected || generation !== paintGeneration || error?.name === 'AbortError') return;
      mount(content, errorMarkup({ title: shellCopy('cantOpen'), text: shellCopy('errorServer'), backLabel: shellCopy('back'), retryLabel: shellCopy('retry') }));
      content.querySelector('[data-error-back]').addEventListener('click', () => ctx.back());
      content.querySelector('[data-error-retry]').addEventListener('click', () => {
        cache.summaries.clear();
        cache.evidence = cache.evidenceAll = cache.rank = cache.activity = null;
        void paintTab();
      });
    }
  }

  function repaintTabsBar() {
    element.querySelectorAll('[role="tab"]').forEach((el) => {
      el.setAttribute('aria-selected', String(el.dataset.tab === state.tab));
    });
  }

  async function onClick(event) {
    const rangeOpt = event.target.closest('[data-seg="range"] .c-seg__opt');
    if (rangeOpt) {
      state.range = rangeOpt.dataset.value;
      await paintTab();
      return;
    }
    const action = event.target.closest('[data-action]');
    if (!action) return;
    const kind = action.dataset.action;
    if (kind === 'goto-tab') {
      state.tab = action.dataset.tab;
      repaintTabsBar();
      await paintTab();
    } else if (kind === 'set-filter') {
      state.evFilter = action.dataset.filter;
      await paintTab();
    } else if (kind === 'skill-open') {
      state.tab = 'Evidence';
      state.evFilter = action.dataset.domain === 'language' ? 'review' : action.dataset.domain;
      repaintTabsBar();
      await paintTab();
    }
  }

  paintShell();
  element.addEventListener('click', onClick);
  await paintTab();

  return () => element.removeEventListener('click', onClick);
}
