/* Frame 27 "Search" (pinned design, focus route `#/search`; Ctrl/Cmd+K routes here from anywhere,
   shell/router.js). No global search endpoint exists (SCRATCH C2 "Explicit checks"), so this
   composes what does, real source by real source (model.js), and never invents a result (rule
   40). The header (back button, field, clear button) is built once and never re-rendered, so
   typing never loses focus or the caret; only `.s-search__body` repaints as the query changes. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { listRow } from '../../kit/components.js';
import { useStyles } from '../../kit/styles.js';
import { api } from '../../infrastructure/api.js';
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

async function settled(promise) {
  try {
    return await promise;
  } catch {
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

  function recentMarkup() {
    if (!recent.length) return html``;
    return html`<div>
      <div class="s-search__label">${t('recentLabel')}</div>
      <div class="s-search__chips">${recent.map((label, i) => html`<button type="button" class="s-search__chip" data-recent="${i}">${label}</button>`)}</div>
    </div>`;
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
    return listRow({
      tag: item.open ? 'button' : 'div',
      variant: 'outline',
      radius: 14,
      pad: '13px 18px',
      leading: html`<span class="s-search__kind">${label}</span>`,
      title: item.title,
      sub: item.meta,
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

  async function runSearch(q) {
    const mine = (token += 1);
    const [catalogue, collection, articles, listening] = await Promise.all([
      settled(api.vocabularyCatalogueSearch(q, language, 8)),
      settled(api.collection({ query: q, limit: 20 })),
      settled(api.readingArticles(language)),
      settled(api.listeningLibrary(language)),
    ]);
    if (mine !== token || !ctx.isCurrent()) return;
    const content = [
      ...articleItems(articles, q),
      ...listeningItems(listening, q),
      ...deviceTextItems(memoryValue, q),
      ...deviceMediaItems(memoryValue, q),
    ];
    groups = [
      { key: 'words', label: t('wordsGroup'), items: wordItems(catalogue) },
      { key: 'content', label: ts('content'), items: content },
      { key: 'library', label: ts('myLibrary'), items: collectionItems(collection, relationshipLabel) },
    ].filter((g) => g.items.length);
    searchedFor = q;
    recent = pushRecent(storage, q);
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
