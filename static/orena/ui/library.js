import { esc } from './html.js';
import { scene } from './brand.js';
import { bindImages } from './content.js';
import { contentCover } from './cover.js';
import { contentRail } from './content-rail.js';
import { link } from '../product/intent.js';

/* The Shared Reading Library: a cover-first library of admin-imported books,
   open to every learner. Mirrors the Vocabulary Library's own pattern in
   world.js - the caller owns a permanent <section data-library-grid> wrapper
   so this repaints only its own container, never the rest of Discover/
   Reading, and "open a book" is an inline detail state inside this same
   container rather than a route, exactly like vocabularyLibrarySection's
   `open` collection state. Chapters are real links: opening one hands off to
   the existing encounter/readable() reader via a `book:<id>/<chapterId>`
   locator (static/orena/ui/encounter.js), not a second reader.

   Under D-057 the cover is the object and everything else is metadata beneath
   it. A book with no edition cover of its own gets a designed one from the one
   deterministic system in `ui/cover.js` - never a single letter on a tinted
   square, which made a shelf read as an alphabet rather than as books. */

export function libraryCoverUrl(bookId) {
  return `/api/reading/library/books/${encodeURIComponent(bookId)}/cover`;
}

/* A book is a book: the motif comes from what it is, and the ground from its
   own identity, so the same book always wears the same cover. */
function coverArt(book, c, { large = false } = {}) {
  const hasCover = Boolean(book.cover_asset_key);
  return `<span class="library-cover${large ? ' library-cover--large' : ''}">${
    hasCover
      ? `<img src="${esc(libraryCoverUrl(book.id))}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : contentCover({ id: book.id, title: book.title, subtitle: book.author, material: 'book' })
  }</span>`;
}

/* How far into a book the learner actually is, from device memory alone. The
   reading map is `{ [bookId]: { chapterId, index, total } }`, built by the
   caller from the continuation entries it already holds; nothing is estimated
   from a title and no request is made to find out. */
function readingProgress(reading, book) {
  const state = reading?.[book.id];
  if (!state) return null;
  const total = Number(state.total) || Number(book.chapter_count) || 0;
  const index = Number(state.index) || 0;
  if (!(index >= 1 && total >= 1 && index <= total)) return { ...state, percent: 0 };
  return { ...state, index, total, percent: Math.max(1, Math.round((index / total) * 100)) };
}

function progressBar(progress) {
  if (!progress?.percent) return '';
  return `<span class="library-progress"><span class="library-progress__bar"><span style="width:${progress.percent}%"></span></span><small>${progress.percent}%</small></span>`;
}

function bookCard(book, c, reading) {
  const progress = readingProgress(reading, book);
  return `<button type="button" class="library-card" data-open-book="${esc(book.id)}">${coverArt(book, c)}<strong class="library-card-title" lang="${esc(book.learning_language || '')}">${esc(book.title)}</strong>${book.author ? `<span class="library-card-author">${esc(book.author)}</span>` : ''}${progressBar(progress)}</button>`;
}

/* Shelves appear when a library is big enough to need them. With a handful of
   books, a shelf per theme would be the same books printed three times; with a
   real catalogue, one flat wall of covers is what a learner has to scroll
   past. So Continue reading appears whenever there is real progress, and the
   themed shelf appears only once the library is larger than the shelf. */
const SHELF_SIZE = 8;
const SHORT_BOOK_WORDS = 2000;

function shelf(c, { id, title, items, reading }) {
  return contentRail({
    id: `library-${id}`,
    title,
    icon: 'book',
    items: items.map((book) => bookCard(book, c, reading)),
    previousLabel: `${c.previous || 'Previous'}: ${title}`,
    nextLabel: `${c.next || 'Next'}: ${title}`,
    className: 'library-shelf',
  });
}

function gridBody(c, state) {
  const { items, error, nextCursor, loadingMore, reading } = state;
  if (error)
    return `<p class="notice" role="alert">${esc(c.unavailable)} <button type="button" data-library-grid-retry>${esc(c.retry)}</button></p>`;
  if (!items) return `<p class="loading" role="status">${esc(c.libraryLoading)}</p>`;
  if (!items.length)
    return `<div class="empty">${scene('empty', { size: 'medium' })}<p>${esc(c.libraryEmpty)}</p></div>`;

  const shelves = [];
  const started = items.filter((book) => reading?.[book.id]);
  if (started.length)
    shelves.push(shelf(c, { id: 'continue', title: c.libraryContinue, items: started, reading }));
  const short = items.filter(
    (book) => Number(book.word_count) > 0 && Number(book.word_count) <= SHORT_BOOK_WORDS,
  );
  if (items.length > SHELF_SIZE && short.length >= 3)
    shelves.push(shelf(c, { id: 'short', title: c.libraryShort, items: short, reading }));

  return `${shelves.join('')}<section class="library-wall" aria-label="${esc(c.libraryBooks)}">${
    shelves.length ? `<div class="section-head"><h3>${esc(c.libraryBooks)}</h3></div>` : ''
  }<div class="library-grid">${items.map((book) => bookCard(book, c, reading)).join('')}</div>${
    nextCursor
      ? `<button type="button" class="outline" data-library-more ${loadingMore ? 'disabled' : ''}>${esc(c.libraryLoadMore)}</button>`
      : ''
  }</section>`;
}

/* A book, not a folder of chapters.

   The cover leads, the title and author sit beside it, and the one thing a
   learner came to do - start, or carry on from where they stopped - is a
   primary action next to them rather than an entry somewhere in a numbered
   list. The contents stay complete and usable underneath, with the chapter
   the learner is actually in marked as current. */
function bookDetail(c, open, reading) {
  const back = `<button type="button" class="quiet" data-close-book>← ${esc(c.libraryBack)}</button>`;
  if (open.error)
    return `${back}<p class="notice" role="alert">${esc(c.unavailable)} <button type="button" data-book-retry>${esc(c.retry)}</button></p>`;
  if (!open.book)
    return `${back}<p class="loading" role="status">${esc(c.libraryLoading)}</p>`;
  const book = open.book;
  const chapters = book.chapters || [];
  const progress = readingProgress(reading, { ...book, chapter_count: chapters.length });
  const currentId = progress?.chapterId;
  const currentIndex = currentId ? chapters.findIndex((chapter) => chapter.id === currentId) : -1;
  const resume = currentIndex >= 0 ? chapters[currentIndex] : chapters[0];
  const facts = [
    chapters.length ? `${chapters.length} ${c.libraryChapterCount}` : '',
    Number(book.word_count) > 0 ? `${Number(book.word_count).toLocaleString()} ${c.libraryWords}` : '',
  ].filter(Boolean).join(' · ');
  const chapterLink = (chapter) => esc(link('encounter', { id: `book:${book.id}/${chapter.id}`, intent: 'reading' }));
  return `${back}<article class="library-detail">${coverArt(book, c, { large: true })}<div class="library-detail-copy"><h2 lang="${esc(book.learning_language || '')}">${esc(book.title)}</h2>${book.author ? `<p class="byline">${esc(book.author)}</p>` : ''}${facts ? `<p class="library-detail-facts">${esc(facts)}</p>` : ''}${progressBar(progress)}${resume ? `<a class="primary" href="${chapterLink(resume)}">${esc(currentIndex >= 0 ? c.resume : c.libraryStartReading)} <span aria-hidden="true">→</span></a>${currentIndex >= 0 ? `<p class="library-detail-where"><small>${esc(c.libraryCurrentChapter)}</small> <span lang="${esc(book.learning_language || '')}">${esc(resume.title)}</span></p>` : ''}` : ''}${book.description ? `<p class="library-detail-note">${esc(book.description)}</p>` : ''}</div></article><section class="library-contents" aria-label="${esc(c.libraryChapters)}"><div class="section-head"><h3>${esc(c.libraryChapters)}</h3></div><ol class="library-chapter-list">${chapters
    .map(
      (chapter, index) =>
        `<li${chapter.id === currentId ? ' data-current' : ''}><a href="${chapterLink(chapter)}"${chapter.id === currentId ? ' aria-current="true"' : ''}><span class="library-chapter-number" aria-hidden="true">${index + 1}</span><span lang="${esc(book.learning_language || '')}">${esc(chapter.title)}</span></a></li>`,
    )
    .join('')}</ol></section>`;
}

/* Inner content only - see the module doc: the caller owns the wrapper. */
export function librarySection(c, state = {}) {
  /* The room is already named Reading and the first shelf names itself, so a
     second visible "Library" heading above them is a word the learner does not
     need (D-057 rule 13). The region keeps its accessible name. */
  const heading = `<h2 class="sr-only">${esc(c.libraryTitle)}</h2>`;
  return `${heading}${state.open ? bookDetail(c, state.open, state.reading) : gridBody(c, state)}`;
}

/* What the learner has actually started, read out of device memory. A book
   chapter is remembered as `book:<bookId>/<chapterId>` with the place it sits
   in (product/memory.js), so this is a read of existing state - never a second
   progress store, and never a request. */
export function readingFromMemory(memory) {
  const reading = {};
  for (const item of memory?.value?.continuation || []) {
    const id = String(item?.id || '');
    if (!id.startsWith('book:')) continue;
    const [bookId, chapterId] = id.slice(5).split('/');
    if (!bookId || !chapterId || reading[bookId]) continue;
    reading[bookId] = {
      chapterId,
      index: Number(item?.place?.index) || 0,
      total: Number(item?.place?.total) || 0,
      title: item.title || '',
    };
  }
  return reading;
}

export function paintLibraryGrid(container, ctx) {
  if (!container) return;
  const { api, c, language, alive } = ctx;
  let items = null;
  let error = false;
  let nextCursor = null;
  let loadingMore = false;
  let open = null;
  /* Each repaint replaces this container's markup, so the shelves inside it
     get bound again and the previous binding's observers are released first -
     otherwise every "load more" leaves a ResizeObserver behind. */
  let releaseShelves = () => {};

  function paint() {
    if (!alive()) return;
    releaseShelves();
    const reading = readingFromMemory(ctx.memory);
    container.innerHTML = librarySection(c, { items, error, nextCursor, loadingMore, open, reading });
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
    releaseShelves = ctx.bindShelves?.(container) || (() => {});
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
  return () => releaseShelves();
}
