import {
  bindContentRails,
  discoverySpread,
  bindTodayWords,
  practiceOverview,
} from './discovery.js';
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
import { voiceInvitations } from '../content/voice-invitations.js';
import { readingEntry, readingSessionId } from '../content/reading.js';
import { openReadingRequest } from './reading.js';
import { publishedReadings } from '../content/reading-library.js';
import { vocabularyKeepPayload as sharedVocabularyKeepPayload } from './vocabulary-experience.js';
import { renderLibraryBrowse } from './library-browse.js';
import { renderSearch } from './search.js';
import { listeningItem } from './media-library.js';

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

/* Vocabulary helpers share the curated catalog (writing_coach/vocabulary_library.py)
   with My Language's saved/review state. Discovery mounts only the Feed; the
   complete Library is rendered by the dedicated Vocabulary route. Both use the
   shared Vocabulary Card renderer and save path
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

/* The one payload shape both "keep" actions send to the existing
   POST /api/library/vocabulary - only `source_kind` tells them apart. No new
   save endpoint, no second card shape. */
export function vocabularyKeepPayload(card, sourceKind, supportLanguage) {
  return sharedVocabularyKeepPayload(card, sourceKind, supportLanguage);
}

export async function renderWorld(root, ctx) {
  const { api, c, language, memory, location, alive } = ctx;
  // The library paints itself asynchronously into its own container and binds
  // its own shelves there; this is how that binding is released with the room.
  let releaseLibrary = () => {};
  const text = contentFor(language).map((x) => ({
    ...x,
    id: `story:${x.id}`,
    language,
  }));
  const result = await Promise.allSettled([
    api.listeningLibrary(language),
    api.readingSessions(12),
    location.page === 'discover'
      ? api.dailyVocabularyFeed(language)
      : Promise.resolve({ items: [] }),
  ]);
  if (!alive()) return;
  const listeningPayload = result[0].status === 'fulfilled' ? result[0].value : {};
  // The same identity boundary the Listening library reads through, so Discover
  // and the library cannot disagree about what an item is called.
  const media = (listeningPayload.items || [])
    .filter((x) => x.language === language)
    .map(listeningItem);
  const vocabulary = result[2].status === 'fulfilled'
    ? result[2].value.items || []
    : [];
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
    /* Reading opens on the books, not on a headline about reading. The room is
       named, once and quietly, and the covers take the first viewport
       (D-057 rule 13 and 15). */
    /* Listening opens on the voices, for the same reason Reading opens on the
       books: the headline and its paragraph told a learner nothing and cost
       the first viewport (D-057 rule 13). */
    const intro = intent === 'reading'
      ? pageIntro({ title: r.reading, compact: true })
      : intent === 'follow'
      ? pageIntro({ title: r.listening, compact: true })
      : !intent
      ? editorialIntro(ctx,{title:intent ? r.listenTitle : r.practiceTitle,note:intent ? r.listenNote : r.practiceNote,state:intent ? 'listening' : 'exploring',eyebrow:intent ? r.listening : r.practice})
      : headline(c[`${intent}Intent`] || c[intent], c[`${intent}IntentNote`] || c[`${intent}Note`], c[`${intent}Name`] || c.practice, INTENT_SCENE[intent] || '');
    /* The way back sits above the heading, and the heading's eyebrow names
       the room - the way back already says "Practice". */
    const practiceContinuation = intent === 'follow'
      ? ''
      : intent === 'reading'
        ? continuationShelf(ctx, 12, {
            title: r.continueLearning,
            compact: true,
            experience: 'reading',
            rail: true,
          })
        : continuation;
    root.innerHTML = `${intent ? practiceReturn(c, intent) : ''}${intro}${intent ? '' : practiceOverview(ctx)}${
      intent === 'reading'
        /* Reading opens on the library the design draws (D-059 Phase 5), with
           books and the learner's own texts in it: the same search, facets,
           sections and cards as #/content, scoped to what can be read. It is
           one library, not a second one - a book card leads to the book page
           (#/book), which is where a chapter is chosen. Bringing a passage in
           stays the room's own action. */
        ? `${readingError}<div class="reading-library" data-library-browse></div><div class="button-row reading-bring"><button class="quiet" type="button" data-read>＋ ${esc(c.readingBring)}</button></div>`
        : (() => {
            /* Listening opens on the same approved library as Reading, scoped
               to what can be listened to (D-059 Phase 7): one library, one set
               of cards, one search. Dictation, shadowing and speaking keep the
               filtered list: those are practice modes over a source, not
               browsing. */
            if (!intent || intent === 'follow')
              return `${catalogError}<div class="listening-library" data-library-browse></div><div class="button-row reading-bring"><button class="quiet" type="button" data-bring>＋ ${esc(c.bring)}</button></div>`;
            return `<section class="voices"><div class="section-head"><h2>${c.chooseMoment}</h2><button class="quiet" data-bring>＋ ${c.bring}</button></div>${catalogError}${
              practiceMedia
                .filter((x) => supports(x, intent))
                .map((x) => mediaItem(x, intent, c))
                .join('') || `<p>${c.noCatalog}</p>`
            }</section>`;
          })()
    }${practiceContinuation}`;
    if (intent === 'reading' || !intent || intent === 'follow')
      releaseLibrary = renderLibraryBrowse(
        root.querySelector('[data-library-browse]'),
        ctx,
        intent === 'reading' ? { readable, media: [] } : { readable: [], media: practiceMedia },
        { only: intent === 'reading' ? ['books'] : ['audio', 'video'] },
      ) || (() => {});
  } else if (location.page === 'search') {
    releaseLibrary = renderSearch(root, ctx, { readable, media: practiceMedia }) || (() => {});
  } else if (location.page === 'content') {
    /* Library (D-059 Phase 4): everything browsable, with facets. What the
       learner kept lives in Saved (#/collection); bringing something in is a
       Library action. */
    releaseLibrary = renderLibraryBrowse(root, ctx, {
      readable,
      media: practiceMedia,
    }) || (() => {});
  } else {
    root.innerHTML = discoverySpread(ctx, {
      media,
      reading: readable,
      speaking: voiceInvitations(language),
      writing: text.filter((item) => item.prompt),
      vocabulary,
      catalogError,
    });
  }
  const unbindContentRails = bindContentRails(root);
  bindTodayWords(root);
  root.querySelectorAll('[data-discover-vocabulary-save]').forEach((button) => {
    button.addEventListener('click', async () => {
      const index = Number(button.dataset.discoverVocabularySave);
      const card = vocabulary[index];
      if (!card || card.saved || button.disabled) return;
      button.disabled = true;
      try {
        await api.saveLibraryVocabulary(vocabularyKeepPayload(card, 'feed', ctx.support));
        if (!alive()) return;
        card.saved = true;
        const surface = button.closest('[data-vocabulary-card]');
        surface?.setAttribute('data-vocabulary-state', card.due ? 'due' : 'learning');
        const state = surface?.querySelector('.vocabulary-state');
        if (state && !card.due) {
          state.className = 'vocabulary-state vocabulary-state--learning';
          state.textContent = c.vocabularyLearningState;
        }
        const saved = document.createElement('span');
        saved.className = 'quiet';
        saved.dataset.vocabularySaved = '';
        saved.textContent = `${c.vocabularySaved || c.saved} ✓`;
        button.replaceWith(saved);
      } catch {
        if (alive()) button.disabled = false;
      }
    });
  });
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
  bindImages(root, c);
  return () => {
    unbindContentRails();
    releaseLibrary();
  };
}
