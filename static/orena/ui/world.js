import { discoverySpread, practiceOverview } from './discovery.js';
import { referenceCopy, editorialIntro } from './reference.js';
import { duration, origin, art, bindImages } from './content.js';
import { companionArt, scene } from './brand.js';
import { pageIntro, intentNavigation, continuationShelf } from './patterns.js';
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
      : headline(c[`${intent}Intent`] || c[intent], c[`${intent}IntentNote`] || c[`${intent}Note`], c.practice, INTENT_SCENE[intent] || '');
    root.innerHTML = `${intro}${intent ? intentNavigation(c, intent) : practiceOverview(ctx)}${
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
    root.innerHTML = discoverySpread(ctx, {media, text, catalogError});
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
