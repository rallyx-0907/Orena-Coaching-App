/* Library (D-066) - the Canonical UI Baseline's library: one bar (the room's name,
   a search, the import action), one row of single-choice type chips, and a grid of
   ContentCards. Reading and Listening are this same surface scoped to what can be
   read or listened to, not two libraries.

   Everything shown is real. A chip is offered only for a type some item in the
   room actually has; a card shows a progress bar and a "time left" only from a
   place the learner has really reached (device memory), and a type only when the
   catalogue or the item's own provenance says so. Missing catalogue facts are
   tracked in docs/project/UI_BACKEND_GAPS.md, never invented. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { art, duration, bindImages } from './content.js';
import { contentCover } from './cover.js';
import { libraryCoverUrl } from './library.js';
import { referenceCopy } from './reference.js';
import { link } from '../product/intent.js';

const KINDS = ['books', 'audio', 'video', 'collections'];

/* The order the chips read in: what a room's items are made of, most concrete
   first, then where they came from. */
const TYPE_ORDER = [
  'book', 'excerpt', 'article', 'news', 'essay', 'story', 'dialogue', 'quote',
  'interview', 'podcast', 'speech', 'video', 'situation', 'culture', 'collection',
  'generated', 'imported',
];
const READING_MATERIALS = new Set(['article', 'news', 'essay', 'story', 'dialogue', 'quote', 'excerpt']);

/* Where the learner stands in an item, from device memory: `place` is the line
   (or chapter) they reached out of the total, exactly as the continuation
   already records it. Never a second progress store. */
function placeOf(memory, id) {
  for (const item of memory?.value?.continuation || []) {
    if (String(item?.id || '') !== id) continue;
    const index = Number(item?.place?.index) || 0;
    const total = Number(item?.place?.total) || 0;
    if (index >= 1 && total >= 1) return { index, total };
  }
  return null;
}
const percentOf = (place) => (place ? Math.min(100, Math.max(1, Math.round((place.index / place.total) * 100))) : null);

function provenance(item) {
  if (item.origin === 'imported') return 'imported';
  if (item.origin === 'generated' || item.generation_mode === 'generated') return 'generated';
  return '';
}

function fromReadable(item, language) {
  const material = String(item.material || item.content_type || '').trim().toLowerCase();
  const made = provenance(item);
  return {
    kind: 'books',
    skill: 'reading',
    id: item.id,
    title: item.title,
    sub: item.author || '',
    level: item.level || item.target_level || '',
    type: made || (READING_MATERIALS.has(material) ? material : ''),
    badge: made,
    time: item.time || '',
    href: link('encounter', { id: item.id, intent: 'reading' }),
    visual: art(item),
    language: item.language || language,
  };
}
function fromBook(book, memory) {
  const state = (memory?.value?.continuation || []).find((item) => String(item?.id || '').startsWith(`book:${book.id}/`));
  const total = Number(state?.place?.total) || Number(book.chapter_count) || 0;
  const index = Number(state?.place?.index) || 0;
  return {
    kind: 'books',
    skill: 'reading',
    id: `book:${book.id}`,
    title: book.title,
    sub: book.author || '',
    level: '',
    type: 'book',
    badge: '',
    time: '',
    percent: state && index >= 1 && total >= 1 ? Math.max(1, Math.round((index / total) * 100)) : null,
    href: link('book', { id: book.id }),
    visual: book.cover_asset_key
      ? `<img src="${esc(libraryCoverUrl(book.id))}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : contentCover({ id: book.id, title: book.title, subtitle: book.author, material: 'book' }),
    language: book.learning_language || '',
  };
}
function fromMedia(item, language, memory) {
  const video = (item.kind || item.media_type || item.playback_kind) === 'video';
  const own = item.origin && item.origin !== 'curated';
  const length = Number(item.duration_ms) || 0;
  const place = placeOf(memory, item.id);
  const left = place && length > 0 ? Math.max(1, Math.ceil(((place.total - place.index) / place.total) * (length / 60000))) : null;
  return {
    kind: video ? 'video' : 'audio',
    skill: 'listening',
    id: item.id,
    title: item.title,
    sub: '',
    level: item.level || '',
    type: own ? 'imported' : String(item.content_type || ''),
    badge: own ? 'imported' : '',
    video,
    length: length > 0 ? duration(length) : '',
    percent: percentOf(place),
    left,
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
    skill: 'vocabulary',
    id: `collection:${collection.id}`,
    title: collection.title || '',
    sub: collection.topic || '',
    level: collection.level || collection.level_range || '',
    type: 'collection',
    badge: '',
    total,
    learned,
    percent: total ? Math.round((learned / total) * 100) : null,
    href: link('language'),
    visual: contentCover({ id: collection.id, title: collection.title, material: 'book' }, { motif: 'life' }),
    language: collection.language_code || '',
  };
}

function card(entry, r) {
  // A provenance the cover already says (a badge) is not said again in the line.
  // The baseline's meta line is lowercase for the type ("hội thoại · HSK 2 · còn 2 phút").
  const kindLabel = entry.type && entry.type !== entry.badge ? (r[`libraryKind_${entry.type}`] || '').toLocaleLowerCase() : '';
  const left = entry.left ? r.libraryLeft.replace('{n}', String(entry.left)) : '';
  const stated = /(\d+)/.exec(String(entry.time || ''));
  const time = stated ? r.libraryMinutes.replace('{n}', stated[1]) : '';
  const parts =
    entry.skill === 'listening'
      ? [kindLabel, entry.level, left]
      : entry.skill === 'vocabulary'
        ? [entry.level, entry.total ? `${entry.learned} / ${entry.total}` : '']
        : [entry.level, kindLabel, time];
  const meta = parts.filter(Boolean).join(' · ');
  const badges = `${entry.video ? `<span class="lib-badge lib-badge--icon" title="${esc(r.libraryKind_video)}">${icon('video-camera', { size: 15 })}</span>` : ''}${entry.badge ? `<span class="lib-badge">${esc(r[`libraryKind_${entry.badge}`] || '')}</span>` : ''}`;
  const bar = entry.percent != null ? `<span class="lib-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${entry.percent}"><span style="width:${entry.percent}%"></span></span>` : '';
  return `<a class="lib-card" href="${esc(entry.href)}" data-skill="${entry.skill}" data-kind="${entry.kind}"${entry.percent != null ? ' data-progress' : ''}><span class="lib-cover">${entry.visual}${badges ? `<span class="lib-badges">${badges}</span>` : ''}${entry.length ? `<span class="lib-length">${esc(entry.length)}</span>` : ''}${bar}</span><strong class="lib-title" lang="${esc(entry.language)}">${esc(entry.title)}</strong>${entry.sub ? `<span class="lib-sub">${esc(entry.sub)}</span>` : ''}${meta ? `<small class="lib-meta">${esc(meta)}</small>` : ''}</a>`;
}

/* `only` scopes the whole surface to one room's kinds. `onImport` is the room's own
   way of bringing something in; the bar offers it and owns nothing about it. */
export function renderLibraryBrowse(root, ctx, sources, { only = null, onImport = null, titleTag = 'h1' } = {}) {
  const { api, c, language, alive, memory } = ctx;
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const scope = only ? KINDS.filter((kind) => only.includes(kind)) : KINDS;
  const skill = scope.length === 1 && scope[0] === 'books' ? 'reading' : scope.every((kind) => kind === 'audio' || kind === 'video') ? 'listening' : 'library';
  const state = {
    type: '',
    query: '',
    books: scope.includes('books') ? null : [],
    booksCursor: null,
    booksFailed: false,
    booksMore: false,
    collections: scope.includes('collections') ? null : [],
  };
  const base = [
    ...(sources.readable || []).map((item) => fromReadable(item, language)),
    ...(sources.media || []).map((item) => fromMedia(item, language, memory)),
  ];
  const everything = () =>
    [
      ...(state.books || []).map((book) => fromBook(book, memory)),
      ...base,
      ...(state.collections || []).map(fromCollection),
    ].filter((entry) => scope.includes(entry.kind));
  const shown = () => {
    const q = state.query.trim().toLowerCase();
    return everything()
      .filter((entry) => !state.type || entry.type === state.type)
      .filter((entry) => !q || `${entry.title} ${entry.sub} ${entry.level} ${r[`libraryKind_${entry.type}`] || ''}`.toLowerCase().includes(q))
      .sort((a, b) => (b.percent ? 1 : 0) - (a.percent ? 1 : 0) || a.title.localeCompare(b.title));
  };

  const importButton = onImport
    ? `<button type="button" class="lib-import" data-lib-import>${icon('upload-simple', { size: 16 })}<span>${esc(r[skill === 'reading' ? 'libraryImportReading' : 'libraryImportListening'])}</span></button>`
    : '';
  root.innerHTML = `<div class="lib" data-skill="${skill}"><header class="lib-head"><${titleTag}>${esc(skill === 'reading' ? r.reading : skill === 'listening' ? r.listening : r.library)}</${titleTag}><label class="lib-search">${icon('magnifying-glass', { size: 16 })}<span class="sr-only">${esc(r.librarySearch)}</span><input type="search" autocomplete="off" placeholder="${esc(r.librarySearch)}" data-lib-query></label>${importButton}</header><div class="lib-chips" role="radiogroup" aria-label="${esc(r.libraryType)}" data-lib-chips></div><div class="lib-results" data-lib-results></div></div>`;
  const chipsRoot = root.querySelector('[data-lib-chips]');
  const results = root.querySelector('[data-lib-results]');

  function paint() {
    if (!alive()) return;
    const types = TYPE_ORDER.filter((type) => everything().some((entry) => entry.type === type));
    if (state.type && !types.includes(state.type)) state.type = '';
    const chip = (value, label) => `<button type="button" role="radio" class="lib-chip" aria-checked="${state.type === value}" data-lib-type="${esc(value)}">${esc(label)}</button>`;
    chipsRoot.innerHTML = types.length ? chip('', r.libraryAll) + types.map((type) => chip(type, r[`libraryKind_${type}`] || type)).join('') : '';
    chipsRoot.hidden = !types.length;

    const list = shown();
    // Loading and empty are not drawn in the design (D-067, rule 39), so nothing is drawn for them:
    // whatever has arrived is shown, and a search that finds nothing shows an empty grid.
    const body = `<div class="lib-grid">${list.map((entry) => card(entry, r)).join('')}</div>`;
    const failed = state.booksFailed
      ? `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.unavailable)}</strong></div><button type="button" class="outline" data-books-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`
      : '';
    const more = state.booksCursor
      ? `<button type="button" class="lib-more" data-books-more${state.booksMore ? ' disabled' : ''}>${icon(state.booksMore ? 'clock' : 'caret-down', { size: 16 })}<span>${esc(r.libraryLoadMore.replace('{n}', String((state.books || []).length)))}</span></button>`
      : '';
    results.innerHTML = `${failed}${body}${more}`;
    bindImages(results, c);
    bind();
  }

  function bind() {
    chipsRoot.querySelectorAll('[data-lib-type]').forEach((button) => {
      button.onclick = () => {
        state.type = button.dataset.libType;
        paint();
      };
    });
    results.querySelector('[data-books-more]')?.addEventListener('click', loadMoreBooks);
    results.querySelector('[data-books-retry]')?.addEventListener('click', loadBooks);
  }
  const query = root.querySelector('[data-lib-query]');
  query.oninput = () => {
    state.query = query.value;
    paint();
  };
  const importAction = root.querySelector('[data-lib-import]');
  if (importAction) importAction.onclick = onImport;

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
    }
    paint();
  }

  paint();
  if (scope.includes('books')) loadBooks();
  if (scope.includes('collections')) loadCollections();
  return () => {};
}
