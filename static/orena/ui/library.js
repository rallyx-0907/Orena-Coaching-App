import { esc } from './html.js';
import { scene } from './brand.js';
import { bindImages } from './content.js';
import { link } from '../product/intent.js';

/* The Shared Reading Library: a cover-first grid of admin-imported books,
   open to every learner. Mirrors the Vocabulary Library's own pattern in
   world.js - the caller owns a permanent <section data-library-grid> wrapper
   so this repaints only its own container, never the rest of Discover/
   Reading, and "open a book" is an inline detail state inside this same
   container rather than a route, exactly like vocabularyLibrarySection's
   `open` collection state. Chapters are real links: opening one hands off to
   the existing encounter/readable() reader via a `book:<id>/<chapterId>`
   locator (static/orena/ui/encounter.js), not a second reader. */

export function libraryCoverUrl(bookId) {
  return `/api/reading/library/books/${encodeURIComponent(bookId)}/cover`;
}

function coverArt(book, c, { large = false } = {}) {
  const hasCover = Boolean(book.cover_asset_key);
  const mark = esc((book.title || '?').trim().slice(0, 1));
  return `<span class="library-cover${large ? ' library-cover--large' : ''}">${
    hasCover
      ? `<img src="${esc(libraryCoverUrl(book.id))}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : `<span class="library-cover-fallback" aria-hidden="true">${mark}</span>`
  }</span>`;
}

function bookCard(book, c) {
  return `<button type="button" class="library-card" data-open-book="${esc(book.id)}">${coverArt(book, c)}<strong class="library-card-title" lang="${esc(book.learning_language || '')}">${esc(book.title)}</strong>${book.author ? `<span class="library-card-author">${esc(book.author)}</span>` : ''}</button>`;
}

function bookDetail(c, open) {
  const back = `<button type="button" class="quiet" data-close-book>← ${esc(c.libraryBack)}</button>`;
  if (open.error)
    return `${back}<p class="notice" role="alert">${esc(c.unavailable)} <button type="button" data-book-retry>${esc(c.retry)}</button></p>`;
  if (!open.book)
    return `${back}<p class="loading" role="status">${esc(c.libraryLoading)}</p>`;
  const book = open.book;
  return `${back}<div class="library-detail">${coverArt(book, c, { large: true })}<div class="library-detail-copy"><h2 lang="${esc(book.learning_language || '')}">${esc(book.title)}</h2>${book.author ? `<p class="byline">${esc(book.author)}</p>` : ''}${book.description ? `<p class="voice-description">${esc(book.description)}</p>` : ''}<ol class="library-chapter-list">${book.chapters
    .map(
      (chapter, index) =>
        `<li><a href="${esc(link('encounter', { id: `book:${book.id}/${chapter.id}`, intent: 'reading' }))}">${index + 1}. ${esc(chapter.title)}</a></li>`,
    )
    .join('')}</ol></div></div>`;
}

function gridBody(c, state) {
  const { items, error, nextCursor, loadingMore } = state;
  if (error)
    return `<p class="notice" role="alert">${esc(c.unavailable)} <button type="button" data-library-grid-retry>${esc(c.retry)}</button></p>`;
  if (!items) return `<p class="loading" role="status">${esc(c.libraryLoading)}</p>`;
  if (!items.length)
    return `<div class="empty">${scene('empty', { size: 'medium' })}<p>${esc(c.libraryEmpty)}</p></div>`;
  return `<div class="library-grid">${items.map((book) => bookCard(book, c)).join('')}</div>${
    nextCursor
      ? `<button type="button" class="outline" data-library-more ${loadingMore ? 'disabled' : ''}>${esc(c.libraryLoadMore)}</button>`
      : ''
  }`;
}

/* Inner content only - see the module doc: the caller owns the wrapper. */
export function librarySection(c, state = {}) {
  const heading = `<div class="section-head"><h2>${esc(c.libraryTitle)}</h2></div>`;
  return `${heading}${state.open ? bookDetail(c, state.open) : gridBody(c, state)}`;
}

export function paintLibraryGrid(container, ctx) {
  if (!container) return;
  const { api, c, language, alive } = ctx;
  let items = null;
  let error = false;
  let nextCursor = null;
  let loadingMore = false;
  let open = null;

  function paint() {
    if (!alive()) return;
    container.innerHTML = librarySection(c, { items, error, nextCursor, loadingMore, open });
    bindImages(container, c);
    container.querySelectorAll('[data-open-book]').forEach((button) => {
      button.onclick = () => openBook(button.dataset.openBook);
    });
    container
      .querySelector('[data-close-book]')
      ?.addEventListener('click', () => {
        open = null;
        paint();
      });
    container.querySelector('[data-library-grid-retry]')?.addEventListener('click', loadList);
    container
      .querySelector('[data-book-retry]')
      ?.addEventListener('click', () => open && openBook(open.id));
    container.querySelector('[data-library-more]')?.addEventListener('click', loadMore);
  }

  async function loadList() {
    items = null;
    error = false;
    nextCursor = null;
    open = null;
    paint();
    try {
      const data = await api.libraryBooks(language);
      if (!alive()) return;
      items = data.items || [];
      nextCursor = data.next_cursor || null;
    } catch {
      if (!alive()) return;
      error = true;
    }
    paint();
  }

  async function loadMore() {
    if (!nextCursor || loadingMore) return;
    loadingMore = true;
    paint();
    try {
      const data = await api.libraryBooks(language, nextCursor);
      if (!alive()) return;
      items = [...(items || []), ...(data.items || [])];
      nextCursor = data.next_cursor || null;
    } catch {
      // Load-more failure leaves the current page on screen; the button
      // itself is the retry affordance, same as elsewhere in this file.
    } finally {
      loadingMore = false;
      if (alive()) paint();
    }
  }

  async function openBook(id) {
    open = { id, book: null, error: false };
    paint();
    try {
      const book = await api.libraryBook(id);
      if (!alive()) return;
      open = { id, book, error: false };
    } catch {
      if (!alive()) return;
      open = { id, book: null, error: true };
    }
    paint();
  }

  loadList();
}
