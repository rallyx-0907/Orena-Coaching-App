import { discoverySpread, practiceOverview } from './discovery.js';
import { referenceCopy, editorialIntro } from './reference.js';
import { duration, origin, art, bindImages } from './content.js';
import { companionArt, scene } from './brand.js';
import { pageIntro, practiceReturn, continuationShelf } from './patterns.js';
import { esc, dialog } from './html.js';
import {
  link,
  continuationLink,
  practiceIntentions,
  supports,
} from '../product/intent.js';
import { contentFor } from '../content/texts.js';
import { readingEntry, readingSessionId } from '../content/reading.js';
import { openReadingRequest, readingRow } from './reading.js';
import {
  publishedReadings,
  filterReadings,
} from '../content/reading-library.js';
import { collectionSearch, bindCollectionSearch } from './collection-search.js';
import {
  renderVocabularyCollectionCard,
  renderVocabularyFeedPreview,
  renderVocabularyRow,
  vocabularyKeepPayload as sharedVocabularyKeepPayload,
} from './vocabulary-experience.js';

// Imported media carries no catalog level, and its length is unknown until the
// asset reports one. Join only what is actually true of this item, so an import
// never shows a stray separator or a fabricated 0:00.
function mediaLine(item) {
  return [
    item.level,
    Number(item.duration_ms) > 0 ? duration(item.duration_ms) : '',
  ]
    .filter(Boolean)
    .map((part) => esc(part))
    .join(' · ');
}
function mediaItem(item, intent, c) {
  return `<a class="voice-row" href="${link('encounter', { id: item.id, intent })}"><span class="voice-cover">${art(item)}<span class="voice-play" aria-hidden="true">▶</span></span><span><small>${mediaLine(item)}${mediaLine(item) ? ' · ' : ''}${item.kind === 'video' || item.kind === 'embed' ? c.video : c.audio}</small><strong lang="${item.language}">${esc(item.title)}</strong>${item.description ? `<span class="voice-description">${esc(item.description)}</span>` : ''}<span class="byline">${esc(item.source?.creator || origin(item, c))}</span></span><span aria-hidden="true">↗</span></a>`;
}
function contentRow(item, intent, c) {
  return `<article class="collection-row"><a class="collection-art" aria-label="${esc(item.title)}" href="${link('encounter', { id: item.id, intent })}">${art(item)}</a><div><small>${esc(origin(item, c))}</small><h2><a lang="${item.language || ''}" href="${link('encounter', { id: item.id, intent })}">${esc(item.title)} ↗</a></h2></div><button class="quiet" data-remove="${esc(item.id)}" aria-label="${esc(c.remove + ': ' + item.title)}">×</button></article>`;
}

/* Vocabulary Library and Daily Feed - two Discover sections over the curated
   catalog (writing_coach/vocabulary_library.py), distinct from My Language's
   own saved/review state. Both render through the one shared Vocabulary Card
   renderer and the one shared save path
   (docs/superpowers/plans/2026-09-14-vocabulary-experience.md Task E). */

/* A projected Vocabulary Card folds every authored support translation into
   `meanings` alongside the target-language definition
   (writing_coach/vocabulary_cards.py's `_meanings_from`) rather than carrying
   a separate `support_translations` field on the wire. This reconstructs that
   mapping from `meanings` for the learner's chosen support language, falling
   back to Vietnamese - the same compatibility boundary the plan documents for
   the existing `translation_vi` field - and finally to no translation at all,
   rather than inventing one. */
export function mapVocabularySupportTranslation(card, supportLanguage) {
  const meanings = Array.isArray(card?.meanings) ? card.meanings : [];
  const targetLanguage = String(card?.identity?.language || '');
  const bySupport = {};
  for (const meaning of meanings) {
    const lang = String(meaning?.language || '');
    if (lang && lang !== targetLanguage && !(lang in bySupport)) {
      bySupport[lang] = String(meaning?.text || '');
    }
  }
  return bySupport[supportLanguage] || bySupport.vi || '';
}

function vocabularyCardDefinition(card) {
  const meanings = Array.isArray(card?.meanings) ? card.meanings : [];
  const targetLanguage = String(card?.identity?.language || '');
  const own = meanings.find((m) => String(m?.language || '') === targetLanguage);
  return String((own || meanings[0])?.text || '');
}

/* The one payload shape both "keep" actions send to the existing
   POST /api/library/vocabulary - only `source_kind` tells them apart. No new
   save endpoint, no second card shape. */
export function vocabularyKeepPayload(card, sourceKind, supportLanguage) {
  return sharedVocabularyKeepPayload(card, sourceKind, supportLanguage);
}

function vocabularyDiscoverCopy(c, supportLanguage) {
  return {
    ...c,
    supportLanguage,
    save: c.vocabularySave || c.keep,
    saved: c.vocabularySaved || c.saved,
    study: c.vocabularyStudy || c.lookCloser,
    open: c.vocabularyOpen || c.lookCloser,
    words: c.vocabularyWordCount,
    learning: c.vocabularyLearningState,
    due: c.vocabularyDueState,
    mastered: c.vocabularyMasteredState,
    newWord: c.vocabularyNew,
  };
}

// Grouped in the order frameworks first appear, preserving the API's
// framework/level/title sort within each group.
export function groupVocabularyCollectionsByFramework(collections) {
  const order = [];
  const groups = new Map();
  for (const collection of Array.isArray(collections) ? collections : []) {
    const framework = String(collection?.framework || '');
    if (!groups.has(framework)) {
      groups.set(framework, []);
      order.push(framework);
    }
    groups.get(framework).push(collection);
  }
  return order.map((framework) => ({ framework, collections: groups.get(framework) }));
}

// `framework` is open-ended content, not a fixed UI enum (see the plan's
// Level/framework/topic metadata section) - a framework with no authored
// label still shows its own name, truthfully, rather than disappearing.
function vocabularyFrameworkLabel(c, framework) {
  const key = `vocabularyFramework_${String(framework || '').replace(/[^a-z0-9]/gi, '').toLowerCase()}`;
  return c[key] || framework;
}

function vocabularyLibraryCollectionRow(c, collection, index, supportLanguage = 'en') {
  return renderVocabularyCollectionCard(vocabularyDiscoverCopy(c, supportLanguage), collection, { index });
}

// A saved catalog card never offers a second save affordance - it says,
// plainly, that it is already in My Language.
export function vocabularyLibraryCardAfterSlot(c, card, index) {
  if (card?.saved) {
    return `<span class="meta" data-vocabulary-kept>${esc(c.vocabularyAlreadyKept)}</span>`;
  }
  return `<button class="quiet" data-library-keep="${index}">${esc(c.keep)} ＋</button>`;
}

export function vocabularyFeedCardAfterSlot(c, index) {
  return `<button class="quiet" data-feed-keep="${index}">${esc(c.keep)} ＋</button>`;
}

/* Inner content only - the caller owns the permanent
   <section data-vocabulary-library> wrapper so a state repaint never
   double-nests it. */
export function vocabularyLibrarySection(c, state = {}) {
  const { collections, error, open, supportLanguage = 'en' } = state;
  const heading = `<div class="section-head"><h2>${esc(c.vocabularyLibraryTitle)}</h2></div><p class="meta">${esc(c.vocabularyLibraryNote)}</p>`;
  let body;
  if (open) {
    if (open.error) {
      body = `<p class="notice" role="alert">${esc(c.unavailable)} <button data-library-retry>${esc(c.retry)}</button></p>`;
    } else if (!open.items) {
      body = `<p class="loading" role="status">${esc(c.vocabularyLibraryLoading)}</p>`;
    } else {
      body = `<button class="quiet" data-close-collection>${esc(c.vocabularyLibraryBack)}</button><h3>${esc(open.title || '')}</h3><section class="vocabulary-row-list vocabulary-card">${open.items
        .map((card, index) => renderVocabularyRow(vocabularyDiscoverCopy(c, supportLanguage), card, { index, saveAttribute: 'data-library-keep' }))
        .join('')}</section>`;
    }
  } else if (error) {
    body = `<p class="notice" role="alert">${esc(c.unavailable)} <button data-library-retry>${esc(c.retry)}</button></p>`;
  } else if (!collections) {
    body = `<p class="loading" role="status">${esc(c.vocabularyLibraryLoading)}</p>`;
  } else if (!collections.length) {
    body = `<div class="empty">${scene('empty', { size: 'medium' })}<p>${esc(c.vocabularyLibraryEmpty)}</p></div>`;
  } else {
    body = groupVocabularyCollectionsByFramework(collections)
      .map(
        (group) =>
          `<h3>${esc(vocabularyFrameworkLabel(c, group.framework))}</h3>${group.collections
            .map((collection, index) => vocabularyLibraryCollectionRow(c, collection, index, supportLanguage))
            .join('')}`,
      )
      .join('');
  }
  return `${heading}${body}`;
}

export function vocabularyFeedSection(c, state = {}) {
  const { items, error, supportLanguage = 'en' } = state;
  const heading = `<div class="section-head"><h2>${esc(c.vocabularyFeedTitle)}</h2></div><p class="meta">${esc(c.vocabularyFeedNote)}</p>`;
  let body;
  if (error) {
    body = `<p class="notice" role="alert">${esc(c.unavailable)} <button data-feed-retry>${esc(c.retry)}</button></p>`;
  } else if (!items) {
    body = `<p class="loading" role="status">${esc(c.vocabularyFeedLoading)}</p>`;
  } else if (!items.length) {
    body = `<div class="empty">${scene('empty', { size: 'medium' })}<p>${esc(c.vocabularyFeedEmpty)}</p></div>`;
  } else {
    body = `<section class="vocabulary-feed-preview">${items
      .map((card, index) => renderVocabularyFeedPreview(vocabularyDiscoverCopy(c, supportLanguage), card, { index, saveAttribute: 'data-feed-keep' }))
      .join('')}</section>`;
  }
  return `${heading}${body}`;
}

/* Both controllers repaint only their own container - opening a collection or
   keeping a Feed word never reloads the rest of Discover. */
async function paintVocabularyLibrary(container, ctx) {
  if (!container) return;
  const { api, c, language, alive, support } = ctx;
  let collections = null;
  let error = false;
  let open = null;
  function paint() {
    if (!alive()) return;
    container.innerHTML = vocabularyLibrarySection(c, { collections, error, open, supportLanguage: support });
    container.querySelectorAll('[data-open-collection]').forEach((button) => {
      button.onclick = () => loadCollection(button.dataset.openCollection);
    });
    container.querySelector('[data-close-collection]')?.addEventListener('click', () => {
      open = null;
      paint();
    });
    container.querySelector('[data-library-retry]')?.addEventListener('click', () => {
      if (open) loadCollection(open.id);
      else loadList();
    });
    container.querySelectorAll('[data-library-keep]').forEach((button) => {
      button.onclick = () => keep(button, Number(button.dataset.libraryKeep));
    });
    container.querySelectorAll('[data-vocabulary-study]').forEach((button) => {
      button.onclick = () => { location.hash = '#/language'; };
    });
  }
  async function loadList() {
    collections = null;
    error = false;
    open = null;
    paint();
    try {
      const data = await api.vocabularyLibraryCollections(language);
      if (!alive()) return;
      collections = data.items || [];
    } catch {
      if (!alive()) return;
      error = true;
    }
    paint();
  }
  async function loadCollection(id) {
    open = { id, items: null, error: false };
    paint();
    try {
      const detail = await api.vocabularyLibraryCollection(id);
      if (!alive()) return;
      open = { id, title: detail.title, items: detail.items || [], error: false };
    } catch {
      if (!alive()) return;
      open = { id, items: null, error: true };
    }
    paint();
  }
  async function keep(button, index) {
    const card = open?.items?.[index];
    if (!card) return;
    button.disabled = true;
    try {
      await api.saveLibraryVocabulary(vocabularyKeepPayload(card, 'collection', support));
      if (!alive()) return;
      open.items[index] = { ...card, saved: true };
      paint();
    } catch {
      if (!alive()) return;
      button.disabled = false;
    }
  }
  await loadList();
}

async function paintVocabularyFeed(container, ctx) {
  if (!container) return;
  const { api, c, language, alive, support } = ctx;
  let items = null;
  let error = false;
  function paint() {
    if (!alive()) return;
    container.innerHTML = vocabularyFeedSection(c, { items, error, supportLanguage: support });
    container.querySelector('[data-feed-retry]')?.addEventListener('click', load);
    container.querySelectorAll('[data-feed-keep]').forEach((button) => {
      button.onclick = () => keep(button, Number(button.dataset.feedKeep));
    });
    container.querySelectorAll('[data-vocabulary-study]').forEach((button) => {
      button.onclick = () => { location.hash = '#/language'; };
    });
  }
  async function load() {
    items = null;
    error = false;
    paint();
    try {
      const data = await api.dailyVocabularyFeed(language);
      if (!alive()) return;
      items = data.items || [];
    } catch {
      if (!alive()) return;
      error = true;
    }
    paint();
  }
  // Feed Keep removes the kept word from the local list optimistically - no
  // full reload, and no second save endpoint: the same POST
  // /api/library/vocabulary Library browsing uses, tagged source_kind 'feed'.
  async function keep(button, index) {
    const card = items?.[index];
    if (!card) return;
    button.disabled = true;
    try {
      await api.saveLibraryVocabulary(vocabularyKeepPayload(card, 'feed', support));
      if (!alive()) return;
      items = items.filter((_, i) => i !== index);
      paint();
    } catch {
      if (!alive()) return;
      button.disabled = false;
    }
  }
  await load();
}
export async function renderWorld(root, ctx) {
  const { api, c, language, memory, location, alive } = ctx;
  const text = contentFor(language).map((x) => ({
    ...x,
    id: `story:${x.id}`,
    language,
  }));
  const result = await Promise.allSettled([
    api.listeningLibrary(language),
    api.readingSessions(12),
  ]);
  if (!alive()) return;
  const media = (
    result[0].status === 'fulfilled' ? result[0].value.items || [] : []
  )
    .filter((x) => x.language === language)
    .map((x) => ({
      ...x,
      id: `media:${x.lesson_id}`,
      kind: x.playback_kind,
      origin: 'curated',
    }));
  const failed = result[0].status === 'rejected';
  // Passages the learner asked for before. They live with the account rather
  // than on the device, so an empty list here is not the same as none kept.
  const reading = (
    result[1].status === 'fulfilled' ? result[1].value.items || [] : []
  ).map((x) => readingEntry(x, language));
  let readingFailed = result[1].status === 'rejected';
  // The recent list is bounded. Kept passages must not disappear simply
  // because the learner requested twelve newer ones.
  if (location.page === 'content') {
    const missing = memory.value.kept.filter(
      (id) => readingSessionId(id) && !reading.some((x) => x.id === id),
    );
    const restored = await Promise.allSettled(
      missing.map((id) => api.readingSession(readingSessionId(id))),
    );
    if (!alive()) return;
    for (const item of restored) {
      if (item.status === 'rejected') readingFailed = true;
      else if (
        item.value.found &&
        item.value.session?.language_code === language
      )
        reading.push(readingEntry(item.value.session, language));
    }
  }
  // Everything that is read rather than listened to, in one list.
  const published = publishedReadings(language);
  const readable = [...published, ...reading, ...text, ...memory.value.imports];
  const all = [
    ...published,
    ...media,
    ...reading,
    ...text,
    ...memory.value.imports,
    ...memory.value.mediaImports,
  ];
  // Curated and imported media are one library: whatever a learner brought in
  // is practisable everywhere the catalog is.
  const practiceMedia = [...media, ...memory.value.mediaImports];
  const intent = location.intent;
  const destination = (id) => link('encounter', { id, intent });
  const headline = (title, note, eyebrow = '', state = '') =>
    pageIntro({ title, note, eyebrow, scene: state });
  const continuation = continuationShelf(ctx);
  const catalogError = failed
    ? `<p class="notice" role="alert">${c.unavailable} <button data-retry>${c.retry}</button></p>`
    : '';
  const readingError = readingFailed
    ? `<p class="notice" role="alert">${c.unavailable} <button data-retry>${c.retry}</button></p>`
    : '';
  /* An intention arrives somewhere, and each somewhere looks like itself. This
     is the difference between a menu of forms and a set of places - one scene,
     at the head of the page, doing orientation rather than decoration. */
  const INTENT_SCENE = {
    follow: 'listening',
    reading: 'reading',
    dictation: 'focus',
    shadowing: 'speaking',
    speaking: 'conversation',
    grammar: 'thinking',
    recall: 'remembering',
  };
  if (location.page === 'practice') {
    const r = referenceCopy[ctx.ui];
    const intro = !intent || intent === 'follow'
      ? editorialIntro(ctx,{title:intent ? r.listenTitle : r.practiceTitle,note:intent ? r.listenNote : r.practiceNote,state:intent ? 'listening' : 'exploring',eyebrow:intent ? r.listening : r.practice})
      : headline(c[`${intent}Intent`] || c[intent], c[`${intent}IntentNote`] || c[`${intent}Note`], c[`${intent}Name`] || c.practice, INTENT_SCENE[intent] || '');
    /* The way back sits above the heading, and the heading's eyebrow names
       the room - the way back already says "Practice". */
    root.innerHTML = `${intent ? practiceReturn(c, intent) : ''}${intro}${intent ? '' : practiceOverview(ctx)}${
      intent === 'reading'
        ? `<section class="voices"><div class="section-head"><h2>${c.readingCollection}</h2><button class="quiet" data-read>＋ ${c.readingBring}</button></div>${readingError}${collectionSearch(
            c,
            {
              facet: c.collectionOrigin,
              options: [
                { value: 'provided', label: c.provided },
                { value: 'generated', label: c.generated },
                { value: 'imported', label: c.imported },
              ],
            },
          )}<div data-reading-results>${
            readable.map((x) => readingRow(x, c)).join('') ||
            `<p>${c.empty}</p>`
          }</div></section>`
        : `<section class="voices"><div class="section-head"><h2>${c.chooseMoment}</h2><button class="quiet" data-bring>＋ ${c.bring}</button></div>${catalogError}${
            practiceMedia
              .filter((x) => supports(x, intent))
              .map((x) => mediaItem(x, intent, c))
              .join('') || `<p>${c.noCatalog}</p>`
          }</section>`
    }${continuation}`;
  } else if (location.page === 'content') {
    const kept = all.filter(
      (x) => memory.value.kept.includes(x.id) || x.origin === 'imported',
    );
    root.innerHTML = `${editorialIntro(ctx,{title:referenceCopy[ctx.ui].collectionTitle,note:referenceCopy[ctx.ui].collectionNote,state:'together',eyebrow:referenceCopy[ctx.ui].content})}${!memory.available ? `<p class="notice">${c.memoryUnavailable}</p>` : ''}${catalogError}${readingError}<section>${kept.length ? kept.map((x) => contentRow(x, null, c)).join('') : `<div class="empty">${scene('empty', { size: 'medium' })}<h2>${c.empty}</h2><p>${c.emptyNote}</p><button class="primary" data-bring>${c.bring} ↗</button></div>`}</section>${continuation}<button class="outline" data-bring>＋ ${c.bring}</button>`;
  } else {
    // Vocabulary Library and Daily Feed are two sections inside this same
    // Discover destination, not a new destination - each mounts and repaints
    // independently once the rest of Discover is on the page.
    root.innerHTML = `${discoverySpread(ctx, {media, text, catalogError})}<section class="voices" data-vocabulary-library aria-label="${esc(c.vocabularyLibraryTitle)}"></section><section class="voices" data-vocabulary-feed aria-label="${esc(c.vocabularyFeedTitle)}"></section>`;
    paintVocabularyLibrary(root.querySelector('[data-vocabulary-library]'), ctx);
    paintVocabularyFeed(root.querySelector('[data-vocabulary-feed]'), ctx);
  }
  root
    .querySelectorAll('[data-bring]')
    .forEach((x) => (x.onclick = ctx.import));
  root
    .querySelectorAll('[data-read]')
    .forEach((x) => (x.onclick = () => openReadingRequest(ctx)));
  root
    .querySelectorAll('[data-retry]')
    .forEach((button) =>
      button.addEventListener('click', () => renderWorld(root, ctx)),
    );
  root.querySelectorAll('[data-remove]').forEach(
    (button) =>
      (button.onclick = () => {
        const id = button.dataset.remove;
        const sheet = dialog({
          title: c.remove,
          body: `<p>${c.removeNote}</p><button class="primary" data-confirm>${c.remove}</button>`,
        });
        sheet.querySelector('[data-confirm]').onclick = () => {
          memory.remove(id);
          sheet.close();
          renderWorld(root, ctx);
        };
      }),
  );
  bindCollectionSearch(root, c, ({ query, facet }) => {
    const found = filterReadings(readable, { query, origin: facet });
    root.querySelector('[data-reading-results]').innerHTML =
      found.map((x) => readingRow(x, c)).join('') || `<p>${c.empty}</p>`;
    return found.length;
  });
  bindImages(root, c);
}
