/* My Library (frame 12, D-088/D-091): everything a learner saved, met, or needs to come back to.
   Five tabs, the live design script's own order: Saved content, Saved language, Collections,
   Active use, Due Review. */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { mediaCard, masteryBars } from '../../kit/components.js';
import { COVER_VISUALS } from '../../kit/cover-visuals.js';
import { langAttr, langSpan } from '../../kit/lang.js';
import { emptyMarkup } from '../../kit/states.js';
import { api } from '../../infrastructure/api.js';
import { shellCopy as sc } from '../../copy/shell.js';
import { moreButton, moreMenu } from '../../kit/overflow.js';
import { toast } from '../../kit/toast.js';
import { syncImports } from '../../shell/context.js';
import { deleteWithUndo, onImportsChanged } from '../../product/import-undo.js';
import { languages } from '../../copy/index.js';
import { meaningLanguageLabel } from '../../product/vocabulary-meaning.js';
import { t } from './copy.js';
import { placeFor } from '../content/model.js';
import { isDeferred } from '../../shell/routes.js';
import {
  contentRows, languageRows, collectionsAndDecks, dueStats, dueListRows, sessionRows, sessionSourceCount,
} from './model.js';

/* Five tabs, the live design script's own order (`orena-script.js` LIBT) - not the four the
   pinned copy's compact export hinted (`hint-placeholder-count="4"` on `libTabs`'s `sc-for`, a
   placeholder guess the truncated export makes when it cannot read real sample data, not a real
   count; §1 "read the source, not a copy"). */
const TABS = ['content', 'language', 'collections', 'active', 'due'];

/* The kit's small tag naming a meaning's language when it is not the support language (D-124). */
function meaningTag(language) {
  const label = meaningLanguageLabel(language, languages().support, languages().ui);
  return label ? html` <span class="o-tag">${label}</span>` : '';
}

function tabLabel(id, dueCount) {
  return {
    content: t('tabContent'), language: t('tabLanguage'), collections: t('tabCollections'),
    active: t('tabActive'), due: t('tabDueCount', { n: dueCount }),
  }[id];
}

function tabsMarkup(active, dueCount) {
  return html`<div class="o-tabs" role="tablist">${TABS.map((id) => html`<button type="button" class="o-tab" role="tab" aria-selected="${id === active ? 'true' : 'false'}" data-tab="${id}"><span>${tabLabel(id, dueCount)}</span><span class="o-tab__bar"></span></button>`)}</div>`;
}

/* languages-5 / finding A: both `row.title` (Saved content) and `row.word` (Saved language) are
   real content this account saved, both fetched through routes scoped to the learner's active
   learning language server-side (GET /api/collection and GET /api/library/vocabulary both read
   `current_language_code()`, writing_coach/collection_api.py / becoming_library.py) - never a
   guess, the actual language every row this call can return is in. */
function contentRow(row, language) {
  return html`<button type="button" class="s-library-content-row" data-content="${row.contentId}">
    <span class="s-library-content-row__body">
      <span class="s-library-content-row__type">${row.domain === 'media' ? sc('listening') : sc('content')}</span>
      <span class="s-library-content-row__title">${row.title ? langSpan(row.title, language) : t('untitledContent')}</span>
      ${row.source || row.unavailable ? html`<span class="s-library-content-row__source">${row.source || t('contentUnavailable')}</span>` : ''}
      <span class="s-library-content-row__progress"><span class="o-progress"><span style="width:${row.pct}%"></span></span><span class="s-library-content-row__pct">${row.pct}%</span></span>
    </span>
    <span class="s-library-content-row__chevron">${raw(icon('chevron-right', { size: 20 }))}</span>
  </button>`;
}

/* A learner's own import: the same row with the design's "⋯" beside it (frame 14's overflow pattern), whose menu
   holds "Delete from Orena" (D-107). Discover never offers it. */
function ownContentRow(row, language, menuFor) {
  const open = menuFor === row.importId;
  return html`<div class="s-library-content-own">
    <div class="s-library-content-row s-library-content-row--own">
      <button type="button" class="s-library-content-row__main" data-content="${row.contentId}">
        <span class="s-library-content-row__body">
          <span class="s-library-content-row__type">${row.domain === 'media' ? sc('listening') : sc('content')}</span>
          <span class="s-library-content-row__title">${langSpan(row.title, language)}</span>
          <span class="s-library-content-row__progress"><span class="o-progress"><span style="width:${row.pct}%"></span></span><span class="s-library-content-row__pct">${row.pct}%</span></span>
        </span>
        <span class="s-library-content-row__chevron">${raw(icon('chevron-right', { size: 20 }))}</span>
      </button>
      ${moreButton({ label: t('more'), open, dataset: row.importId })}
    </div>
    ${open ? moreMenu({ items: [{ key: 'delete', label: t('deleteFromOrena') }], closeLabel: sc('close'), scope: row.importId }) : ''}
  </div>`;
}

function contentPanel(rows, language, menuFor) {
  if (!rows.length) return html``;
  return html`<div class="s-library-content-grid">${rows.map((row) => (row.importId ? ownContentRow(row, language, menuFor) : contentRow(row, language)))}</div>`;
}

function languageRow(row, language) {
  return html`<div class="s-library-lang-row">
    <span class="s-library-chip">${row.kind === 'phrase' ? t('typePhrase') : sc('word')}</span>
    <button type="button" class="s-library-lang-row__text" data-word-open="${row.word}"><span class="s-library-lang-row__word" lang="${langAttr(language)}">${row.word}${row.reading ? html` <span class="s-library-lang-row__reading">${row.reading}</span>` : ''}</span>${row.sub ? html`<span class="s-library-lang-row__sub">${row.sub}${meaningTag(row.subLanguage)}</span>` : ''}</button>
    ${row.isNew ? html`<span class="${cls('s-library-chip', 's-library-chip--new')}">${t('newBadge')}</span>` : html`${masteryBars({ filled: row.filled })}`}
    <button type="button" class="s-library-lang-row__play" data-play="${row.word}" aria-label="${sc('pronunciation')}">${raw(icon('volume-2', { size: 18 }))}</button>
  </div>`;
}

function languagePanel(rows, language) {
  if (!rows.length) {
    return html`<div class="s-library-lang-empty">${emptyMarkup({ text: t('emptyLanguage'), iconName: 'inbox' })}</div>`;
  }
  return html`<div class="s-library-lang-list">${rows.map((row) => languageRow(row, language))}</div>`;
}

function itemCountLabel(n) {
  return t.plural('collectionItems', n);
}

function collectionsPanel(rows) {
  if (!rows.length) return html`<div class="s-library-lang-empty">${emptyMarkup({ text: t('emptyCollections'), iconName: 'inbox' })}</div>`;
  return html`<div class="s-library-collections-grid">${rows.map((row) => mediaCard({
    title: row.title,
    cover: COVER_VISUALS.collection,
    meta: itemCountLabel(row.size),
    dataset: { collection: row.collectionId },
  }))}</div>`;
}

function kindFallbackLabel(key) {
  const map = {
    kindWord: sc('word'), kindReading: sc('content'), kindMedia: sc('listening'),
    kindWriting: sc('writing'), kindSpeaking: t('kindSpeaking'), kindGrammar: sc('grammar'),
  };
  return map[key] || sc('word');
}

/* The four Active-use shortcuts (design: `activeUse[]`, `orena-script.js` line ~550) - a fixed
   menu into Vocabulary's own Recall/Use/Transfer flows, not a backend-fetched row set: every
   route it opens (`review`, `transfer`, `situation`, `timed`) is a real focus route already in
   `shell/routes.js`; none has a screen registered yet, so today each lands on the router's own
   Coming-soon fallback (`shell/screens.js`'s own contract - "a route whose screen is not listed
   here renders the design's Coming soon screen"), exactly like the Due tab's own "Start review"
   button already does. Titles reuse `shellCopy` where the design's card title is the same string
   as a place this shell already names (`review`, `contextTransfer`, `timedRecall`); the two design
   card titles with no shell equivalent ("Due review", "Situation Reaction · context variant") are
   this screen's own copy. The due count feeding two of the four descriptions is real
   (`dueStats`); `dur` is not carried - see copy.js. */
function activeCards(stats) {
  return activeCardList(stats).filter((card) => !isDeferred(card.route)); // D-101 H9
}

function activeCardList(stats) {
  return [
    { key: 'due', stage: t('stageRecall'), title: t('activeDueTitle'), desc: t.plural('activeDueDesc', stats.dueCount), route: 'review' },
    { key: 'transfer', stage: t('stageUse'), title: sc('contextTransfer'), desc: t('activeTransferDesc'), route: 'transfer' },
    { key: 'situation', stage: t('stageTransfer'), title: t('activeSituationTitle'), desc: t('activeSituationDesc'), route: 'situation' },
    { key: 'timed', stage: t('stageFast'), title: sc('timedRecall'), desc: t.plural('activeTimedDesc', stats.dueWords), route: 'timed' },
  ];
}

function activePanel(stats) {
  return html`<div class="s-library-active-grid">${activeCards(stats).map((card) => html`<button type="button" class="s-library-active-card" data-active="${card.route}">
    <span class="s-library-active-card__top"><span class="s-library-active-card__stage">${card.stage}</span></span>
    <span class="s-library-active-card__title">${card.title}</span>
    <span class="s-library-active-card__desc">${card.desc}</span>
  </button>`)}</div>`;
}

function duePanel(stats, list) {
  return html`<div class="s-library-due-grid">
    <div class="s-library-due-hero">
      <div class="s-library-due-hero__eyebrow">${t('dueNow')}</div>
      <div class="s-library-due-hero__count">${stats.dueCount} <span>${t.plural('dueItemsLabel', stats.dueCount)}</span></div>
      <div class="s-library-due-hero__stats">
        <span><b>${stats.dueWords}</b> ${t.plural('statWords', stats.dueWords)}</span>
        <span><b>${stats.duePhrases}</b> ${t.plural('statPhrases', stats.duePhrases)}</span>
        <span><b>${stats.dueSource}</b> ${t('statSource')}</span>
      </div>
      <button type="button" class="o-btn o-btn--primary s-library-due-cta" data-start-review>${t('startReview')}</button>
    </div>
    <div class="s-library-due-list">
      <div class="s-library-due-list__title">${t('inThisSession')}</div>
      ${list.map((row) => html`<div class="s-library-due-row"><span class="s-library-due-row__text">${row.text || kindFallbackLabel(row.kindKey)}</span><span class="s-library-due-row__meta">${row.sourceKey ? t(row.sourceKey) : row.text && row.kindKey ? kindFallbackLabel(row.kindKey) : ''}</span></div>`)}
    </div>
  </div>`;
}

async function safe(promise, fallback) {
  try {
    return await promise;
  } catch {
    return fallback;
  }
}

export default async function library(element, ctx) {
  await useStyles('screens/library/library.css');
  await useStyles('kit/overflow.css');
  const support = languages().support;
  const language = ctx.context.language;
  const requestedTab = ctx.query?.get('tab');
  let active = TABS.includes(requestedTab) ? requestedTab : 'content';
  let menuFor = '';
  // The account's view of the imports first, so a deletion made on another device is not shown here.
  await syncImports(ctx.context.memory, language).catch(() => false);

  const [collection, vocabulary, collections, decks, queue, dueItems, curated] = await Promise.all([
    api.collection({ domains: ['reading', 'media'], limit: 24 }),
    api.libraryVocabulary({ limit: 24 }),
    safe(api.libraryCollections(), { collections: [] }),
    safe(api.vocabularyDecks(), { items: [] }),
    safe(api.libraryReviewQueue(), { pinned: [], pinned_count: 0, due_count: 0, total: 0 }),
    safe(api.libraryVocabulary({ status: 'due', order: 'due', limit: 50 }), null),
    safe(api.vocabularyLibraryCollections(language), { items: [] }),
  ]);

  const ownRows = () => {
    const memory = ctx.context.memory?.value;
    return [
      ...(memory?.imports || []).map((item) => ({ importId: item.id, contentId: item.id, domain: 'reading', title: item.title || '', source: '', pct: placeFor(memory?.continuation, item.id).percent })),
      ...(memory?.mediaImports || []).map((item) => ({ importId: item.id, contentId: `upload:${item.id}`, domain: 'media', title: item.title || '', source: '', pct: placeFor(memory?.continuation, `upload:${item.id}`).percent })),
    ];
  };
  const rows = {
    content: contentRows(collection.entries || [], ctx.context.memory?.value?.continuation || []),
    language: languageRows(vocabulary.items || [], support),
    collections: collectionsAndDecks(collections.collections || [], decks.items || [], curated.items || []),
  };
  const stats = dueStats(queue);
  /* "In this session" lists the due words Review will ask (V-12, HV-4 A), and the source-aware count is that
     session's. When that list cannot be read, the pinned items stand in as before. */
  const dueRows = dueItems ? sessionRows(dueItems.items) : dueListRows(queue);
  if (dueItems) stats.dueSource = sessionSourceCount(dueRows);

  function panelFor(id) {
    if (id === 'content') return contentPanel([...ownRows(), ...rows.content], language, menuFor);
    if (id === 'language') return languagePanel(rows.language, language);
    if (id === 'collections') return collectionsPanel(rows.collections);
    if (id === 'active') return activePanel(stats);
    return duePanel(stats, dueRows);
  }

  function paint() {
    mount(
      element,
      html`<div class="s-library">
        <h1 class="o-h1">${sc('myLibrary')}</h1>
        ${tabsMarkup(active, stats.dueCount)}
        <div data-panel>${panelFor(active)}</div>
      </div>`,
    );
    bind();
    cueTabs();
  }

  /* The strip scrolls on a phone (LEX-068): the chosen tab is brought into view, and an edge fade shows that
     more tabs wait on that side. */
  function cueTabs() {
    const strip = element.querySelector('.o-tabs');
    if (!strip) return;
    const chosen = strip.querySelector('[aria-selected="true"]');
    if (chosen && strip.scrollWidth > strip.clientWidth) {
      strip.scrollLeft = Math.max(0, chosen.offsetLeft - (strip.clientWidth - chosen.offsetWidth) / 2);
    }
    const mark = () => {
      const more = strip.scrollWidth - strip.clientWidth > 2;
      strip.toggleAttribute('data-more-right', more && strip.scrollLeft + strip.clientWidth < strip.scrollWidth - 2);
      strip.toggleAttribute('data-more-left', more && strip.scrollLeft > 2);
    };
    strip.addEventListener('scroll', mark, { passive: true });
    mark();
  }

  function bind() {
    for (const button of element.querySelectorAll('[data-tab]')) {
      button.addEventListener('click', () => {
        active = button.dataset.tab;
        menuFor = '';
        history.replaceState(history.state, '', ctx.href('library', {}, { tab: active }));
        paint();
      });
    }
    for (const button of element.querySelectorAll('[data-content]')) {
      button.addEventListener('click', () => ctx.go(ctx.href('content', { id: button.dataset.content })));
    }
    for (const button of element.querySelectorAll('[data-word-open]')) {
      button.addEventListener('click', () => ctx.go(ctx.href('word', { id: button.dataset.wordOpen })));
    }
    for (const button of element.querySelectorAll('[data-more]')) {
      button.addEventListener('click', () => {
        menuFor = menuFor === button.dataset.more ? '' : button.dataset.more;
        paint();
      });
    }
    element.querySelector('[data-menu-close]')?.addEventListener('click', () => {
      menuFor = '';
      paint();
    });
    element.querySelector('[data-menu-item="delete"]')?.addEventListener('click', async () => {
      const id = menuFor;
      menuFor = '';
      // Hidden at once with the design's toast and its Undo; the deletion is committed when that window ends.
      deleteWithUndo(ctx.context.memory, id, { toast, text: t('deletedFromOrena'), undoLabel: sc('undo') });
      paint();
    });
    /* `#/collection/:id` (route `collection`) is a different, third backend concept - a curated
       vocabulary pack (concept A, C6 §2.1), fetched via GET /api/vocabulary/library/collections/{id};
       model.js's own comment says as much ("does not belong to a learner's own library"). Neither a
       My Library collection (`library:<id>`) nor a Vocabulary deck (`deck:<id>`) has a detail screen
       built yet - `shell/screens.js` lists no such folder - so both land on the design's own
       Coming-soon (`coming/:key`), honestly, instead of the wrong concept-A screen 404ing on every
       card (UI_BACKEND_GAPS.md N-23). `key: 'collection'` reuses the one existing shellCopy title
       both concepts are a kind of ("Collection"/"Bộ sưu tập"/"合集") rather than inventing new copy
       for either concept (`copy/shell.js` is not this screen's file to add a key to). */
    for (const button of element.querySelectorAll('[data-collection]')) {
      const id = button.dataset.collection;
      // A curated collection has its own screen; a library collection and a deck have none yet (N-23).
      button.addEventListener('click', () => ctx.go(id.startsWith('curated:') ? ctx.href('collection', { id: id.slice('curated:'.length) }) : ctx.href('coming', { key: 'collection' })));
    }
    element.querySelector('[data-start-review]')?.addEventListener('click', () => ctx.go(ctx.href('review')));
    for (const button of element.querySelectorAll('[data-active]')) {
      button.addEventListener('click', () => ctx.go(ctx.href(button.dataset.active)));
    }
    for (const button of element.querySelectorAll('[data-play]')) {
      button.addEventListener('click', async () => {
        if (button.disabled) return;
        button.disabled = true;
        try {
          const found = await api.wordAudio(button.dataset.play);
          if (!found?.available) return;
          await new Audio(found.url).play().catch(() => {});
        } catch {
          /* Nothing to play; the frame draws no error state for this control. */
        } finally {
          button.disabled = false;
        }
      });
    }
  }

  paint();
  // An Undo (or the end of a window) elsewhere repaints the list while this room is the current one.
  const stopListening = onImportsChanged(() => {
    if (ctx.isCurrent && !ctx.isCurrent()) stopListening();
    else paint();
  });
  return stopListening;
}
