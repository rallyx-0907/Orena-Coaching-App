/* Frame "Grammar Library" with its "Grammar category" panel (design export 2026-10-08; route "grammarlib"). A browsing
   place (Design Contract rule 47): shell drawn, rail/tab bar present.

   Data: the Grammar Store's catalogue for the learning language and the learner's completed points, through the one
   seam product/grammar-source.js; model.js buildLibrary shapes them as the frame's state script (`glVals`) does, for
   the corpus as it is (see its notes for what the corpus cannot supply). The level, the open category, the "all" chip,
   the status filter, the sort and the view live in the address, so reload and Back from a point keep them; the search
   text lives in the history entry's state instead (model.js withSearch), so Back from a point keeps it too without
   putting it in a shareable address. Where the learner had scrolled to is restored by the router (shell/scroll-memory.js).

   A category card opens that category's panel under the grid and brings the panel into view: on a phone it sits a
   screen below the cards, and a press that changed nothing the learner could see read as a dead button.

   The header row (back, breadcrumb, search, status) is drawn once and the rest of the page re-renders under it, so the
   search field keeps its focus while the learner types. */
import { html, mount, raw } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { icon } from '../../kit/icons.js';
import { langSpan } from '../../kit/lang.js';
import { emptyMarkup } from '../../kit/states.js';
import { shellCopy as shell } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { t } from './copy.js';
import { grammarLibraryData, grammarProgress } from '../../product/grammar-source.js';
import { NO_FUNCTION, SORTS, STATUSES, buildLibrary, readSearch, statusControl, withSearch } from './model.js';

const GLYPH = Object.freeze({ zh: '语', en: 'Aa' });
const QUERY_KEYS = Object.freeze(['level', 'cat', 'all', 'st', 'sort', 'view']);

/* Scrolls the main column to `element`, without animation when the learner asks for less motion. */
function bringIntoView(element) {
  if (!element) return;
  const calm = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  element.scrollIntoView({ behavior: calm ? 'auto' : 'smooth', block: 'start' });
}

const hueStyle = (entry) => `--hue:${entry.hue}`;

function tile(entry, size, iconSize) {
  return html`<span class="s-gl__tile s-gl__tile--${size}" style="${hueStyle(entry)}">${raw(icon(entry.icon, { size: iconSize, stroke: 2.2 }))}</span>`;
}

function ring(entry) {
  // Progress could not be read: no ring at all rather than a "New" that may be wrong.
  if (entry.learned === null) return '';
  const label = entry.learned
    ? entry.score ? t('learnedScore', { correct: entry.score.correct, total: entry.score.total }) : t('status_L')
    : t('status_N');
  return html`<span class="s-gl__ring${entry.learned ? ' s-gl__ring--done' : ''}" role="img" aria-label="${label}">${entry.learned ? raw(icon('check', { size: 14, stroke: 3 })) : ''}</span>`;
}

function tag(entry, extra = '') {
  return html`<span class="s-gl__tag${extra}" style="${hueStyle(entry)}">${entry.tag}</span>`;
}

function title(entry, cls) {
  return html`<span class="${cls}">${langSpan(entry.title, entry.lang)}</span>`;
}

function reading(entry, cls, pinyin) {
  return entry.reading && pinyin ? html`<span class="${cls}">${entry.reading}</span>` : '';
}

function continueCard(entry, pinyin) {
  return html`<button type="button" class="s-gl__cont" data-open="${entry.id}">
    ${tile(entry, 44, 21)}
    <span class="s-gl__contBody">
      ${title(entry, 's-gl__contTitle')}${reading(entry, 's-gl__contRd', pinyin)}
      <span class="s-gl__contMean">${entry.mean}</span>
      ${tag(entry, ' s-gl__tag--cont')}
    </span>
    ${ring(entry)}
  </button>`;
}

function categoryCard(category) {
  return html`<button type="button" class="s-gl__cat" data-cat="${category.id || NO_FUNCTION}" aria-pressed="${category.selected ? 'true' : 'false'}" style="${hueStyle(category)}">
    ${tile(category, 48, 22)}
    <span class="s-gl__catBody">
      <span class="s-gl__catName">${category.name}</span>
      <span class="s-gl__catCount">${t.plural('topics', category.count)}</span>
      <span class="s-gl__catEx">${category.count ? `${category.examples.join(', ')}${category.more ? '…' : ''}` : t('noTopics')}</span>
    </span>
    <span class="s-gl__chev" aria-hidden="true">${raw(icon('chevron-right', { size: 18 }))}</span>
  </button>`;
}

function topicCard(entry, pinyin) {
  return html`<button type="button" class="s-gl__topic" data-open="${entry.id}">
    <span class="s-gl__topicHead">${title(entry, 's-gl__topicTitle')}${reading(entry, 's-gl__topicRd', pinyin)}</span>
    <span class="s-gl__topicMean">${entry.mean}</span>
    <span class="s-gl__topicFoot">${tag(entry, ' s-gl__tag--clip')}${ring(entry)}</span>
  </button>`;
}

function topicRow(entry, pinyin) {
  return html`<button type="button" class="s-gl__row" data-open="${entry.id}">
    ${tile(entry, 38, 18)}
    <span class="s-gl__rowBody">${title(entry, 's-gl__rowTitle')}${reading(entry, 's-gl__rowRd', pinyin)}<span class="s-gl__rowMean">${entry.mean}</span></span>
    ${tag(entry, ' s-gl__tag--row')}
    ${ring(entry)}
  </button>`;
}

function option(value, label, selected) {
  return html`<option value="${value}"${selected ? raw(' selected') : ''}>${label}</option>`;
}

export default async function grammarLibrary(element, ctx) {
  await useStyles('screens/grammar/grammar.css');
  const target = ctx.context.language === 'zh' ? 'zh' : 'en';
  const [data, firstProgress] = await Promise.all([grammarLibraryData(target), grammarProgress()]);
  let progress = firstProgress;
  if (!ctx.isCurrent()) return;

  const state = { q: readSearch(history.state) };
  for (const key of QUERY_KEYS) state[key] = ctx.query?.get?.(key) || '';
  if (state.view !== 'list') state.view = '';
  const pinyin = ctx.context.pinyin !== false;
  const langTitle = t(`langTitle_${target}`);

  if (!data.points.length) {
    mount(element, html`<section class="s-gl">${emptyMarkup({ text: t('empty'), iconName: 'inbox' })}</section>`);
    return;
  }

  mount(
    element,
    html`<section class="s-gl">
      <div class="s-gl__top">
        <button type="button" class="s-gl__back" data-back aria-label="${shell('back')}">${raw(icon('arrow-left', { size: 19 }))}</button>
        <nav class="s-gl__crumb" aria-label="${t('title')}"><span class="s-gl__crumbRoot">${t('title')}</span>${raw(icon('chevron-right', { size: 14 }))}<span class="s-gl__crumbHere">${langTitle}</span></nav>
        <div class="s-gl__find">
          <label class="s-gl__search">${raw(icon('search', { size: 17 }))}<input type="search" data-q placeholder="${t('search')}" aria-label="${t('search')}" autocomplete="off" /></label>
          <select class="s-gl__status" data-st aria-label="${t('status_all')}">${STATUSES.map((value) => option(value, t(`status_${value}`), value === (state.st || 'all')))}</select>
        </div>
      </div>
      <div class="s-gl__body" data-body></div>
    </section>`,
  );
  const body = element.querySelector('[data-body]');
  const q = element.querySelector('[data-q]');
  q.value = state.q;
  const st = element.querySelector('[data-st]');

  function remember() {
    const params = {};
    for (const key of QUERY_KEYS) if (state[key]) params[key] = state[key];
    history.replaceState(history.state, '', ctx.href('grammarlib', {}, params));
  }

  function render() {
    const view = buildLibrary({
      rows: data.points, functions: data.functions, progress, current: ctx.context.level || '', state, support: languages().support, ui: languages().ui, t,
    });
    const level = view.level.key;
    const percent = view.progressKnown && view.stats.total ? (view.stats.learned / view.stats.total) * 100 : 0;
    const status = statusControl(view, state);
    st.disabled = status.disabled;
    st.value = status.value;
    const stat = (value) => (value === null ? '—' : value);
    const panel = view.panel;
    const list = state.view === 'list';
    mount(
      body,
      html`<div class="s-gl__levelGroup">
        <div class="s-gl__hero">
          <span class="s-gl__glyph" aria-hidden="true">${GLYPH[target]}</span>
          <div class="s-gl__heroHead"><div class="s-gl__heroLevel">${level}</div><div class="s-gl__heroSub">${langTitle} · ${t.plural('topics', view.stats.total)}</div></div>
          <div class="s-gl__stats">
            <div class="s-gl__stat"><span class="s-gl__statN"><span class="s-gl__dot s-gl__dot--learned"></span>${stat(view.stats.learned)}</span><span class="s-gl__statLabel">${t('learned')}</span></div>
            <div class="s-gl__stat"><span class="s-gl__statN"><span class="s-gl__dot s-gl__dot--new"></span>${stat(view.stats.notStarted)}</span><span class="s-gl__statLabel">${t('notStarted')}</span></div>
          </div>
          <div class="s-gl__bar" aria-hidden="true"><span style="${`width:${percent}%`}"></span></div>
        </div>
        <div class="s-gl__levels">${view.levels.map((entry) => html`<button type="button" class="s-gl__level" data-level="${entry.key}" aria-pressed="${entry.selected ? 'true' : 'false'}">${entry.key}<span class="s-gl__levelN">${entry.count}</span></button>`)}</div>
      </div>

      ${view.progressKnown
        ? view.continue.length
          ? html`<div class="s-gl__group"><h2 class="s-gl__h2">${t('continueTitle')}</h2><div class="s-gl__grid">${view.continue.map((entry) => continueCard(entry, pinyin))}</div></div>`
          : ''
        : html`<div class="s-gl__group"><div class="s-gl__progressOff" role="status"><span>${t('progressUnavailable')}</span><button type="button" class="s-gl__clear" data-retry-progress>${shell('retry')}</button></div></div>`}

      <div class="s-gl__group">
        <h2 class="s-gl__h2">${t('categoriesTitle')}</h2>
        <div class="s-gl__grid">${view.categories.map(categoryCard)}</div>
      </div>

      ${panel
        ? html`<div class="s-gl__panel">
          <div class="s-gl__panelHead">
            ${tile(panel, 48, 22)}
            <div class="s-gl__panelText"><div class="s-gl__panelName">${panel.name}</div><div class="s-gl__panelSub">${t.plural('topics', panel.count)}</div></div>
            <button type="button" class="s-gl__seeAll" data-see-all="${panel.id || NO_FUNCTION}">${t('seeAll')}${raw(icon('arrow-right', { size: 16 }))}</button>
          </div>
          ${view.panelItems.length
            ? html`<div class="s-gl__grid">${view.panelItems.map((entry) => topicCard(entry, pinyin))}</div>`
            : html`<div class="s-gl__panelEmpty">${view.filtering ? t('catEmptyFiltered') : t('catEmpty', { level })}</div>`}
        </div>`
        : ''}

      <div class="s-gl__all" data-all>
        <div class="s-gl__allHead">
          <h2 class="s-gl__h2 s-gl__allTitle">${t('allTitle', { level, n: view.all.length })}</h2>
          <select class="s-gl__sort" data-sort aria-label="${t('sortLabel')}">${SORTS.map((value) => option(value, t(`sort_${value}`), value === view.sort))}</select>
          <div class="s-gl__views">${[['', 'layout-grid', t('viewGrid')], ['list', 'list', t('viewList')]].map(([value, name, aria]) => html`<button type="button" class="s-gl__view" data-view="${value || 'grid'}" aria-label="${aria}" aria-pressed="${(state.view || '') === value ? 'true' : 'false'}">${raw(icon(name, { size: 17 }))}</button>`)}</div>
        </div>
        <div class="s-gl__chips">${[{ id: 'all', name: t('chipAll') }, ...view.categories].map((entry) => html`<button type="button" class="s-gl__chip" data-chip="${entry.id || NO_FUNCTION}" aria-pressed="${entry.id === view.allCat ? 'true' : 'false'}">${entry.name}</button>`)}</div>
        ${view.all.length
          ? list
            ? html`<div class="s-gl__list">${view.all.map((entry) => topicRow(entry, pinyin))}</div>`
            : html`<div class="s-gl__grid">${view.all.map((entry) => topicCard(entry, pinyin))}</div>`
          : html`<div class="s-gl__allEmpty"><div class="s-gl__allEmptyTitle">${t('emptyFiltered')}</div><button type="button" class="s-gl__clear" data-clear>${t('clearFilters')}</button></div>`}
      </div>`,
    );
  }

  render();

  q.addEventListener('input', () => {
    state.q = q.value;
    history.replaceState(withSearch(history.state, state.q), '');
    render();
  });
  element.addEventListener('change', (event) => {
    if (event.target === st) state.st = st.value === 'all' ? '' : st.value;
    else if (event.target.matches('[data-sort]')) state.sort = event.target.value === 'def' ? '' : event.target.value;
    else return;
    remember();
    render();
  });
  element.addEventListener('click', (event) => {
    const hit = (selector) => event.target.closest(selector);
    if (hit('[data-back]')) {
      ctx.back();
      return;
    }
    const retry = hit('[data-retry-progress]');
    if (retry) {
      retry.disabled = true;
      grammarProgress().then((next) => {
        if (!ctx.isCurrent()) return;
        progress = next;
        render();
      });
      return;
    }
    const open = hit('[data-open]');
    if (open) {
      ctx.go(ctx.href('gconcept', { id: open.dataset.open }));
      return;
    }
    const level = hit('[data-level]');
    const cat = hit('[data-cat]');
    const seeAll = hit('[data-see-all]');
    const chip = hit('[data-chip]');
    const viewButton = hit('[data-view]');
    // "all" is no category; a topic with no function stays "-" in the address (model.js NO_FUNCTION).
    const id = (value) => (value === 'all' ? '' : value);
    if (level) Object.assign(state, { level: level.dataset.level, cat: '', all: '' });
    else if (cat) state.cat = id(cat.dataset.cat);
    else if (seeAll) state.all = id(seeAll.dataset.seeAll);
    else if (chip) state.all = id(chip.dataset.chip);
    else if (viewButton) state.view = viewButton.dataset.view === 'list' ? 'list' : '';
    else if (hit('[data-clear]')) {
      Object.assign(state, { q: '', st: '', all: '' });
      history.replaceState(withSearch(history.state, ''), '');
      q.value = '';
      st.value = 'all';
    } else return;
    remember();
    render();
    if (seeAll) bringIntoView(element.querySelector('[data-all]'));
    else if (cat) bringIntoView(element.querySelector('.s-gl__panel'));
    // The page re-renders under the header; the control the learner pressed keeps the focus (design review 2026-10-08).
    const again = (attr, value) => body.querySelector(`[${attr}="${CSS.escape(value)}"]`);
    const keep = level ? again('data-level', level.dataset.level) : cat ? again('data-cat', cat.dataset.cat)
      : chip ? again('data-chip', chip.dataset.chip) : viewButton ? again('data-view', viewButton.dataset.view) : null;
    keep?.focus({ preventScroll: true });
  });
}
