import { esc } from './html.js';
import { icon } from './phosphor.js';
import { referenceCopy } from './reference.js';
import { bindImages } from './content.js';
import { contentCover } from './cover.js';
import { link } from '../product/intent.js';

/* The book page: one shared library book, on its own route (#/book?id=).

   The library that leads here is the approved browse surface in
   library-browse.js - Library (#/content) and the Reading room are the same
   library, scoped. This module owns what a single book looks like once it is
   chosen, and hands off to the reader through the `book:<id>/<chapterId>`
   locator encounter.js parses (never a second reader).

   Under D-057 the cover is the object and everything else is metadata beneath
   it. A book with no edition cover of its own gets a designed one from the one
   deterministic system in `ui/cover.js`. */

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

/* The approved book detail (D-059 Phase 5, Screens part 4 section 16).

   Overview first, chapters below: the cover, what the book is, how far in the
   learner is and the one action they came for sit above the fold; the chapters
   follow as a compact list with a single highlighted next row; description,
   the words this book has already taught and recommendations sit in the side
   column where they cannot crowd the decision.

   Everything shown is read from something real. Chapters behind the current
   one are read - the same derivation the shelf percentage already uses, never
   a second progress store. Per-chapter reading time, time read, quiz average,
   audio and "similar level" have no source yet: each keeps its place in the
   composition with the design system's unavailable state and is tracked in
   docs/project/UI_BACKEND_GAPS.md (D-060), never removed and never invented. */
const CHAPTER_PREVIEW = 5;

const fill = (template, values) =>
  String(template || '').replace(/\{(\w+)\}/g, (match, key) => (key in values ? String(values[key]) : match));

/* A stat tile: the label, then the figure - or the honest dash when nothing
   measures it yet. */
function bookStat(label, value, { note = '', tone = '' } = {}) {
  return `<div class="book-stat"${tone ? ` data-tone="${tone}"` : ''}><span class="ds-label">${esc(label)}</span><strong>${esc(value)}</strong>${note ? `<small>${esc(note)}</small>` : ''}</div>`;
}

function bookDetail(c, r, open, reading, view = {}) {
  /* A link, not history.back(): the reader reaches this page by navigating to
     it, so a history step here lands back in the reader and the two bounce off
     each other with no way out of the book. */
  const back = `<a class="icon-button book-back" href="${esc(link('practice', { intent: 'reading' }))}" aria-label="${esc(c.libraryBack)}">${icon('caret-right', { size: 20, className: 'is-flipped' })}</a>`;
  if (open.error)
    return `${back}<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.unavailable)}</strong></div><button type="button" class="outline" data-book-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`;
  if (!open.book)
    return `${back}<div class="book-page" role="status" aria-label="${esc(c.libraryLoading)}"><div class="book-hero"><span class="skeleton book-hero__cover"></span><div class="book-hero__copy"><span class="skeleton skeleton--line"></span><span class="skeleton skeleton--title"></span><span class="skeleton skeleton--line"></span></div></div></div>`;

  const book = open.book;
  const language = book.learning_language || '';
  const chapters = book.chapters || [];
  const progress = readingProgress(reading, { ...book, chapter_count: chapters.length });
  const currentId = progress?.chapterId;
  const currentIndex = currentId ? chapters.findIndex((chapter) => chapter.id === currentId) : -1;
  const resume = currentIndex >= 0 ? chapters[currentIndex] : chapters[0];
  const total = chapters.length;
  const chapterLink = (chapter) => esc(link('encounter', { id: `book:${book.id}/${chapter.id}`, intent: 'reading' }));

  const chips = [
    `<span class="chip chip--domain" data-domain="reading">${esc(r.reading)}</span>`,
    language ? `<span class="chip">${esc(c[`language_${language}`] || language.toUpperCase())}</span>` : '',
    total ? `<span class="chip">${esc(`${total} ${c.libraryChapterCount}`)}</span>` : '',
    Number(book.word_count) > 0
      ? `<span class="chip">${esc(`${Number(book.word_count).toLocaleString()} ${c.libraryWords}`)}</span>`
      : '',
  ].filter(Boolean).join('');

  const percent = progress?.percent || 0;
  const place = percent
    ? `${percent}% · ${fill(r.bookChapterOf, { n: progress.index, t: progress.total })}`
    : r.bookNotStarted;
  const progressRow = `<div class="book-hero__progress"><span class="progress-bar"${percent ? '' : ' data-unavailable'}><span style="width:${percent}%"></span></span><span class="ds-data">${esc(place)}</span></div>`;

  const quiet = (name, label) =>
    `<button type="button" class="icon-button" disabled aria-label="${esc(`${label} — ${r.bookSoon}`)}" title="${esc(r.bookSoon)}">${icon(name, { size: 20 })}</button>`;
  const actions = resume
    ? `<div class="book-hero__actions"><a class="primary" href="${chapterLink(resume)}">${icon('book-open', { size: 18, filled: true })}<span>${esc(
        currentIndex >= 0 ? fill(r.bookContinueChapter, { n: currentIndex + 1 }) : c.libraryStartReading,
      )}</span></a>${quiet('bookmark-simple', r.bookBookmark)}${quiet('download-simple', r.bookDownload)}${quiet('dots-three', r.bookMore)}</div>`
    : '';

  const savedWords = Array.isArray(open.words) ? open.words : null;
  const stats = `<div class="book-hero__stats">${bookStat(
    r.bookStatWordsSaved,
    savedWords ? String(savedWords.length) : '—',
    savedWords ? {} : { note: r.bookNotMeasured },
  )}${bookStat(r.bookStatTime, '—', { note: r.bookNotMeasured })}${bookStat(
    r.bookStatQuiz,
    '—',
    { note: r.bookNotMeasured },
  )}${bookStat(r.bookStatAudio, '—', { note: r.bookAudioGap })}</div>`;

  /* The chapters behind the current one are read; the current one is next. */
  const done = (index) => currentIndex >= 0 && index < currentIndex;
  const rows = chapters.map((chapter, index) => ({ chapter, index }));
  const listed = view.unreadOnly ? rows.filter(({ index }) => !done(index)) : rows;
  const windowStart = view.expanded
    ? 0
    : Math.max(0, Math.min(Math.max(currentIndex, 0) - 3, Math.max(0, listed.length - CHAPTER_PREVIEW)));
  const shown = view.expanded ? listed : listed.slice(windowStart, windowStart + CHAPTER_PREVIEW);
  const chapterRow = ({ chapter, index }) => {
    const isCurrent = chapter.id === currentId;
    const words = Number(chapter.word_count) > 0
      ? fill(r.bookChapterWords, { n: Number(chapter.word_count).toLocaleString() })
      : '';
    return `<li${isCurrent ? ' data-current' : ''}><a class="book-chapter" href="${chapterLink(chapter)}"${isCurrent ? ' aria-current="true"' : ''}${done(index) ? ' data-done' : ''}><span class="book-chapter__n ds-data">${String(index + 1).padStart(2, '0')}</span><span class="book-chapter__text"><span class="book-chapter__title" lang="${esc(language)}">${esc(chapter.title)}</span>${words ? `<small class="ds-data">${esc(words)}</small>` : ''}</span>${
      isCurrent
        ? `<span class="chip book-chapter__next">${esc(r.bookNext)}</span>`
        : done(index)
          ? `<span class="book-chapter__done" title="${esc(r.bookRead)}">${icon('check-circle', { size: 18, filled: true })}<span class="sr-only">${esc(r.bookRead)}</span></span>`
          : ''
    }</a></li>`;
  };
  const contents = `<section class="book-chapters" aria-label="${esc(c.libraryChapters)}"><div class="book-section-head"><h3 class="book-section-title">${esc(c.libraryChapters)}</h3><button type="button" class="book-filter ds-label" data-unread-only aria-pressed="${Boolean(view.unreadOnly)}">${icon('funnel', { size: 14 })}<span>${esc(r.bookUnreadOnly)}</span></button></div><ol class="book-chapter-list">${shown.map(chapterRow).join('')}</ol>${
    listed.length > shown.length
      ? `<button type="button" class="book-show-all" data-show-all-chapters>${esc(fill(r.bookShowAll, { n: listed.length }))}${icon('caret-down', { size: 16 })}</button>`
      : ''
  }</section>`;

  const wordChips = savedWords
    ? savedWords.slice(0, 12).map((word) => `<span class="chip" lang="${esc(language)}">${esc(word)}</span>`).join('') +
      (savedWords.length > 12 ? `<span class="chip book-words__more ds-data">+${savedWords.length - 12}</span>` : '')
    : '';
  const side = `<aside class="book-side">${
    book.description
      ? `<section><span class="ds-label">${esc(r.bookAbout)}</span><p class="book-about">${esc(book.description)}</p></section>`
      : ''
  }<section><span class="ds-label">${esc(r.bookWordsFrom)}</span>${
    savedWords
      ? savedWords.length
        ? `<div class="book-words">${wordChips}</div>`
        : `<p class="book-side__note">${esc(r.bookNoWordsSaved)}</p>`
      : `<div class="book-words" aria-hidden="true">${'<span class="skeleton skeleton--chip"></span>'.repeat(3)}</div>`
  }</section><section><span class="ds-label">${esc(r.bookSimilar)}</span><p class="book-side__note">${esc(r.bookSimilarGap)}</p></section></aside>`;

  return `<article class="book-page">${back}<header class="book-hero"><div class="book-hero__cover">${coverArt(book, c, { large: true })}</div><div class="book-hero__copy"><div class="book-hero__chips">${chips}</div><div><h2 class="book-hero__title" lang="${esc(language)}">${esc(book.title)}</h2>${
    book.author ? `<p class="book-hero__byline">${esc(book.author)}</p>` : ''
  }</div>${progressRow}${actions}${stats}</div></header><div class="book-body">${contents}${side}</div></article>`;
}

/* Inner content only - see the module doc: the caller owns the wrapper. */
/* The page's markup, pure: the caller owns the container and the state. */
export function librarySection(c, state = {}) {
  const heading = `<h2 class="sr-only">${esc(c.libraryTitle)}</h2>`;
  const r = referenceCopy[state.ui] || referenceCopy.en;
  return `${heading}${bookDetail(c, r, state.open || {}, state.reading, state.view)}`;
}

/* The words this book has already taught, out of the learner's own saved
   vocabulary: a word is from this book when it was kept while reading one of
   its chapters (`focus_note` is the chapter title the reader passed). This is
   a read of existing saved data, never a second store and never an estimate. */
export function wordsFromBook(items, book) {
  const titles = new Set(
    [book?.title, ...(book?.chapters || []).map((chapter) => chapter.title)]
      .map((title) => String(title || '').trim())
      .filter(Boolean),
  );
  const seen = new Set();
  const words = [];
  for (const item of items || []) {
    const where = String(item?.focus_note || '').trim();
    const word = String(item?.word || '').trim();
    if (!word || !titles.has(where) || seen.has(word)) continue;
    seen.add(word);
    words.push(word);
  }
  return words;
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

/* The two controls the chapter list owns. Both are view state: what the
   learner asked to see, never a second copy of what they have read. */
function bindBookControls(container, view, paint) {
  const filter = container.querySelector('[data-unread-only]');
  if (filter)
    filter.onclick = () => {
      view.unreadOnly = !view.unreadOnly;
      paint();
    };
  const showAll = container.querySelector('[data-show-all-chapters]');
  if (showAll)
    showAll.onclick = () => {
      view.expanded = true;
      paint();
    };
}

/* The words kept from this book, from the learner's own saved vocabulary. A
   failed read leaves the tile and the side panel on their honest dash rather
   than removing them. */
async function loadBookWords(open, paint, ctx) {
  const { api, alive } = ctx;
  const book = open.book;
  try {
    const data = await api.libraryVocabulary();
    if (!alive() || open.book !== book) return;
    open.words = wordsFromBook(data?.items || data || [], book);
  } catch {
    if (!alive() || open.book !== book) return;
    open.words = null;
  }
  paint();
}

/* The route: #/book?id=<book id>, which every library card links to. */
export function paintBookPage(container, ctx, id) {
  if (!container) return () => {};
  const { api, c, alive } = ctx;
  let open = { id, book: null, error: false, words: null };
  const view = { unreadOnly: false, expanded: false };
  const paint = () => {
    if (!alive()) return;
    container.innerHTML = librarySection(c, {
      open, reading: readingFromMemory(ctx.memory), view, ui: ctx.ui,
    });
    bindImages(container, c);
    bindBookControls(container, view, paint);
    container.querySelector('[data-book-retry]')?.addEventListener('click', load);
  };
  async function load() {
    open = { id, book: null, error: false, words: null };
    paint();
    try {
      const book = await api.libraryBook(id);
      if (!alive()) return;
      open = { id, book, error: false, words: null };
    } catch {
      if (!alive()) return;
      open = { id, book: null, error: true };
    }
    paint();
    if (open.book) loadBookWords(open, paint, ctx);
  }
  load();
  return () => {};
}
