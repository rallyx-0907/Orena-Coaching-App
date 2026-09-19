/* Library (D-059, D-060) - the approved "browse at scale" composition:
   facets beside a grid on a desk (type, level, topic, clear), a library search,
   a sort and a grid/list switch above the grid, one titled section per kind,
   and on a phone the facets as a bottom sheet with "show N results".

   Everything shown is real: the shared book library (paged), every readable
   passage and imported text the learner has, the listening catalogue and the
   learner's own media, and the vocabulary collections. Facets are built from
   the values the items actually carry - a level or topic nobody has is never
   offered. Missing catalogue facts (a total title count, a "recently added"
   date, levels on books) are tracked gaps (GAP-022), not invented. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { art, duration, bindImages } from './content.js';
import { contentCover } from './cover.js';
import { libraryCoverUrl, readingFromMemory } from './library.js';
import { referenceCopy } from './reference.js';
import { link } from '../product/intent.js';

const KINDS = ['books', 'audio', 'video', 'collections'];
const KIND_ICON = { books: 'book-open', audio: 'headphones', video: 'play', collections: 'cards' };
const LEVEL_ORDER = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'HSK 1', 'HSK 2', 'HSK 3', 'HSK 4', 'HSK 5', 'HSK 6'];
const levelRank = (level) => {
  const index = LEVEL_ORDER.indexOf(String(level || '').toUpperCase().replace(/^HSK(\d)/, 'HSK $1'));
  return index < 0 ? 99 : index;
};
const topicKey = (topic) => String(topic || '').trim().toLowerCase().replace(/_/g, '-');

/* A topic is offered only when the interface can name it in the learner's
   support language; a raw content tag in another language is metadata, not a
   label (Design Contract rule 26). */
function topicLabel(c, key) {
  return c[`topic_${key}`] || '';
}

/* Every source normalised to one entry shape. */
function fromReadable(item, language) {
  return {
    kind: 'books',
    id: item.id,
    title: item.title,
    sub: item.author || '',
    level: item.level || item.target_level || '',
    topic: topicKey(item.topic || item.material),
    href: link('encounter', { id: item.id, intent: 'reading' }),
    visual: art(item),
    language: item.language || language,
  };
}
function fromBook(book, reading) {
  const state = reading?.[book.id];
  const total = Number(state?.total) || Number(book.chapter_count) || 0;
  const index = Number(state?.index) || 0;
  const percent = state && index >= 1 && total >= 1 ? Math.max(1, Math.round((index / total) * 100)) : null;
  return {
    kind: 'books',
    id: `book:${book.id}`,
    title: book.title,
    sub: book.author || '',
    level: '',
    topic: '',
    percent,
    href: link('book', { id: book.id }),
    visual: book.cover_asset_key
      ? `<img src="${esc(libraryCoverUrl(book.id))}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : contentCover({ id: book.id, title: book.title, subtitle: book.author, material: 'book' }),
    language: book.learning_language || '',
  };
}
function fromMedia(item, language) {
  const video = (item.kind || item.media_type || item.playback_kind) === 'video';
  return {
    kind: video ? 'video' : 'audio',
    id: item.id,
    title: item.title,
    sub: '',
    level: item.level || '',
    topic: topicKey(item.topic),
    length: Number(item.duration_ms) > 0 ? duration(item.duration_ms) : '',
    href: link('encounter', { id: item.id, intent: 'follow' }),
    visual: art(item),
    language: item.language || language,
  };
}
function fromCollection(collection) {
  const progress = collection.progress || {};
  const total = Number(progress.total_count ?? collection.word_count ?? collection.total) || 0;
  const learned = Number(progress.learned_count ?? progress.mastered_count) || 0;
  return {
    kind: 'collections',
    id: `collection:${collection.id}`,
    title: collection.title || '',
    sub: collection.topic || '',
    level: collection.level || collection.level_range || '',
    topic: topicKey(collection.topic),
    total,
    learned,
    percent: total ? Math.round((learned / total) * 100) : null,
    href: link('language'),
    visual: contentCover({ id: collection.id, title: collection.title, material: 'book' }, { motif: 'life' }),
    language: collection.language_code || '',
  };
}

function card(entry, c, view) {
  const meta = [entry.level, entry.length, entry.percent != null && entry.kind === 'books' ? `${entry.percent}%` : '', entry.kind === 'collections' && entry.total ? `${entry.learned} / ${entry.total}` : ''].filter(Boolean).join(' · ');
  const bar = entry.percent != null ? `<span class="progress-bar library-item__bar"><span style="width:${entry.percent}%"></span></span>` : '';
  if (view === 'list')
    return `<a class="library-row" href="${esc(entry.href)}" data-kind="${entry.kind}"><span class="library-row__visual">${entry.visual}</span><span class="library-row__text"><strong lang="${esc(entry.language)}">${esc(entry.title)}</strong>${entry.sub ? `<span class="library-row__sub">${esc(entry.sub)}</span>` : ''}${meta ? `<small>${esc(meta)}</small>` : ''}</span>${icon('caret-right', { size: 18, className: 'library-row__go' })}</a>`;
  return `<a class="library-item" href="${esc(entry.href)}" data-kind="${entry.kind}"><span class="library-item__visual">${entry.visual}${bar}</span><strong lang="${esc(entry.language)}">${esc(entry.title)}</strong>${meta ? `<small>${esc(meta)}</small>` : ''}</a>`;
}

/* `only` scopes the whole surface to one kind - the Reading room is this same
   library with books and texts in it, not a second library. The type facet
   goes with the choice it no longer offers. */
export function renderLibraryBrowse(root, ctx, sources, { only = null } = {}) {
  const { api, c, language, alive } = ctx;
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const reading = readingFromMemory(ctx.memory);
  const scope = only ? KINDS.filter((kind) => only.includes(kind)) : null;
  const state = {
    kinds: new Set(scope || []),
    levels: new Set(),
    topics: new Set(),
    query: '',
    sort: 'title',
    view: 'grid',
    sheet: false,
    books: null,
    booksCursor: null,
    booksFailed: false,
    booksMore: false,
    collections: null,
    collectionsFailed: false,
  };
  const base = [
    ...(sources.readable || []).map((item) => fromReadable(item, language)),
    ...(sources.media || []).map((item) => fromMedia(item, language)),
  ];

  const everything = () => [
    ...(state.books || []).map((book) => fromBook(book, reading)),
    ...base,
    ...(state.collections || []).map(fromCollection),
  ];
  const matches = (entry, { ignore = '' } = {}) => {
    if (ignore !== 'kind' && state.kinds.size && !state.kinds.has(entry.kind)) return false;
    if (ignore !== 'level' && state.levels.size && !state.levels.has(entry.level)) return false;
    if (ignore !== 'topic' && state.topics.size && !state.topics.has(entry.topic)) return false;
    const q = state.query.trim().toLowerCase();
    if (q && !`${entry.title} ${entry.sub} ${entry.topic}`.toLowerCase().includes(q)) return false;
    return true;
  };
  const sorted = (list) =>
    [...list].sort((a, b) =>
      state.sort === 'level'
        ? levelRank(a.level) - levelRank(b.level) || a.title.localeCompare(b.title)
        : a.title.localeCompare(b.title),
    );

  const facets = () => {
    const all = everything();
    const levels = [...new Set(all.map((x) => x.level).filter(Boolean))].sort((a, b) => levelRank(a) - levelRank(b));
    const topics = [...new Set(all.map((x) => x.topic).filter((topic) => topic && topicLabel(c, topic)))].sort();
    const kindRow = (kind) =>
      `<label class="facet-check"><input type="checkbox" data-facet-kind="${kind}"${state.kinds.has(kind) ? ' checked' : ''}><span class="facet-check__box" aria-hidden="true">${icon('check', { size: 12 })}</span><span>${esc(r[`libraryType_${kind}`])}</span></label>`;
    const chip = (group, value, label) =>
      `<button type="button" class="facet-chip" data-facet-${group}="${esc(value)}" aria-pressed="${state[group === 'level' ? 'levels' : 'topics'].has(value)}">${esc(label)}</button>`;
    return `<div class="library-facets__head"><strong>${esc(r.libraryFilters)}</strong><button type="button" class="quiet" data-facet-clear>${esc(r.libraryClear)}</button></div>${scope ? '' : `<fieldset class="facet-group"><legend class="ds-label">${esc(r.libraryType)}</legend>${KINDS.map(kindRow).join('')}</fieldset>`}${levels.length ? `<fieldset class="facet-group"><legend class="ds-label">${esc(r.libraryLevel)}</legend><div class="facet-chips">${levels.map((level) => chip('level', level, level)).join('')}</div></fieldset>` : ''}${topics.length ? `<fieldset class="facet-group"><legend class="ds-label">${esc(r.libraryTopic)}</legend><div class="facet-topics">${topics.map((topic) => chip('topic', topic, topicLabel(c, topic))).join('')}</div></fieldset>` : ''}<button type="button" class="library-facets__clear" data-facet-clear>${icon('x', { size: 14 })}<span>${esc(r.libraryClearFilters)}</span></button><button type="button" class="primary library-facets__show" data-sheet-close>${esc(r.libraryShowResults.replace('{n}', String(everything().filter((x) => matches(x)).length)))}</button>`;
  };

  const section = (kind, entries) => {
    const title = `${r[`libraryType_${kind}`]}`;
    let body;
    if (kind === 'books' && state.books === null && !state.booksFailed)
      body = `<div class="library-grid library-grid--books" aria-hidden="true">${Array.from({ length: 5 }, () => '<span class="skeleton library-skeleton"></span>').join('')}</div>`;
    else if (!entries.length) return '';
    else
      body = `<div class="library-${state.view === 'list' ? 'list' : `grid library-grid--${kind}`}">${sorted(entries).map((entry) => card(entry, c, state.view)).join('')}</div>`;
    const failed = kind === 'books' && state.booksFailed
      ? `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.unavailable)}</strong></div><button type="button" class="outline" data-books-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`
      : '';
    const more = kind === 'books' && state.booksCursor
      ? `<button type="button" class="library-more" data-books-more${state.booksMore ? ' disabled' : ''}>${icon(state.booksMore ? 'clock' : 'caret-down', { size: 16 })}<span>${esc(r.libraryLoadMore.replace('{n}', String((state.books || []).length)))}</span></button>`
      : '';
    return `<section class="library-section" data-library-section="${kind}"><header class="library-section__head"><h2>${icon(KIND_ICON[kind], { size: 18 })}<span>${esc(title)}</span></h2><span class="ds-label library-section__count">${esc(r.libraryTitles.replace('{n}', String(entries.length)))}</span></header>${failed}${body}${more}</section>`;
  };

  function paint() {
    if (!alive()) return;
    const focusId = document.activeElement?.id;
    const all = everything().filter((x) => matches(x));
    const byKind = Object.fromEntries(KINDS.map((kind) => [kind, all.filter((x) => x.kind === kind)]));
    const shown = KINDS.filter((kind) => !state.kinds.size || state.kinds.has(kind));
    const sections = shown.map((kind) => section(kind, byKind[kind])).join('');
    const active = (scope ? 0 : state.kinds.size) + state.levels.size + state.topics.size;
    const empty = !all.length && state.books !== null
      ? `<div class="state-panel state-panel--empty">${icon('magnifying-glass', { size: 22 })}<div><strong>${esc(r.libraryNoResults)}</strong></div><button type="button" class="primary" data-facet-clear>${esc(r.libraryClearFilters)}</button></div>`
      : '';
    root.innerHTML = `<h1 class="sr-only">${esc(r.library)}</h1><div class="library-browse" data-sheet="${state.sheet ? 'open' : 'closed'}"><aside class="library-facets" aria-label="${esc(r.libraryFilters)}">${facets()}</aside><button type="button" class="library-sheet-backdrop" data-sheet-close tabindex="-1" aria-hidden="true"></button><div class="library-main"><div class="library-toolbar"><label class="library-search"><span class="sr-only">${esc(r.librarySearch)}</span>${icon('magnifying-glass', { size: 18 })}<input id="librarySearch" type="search" autocomplete="off" placeholder="${esc(r.librarySearch)}" value="${esc(state.query)}" data-library-query></label><button type="button" class="library-tool library-tool--filters" data-sheet-open aria-expanded="${state.sheet}">${icon('funnel', { size: 16 })}<span>${esc(r.libraryFilters)}</span>${active ? `<span class="library-tool__count">${active}</span>` : ''}</button><button type="button" class="library-tool" data-library-sort>${icon('sliders-horizontal', { size: 16 })}<span>${esc(state.sort === 'level' ? r.librarySortLevel : r.librarySortTitle)}</span></button><div class="segmented library-view" role="radiogroup" aria-label="${esc(r.libraryView)}"><button type="button" role="radio" aria-checked="${state.view === 'grid'}" data-library-view="grid" aria-label="${esc(r.libraryViewGrid)}">${icon('squares-four', { size: 16 })}</button><button type="button" role="radio" aria-checked="${state.view === 'list'}" data-library-view="list" aria-label="${esc(r.libraryViewList)}">${icon('list', { size: 16 })}</button></div></div>${empty}${sections}</div></div>`;
    bindImages(root, c);
    bind();
    if (focusId) document.getElementById(focusId)?.focus();
    if (focusId === 'librarySearch') {
      const input = document.getElementById('librarySearch');
      input?.setSelectionRange(input.value.length, input.value.length);
    }
  }

  function toggle(set, value) {
    if (set.has(value)) set.delete(value);
    else set.add(value);
    paint();
  }
  function bind() {
    root.querySelectorAll('[data-facet-kind]').forEach((input) => (input.onchange = () => toggle(state.kinds, input.dataset.facetKind)));
    root.querySelectorAll('[data-facet-level]').forEach((button) => (button.onclick = () => toggle(state.levels, button.dataset.facetLevel)));
    root.querySelectorAll('[data-facet-topic]').forEach((button) => (button.onclick = () => toggle(state.topics, button.dataset.facetTopic)));
    root.querySelectorAll('[data-facet-clear]').forEach((button) => (button.onclick = () => {
      state.kinds = new Set(scope || []);
      state.levels.clear();
      state.topics.clear();
      state.query = '';
      paint();
    }));
    const query = root.querySelector('[data-library-query]');
    query.oninput = () => {
      state.query = query.value;
      paint();
    };
    root.querySelector('[data-library-sort]').onclick = () => {
      state.sort = state.sort === 'title' ? 'level' : 'title';
      paint();
    };
    root.querySelectorAll('[data-library-view]').forEach((button) => (button.onclick = () => {
      state.view = button.dataset.libraryView;
      paint();
    }));
    root.querySelector('[data-sheet-open]').onclick = () => {
      state.sheet = true;
      paint();
      root.querySelector('.library-facets input, .library-facets button')?.focus();
    };
    root.querySelectorAll('[data-sheet-close]').forEach((button) => (button.onclick = () => {
      state.sheet = false;
      paint();
    }));
    root.querySelector('[data-books-more]')?.addEventListener('click', loadMoreBooks);
    root.querySelector('[data-books-retry]')?.addEventListener('click', loadBooks);
  }

  async function loadBooks() {
    state.books = null;
    state.booksFailed = false;
    paint();
    try {
      const data = await api.libraryBooks(language);
      if (!alive()) return;
      state.books = data.items || [];
      state.booksCursor = data.next_cursor || null;
    } catch {
      if (!alive()) return;
      state.books = [];
      state.booksFailed = true;
    }
    paint();
  }
  async function loadMoreBooks() {
    if (!state.booksCursor || state.booksMore) return;
    state.booksMore = true;
    paint();
    try {
      const data = await api.libraryBooks(language, state.booksCursor);
      if (!alive()) return;
      state.books = [...state.books, ...(data.items || [])];
      state.booksCursor = data.next_cursor || null;
    } catch {
      // The button stays as the retry.
    } finally {
      state.booksMore = false;
      paint();
    }
  }
  async function loadCollections() {
    try {
      const data = await api.vocabularyLibraryCollections(language);
      if (!alive()) return;
      state.collections = data.items || data.collections || [];
    } catch {
      state.collections = [];
      state.collectionsFailed = true;
    }
    paint();
  }

  const onKey = (event) => {
    if (event.key === 'Escape' && state.sheet) {
      state.sheet = false;
      paint();
      root.querySelector('[data-sheet-open]')?.focus();
    }
  };
  document.addEventListener('keydown', onKey);
  paint();
  loadBooks();
  loadCollections();
  return () => document.removeEventListener('keydown', onKey);
}
