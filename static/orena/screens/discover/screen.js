/* Frame 04-Discover.html + the Filter Sheet overlay (52-Filter-Sheet.html). Browse everything a
   learner can start from: published Reading articles, the shared Reading library, the Listening
   library (curated and shared imports, already merged by the server), curated vocabulary
   collections, and this device's own kept text/media (product/memory.js). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { mediaCard, headlineTitle, settleCovers } from '../../kit/components.js';
import { langSpan, langAttr } from '../../kit/lang.js';
import { emptyMarkup } from '../../kit/states.js';
import { openSheet, sheetHead, fillSheet } from '../../kit/overlay.js';
import { api } from '../../infrastructure/api.js';
import { syncImports } from '../../shell/context.js';
import { openMedia } from '../../product/media-source.js';
import { sourceFromLesson } from '../../product/speaking-source.js';
import { shellCopy as ts } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { t } from './copy.js';
import { overviewMarkup } from './overview.js';
import {
  entryFromArticle, entryFromBook, entryFromMedia, entryFromCollection,
  entryFromTextImport, entryFromMediaImport, filterOptions, visibleEntries,
  presentCard, hrefFor, overviewSections, typeLabel, topicLabel, hasAnyFilter, filterCount, practiceCandidates, practiceHref, preparedMediaEntry,
} from './model.js';

const TAB_LABEL_KEY = { all: 'tabAll', read: 'tabRead', listen: 'tabListen', collections: 'tabCollections', imported: 'tabImported' };
const TABS = Object.keys(TAB_LABEL_KEY);
const FILTER_GROUPS = [
  { key: 'level', labelKey: 'groupLevel' },
  { key: 'topic', labelKey: 'groupTopic' },
  { key: 'type', labelKey: 'groupType' },
];

const bookCoverUrl = (id) => `/api/reading/library/books/${encodeURIComponent(id)}/cover`;

function emptyFilters() {
  return { level: new Set(), topic: new Set(), type: new Set() };
}

export default async function discover(element, ctx) {
  await useStyles('screens/discover/discover.css');
  const learner = ctx.context;
  const language = learner.language;
  const support = languages().support;
  const memory = learner.memory;
  const continuation = memory?.value?.continuation || [];
  const practice = ['pronunciation','shadowing','dictation','listening'].includes(ctx.query.get('practice')) ? ctx.query.get('practice') : '';
  const pronunciation = practice === 'pronunciation';
  // Shadowing (D-139 HD-2) chooses media for the same room; only media with a model recording, never an authored sentence.
  const speakingPractice = pronunciation || practice === 'shadowing';
  const practiceLabel = pronunciation ? 'pronunciation' : practice === 'listening' ? 'listeningComprehension' : practice;
  if (practice) ctx.setCrumb(ts(practiceLabel));
  const practicePlace = { source: ctx.query.get('source'), segment: ctx.query.get('segment'), intent: practice };

  const state = { tab: practice ? 'all' : TABS.includes(ctx.query.get('tab')) ? ctx.query.get('tab') : 'all', query: '', filters: emptyFilters(), entries: [], loading: true, failed: false };
  let sheetHandle = null;

  mount(
    element,
    html`<div class="s-discover">
      <div class="o-pagehead">
        ${practice
          // A practice chooser is entered from Practice Hub or a room, so it has its own way back (G-15, review 2026-10-08).
          ? html`<div class="s-discover__practicehead"><button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${ts('back')}">${raw(icon('arrow-left', { size: 21 }))}</button><h1 class="o-h1">${ts(practiceLabel)}</h1></div>`
          : html`<div><h1 class="o-h1">${ts('discover')}</h1><p class="s-discover__sub">${t('subtitle')}</p></div>`}
        <div class="s-discover__actions">
          <button type="button" class="o-btn o-btn--secondary" data-filters>${raw(icon('list-filter', { size: 16 }))}${t('filters')}<span data-filtercount></span></button>
          ${practice === 'listening' ? '' : html`<button type="button" class="o-btn o-btn--primary" data-import>+ ${t('importAction')}</button>`}
        </div>
      </div>
      <div class="o-search">
        ${raw(icon('search', { size: 18 }))}
        <input type="search" autocomplete="off" placeholder="${t(practice ? 'practiceSearch' : 'searchPlaceholder')}" data-query>
      </div>
      ${practice ? html`<p class="o-muted s-discover__hint">${t(speakingPractice ? 'choosePracticeMedia' : practice === 'dictation' ? 'chooseDictationMedia' : 'chooseListeningMedia')}</p>` : ''}
      <div class="o-tabs" data-tabs ${practice ? raw('hidden') : ''}></div>
      <div class="s-discover__results" data-results-row></div>
      <div data-results></div>
    </div>`,
  );

  const root = element.querySelector('.s-discover');
  const tabsEl = root.querySelector('[data-tabs]');
  const resultsRowEl = root.querySelector('[data-results-row]');
  const resultsEl = root.querySelector('[data-results]');
  const filterCountEl = root.querySelector('[data-filtercount]');
  const queryInput = root.querySelector('[data-query]');

  function visible() {
    return visibleEntries(state.entries, { tab: state.tab, query: state.query, filters: state.filters });
  }

  function paintTabs() {
    if (practice) return;
    mount(
      tabsEl,
      html`${TABS.map((id) => html`<button type="button" class="o-tab" role="tab" aria-selected="${state.tab === id ? 'true' : 'false'}" data-tab="${id}"><span>${t(TAB_LABEL_KEY[id])}</span><span class="o-tab__bar"></span></button>`)}`,
    );
    tabsEl.querySelectorAll('[data-tab]').forEach((button) => {
      button.addEventListener('click', () => openTab(button.dataset.tab));
    });
  }

  // The tab bar and every section's "See all" change the tab the same way: in place, no route.
  function openTab(id) {
    if (!TABS.includes(id) || id === state.tab) return;
    state.tab = id;
    paintTabs();
    paintResults();
  }

  // One card for one entry, as every tab draws it (the All overview reuses it unchanged).
  function cardFor(entry) {
    // Navigation history is not completion of this newly chosen practice.
    const card = presentCard(practice ? { ...entry, started: false, progressPct: null } : entry, t);
    return mediaCard({ ...card, title: langSpan(headlineTitle(card.title), card.titleLang), fullTitle: card.title, dataset: { go: practice ? practiceHref(entry, ctx.href, practicePlace) : hrefFor(entry, ctx.href) } });
  }

  function paintFilterBadge() {
    const count = filterCount(state.filters);
    mount(filterCountEl, count ? html`<span class="s-discover__filtercount">${count}</span>` : '');
  }

  function paintResults() {
    const list = visible();
    const hasFilters = hasAnyFilter(state.filters);
    /* D2 bindings / orena-script.js: the count row names the active tab once it narrows the
       scope ("N items · Read") - real interactive state, not the frame's sample wording. */
    const tabSuffix = state.tab === 'all' ? '' : ` · ${t(TAB_LABEL_KEY[state.tab])}`;
    mount(
      resultsRowEl,
      html`<div>${t.plural('resultsLabel', list.length)}${tabSuffix}</div>${hasFilters && list.length ? html`<button type="button" class="o-btn o-btn--link" data-clear>${t('clearFilters')}</button>` : ''}`,
    );
    resultsRowEl.querySelector('[data-clear]')?.addEventListener('click', clearFilters);

    const overview = !practice && state.tab === 'all';

    if (!list.length && !state.loading) {
      mount(resultsEl, emptyMarkup({ text: t('emptyText'), actionLabel: hasFilters || state.query.trim() ? t('clearFilters') : '', iconName: 'inbox' }));
      resultsEl.querySelector('[data-empty-action]')?.addEventListener('click', clearFilters);
    } else if (overview) {
      /* D-16V: All is an overview of four sections, never one grid of every type. Each section
         draws the same cards its own tab draws (cardFor) and a "See all" that opens that tab. */
      mount(resultsEl, overviewMarkup(overviewSections(state.entries, { query: state.query, filters: state.filters }), { card: cardFor, t }));
      resultsEl.querySelectorAll('[data-see-all]').forEach((button) => {
        button.addEventListener('click', () => {
          openTab(button.dataset.seeAll);
          // The section the learner pressed sits far down the page; the tab they opened starts at its top.
          root.scrollIntoView({ block: 'start' });
        });
      });
    } else {
      mount(resultsEl, html`<div class="s-discover__grid">${list.map(cardFor)}</div>`);
    }
    settleCovers(resultsEl);
    paintFilterBadge();
    if (sheetHandle) paintSheetBody(sheetHandle.element);
  }

  function clearFilters() {
    state.filters = emptyFilters();
    state.query = '';
    queryInput.value = '';
    paintResults();
  }

  function toggleFilter(group, value) {
    const set = state.filters[group];
    if (set.has(value)) set.delete(value);
    else set.add(value);
    paintResults();
  }

  function paintSheetBody(sheet) {
    const groups = filterOptions(state.entries);
    const body = html`${sheetHead({ title: t('filters'), closeLabel: ts('close') })}
      <div class="o-sheet__body">
        ${FILTER_GROUPS.map(
          (group) => html`<div>
            <div class="s-discover-fgroup__label">${t(group.labelKey)}</div>
            <div class="s-discover-fgroup__chips">
              ${groups[group.key].map((value) => {
                const pressed = state.filters[group.key].has(value);
                const label = group.key === 'type' ? typeLabel(value, t) : group.key === 'topic' ? topicLabel(value, t) : value;
                // languages-4 (3) / finding B.3: the topic group's own chip is the same open,
                // untranslatable content metadata as the card's own topic tag (presentCard above) -
                // marked lang="en" for the same reason, never silently unlabelled.
                return html`<button type="button" class="o-chip" aria-pressed="${pressed ? 'true' : 'false'}" data-fgroup="${group.key}" data-fvalue="${value}">${label}</button>`;
              })}
            </div>
          </div>`,
        )}
      </div>
      <div class="o-sheet__foot">
        <button type="button" class="o-btn o-btn--secondary" data-sheet-clear>${t('clear')}</button>
        <button type="button" class="o-btn o-btn--primary" data-sheet-close${visible().length ? '' : raw(' disabled')}>${t.plural('showResults', visible().length)}</button>
      </div>`;
    /* fillSheet (kit/overlay.js) mounts the markup and wires every [data-sheet-close] to
       handle.close() itself (bindClose) - the header X and the "Show N results" footer button
       both carry that attribute, so both close the sheet with no extra wiring here. */
    fillSheet(sheet, sheetHandle, body);
    sheet.querySelectorAll('[data-fgroup]').forEach((button) => {
      button.addEventListener('click', () => toggleFilter(button.dataset.fgroup, button.dataset.fvalue));
    });
    sheet.querySelector('[data-sheet-clear]').addEventListener('click', clearFilters);
  }

  root.querySelector('[data-back]')?.addEventListener('click', () => ctx.back());
  root.querySelector('[data-filters]').addEventListener('click', () => {
    openSheet({
      label: t('filters'),
      render(sheet, handle) {
        sheetHandle = handle;
        paintSheetBody(sheet);
        return () => {
          sheetHandle = null;
        };
      },
    });
  });

  root.querySelector('[data-import]')?.addEventListener('click', () => {
    import('../import/sheet.js')
      .then((module) => module.openImport(ctx, { mediaRoute: speakingPractice ? 'shadow' : practice === 'dictation' ? 'dictation' : 'listening' }))
      .catch((error) => console.error('[Orena] Import is not available yet', error));
  });

  let searchTimer = null;
  queryInput.addEventListener('input', () => {
    state.query = queryInput.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(paintResults, 120);
  });

  paintTabs();
  paintResults();

  /* Every published article, page by page (the endpoint pages with a cursor): the search and the
     Read tab look across the whole catalogue, not only its first page (D-129 R-32). */
  async function allReadingArticles(code) {
    const items = [];
    let cursor;
    for (let page = 0; page < 20; page += 1) {
      const value = await api.readingArticles(code, cursor).catch(() => null);
      if (!value) break;
      items.push(...(value.items || []));
      cursor = value.next_cursor;
      if (!cursor) break;
    }
    return { items };
  }

  /* Each source lands in its own bucket and is painted as it arrives (not in practice mode, which
     waits for every source): a slow or failed source leaves only its own section late or out, never
     the others (D-16V). The bucket order is the order the tabs and the sections list their cards. */
  const buckets = { articles: [], books: [], media: [], collections: [] };
  function compose() {
    const textEntries = (memory?.value?.imports || []).map((item) => entryFromTextImport(item));
    const mediaEntries = (memory?.value?.mediaImports || []).map((item) => entryFromMediaImport(item, continuation));
    state.entries = [
      ...buckets.articles.map((item) => entryFromArticle(item, continuation)),
      ...buckets.books.map((item) => entryFromBook(item, continuation, bookCoverUrl(item.id))),
      ...buckets.media.map((item) => entryFromMedia(item, continuation)),
      ...buckets.collections.map((item) => entryFromCollection(item)),
      ...textEntries,
      ...mediaEntries,
    ];
  }
  function arrived() {
    if (practice || !ctx.isCurrent()) return;
    compose();
    paintResults();
  }
  const bucketed = (key, request) => request.then((value) => {
    buckets[key] = value?.items || [];
    arrived();
    return value;
  });

  async function load() {
    if (!practice) compose();
    const [, , , , speaking] = await Promise.all([
      bucketed('articles', allReadingArticles(language)),
      bucketed('books', api.libraryBooks(language).catch(() => ({ items: [] }))),
      bucketed('media', api.listeningLibrary(language).catch(() => ({ items: [] }))),
      bucketed('collections', api.vocabularyLibraryCollections(language).catch(() => ({ items: [] }))),
      pronunciation ? api.speakingLibrary(language).catch(() => ({items:[]})) : Promise.resolve({items:[]}),
      // The account's imports: a deletion made on another device leaves this list (no deletion is offered here).
      syncImports(memory, language).catch(() => false).then((value) => { arrived(); return value; }),
    ]);
    compose();
    if (practice) {
      const privateMedia = await Promise.all((practice === 'listening' ? [] : memory?.value?.mediaImports || []).map(async item => {
        try {
          const payload = await openMedia(item.id, {api, support, language, owner:learner.owner});
          const source = sourceFromLesson(item.id, payload, '', support);
          return preparedMediaEntry(item.id, payload, source, language, continuation);
        } catch { return null; }
      }));
      const authored = pronunciation ? (speaking.items || []).filter(item=>item.practice_type === 'sentences').map(item=>({
        id:item.id, speakingId:item.id, kind:'text', title:item.title || '', language:item.language || language,
        author:'',level:item.level || '',topic:'',image:'',
      })) : [];
      const candidates = [...practiceCandidates(state.entries, practice), ...practiceCandidates(privateMedia.filter(Boolean), practice), ...authored];
      state.entries = [...new Map(candidates.map(entry=>[entry.id,entry])).values()];
    }
  }

  await load();
  if (!ctx.isCurrent()) return;
  state.loading = false;
  paintResults();

  return () => {
    clearTimeout(searchTimer);
  };
}
