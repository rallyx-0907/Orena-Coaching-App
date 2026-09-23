import { esc } from './html.js';
import { referenceCopy } from './reference.js';
import { icon } from './phosphor.js';
import { link } from '../product/intent.js';

/* Thư viện của tôi (D-067, "Thư viện của tôi · desktop" and "· mobile") - one
   library over everything the learner kept, whatever kind it is.

   The human settled what this room is on 2026-09-23 (D-074): Vocabulary is the
   shared catalogue a learner takes words from, and this is the learner's own
   library. The room owns nothing it draws. It reads two things and writes one:

   - `GET /api/collection`, the typed query over the owners that already exist
     (`writing_coach/collection_query.py`), for the rows themselves;
   - `GET /api/library/items`, the learner's own state over those rows - kept,
     marked, filed - asked once for the page, never once per row;
   - `POST`/`PATCH /api/library/items`, which records keeping and marking, and
     carries the version it read so two tabs cannot overwrite each other
     silently.

   Six of the eight kinds the frame draws have an owner. A note is stored
   nowhere in this repository and a book is catalogue only, so neither is a
   chip; both are recorded in `docs/project/UI_BACKEND_GAPS.md` rather than
   faked with an empty tab.

   Nothing here invents a schedule. The queue is what the design asks for -
   "marked first, then whatever is due" - over the schedule that exists, which
   is the saved words'. A passage is in the queue when the learner marked it,
   and not otherwise. */

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
/* The domain a row comes from, and the kind the library stores it under. They
   are the same word for every kind but the saved language, which the library
   calls `word` because that is what the schema's check constraint calls it. */
const ITEM_KIND = {
  language: 'word', grammar: 'grammar', reading: 'reading',
  media: 'listening', writing: 'writing', speaking: 'speaking',
};
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
    /* The learner's own state, by the ref each row is drawn from, plus the
       sets and the queue. `unavailable` is true when the account database is
       not there: the room still lists, and says what it cannot do. */
    own: new Map(), collections: [], queue: null, unavailable: false,
    detail: null, picking: null, busy: '', naming: null,
    /* What a word's recording may be played under, by word. Asked for only
       when a word's panel is open - this room draws no speaker, because its
       frames draw none; it credits what the review card plays. */
    credit: new Map(),
  };

  const kindOf = (id) => KINDS.find((kind) => kind.id === id);
  const refOf = (entry) => `${entry.ref.domain}:${entry.ref.id}`;
  const ownOf = (entry) => state.own.get(refOf(entry)) || null;
  const entryFor = (ref) => (state.entries || []).find((entry) => refOf(entry) === ref) || null;

  /* --- What is waiting (the frame's "CẦN ÔN HÔM NAY") -------------------- */
  function dueCard() {
    if (state.unavailable || !state.queue) return '';
    const marked = Number(state.queue.pinned_count || 0);
    const due = Number(state.queue.due_count || 0);
    const total = marked + due;
    const line = [
      marked ? String(r.myLibraryMarked).replace('{n}', String(marked)) : '',
      due ? String(r.myLibraryDueOf).replace('{n}', String(due)) : '',
    ].filter(Boolean).join(' · ');
    return `<section class="my-library-due"><div class="my-library-due__body"><span class="ds-label">${esc(r.myLibraryDue)}</span>`
      + `<div class="my-library-due__count"><strong>${esc(String(total))}</strong><span>${esc(String(r.myLibraryDueCount).replace('{n}', '').trim())}</span></div>`
      + `<p>${esc(line || r.myLibraryDueNone)}</p></div>`
      + (total ? `<a class="primary" href="${esc(link('practice', { intent: 'recall' }))}">${icon('play', { filled: true, size: 15 })}<span>${esc(r.myLibraryReviewNow)}</span></a>` : '')
      + `</section>`;
  }

  /* --- The sets (one kind each, as the frame says) ---------------------- */
  function sets() {
    if (state.unavailable) return '';
    const rows = state.collections.map((set) => {
      const kind = KINDS.find((entry) => ITEM_KIND[entry.id] === set.kind);
      const sub = String(r.myLibrarySetSize)
        .replace('{kind}', r[kind?.label] || set.kind)
        .replace('{n}', String(set.size));
      return `<div class="my-library-set"><span class="my-library-set__mark">${icon(kind?.icon || 'folder-simple', { size: 20 })}</span>`
        + `<span class="my-library-set__body"><strong>${esc(set.title)}</strong><small>${esc(sub)}</small></span></div>`;
    }).join('');
    return `<aside class="my-library__sets"><header><h2>${esc(r.myLibrarySets)}</h2><span>${esc(r.myLibrarySetsNote)}</span>`
      + `<button type="button" class="my-library__new-set" data-library-new-set>${esc(r.myLibraryNewSet)}</button></header>`
      + naming()
      + (rows || `<p class="meta">${esc(r.myLibrarySetsNone)}</p>`)
      + `</aside>`;
  }

  /* Naming a set happens in the room, in a field of its own. A browser
     prompt would be a dialog the design does not draw, and one that stops
     everything else on the page while it is open. */
  function naming() {
    if (!state.naming) return '';
    const kind = KINDS.find((entry) => ITEM_KIND[entry.id] === state.naming.kind);
    return `<form class="my-library-name" data-library-name-form>`
      + `<label class="library-search"><span class="sr-only">${esc(r.myLibrarySetName)}</span>`
      + `<input id="myLibrarySetName" type="text" autocomplete="off" maxlength="120" placeholder="${esc(r.myLibrarySetName)}" value="${esc(state.naming.title)}" data-library-name></label>`
      + `<span class="my-library-name__kind">${esc(r[kind?.label] || '')}</span>`
      + `<button type="submit" class="primary">${esc(r.myLibrarySetSave)}</button>`
      + `</form>`;
  }

  /* --- The rows --------------------------------------------------------- */
  function rows() {
    if (state.failed)
      return `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.unavailable)}</strong></div><button type="button" class="outline" data-library-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`;
    if (!state.entries)
      return `<div class="my-library__list" aria-hidden="true">${Array.from({ length: 4 }, () => '<span class="skeleton skeleton--card"></span>').join('')}</div>`;
    if (!state.entries.length)
      return `<div class="state-panel state-panel--empty">${icon('bookmarks-simple', { size: 22 })}<div><strong>${esc(state.query ? r.libraryNoResults : r.myLibraryEmpty)}</strong></div></div>`;
    const list = state.entries.map((entry) => {
      const kind = kindOf(entry.ref.domain);
      const own = ownOf(entry);
      const relationship = r[RELATIONSHIP[entry.relationship]] || '';
      const meta = [r[kind?.label] || '', relationship].filter(Boolean).join(' · ');
      const when = day(entry.updatedAt);
      const marked = Boolean(own?.pinned);
      const ref = esc(refOf(entry));
      /* The body opens the detail panel; the buttons do their own thing and do
         not open it, which is what the frame's own spec asks for. */
      const controls = state.unavailable ? '' : `<span class="my-library-item__actions">`
        + `<button type="button" class="my-library-item__act" aria-pressed="${marked}" title="${esc(marked ? r.myLibraryUnmark : r.myLibraryMark)}" data-library-mark="${ref}">${icon('bookmark-simple', { filled: marked, size: 17 })}</button>`
        + `<button type="button" class="my-library-item__act" title="${esc(r.myLibraryAddToSet)}" data-library-file="${ref}">${icon('folder-plus', { size: 17 })}</button>`
        + `</span>`;
      const open = entry.action
        ? `<a class="my-library-item__act" href="${esc(entry.action.route)}" title="${esc(r.myLibraryOpenSource)}">${icon('arrow-square-out', { size: 17 })}</a>`
        : '';
      return `<div class="my-library-item"${marked ? ' data-marked' : ''}>`
        + `<button type="button" class="my-library-item__body" data-library-open="${ref}">`
        + `<span class="my-library-item__head"><span class="my-library-item__title"${kind?.serif ? ` lang="${esc(language)}"` : ''}>${esc(entry.title || '')}</span>`
        + (entry.snippet ? `<span class="my-library-item__gloss">${esc(entry.snippet)}</span>` : '') + `</span>`
        + `<span class="my-library-item__meta">${esc(meta)}</span></button>`
        + (when ? `<span class="my-library-item__when ds-data">${esc(when)}</span>` : '')
        + controls + open + `</div>`;
    }).join('');
    const more = state.cursor
      ? `<div class="button-row"><button type="button" class="outline" data-library-more${state.loading ? ' disabled' : ''}>${esc(String(r.libraryLoadMore).replace('{n}', String(state.entries.length)))}</button></div>`
      : '';
    return `<div class="my-library__list">${list}</div>${more}`;
  }

  /* --- One thing, in full (the frame's right-hand panel) ---------------- */
  function detail() {
    if (!state.detail) return '';
    const { entry, own } = state.detail;
    const kind = kindOf(entry.ref.domain);
    const marked = Boolean(own?.pinned);
    const held = !marked && own?.state === 'mastered';
    const learning = !marked && own?.state === 'learning';
    const context = String(entry.detail?.sourceFragment || '');
    /* The history is the owner's own record of reviewing this thing. Only the
       saved language has one, so only a word shows it - a passage with three
       dashes would be three measures nobody took (rule 4, recorded in
       UI_BACKEND_GAPS.md). */
    const isWord = entry.ref.domain === 'language';
    const history = isWord
      ? `<div class="my-library-detail__history">`
        + `<div><span class="ds-label">${esc(r.myLibraryRecalls)}</span><strong>${esc(String(entry.detail?.successfulRecalls ?? 0))}</strong></div>`
        + `<div><span class="ds-label">${esc(r.myLibraryLastReview)}</span><strong>${esc(day(entry.detail?.lastReviewedAt) || '—')}</strong></div>`
        + `<div><span class="ds-label">${esc(r.myLibraryNextReview)}</span><strong>${esc(day(entry.detail?.nextReviewAt) || '—')}</strong></div>`
        + `</div>`
      : '';
    const inSets = (own?.collections || []).map((set) =>
      `<span class="my-library-detail__set">${icon('folder-simple', { size: 14 })}${esc(set.title)}</span>`).join('');
    return `<div class="my-library-scrim" data-library-close></div>`
      + `<aside class="my-library-detail" role="dialog" aria-label="${esc(entry.title || '')}">`
      + `<header><span class="my-library-detail__kind">${icon(kind?.icon || 'bookmarks-simple', { size: 15 })}${esc(r[kind?.label] || '')}</span>`
      + `<button type="button" class="my-library-item__act" title="${esc(r.myLibraryClose)}" data-library-close>${icon('x', { size: 17 })}</button></header>`
      + `<div class="my-library-detail__head"><span class="my-library-detail__title"${kind?.serif ? ` lang="${esc(language)}"` : ''}>${esc(entry.title || '')}</span>`
      + (entry.snippet ? `<span class="my-library-detail__gloss">${esc(entry.snippet)}</span>` : '') + `</div>`
      + (context ? `<section class="my-library-detail__context"><span class="ds-label">${esc(r.myLibraryContext)}</span><p lang="${esc(language)}">${esc(context)}</p></section>` : '')
      + (state.unavailable
        ? `<p class="meta">${esc(r.myLibraryUnavailable)}</p>`
        : `<section class="my-library-detail__state"><span class="ds-label">${esc(r.myLibraryState)}</span>`
          + `<div class="my-library-detail__choice" role="group">`
          + `<button type="button" aria-pressed="${marked}" data-library-state="marked">${icon('bookmark-simple', { filled: marked, size: 15 })}<span>${esc(r.myLibraryStateMarked)}</span></button>`
          + `<button type="button" aria-pressed="${learning}" data-library-state="learning">${icon('circle-half', { size: 15 })}<span>${esc(r.myLibraryStateLearning)}</span></button>`
          + `<button type="button" aria-pressed="${held}" data-library-state="mastered">${icon('check-circle', { filled: held, size: 15 })}<span>${esc(r.myLibraryStateKnown)}</span></button>`
          + `</div><p>${esc(r.myLibraryStateNote)}</p></section>`)
      + history
      + (inSets ? `<section class="my-library-detail__sets"><span class="ds-label">${esc(r.myLibraryInSets)}</span><div>${inSets}</div></section>` : '')
      + credit(entry)
      + `<div class="my-library-detail__foot">`
      + (state.unavailable ? '' : `<button type="button" class="outline" data-library-file="${esc(refOf(entry))}">${icon('folder-plus', { size: 16 })}<span>${esc(r.myLibraryAddToSet)}</span></button>`)
      + (entry.action ? `<a class="primary" href="${esc(entry.action.route)}">${icon('arrow-square-out', { size: 16 })}<span>${esc(r.myLibraryOpenSource)}</span></a>` : '')
      + `</div></aside>`;
  }

  /* The credit a Commons recording obliges: who recorded it, under what, and
     where it came from (human decision, 2026-09-23). The design draws no place
     for this, so it is here rather than on the review card that plays it, and
     the source is a link because "where it came from" is the part a licence
     asks to be reachable. */
  function credit(entry) {
    if (entry.ref.domain !== 'language') return '';
    const found = state.credit.get(entry.title);
    if (!found) return '';
    return `<section class="my-library-detail__credit"><span class="ds-label">${esc(r.myLibraryAudioCredit)}</span>`
      + `<p>${esc(found.attribution)}</p>`
      + (found.source ? `<a href="${esc(found.source)}" target="_blank" rel="noreferrer noopener">${esc(r.myLibraryAudioSource)}</a>` : '')
      + `</section>`;
  }

  /* --- Choosing a set: only sets of this thing's own kind ---------------- */
  function picker() {
    if (!state.picking) return '';
    const { entry } = state.picking;
    const wanted = ITEM_KIND[entry.ref.domain];
    const kind = kindOf(entry.ref.domain);
    const options = state.collections.filter((set) => set.kind === wanted);
    const rows = options.map((set) =>
      `<button type="button" class="my-library-pick__row" data-library-pick="${esc(set.id)}">${icon('folder-simple', { size: 16 })}<span>${esc(set.title)}</span></button>`).join('');
    return `<div class="my-library-scrim" data-library-close></div>`
      + `<div class="my-library-pick" role="dialog" aria-label="${esc(r.myLibraryAddToSet)}">`
      + `<header><strong>${esc(r.myLibraryAddToSet)}</strong><span>${esc(r[kind?.label] || '')}</span></header>`
      + (rows || `<p class="meta">${esc(r.myLibrarySetsNone)}</p>`)
      + (state.naming
        ? naming()
        : `<button type="button" class="outline" data-library-new-set>${icon('plus', { size: 16 })}<span>${esc(r.myLibraryNewSet)}</span></button>`)
      + `</div>`;
  }

  function paint() {
    if (!alive()) return;
    const focused = document.activeElement?.id;
    const total = state.total;
    const counted = total == null ? '' : String(r[state.partial ? 'myLibraryAtLeast' : 'myLibraryCount']).replace('{n}', String(total));
    const chips = KINDS.map((kind) => {
      const on = state.kind === kind.id;
      /* Once a whole read has come back, a kind with nothing in it is a real
         zero, not an unknown. Before that there is no count to show. */
      const count = state.entries === null && !Object.keys(state.totals).length
        ? null
        : Number(state.totals[kind.id] || 0);
      return `<button type="button" class="my-library-chip" aria-pressed="${on}" data-library-kind="${kind.id}">${icon(kind.icon, { size: 16, filled: on })}<span>${esc(r[kind.label])}</span>${count == null ? '' : `<span class="my-library-chip__count ds-data">${esc(String(count))}</span>`}</button>`;
    }).join('');
    root.innerHTML = `<section class="my-library"><header class="my-library__bar"><h1>${esc(r.myLibrary)}</h1>${counted ? `<span class="my-library__count ds-data">${esc(counted)}</span>` : ''}<label class="library-search my-library__search"><span class="sr-only">${esc(r.myLibrarySearch)}</span>${icon('magnifying-glass', { size: 18 })}<input id="myLibraryQuery" type="search" autocomplete="off" placeholder="${esc(r.myLibrarySearch)}" value="${esc(state.query)}" data-library-query></label></header>`
      + `<div class="my-library__columns"><div class="my-library__main">${dueCard()}<div class="my-library__kinds">${chips}</div>${rows()}</div>${sets()}</div>`
      + detail() + picker() + `</section>`;
    bind();
    if (focused) {
      const element = document.getElementById(focused);
      element?.focus();
      if (element?.setSelectionRange) element.setSelectionRange(element.value.length, element.value.length);
    }
  }

  function bind() {
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
    root.querySelectorAll('[data-library-open]').forEach((button) => (button.onclick = () => {
      const entry = entryFor(button.dataset.libraryOpen);
      if (!entry) return;
      state.detail = { entry, own: ownOf(entry) };
      paint();
      askCredit(entry);
    }));
    root.querySelectorAll('[data-library-close]').forEach((button) => (button.onclick = () => {
      state.detail = null; state.picking = null; paint();
    }));
    root.querySelectorAll('[data-library-mark]').forEach((button) => (button.onclick = () => mark(button.dataset.libraryMark)));
    root.querySelectorAll('[data-library-state]').forEach((button) => (button.onclick = () => choose(button.dataset.libraryState)));
    root.querySelectorAll('[data-library-file]').forEach((button) => (button.onclick = () => {
      const entry = entryFor(button.dataset.libraryFile);
      if (entry) { state.picking = { entry }; state.detail = null; paint(); }
    }));
    root.querySelectorAll('[data-library-pick]').forEach((button) => (button.onclick = () => file(button.dataset.libraryPick)));
    root.querySelectorAll('[data-library-new-set]').forEach((button) => (button.onclick = () => {
      const entry = state.picking?.entry || null;
      state.naming = { kind: entry ? ITEM_KIND[entry.ref.domain] : ITEM_KIND[state.kind || 'language'], title: '' };
      paint();
      document.getElementById('myLibrarySetName')?.focus();
    }));
    const naming = root.querySelector('[data-library-name-form]');
    if (naming) naming.onsubmit = (event) => { event.preventDefault(); newSet(); };
    const named = root.querySelector('[data-library-name]');
    if (named) named.oninput = () => { if (state.naming) state.naming.title = named.value; };
  }

  /* One word, once: the answer is cached on the server by (entry identity,
     reading), so an open panel costs one request the first time and none
     afterwards. A word with no recording credits nothing. */
  async function askCredit(entry) {
    if (entry.ref.domain !== 'language' || state.credit.has(entry.title)) return;
    state.credit.set(entry.title, null);
    try {
      const answer = await api.wordAudio(entry.title, entry.detail?.readingKey || '');
      if (!alive()) return;
      if (answer?.available) {
        state.credit.set(entry.title, answer);
        paint();
      }
    } catch {
      /* No credit to show, and nothing to say about it. */
    }
  }

  /* --- Writing ---------------------------------------------------------- */

  /* Keeping is implicit in marking: the first time the learner marks
     something, the relationship is recorded, and then marked. */
  async function itemFor(entry) {
    const existing = ownOf(entry);
    if (existing) return existing;
    const kind = ITEM_KIND[entry.ref.domain];
    const payload = kind === 'word'
      ? { kind, word: entry.title }
      : { kind, source_id: entry.ref.id, relationship: entry.relationship === 'kept' ? 'kept' : 'started' };
    const answer = await api.libraryKeep(payload);
    state.own.set(refOf(entry), answer.item);
    return answer.item;
  }

  async function mark(ref) {
    const entry = entryFor(ref);
    if (!entry || state.busy === ref) return;
    state.busy = ref;
    try {
      const item = await itemFor(entry);
      const changed = await api.libraryItemPatch(item.id, {
        expected_version: item.version, pinned: !item.pinned,
      });
      state.own.set(ref, { ...changed.item, collections: item.collections || [] });
      state.queue = await api.libraryReviewQueue().catch(() => state.queue);
    } catch {
      /* The paint below shows what is actually stored, not what was asked. */
    } finally {
      state.busy = '';
    }
    if (alive()) { refreshDetail(); paint(); }
  }

  /* The frame's three states are one control: marked is the pin, the other two
     are the learner's own override of what the owner would say. */
  async function choose(which) {
    if (!state.detail) return;
    const entry = state.detail.entry;
    try {
      const item = await itemFor(entry);
      const answer = await api.libraryItemPatch(item.id, {
        expected_version: item.version,
        pinned: which === 'marked',
        state: which === 'marked' ? null : which,
        clear_state: which === 'marked',
      });
      state.own.set(refOf(entry), { ...answer.item, collections: item.collections || [] });
      state.queue = await api.libraryReviewQueue().catch(() => state.queue);
    } catch {
      /* Same again: what is painted is what is stored. */
    }
    if (alive()) { refreshDetail(); paint(); }
  }

  async function file(collectionId) {
    if (!state.picking) return;
    const entry = state.picking.entry;
    try {
      const item = await itemFor(entry);
      await api.libraryCollectionAdd(collectionId, item.id);
      const detailed = await api.libraryItem(item.id).catch(() => null);
      if (detailed?.item) state.own.set(refOf(entry), detailed.item);
      const sets = await api.libraryCollections().catch(() => null);
      if (sets) state.collections = sets.collections || [];
    } catch {
      /* Nothing to say here that the next paint will not say. */
    }
    state.picking = null;
    if (alive()) paint();
  }

  async function newSet() {
    if (!state.naming) return;
    const entry = state.picking?.entry || null;
    const kind = state.naming.kind;
    const title = String(state.naming.title || '').trim();
    if (!title) return;
    state.naming = null;
    try {
      const answer = await api.libraryCollectionCreate({ kind, title });
      state.collections = [...state.collections, { ...answer.collection, size: 0 }]
        .sort((a, b) => String(a.title).localeCompare(String(b.title)));
      if (entry) { await file(answer.collection.id); return; }
    } catch {
      /* A duplicate name, or a kind that has no owner: the list is unchanged. */
    }
    if (alive()) paint();
  }

  function refreshDetail() {
    if (!state.detail) return;
    const entry = entryFor(refOf(state.detail.entry)) || state.detail.entry;
    state.detail = { entry, own: ownOf(entry) };
  }

  /* --- Reading ---------------------------------------------------------- */

  /* One page, asked for as a page, and one lookup of the learner's own state
     over the rows it holds. The counts per kind come back with the page, so
     the chips are labelled from the same read. */
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
      await loadOwn();
    } catch {
      if (!alive() || token !== state.request) return;
      state.failed = true;
    } finally {
      if (token === state.request) state.loading = false;
    }
    if (alive() && token === state.request) paint();
  }

  async function loadOwn() {
    const words = (state.entries || []).filter((entry) => entry.ref.domain === 'language').map((entry) => entry.title);
    const sources = (state.entries || []).filter((entry) => entry.ref.domain !== 'language').map((entry) => entry.ref.id);
    try {
      const [byWord, bySource, sets, queue] = await Promise.all([
        words.length ? api.libraryItems({ kind: 'word', words }) : Promise.resolve({ items: [] }),
        sources.length ? api.libraryItems({ sources }) : Promise.resolve({ items: [] }),
        api.libraryCollections(),
        api.libraryReviewQueue(),
      ]);
      if (!alive()) return;
      state.unavailable = false;
      state.own = new Map();
      for (const item of byWord.items || []) {
        const entry = (state.entries || []).find((row) => row.ref.domain === 'language' && row.title === item.word);
        if (entry) state.own.set(refOf(entry), item);
      }
      for (const item of bySource.items || []) {
        const entry = (state.entries || []).find((row) => row.ref.domain !== 'language' && row.ref.id === item.source_id);
        if (entry) state.own.set(refOf(entry), item);
      }
      state.collections = sets.collections || [];
      state.queue = queue;
    } catch {
      /* The account database is not there. The room still lists what the
         owners hold; it cannot mark or file, and the detail panel says so. */
      if (!alive()) return;
      state.unavailable = true;
      state.own = new Map();
      state.collections = [];
      state.queue = null;
    }
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
