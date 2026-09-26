import { bindTodayWords } from './discovery.js';
import { homeHtml, bindHome } from './home.js';
import { origin, art, bindImages } from './content.js';
import { companionArt } from './brand.js';
import { esc, dialog } from './html.js';
import {
  link,
  continuationLink,
  practiceIntentions,
} from '../product/intent.js';
import { contentFor } from '../content/texts.js';
import { voiceInvitations } from '../content/voice-invitations.js';
import { publishedReadings } from '../content/reading-library.js';
import { vocabularyKeepPayload as sharedVocabularyKeepPayload } from './vocabulary-experience.js';
import { renderLibraryBrowse } from './library-browse.js';
import { renderSearch } from './search.js';
import { listeningItem } from './media-library.js';

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
  let unbindHome = () => {};
  const text = contentFor(language).map((x) => ({
    ...x,
    id: `story:${x.id}`,
    language,
  }));
  const result = await Promise.allSettled([
    api.listeningLibrary(language),
    location.page === 'discover'
      ? api.dailyVocabularyFeed(language)
      : Promise.resolve({ items: [] }),
    // The vocabulary collections the Home rail shows.
    location.page === 'discover'
      ? api.vocabularyLibraryCollections(language)
      : Promise.resolve({ items: [] }),
    // Published Reading articles. A runtime without the Reading engine answers
    // 503 and the shelf is simply shorter - a room is not a place to explain a
    // migration, and `allSettled` already treats that as "nothing to add".
    api.readingArticles(language),
    /* The article the Reading selection policy chooses next for this learner
       (D-082): by measured ability, recent results and weak question types.
       Home's "for you" rail is where the design puts what fits the learner. */
    location.page === 'discover' ? api.readingPracticeNext() : Promise.resolve(null),
  ]);
  if (!alive()) return;
  const listeningPayload = result[0].status === 'fulfilled' ? result[0].value : {};
  // The same identity boundary the Listening library reads through, so Discover
  // and the library cannot disagree about what an item is called.
  const media = (listeningPayload.items || [])
    .filter((x) => x.language === language)
    .map(listeningItem);
  const vocabulary = result[1].status === 'fulfilled'
    ? result[1].value.items || []
    : [];
  const failed = result[0].status === 'rejected';
  /* Articles an administrator admitted through the Reading content engine.
     They are read exactly like everything else here, so they join the same
     list rather than getting a shelf of their own: what the learner gains is
     more to read, not a new place to look. */
  const articles = (result[3]?.status === 'fulfilled' ? result[3].value.items || [] : []).map(
    (article) => ({
      id: `article:${article.id}`,
      kind: 'article',
      material: 'article',
      title: article.title,
      subtitle: article.excerpt || '',
      topic: article.topic || '',
      level: article.level || '',
      time: article.reading_time_seconds
        ? `${Math.max(1, Math.round(article.reading_time_seconds / 60))} min`
        : '',
      language: article.language || language,
    }),
  );
  /* The policy's choice, as the card the catalogue already has for it; an
     article outside this page of the catalogue is drawn from what the choice
     itself carries. Nothing is chosen, nothing is drawn. */
  const choice = result[4]?.status === 'fulfilled' && result[4].value?.available ? result[4].value.next : null;
  const recommended = choice?.article_id
    ? articles.find((item) => item.id === `article:${choice.article_id}`) ||
      (choice.set?.article?.title
        ? {
            id: `article:${choice.article_id}`,
            kind: 'article',
            material: 'article',
            title: choice.set.article.title,
            level: choice.set.article.level || '',
            language,
          }
        : null)
    : null;
  /* A copy that carries the signed recommendation: only this card leads to a
     submit recorded as the policy's; the catalogue's own card does not. */
  const nextReading = recommended ? { ...recommended, recommendation: choice.recommendation || '' } : null;
  // Everything that is read rather than listened to, in one list.
  const published = publishedReadings(language);
  const readable = [...articles, ...published, ...text, ...memory.value.imports];
  const all = [
    ...articles,
    ...published,
    ...media,
    ...text,
    ...memory.value.imports,
    ...memory.value.mediaImports,
  ];
  // Curated and imported media are one library: whatever a learner brought in
  // is practisable everywhere the catalog is.
  const practiceMedia = [...media, ...memory.value.mediaImports];
  const intent = location.intent;
  const catalogError = failed
    ? `<p class="notice" role="alert">${c.unavailable} <button data-retry>${c.retry}</button></p>`
    : '';
  const readingError = result[3].status === 'rejected'
    ? `<p class="notice" role="alert">${c.unavailable} <button data-retry>${c.retry}</button></p>`
    : '';
  if (location.page === 'practice') {
    /* Reading and Listening open on their libraries (D-059 Phases 5 and 7): the same search,
       facets, sections and cards as #/content, scoped to what can be read or listened to. Every
       other practice address is sent to its own flow before it gets here (D-078,
       product/legacy-routes.js): the Practice hub and its list of moments are retired. */
    root.innerHTML =
      intent === 'reading'
        ? `${readingError}<div class="reading-library" data-library-browse></div>`
        : `${catalogError}<div class="listening-library" data-library-browse></div>`;
    releaseLibrary = renderLibraryBrowse(
      root.querySelector('[data-library-browse]'),
      ctx,
      intent === 'reading' ? { readable, media: [] } : { readable: [], media: practiceMedia },
      {
        only: intent === 'reading' ? ['books'] : ['audio', 'video'],
        onImport: ctx.import,
        titleTag: 'h1',
      },
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
    /* The card offers a review, so it asks how much is due - one counted
       number, not the learner's whole vocabulary (D-065). A failed read leaves
       the card saying nothing is due rather than inventing a number. */
    let due = 0;
    try {
      const counts = await api.libraryVocabularySummary();
      due = Number(counts?.summary?.due || 0);
    } catch {
      due = 0;
    }
    if (!alive()) return;
    root.innerHTML = homeHtml(ctx, {
      media,
      reading: readable,
      nextReading,
      vocabulary,
      saved: [...(memory.value.imports || []), ...(memory.value.mediaImports || [])],
      due,
      collections: result[2].status === 'fulfilled' ? result[2].value.items || result[2].value.collections || [] : [],
      catalogError,
    });
    unbindHome = bindHome(root, ctx);
  }
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
    unbindHome();
    releaseLibrary();
  };
}
