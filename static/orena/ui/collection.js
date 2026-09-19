import { esc } from './html.js';
import { referenceCopy } from './reference.js';
import { link, sourceLink } from '../product/intent.js';
import { icon } from './phosphor.js';
import { art } from './content.js';
import { masteryStars } from './vocabulary-experience.js';

/* Saved (D-059 Phase 4, D-060) - "Saved content · four kinds, kept apart":
   Words, Highlights, Notes and Content, each with its count, never mixed into
   one feed. Words are the learner's saved vocabulary (with search, a mastery
   filter, a sort and the due banner); Highlights are the phrases they kept
   from a text; Content is what they brought in. Notes are drawn by the design
   and not stored anywhere yet - that tab says so (GAP-024). */

const KINDS = ['words', 'highlights', 'notes', 'content'];
const KIND_ICON = { words: 'cards', highlights: 'sparkle', notes: 'pencil-simple', content: 'bookmark-simple' };
const SOURCE_KIND = { feed: 'library', reading: 'reading', listening: 'listening', speaking: 'speaking', writing: 'writing', dictation: 'dictation', essay: 'writing' };

/* Kept for other surfaces that read the learner's retained items. */
export function collectionItems(ctx) {
  const { memory } = ctx;
  const out = [];
  for (const entry of memory.value.imports || []) out.push({ ...entry, kind: 'content' });
  for (const entry of memory.value.mediaImports || []) out.push({ ...entry, kind: 'content' });
  for (const [term, kept] of Object.entries(memory.value.keptLanguage || {}))
    out.push({ id: `language:${term}`, title: term, kind: 'language', ...kept });
  return out;
}

export function renderCollection(root, ctx) {
  const c = ctx.c;
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const { memory, api, alive, language } = ctx;
  const highlights = Object.entries(memory.value.keptLanguage || {}).map(([term, kept]) => ({ term, ...kept }));
  const content = [...(memory.value.imports || []), ...(memory.value.mediaImports || [])];
  const state = { kind: 'words', words: null, failed: false, query: '', starred: false, sort: 'recent' };

  const count = (kind) =>
    kind === 'words' ? (state.words ? String(state.words.length) : '…')
      : kind === 'highlights' ? String(highlights.length)
        : kind === 'content' ? String(content.length)
          : '—';

  function wordsView() {
    if (state.failed)
      return `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.unavailable)}</strong></div><button type="button" class="outline" data-words-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`;
    if (!state.words)
      return `<div class="saved-grid" aria-hidden="true">${Array.from({ length: 4 }, () => '<span class="skeleton skeleton--card"></span>').join('')}</div>`;
    if (!state.words.length)
      return `<div class="state-panel state-panel--empty">${icon('bookmark-simple', { size: 22 })}<div><strong>${esc(r.savedNoWords)}</strong><p>${esc(r.savedNoWordsNote)}</p></div><a class="primary" href="${esc(link('practice', { intent: 'reading' }))}">${icon('book-open', { size: 16 })}<span>${esc(r.savedOpenBook)}</span></a></div>`;
    const q = state.query.trim().toLowerCase();
    let list = state.words.filter((w) => !q || `${w.word} ${w.translation_vi || ''} ${Object.values(w.support_translations || {}).join(' ')}`.toLowerCase().includes(q));
    if (state.starred) list = list.filter((w) => (Number(w.review_stage) || 0) < 2);
    list = [...list].sort((a, b) => (state.sort === 'recent' ? String(b.added_at || '').localeCompare(String(a.added_at || '')) : String(a.word).localeCompare(String(b.word))));
    const due = state.words.filter((w) => w.due).length;
    const rows = list.map((w) => {
      const stars = masteryStars(w);
      const filled = (stars.match(/★/g) || []).length;
      const from = SOURCE_KIND[w.source_kind] || '';
      const meaning = w.support_translations?.[ctx.support] || w.translation_vi || '';
      return `<a class="saved-word" href="${esc(w.source_essay_id ? link('expression', { id: `essay:${w.source_essay_id}` }) : link('language'))}"><span class="saved-word__text"><strong lang="${esc(language)}">${esc(w.word)}</strong><small>${esc([w.phonetic, meaning].filter(Boolean).join(' · '))}${from ? ` · ${esc(r.savedFrom)} <span class="saved-word__from">${esc(r[from] || from)}</span>` : ''}</small></span><span class="vocabulary-stars" aria-label="${esc(stars)}">${[0, 1, 2].map((n) => icon('star', { filled: n < filled, size: 12, className: n < filled ? 'is-earned' : '' })).join('')}</span></a>`;
    }).join('');
    return `<div class="saved-tools"><label class="library-search"><span class="sr-only">${esc(r.savedSearchWords)}</span>${icon('magnifying-glass', { size: 18 })}<input id="savedQuery" type="search" autocomplete="off" placeholder="${esc(r.savedSearchWords)}" value="${esc(state.query)}" data-saved-query></label><button type="button" class="saved-filter" aria-pressed="${state.starred}" data-saved-starred>${icon('funnel', { size: 14 })}<span>${esc(r.savedOneStar)}</span></button><button type="button" class="saved-filter" data-saved-sort>${icon('sliders-horizontal', { size: 14 })}<span>${esc(state.sort === 'recent' ? r.savedRecent : r.librarySortTitle)}</span></button></div><div class="saved-grid">${rows || `<p class="meta">${esc(r.libraryNoResults)}</p>`}</div>${due ? `<div class="saved-due" data-live><span class="saved-due__icon" data-domain="vocabulary">${icon('cards', { filled: true, size: 20 })}</span><div><strong>${esc(r.savedDue.replace('{n}', String(due)))}</strong></div><a class="primary" href="${esc(link('practice', { intent: 'recall' }))}">${esc(r.recall)}</a></div>` : ''}`;
  }

  function highlightsView() {
    if (!highlights.length)
      return `<div class="state-panel state-panel--empty">${icon('sparkle', { size: 22 })}<div><strong>${esc(r.savedNoHighlights)}</strong></div></div>`;
    return `<div class="saved-list">${highlights.map((h) => `<a class="saved-row" href="${esc(h.source ? sourceLink(h.source) : link('language'))}"><span class="saved-row__text"><strong lang="${esc(language)}">${esc(h.term)}</strong>${h.where ? `<small>${esc(h.where)}</small>` : ''}</span>${icon('caret-right', { size: 18 })}</a>`).join('')}</div>`;
  }

  function contentView() {
    if (!content.length)
      return `<div class="state-panel state-panel--empty">${icon('bookmark-simple', { size: 22 })}<div><strong>${esc(r.savedNoContent)}</strong></div><button type="button" class="primary" data-bring>${icon('plus', { size: 16 })}<span>${esc(c.bring)}</span></button></div>`;
    return `<div class="saved-list">${content.map((x) => `<a class="saved-row" href="${esc(sourceLink(x.id))}"><span class="saved-row__visual">${art(x)}</span><span class="saved-row__text"><strong>${esc(x.title || x.id)}</strong><small>${esc(x.kind === 'audio' || x.kind === 'video' || String(x.id).startsWith('url:') ? r.libraryType_audio : r.libraryType_books)}</small></span>${icon('caret-right', { size: 18 })}</a>`).join('')}</div><button type="button" class="library-more" data-bring>${icon('plus', { size: 16 })}<span>${esc(c.bring)}</span></button>`;
  }

  const notesView = () =>
    `<div class="state-panel state-panel--empty">${icon('pencil-simple', { size: 22 })}<div><strong>${esc(r.savedNotesUnavailable)}</strong></div></div>`;

  function paint() {
    if (!alive()) return;
    const focused = document.activeElement?.id;
    const body = { words: wordsView, highlights: highlightsView, notes: notesView, content: contentView }[state.kind]();
    root.innerHTML = `<section class="saved-page"><h1 class="saved-title">${esc(r.savedTitle)}</h1><div class="saved-panel"><div class="saved-tabs" role="tablist" aria-label="${esc(r.savedTitle)}">${KINDS.map((kind) => `<button type="button" role="tab" class="saved-tab" aria-selected="${state.kind === kind}" data-saved-kind="${kind}">${icon(KIND_ICON[kind], { size: 14, filled: state.kind === kind })}<span>${esc(r[`saved_${kind}`])}</span><span class="saved-tab__count">${esc(count(kind))}</span></button>`).join('')}</div><div class="saved-body" role="tabpanel">${body}</div></div></section>`;
    root.querySelectorAll('[data-saved-kind]').forEach((b) => (b.onclick = () => { state.kind = b.dataset.savedKind; paint(); }));
    const query = root.querySelector('[data-saved-query]');
    if (query) query.oninput = () => { state.query = query.value; paint(); };
    root.querySelector('[data-saved-starred]')?.addEventListener('click', () => { state.starred = !state.starred; paint(); });
    root.querySelector('[data-saved-sort]')?.addEventListener('click', () => { state.sort = state.sort === 'recent' ? 'title' : 'recent'; paint(); });
    root.querySelector('[data-words-retry]')?.addEventListener('click', load);
    root.querySelectorAll('[data-bring]').forEach((b) => (b.onclick = () => ctx.import?.()));
    if (focused) {
      const el = document.getElementById(focused);
      el?.focus();
      if (el?.setSelectionRange) el.setSelectionRange(el.value.length, el.value.length);
    }
  }
  async function load() {
    state.words = null;
    state.failed = false;
    paint();
    try {
      const data = await api.libraryVocabulary();
      state.words = data.items || [];
    } catch {
      state.failed = true;
    }
    paint();
  }
  load();
  return () => {};
}
