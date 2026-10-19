/* Frame 27 "Search" (pinned design, focus route `#/search`; Ctrl/Cmd+K routes here from anywhere,
   shell/router.js). No global search endpoint exists (SCRATCH C2 "Explicit checks"), so this
   composes what does, real source by real source (model.js), and never invents a result (rule
   40). The header (back button, field, clear button) is built once and never re-rendered, so
   typing never loses focus or the caret; only `.s-search__body` repaints as the query changes. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { listRow } from '../../kit/components.js';
import { langSpan } from '../../kit/lang.js';
import { useStyles } from '../../kit/styles.js';
import { errorMarkup } from '../../kit/states.js';
import { api } from '../../infrastructure/api.js';
import { catalogueLanguage } from '../../product/vocabulary-card.js';
import { shellCopy as ts } from '../../copy/shell.js';
import { t } from './copy.js';
import {
  normalizeQuery, readRecent, pushRecent, matchesText,
  wordItems, articleItems, listeningItems, deviceTextItems, deviceMediaItems, collectionItems, totalItems,
} from './model.js';

const DEBOUNCE_MS = 220;

const KIND_LABEL = {
  word: () => ts('word'),
  article: () => t('kindArticle'),
  media: () => t('kindMedia'),
  upload: () => t('kindUpload'),
  text: () => t('kindText'),
  writing: () => ts('writing'),
  speaking: () => ts('pronunciation'),
  grammar: () => ts('grammar'),
};

function relationshipLabel(key) {
  return t.has(key) ? t(key) : '';
}

function safeStorage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/* A source that failed answers null and is counted: a search whose sources failed and found nothing is a failed
   search (the load-error card with Retry), never "nothing found". */
async function settled(promise, failures) {
  try {
    return await promise;
  } catch {
    failures.count += 1;
    return null;
  }
}

export default async function search(element, ctx) {
  await useStyles('screens/search/search.css');
  const storage = safeStorage();
  const c = ctx.context;
  const language = c.language;
  const memoryValue = c.memory?.value || { imports: [], mediaImports: [] };

  let query = '';
  let recent = readRecent(storage);
  let groups = [];
  let searchedFor = null;
  let searchFailed = false;
  let startedFor = ''; // the query last sent: a keystroke that normalises to it (a trailing space) sends nothing new
  let debounceTimer = 0;
  let token = 0;

  element.classList.add('s-search');
  mount(
    element,
    html`<div class="s-search__head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${ts('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-search__field">
        ${raw(icon('search', { size: 18 }))}
        <input type="text" data-query aria-label="${ts('search')}" placeholder="${t('placeholder')}" autocomplete="off" spellcheck="false">
        <button type="button" class="s-search__clear" data-clear hidden aria-label="${t('clearLabel')}">${raw(icon('x', { size: 17 }))}</button>
      </div>
    </div>
    <div class="s-search__body" data-scroll-region></div>`,
  );

  const input = element.querySelector('[data-query]');
  const clearBtn = element.querySelector('[data-clear]');
  const body = element.querySelector('.s-search__body');
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());

  function noneMarkup() {
    return html`<div class="s-search__none">
      <div class="o-empty__art o-art">${raw(icon('inbox', { size: 22 }))}</div>
      <div class="s-search__none-text">${t('noneMessage', { query })}</div>
    </div>`;
  }

  function failedMarkup() {
    return errorMarkup({
      title: ts('errorPlace', { place: ts('search') }),
      text: ts(navigator.onLine === false ? 'errorOffline' : 'errorServer'),
      backLabel: ts('back'),
      retryLabel: ts('retry'),
    });
  }

  // Before typing (LEX-074, frame 27's empty state): the learner's recent searches when there are any, and the
  // one line saying what Search covers - the sources runSearch really reads.
  function recentMarkup() {
    return html`${recent.length
      ? html`<div>
      <div class="s-search__label">${t('recentLabel')}</div>
      <div class="s-search__chips">${recent.map((label, i) => html`<button type="button" class="s-search__chip" data-recent="${i}">${label}</button>`)}</div>
    </div>`
      : ''}
    <div class="s-search__hint">${t('scopeHint')}</div>`;
  }

  function resultsMarkup() {
    const count = totalItems(groups);
    return html`<div class="s-search__count">${t.plural('resultsFor', count, { query })}</div>
      ${groups.map(
        (group) => html`<div class="s-search__group">
          <div class="s-search__label">${group.label} · ${group.items.length}</div>
          <div class="s-search__rows">${group.items.map((item, i) => resultRow(group.key, i, item))}</div>
        </div>`,
      )}`;
  }

  function resultRow(groupKey, index, item) {
    const label = KIND_LABEL[item.kindKey] ? KIND_LABEL[item.kindKey]() : item.kindKey;
    // languages-5 fix (review issue 1, finding B.3 "also Search"): an article/media result's own
    // `topic` (model.js) is the same open, untranslatable content metadata as Discover's card tag
    // (docs/project/UI_BACKEND_GAPS.md N-35) - rendered in its own lang="en" span, never folded
    // unmarked into the meta string the way it used to be.
    const sub = item.topic ? html`${langSpan(item.topic, 'en')}${item.meta ? html` · ${item.meta}` : ''}` : item.meta;
    return listRow({
      tag: item.open ? 'button' : 'div',
      variant: 'outline',
      radius: 14,
      pad: '13px 18px',
      leading: html`<span class="s-search__kind">${label}</span>`,
      // languages-5 / finding A: word/article/media results carry the real language they were
      // queried in (model.js); every other kind (a learner's own saved item/import) has none and
      // renders bare - never guessed.
      title: langSpan(item.title, item.lang),
      sub,
      chevron: !!item.open,
      dataset: { group: groupKey, index },
    });
  }

  function renderBody() {
    if (!query.trim()) {
      mount(body, recentMarkup());
      bindRecent();
      return;
    }
    if (searchedFor !== query.trim()) return; // a newer keystroke is in flight - keep showing the last settled answer, never a flash of "no results"
    if (searchFailed && !totalItems(groups)) {
      mount(body, failedMarkup());
      body.querySelector('[data-error-back]').addEventListener('click', () => ctx.back());
      body.querySelector('[data-error-retry]').addEventListener('click', () => runSearch(searchedFor, { again: true }));
      return;
    }
    mount(body, totalItems(groups) ? resultsMarkup() : noneMarkup());
    bindRows();
  }

  function bindRecent() {
    body.querySelectorAll('[data-recent]').forEach((chip) => {
      chip.addEventListener('click', () => setQuery(recent[Number(chip.dataset.recent)], { immediate: true }));
    });
  }

  function bindRows() {
    body.querySelectorAll('[data-group]').forEach((row) => {
      const group = groups.find((g) => g.key === row.dataset.group);
      const item = group?.items[Number(row.dataset.index)];
      if (!item?.open) return;
      row.addEventListener('click', () => ctx.go(ctx.href(item.open.route, { id: item.open.id })));
    });
  }

  async function runSearch(q, { again = false } = {}) {
    if (!again && q === startedFor && !searchFailed) return;
    startedFor = q;
    const failures = { count: 0 };
    const mine = (token += 1);
    // The catalogue is asked in the query's own language (a Han query is the Chinese catalogue, a Latin one the
    // English catalogue), whatever the learner is learning now - the Word screen reads it the same way.
    const wordLanguage = catalogueLanguage(q, language);
    const [catalogue, collection, articles, listening] = await Promise.all([
      settled(api.vocabularyCatalogueSearch(q, wordLanguage, 8), failures),
      settled(api.collection({ query: q, limit: 20 }), failures),
      settled(api.readingArticles(language), failures),
      settled(api.listeningLibrary(language), failures),
    ]);
    if (mine !== token || !ctx.isCurrent()) {
      if (startedFor === q) startedFor = '';
      return;
    }
    const content = [
      ...articleItems(articles, q, language),
      ...listeningItems(listening, q, language),
      ...deviceTextItems(memoryValue, q),
      ...deviceMediaItems(memoryValue, q),
    ];
    groups = [
      { key: 'words', label: t('wordsGroup'), items: wordItems(catalogue, wordLanguage) },
      { key: 'content', label: ts('content'), items: content },
      { key: 'library', label: ts('myLibrary'), items: collectionItems(collection, relationshipLabel) },
    ].filter((g) => g.items.length);
    searchedFor = q;
    searchFailed = failures.count > 0;
    if (!searchFailed) recent = pushRecent(storage, q);
    renderBody();
  }

  function setQuery(value, { immediate = false } = {}) {
    query = value;
    input.value = value;
    clearBtn.hidden = !value.trim();
    clearTimeout(debounceTimer);
    const q = normalizeQuery(value);
    if (!q) {
      token += 1; // invalidate any in-flight runSearch so it can't land after the field is cleared
      searchedFor = null;
      searchFailed = false;
      startedFor = '';
      groups = [];
      renderBody();
      return;
    }
    if (immediate) runSearch(q);
    else debounceTimer = setTimeout(() => runSearch(q), DEBOUNCE_MS);
  }

  input.addEventListener('input', () => setQuery(input.value));
  clearBtn.addEventListener('click', () => {
    setQuery('');
    input.focus();
  });

  renderBody();
  // `#/search?q=…` (Discover's "Search everywhere") opens with the query typed and run.
  const initial = normalizeQuery(ctx.query?.get('q'));
  if (initial) setQuery(initial, { immediate: true });
  /* The router focuses `<main>` right after this mount resolves (route-change a11y, shell/
     router.js); the design's own openSearch handler beats that with the same 150ms delay
     (orena-script.js: `setTimeout(()=>this.searchEl&&this.searchEl.focus(),150)`), so this
     mirrors it rather than fighting the shell for a synchronous focus. */
  const focusTimer = setTimeout(() => { if (ctx.isCurrent()) input.focus(); }, 150);

  return () => {
    clearTimeout(debounceTimer);
    clearTimeout(focusTimer);
  };
}
