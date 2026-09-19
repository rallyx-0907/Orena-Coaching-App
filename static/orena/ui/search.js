/* Global search (D-059 Phase 4, D-060) - "Global search · grouped results":
   one search box with its result count, kind chips (All, Words, Books, Audio,
   Collections), and results grouped by what the learner was looking for - the
   word itself first, then their own texts with the sentence in context, then
   the library. Not a chat, not one flat list.

   Every result is real and found on the device from what Orena already
   serves: saved vocabulary, the text of passages the learner has (built-in,
   published and imported), and the titles of books, media and collections.
   Searching inside shared-library book chapters needs a server-side index and
   is a tracked gap (GAP-026); that group says so rather than pretending. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { art, duration, bindImages } from './content.js';
import { contentCover } from './cover.js';
import { libraryCoverUrl } from './library.js';
import { referenceCopy } from './reference.js';
import { link } from '../product/intent.js';
import { masteryStars } from './vocabulary-experience.js';

const CHIPS = ['all', 'words', 'books', 'audio', 'collections'];
const norm = (value) => String(value || '').toLowerCase();

function textOf(item) {
  if (Array.isArray(item.paragraphs)) return item.paragraphs.map((p) => (typeof p === 'string' ? p : p?.text || '')).join(' ');
  return String(item.text || item.body || '');
}
/* The sentence around the match, with the match marked. */
function snippet(text, query) {
  const at = norm(text).indexOf(norm(query));
  if (at < 0) return '';
  const start = Math.max(0, text.lastIndexOf('.', at) + 1, at - 60);
  const end = Math.min(text.length, at + query.length + 70);
  const before = text.slice(start, at).trimStart();
  const hit = text.slice(at, at + query.length);
  const after = text.slice(at + query.length, end);
  return `${start > 0 ? '…' : ''}${esc(before)}<mark>${esc(hit)}</mark>${esc(after)}${end < text.length ? '…' : ''}`;
}

export function renderSearch(root, ctx, sources) {
  const { api, c, language, alive } = ctx;
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const state = { query: ctx.location.q || '', chip: 'all', words: null, books: [], collections: [] };

  function results() {
    const q = norm(state.query.trim());
    if (!q) return { words: [], texts: [], library: [] };
    const words = (state.words || []).filter((w) => norm(w.word).includes(q) || norm(w.translation_vi).includes(q) || norm(Object.values(w.support_translations || {}).join(' ')).includes(q));
    const texts = (sources.readable || [])
      .map((item) => ({ item, hit: snippet(textOf(item), state.query.trim()) }))
      .filter((x) => x.hit);
    const library = [
      ...state.books.filter((b) => norm(`${b.title} ${b.author}`).includes(q)).map((b) => ({ kind: 'books', title: b.title, meta: b.author || '', href: link('book', { id: b.id }), visual: b.cover_asset_key ? `<img src="${esc(libraryCoverUrl(b.id))}" alt="" loading="lazy">` : contentCover({ id: b.id, title: b.title, material: 'book' }) })),
      ...(sources.readable || []).filter((x) => norm(x.title).includes(q)).map((x) => ({ kind: 'books', title: x.title, meta: x.level || '', href: link('encounter', { id: x.id, intent: 'reading' }), visual: art(x) })),
      ...(sources.media || []).filter((x) => norm(`${x.title} ${x.description || ''}`).includes(q)).map((x) => ({ kind: 'audio', title: x.title, meta: [r.libraryType_audio, Number(x.duration_ms) > 0 ? duration(x.duration_ms) : ''].filter(Boolean).join(' · '), href: link('encounter', { id: x.id, intent: 'follow' }), visual: art(x) })),
      ...state.collections.filter((x) => norm(x.title).includes(q)).map((x) => ({ kind: 'collections', title: x.title, meta: r.libraryType_collections, href: link('language'), visual: contentCover({ id: x.id, title: x.title }, { motif: 'life' }) })),
    ];
    return { words, texts, library };
  }

  function paint() {
    if (!alive()) return;
    const { words, texts, library } = results();
    const show = (kind) => state.chip === 'all' || state.chip === kind;
    const libraryShown = library.filter((x) => state.chip === 'all' || x.kind === state.chip);
    const total = (show('words') ? words.length : 0) + (show('books') ? texts.length : 0) + libraryShown.length;
    const wordRows = show('words') && words.length
      ? `<section class="search-group" aria-label="${esc(r.searchWords)}"><h2 class="search-group__label ds-label">${esc(r.searchWord)}</h2>${words.slice(0, 5).map((w, i) => {
          const meaning = w.support_translations?.[ctx.support] || w.translation_vi || w.definition || '';
          const stars = masteryStars(w);
          const filled = (stars.match(/★/g) || []).length;
          return `<a class="search-word${i ? '' : ' search-word--lead'}" href="${esc(link('language'))}"><span class="search-word__text"><span class="search-word__head"><strong lang="${esc(language)}">${esc(w.word)}</strong>${w.phonetic ? `<span class="search-word__reading" lang="${esc(language)}">${esc(w.phonetic)}</span>` : ''}</span><span class="search-word__meaning">${esc(meaning)}</span></span><span class="vocabulary-stars" aria-label="${esc(stars)}">${[0, 1, 2].map((n) => icon('star', { filled: n < filled, size: 12, className: n < filled ? 'is-earned' : '' })).join('')}</span></a>`;
        }).join('')}</section>`
      : '';
    const textRows = show('books') && state.query.trim()
      ? `<section class="search-group" aria-label="${esc(r.searchInYourTexts)}"><h2 class="search-group__label ds-label">${esc(r.searchInYourTexts)} · ${texts.length}</h2>${texts.slice(0, 6).map(({ item, hit }) => `<a class="search-hit" href="${esc(link('encounter', { id: item.id, intent: 'reading' }))}"><span class="search-hit__visual">${art(item)}</span><span class="search-hit__text"><strong lang="${esc(item.language || language)}">${esc(item.title)}</strong><span class="search-hit__line" lang="${esc(item.language || language)}">${hit}</span></span>${icon('caret-right', { size: 18 })}</a>`).join('')}<p class="search-gap">${icon('info', { size: 14 })}<span>${esc(r.searchBooksGap)}</span></p></section>`
      : '';
    const libraryRows = libraryShown.length
      ? `<section class="search-group" aria-label="${esc(r.library)}"><h2 class="search-group__label ds-label">${esc(r.library)} · ${libraryShown.length}</h2><div class="search-library">${libraryShown.slice(0, 12).map((x) => `<a class="search-tile" href="${esc(x.href)}" data-kind="${x.kind}"><span class="search-tile__visual">${x.visual}</span><span class="search-tile__text"><strong>${esc(x.title)}</strong>${x.meta ? `<small>${esc(x.meta)}</small>` : ''}</span></a>`).join('')}</div></section>`
      : '';
    const empty = state.query.trim() && !total && state.words !== null
      ? `<div class="state-panel state-panel--empty">${icon('magnifying-glass', { size: 22 })}<div><strong>${esc(r.searchNothing)}</strong></div></div>`
      : '';
    const loading = state.words === null && state.query.trim()
      ? `<div class="search-group" aria-hidden="true"><span class="skeleton skeleton--card"></span><span class="skeleton skeleton--card"></span></div>`
      : '';
    const focused = document.activeElement?.id === 'searchQuery';
    root.innerHTML = `<section class="search-page"><h1 class="sr-only">${esc(r.searchTitle)}</h1><div class="search-panel"><form class="search-box" role="search" data-search-form><label class="sr-only" for="searchQuery">${esc(r.searchPlaceholder)}</label>${icon('magnifying-glass', { size: 20 })}<input id="searchQuery" type="search" autocomplete="off" value="${esc(state.query)}" placeholder="${esc(r.searchPlaceholder)}" data-search-query>${state.query.trim() ? `<span class="search-box__count ds-label" aria-live="polite">${esc(r.searchResults.replace('{n}', String(total)))}</span><button type="button" class="search-box__clear" data-search-clear aria-label="${esc(r.libraryClear)}">${icon('x', { size: 18 })}</button>` : ''}</form><div class="search-chips" role="radiogroup" aria-label="${esc(r.libraryType)}">${CHIPS.map((chip) => `<button type="button" class="facet-chip search-chip" role="radio" aria-checked="${state.chip === chip}" data-search-chip="${chip}">${esc(r[`searchChip_${chip}`])}</button>`).join('')}</div><div class="search-results">${loading}${wordRows}${textRows}${libraryRows}${empty}</div></div></section>`;
    bindImages(root, c);
    const input = root.querySelector('[data-search-query]');
    input.oninput = () => {
      state.query = input.value;
      history.replaceState(null, '', link('search', { q: state.query }));
      paint();
    };
    root.querySelector('[data-search-form]').onsubmit = (event) => event.preventDefault();
    root.querySelector('[data-search-clear]')?.addEventListener('click', () => {
      state.query = '';
      history.replaceState(null, '', link('search'));
      paint();
      root.querySelector('[data-search-query]')?.focus();
    });
    root.querySelectorAll('[data-search-chip]').forEach((button) => (button.onclick = () => {
      state.chip = button.dataset.searchChip;
      paint();
    }));
    if (focused || !state.query) {
      const again = root.querySelector('[data-search-query]');
      again.focus();
      again.setSelectionRange(again.value.length, again.value.length);
    }
  }

  paint();
  Promise.allSettled([api.libraryVocabulary(), api.libraryBooks(language), api.vocabularyLibraryCollections(language)]).then(([words, books, collections]) => {
    if (!alive()) return;
    state.words = words.status === 'fulfilled' ? words.value.items || [] : [];
    state.books = books.status === 'fulfilled' ? books.value.items || [] : [];
    state.collections = collections.status === 'fulfilled' ? collections.value.items || collections.value.collections || [] : [];
    paint();
  });
  return () => {};
}
