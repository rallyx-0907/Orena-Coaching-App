/* My Library (frame 12, D-088/D-091): everything a learner saved, met, or needs to come back to.
   Five tabs, the live design script's own order: Saved content, Saved language, Collections,
   Active use, Due Review. */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { mediaCard, masteryBars } from '../../kit/components.js';
import { langAttr, langSpan } from '../../kit/lang.js';
import { emptyMarkup } from '../../kit/states.js';
import { api } from '../../infrastructure/api.js';
import { shellCopy as sc } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { t } from './copy.js';
import { isDeferred } from '../../shell/routes.js';
import {
  contentRows, languageRows, collectionsAndDecks, dueStats, dueListRows,
} from './model.js';

/* Five tabs, the live design script's own order (`orena-script.js` LIBT) - not the four the
   pinned copy's compact export hinted (`hint-placeholder-count="4"` on `libTabs`'s `sc-for`, a
   placeholder guess the truncated export makes when it cannot read real sample data, not a real
   count; §1 "read the source, not a copy"). */
const TABS = ['content', 'language', 'collections', 'active', 'due'];

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
function contentPanel(rows, language) {
  if (!rows.length) return html``;
  return html`<div class="s-library-content-grid">${rows.map((row) => html`<button type="button" class="s-library-content-row" data-content="${row.contentId}">
    <span class="s-library-content-row__body">
      <span class="s-library-content-row__type">${row.domain === 'media' ? sc('listening') : sc('content')}</span>
      <span class="s-library-content-row__title">${langSpan(row.title, language)}</span>
      ${row.source ? html`<span class="s-library-content-row__source">${row.source}</span>` : ''}
      <span class="s-library-content-row__progress"><span class="o-progress"><span style="width:${row.pct}%"></span></span><span class="s-library-content-row__pct">${row.pct}%</span></span>
    </span>
    <span class="s-library-content-row__chevron">${raw(icon('chevron-right', { size: 20 }))}</span>
  </button>`)}</div>`;
}

function languageRow(row, language) {
  return html`<div class="s-library-lang-row">
    <span class="s-library-chip">${row.kind === 'phrase' ? t('typePhrase') : sc('word')}</span>
    <span class="s-library-lang-row__text"><span class="s-library-lang-row__word" lang="${langAttr(language)}">${row.word}</span>${row.sub ? html`<span class="s-library-lang-row__sub">${row.sub}</span>` : ''}</span>
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
  if (!rows.length) return html``;
  return html`<div class="s-library-collections-grid">${rows.map((row) => mediaCard({
    title: row.title,
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
      ${list.map((row) => html`<div class="s-library-due-row"><span class="s-library-due-row__text">${row.text || kindFallbackLabel(row.kindKey)}</span><span class="s-library-due-row__meta">${row.text ? kindFallbackLabel(row.kindKey) : ''}</span></div>`)}
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
  const support = languages().support;
  const language = ctx.context.language;
  let active = 'content';

  const [collection, vocabulary, collections, decks, queue] = await Promise.all([
    api.collection({ domains: ['reading', 'media'], limit: 24 }),
    api.libraryVocabulary({ limit: 24 }),
    safe(api.libraryCollections(), { collections: [] }),
    safe(api.vocabularyDecks(), { items: [] }),
    safe(api.libraryReviewQueue(), { pinned: [], pinned_count: 0, due_count: 0, total: 0 }),
  ]);

  const rows = {
    content: contentRows(collection.entries || []),
    language: languageRows(vocabulary.items || [], support),
    collections: collectionsAndDecks(collections.collections || [], decks.items || []),
  };
  const stats = dueStats(queue);
  const dueRows = dueListRows(queue);

  function panelFor(id) {
    if (id === 'content') return contentPanel(rows.content, language);
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
  }

  function bind() {
    for (const button of element.querySelectorAll('[data-tab]')) {
      button.addEventListener('click', () => {
        active = button.dataset.tab;
        paint();
      });
    }
    for (const button of element.querySelectorAll('[data-content]')) {
      button.addEventListener('click', () => ctx.go(ctx.href('content', { id: button.dataset.content })));
    }
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
      button.addEventListener('click', () => ctx.go(ctx.href('coming', { key: 'collection' })));
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
}
