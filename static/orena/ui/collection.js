import { esc } from './html.js';
import { referenceCopy } from './reference.js';
import { icon } from './phosphor.js';

/* Thư viện của tôi (D-067, "Thư viện của tôi · desktop" and "· mobile") - one
   library over everything the learner kept, whatever kind it is.

   The human settled what this room is on 2026-09-23: Vocabulary is the shared
   catalogue a learner takes words from, and this is the learner's own library.
   So the room owns nothing: it reads `GET /api/collection`, the typed query
   over the owners that already exist (`writing_coach/collection_query.py`),
   and every row opens the place it came from through that owner's own route.
   No second store, no copy of a word, a passage or a take.

   Six of the eight kinds the frame draws have an owner today. A note has no
   owner in this repository at all and a book is catalogue only, so neither is
   a chip here - and the row's SRS column, its state pill, the mark and
   add-to-collection buttons, the due-today card, the collections column and
   the detail overlay all need the kept-item relation that does not exist yet.
   Every one of those is recorded in `docs/project/UI_BACKEND_GAPS.md`; none is
   invented here, and none is faked with a number nobody measured (rules 4, 7,
   43).

   What the old room drew - Saved, with four device-memory tabs - is deleted
   rather than restyled (rule 44). Its highlights and imports lived in the
   browser; this reads the account's own owners. */

/* The kinds, in the frame's order, each with the owner that answers it and the
   icon the frame gives it. */
const KINDS = [
  { id: 'language', icon: 'cards', label: 'myLibraryKind_language', serif: true },
  { id: 'grammar', icon: 'book-open-text', label: 'myLibraryKind_grammar' },
  { id: 'reading', icon: 'article', label: 'myLibraryKind_reading', serif: true },
  { id: 'media', icon: 'headphones', label: 'myLibraryKind_media', serif: true },
  { id: 'writing', icon: 'pen-nib', label: 'myLibraryKind_writing' },
  { id: 'speaking', icon: 'microphone', label: 'myLibraryKind_speaking' },
];
const PAGE = 24;
const SEARCH_DEBOUNCE_MS = 250;

/* How the row says where an entry stands with its owner. The owners record a
   relationship, not a grade, so this is the relationship and nothing else. */
const RELATIONSHIP = {
  saved: 'myLibraryRel_saved',
  started: 'myLibraryRel_started',
  submitted: 'myLibraryRel_submitted',
  practised: 'myLibraryRel_practised',
  spoken: 'myLibraryRel_spoken',
  completed: 'myLibraryRel_completed',
};

function day(value) {
  const stamp = String(value || '').trim();
  if (!stamp) return '';
  const when = new Date(stamp);
  return Number.isNaN(when.valueOf())
    ? ''
    : `${String(when.getDate()).padStart(2, '0')}/${String(when.getMonth() + 1).padStart(2, '0')}`;
}

export function renderCollection(root, ctx) {
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const c = ctx.c;
  const { api, alive, language } = ctx;
  const state = {
    kind: '', entries: null, failed: false, query: '', totals: {}, total: null,
    cursor: '', loading: false, request: 0, timer: null, partial: false,
  };

  const kindOf = (id) => KINDS.find((kind) => kind.id === id);

  function rows() {
    if (state.failed)
      return `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.unavailable)}</strong></div><button type="button" class="outline" data-library-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`;
    if (!state.entries)
      return `<div class="my-library__list" aria-hidden="true">${Array.from({ length: 4 }, () => '<span class="skeleton skeleton--card"></span>').join('')}</div>`;
    if (!state.entries.length)
      return `<div class="state-panel state-panel--empty">${icon('bookmarks-simple', { size: 22 })}<div><strong>${esc(state.query ? r.libraryNoResults : r.myLibraryEmpty)}</strong></div></div>`;
    const list = state.entries.map((entry) => {
      const kind = kindOf(entry.ref.domain);
      const relationship = r[RELATIONSHIP[entry.relationship]] || '';
      const meta = [r[kind?.label] || '', relationship].filter(Boolean).join(' · ');
      const when = day(entry.updatedAt);
      const body = `<div class="my-library-item__body"><div class="my-library-item__head"><span class="my-library-item__title"${kind?.serif ? ` lang="${esc(language)}"` : ''}>${esc(entry.title || '')}</span>${entry.snippet ? `<span class="my-library-item__gloss">${esc(entry.snippet)}</span>` : ''}</div><span class="my-library-item__meta">${esc(meta)}</span></div>${when ? `<span class="my-library-item__when ds-data">${esc(when)}</span>` : ''}`;
      /* An entry opens where it came from, through the owner's own route. An
         owner that has no route back says nothing rather than guessing one. */
      return entry.action
        ? `<a class="my-library-item" href="${esc(entry.action.route)}">${body}${icon('caret-right', { size: 18 })}</a>`
        : `<div class="my-library-item" data-unreachable>${body}</div>`;
    }).join('');
    const more = state.cursor
      ? `<div class="button-row"><button type="button" class="outline" data-library-more${state.loading ? ' disabled' : ''}>${esc(String(r.libraryLoadMore).replace('{n}', String(state.entries.length)))}</button></div>`
      : '';
    return `<div class="my-library__list">${list}</div>${more}`;
  }

  function paint() {
    if (!alive()) return;
    const focused = document.activeElement?.id;
    /* The count the bar carries is the one the read actually knows. An owner
       that was unavailable or that filled its page makes it a lower bound, and
       the bar says so rather than rounding it into a total. */
    const total = state.total;
    const counted = total == null ? '' : String(r[state.partial ? 'myLibraryAtLeast' : 'myLibraryCount']).replace('{n}', String(total));
    const chips = KINDS.map((kind) => {
      const on = state.kind === kind.id;
      /* Once a whole read has come back, a kind with nothing in it is a
         real zero, not an unknown. Before that there is no count to show. */
      const count = state.entries === null && !Object.keys(state.totals).length
        ? null
        : Number(state.totals[kind.id] || 0);
      return `<button type="button" class="my-library-chip" aria-pressed="${on}" data-library-kind="${kind.id}">${icon(kind.icon, { size: 16, filled: on })}<span>${esc(r[kind.label])}</span>${count == null ? '' : `<span class="my-library-chip__count ds-data">${esc(String(count))}</span>`}</button>`;
    }).join('');
    root.innerHTML = `<section class="my-library"><header class="my-library__bar"><h1>${esc(r.myLibrary)}</h1>${counted ? `<span class="my-library__count ds-data">${esc(counted)}</span>` : ''}<label class="library-search my-library__search"><span class="sr-only">${esc(r.myLibrarySearch)}</span>${icon('magnifying-glass', { size: 18 })}<input id="myLibraryQuery" type="search" autocomplete="off" placeholder="${esc(r.myLibrarySearch)}" value="${esc(state.query)}" data-library-query></label></header><div class="my-library__kinds">${chips}</div>${rows()}</section>`;
    root.querySelectorAll('[data-library-kind]').forEach((button) => (button.onclick = () => {
      state.kind = state.kind === button.dataset.libraryKind ? '' : button.dataset.libraryKind;
      load();
    }));
    const query = root.querySelector('[data-library-query]');
    if (query) query.oninput = () => { state.query = query.value; later(); };
    root.querySelector('[data-library-more]')?.addEventListener('click', (event) => {
      event.currentTarget.disabled = true;
      load({ append: true });
    });
    root.querySelector('[data-library-retry]')?.addEventListener('click', () => load());
    if (focused) {
      const element = document.getElementById(focused);
      element?.focus();
      if (element?.setSelectionRange) element.setSelectionRange(element.value.length, element.value.length);
    }
  }

  /* One page, asked for as a page. The counts per kind come back with it, so
     the chips are labelled from the same read rather than one read each. */
  async function load({ append = false } = {}) {
    const token = (state.request += 1);
    state.failed = false;
    state.loading = true;
    if (!append) {
      state.entries = null;
      state.cursor = '';
      paint();
    }
    try {
      const data = await api.collection({
        limit: PAGE,
        cursor: append ? state.cursor : '',
        query: state.query.trim(),
        domains: state.kind ? [state.kind] : [],
      });
      if (!alive() || token !== state.request) return;
      state.entries = append ? [...(state.entries || []), ...(data.entries || [])] : data.entries || [];
      state.cursor = data.nextCursor || '';
      state.partial = data.completeness !== 'complete';
      /* Only an unfiltered read knows every kind's count; a read of one kind
         keeps the counts it was last told rather than blanking the others. */
      if (!state.kind) state.totals = data.domainTotals || {};
      /* A partial read has no exact total, but it does know how much it read:
         the per-owner counts add up to it. That is a floor the bar can say
         honestly - never the page's own length, which would call 24 rows the
         whole library. */
      const counted = Object.values(data.domainTotals || {}).reduce((sum, n) => sum + Number(n || 0), 0);
      state.total = data.total == null ? counted || state.entries.length : Number(data.total);
    } catch {
      if (!alive() || token !== state.request) return;
      state.failed = true;
    } finally {
      if (token === state.request) state.loading = false;
    }
    if (alive() && token === state.request) paint();
  }

  const later = () => {
    if (state.timer) clearTimeout(state.timer);
    state.timer = setTimeout(() => load(), SEARCH_DEBOUNCE_MS);
  };
  load();
  return () => {
    if (state.timer) clearTimeout(state.timer);
  };
}
