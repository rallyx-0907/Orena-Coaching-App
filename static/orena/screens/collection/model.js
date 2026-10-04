/* Pure data mapping for Collection Detail (frame 21, D2 §6) - no DOM, no fetch, so
   scripts/test_orena_screen_collection.mjs can prove it without a browser.

   Source: GET /api/vocabulary/library/collections/{id} (app.py
   becoming_vocabulary_library_collection_detail) -> {id, language_code, framework, level,
   level_range, topic, title, item_count, levels, provenance, items[], progress}. Each item is a
   vocabulary_card_from_catalog_entry() card cross-referenced with the learner's saved state:
   {identity:{language,normalized}, headword, meanings:[{language,text}], saved, review_stage,
   due, successful_recalls, lapse_count, ...}.

   Two fields the frame draws have no backend source at all (rule 40 - never invented):
   - col.desc (the collection's own curated description): VocabularyCollection carries no
     description column (writing_coach/persistence/models.py) - always ''.
   - colProgress ("{{n}} met in your sources"): no aggregate exists for how many of a
     collection's words the learner has met in their own reading/listening content - always 0.
   Both are recorded in the surface report as backend gaps, not guessed at. */

import { collectionWordKey } from './actions.js';

/* A word's meaning in the learner's support language. `card.meanings` is a flat
   {language,text}[] the backend already resolved (support_translations + short/detailed
   definitions); this picks the one that matches, then any meaning that is not the word's own
   target-language definition, then whatever is first - it never assumes a language (rule:
   no hardcoding a support locale). */
export function supportMeaning(card = {}, support = '') {
  const meanings = Array.isArray(card.meanings) ? card.meanings : [];
  const target = String(card.identity?.language || '');
  const wanted = String(support || '');
  const exact = meanings.find((meaning) => String(meaning?.language || '') === wanted && meaning?.text);
  if (exact) return String(exact.text);
  const other = meanings.find((meaning) => String(meaning?.language || '') !== target && meaning?.text);
  if (other) return String(other.text);
  return String(meanings[0]?.text || '');
}

/* Mastery bars: 4 bars, `review_stage` (0-4, already the backend's own clamp point elsewhere -
   masteryStars uses the same range) filled in green when the word is saved; a word never saved
   is drawn as NEW instead of a bar count (D2: the two are mutually exclusive, isNew/notNew). */
export function wordRow(card = {}, support = '') {
  const headword = String(card.headword || '');
  const saved = Boolean(card.saved);
  const stage = Math.max(0, Math.min(4, Number(card.review_stage) || 0));
  return {
    id: headword,
    word: headword,
    // languages-5 / finding A: the card's own `identity.language` (this module's header comment:
    // vocabulary_card_from_catalog_entry()'s `{identity:{language,normalized}, ...}` shape) - the
    // word's own real field, not the collection's language_code (a multi-level pack could in
    // principle mix scripts; this build's collections do not, but the per-word field is the more
    // precise source and costs nothing extra to read).
    lang: String(card.identity?.language || ''),
    meaning: supportMeaning(card, support),
    isNew: !saved,
    filled: saved ? stage : 0,
    total: 4,
  };
}

/* The whole screen's view model from one API response. `percent` is the bare progress bar's
   fill: the share of the collection's words the learner has some saved relationship with at
   all (progress.learned_count / item_count) - the closest real measure to "how far along this
   pack is" the backend can answer; it is not a mastery-only figure (mastered_count would
   under-count a pack the learner has only begun). */
export function collectionViewModel(collection = {}, support = '') {
  const items = Array.isArray(collection.items) ? collection.items : [];
  const progress = collection.progress || {};
  const wordCount = Number(collection.item_count) || items.length;
  const learned = Math.max(0, Number(progress.learned_count) || 0);
  const percent = wordCount > 0 ? Math.max(0, Math.min(100, Math.round((learned / wordCount) * 100))) : 0;
  return {
    id: String(collection.id || ''),
    title: String(collection.title || ''),
    // languages-5 / finding A: the collection's own field (writing_coach/vocabulary_library.py
    // `_summary`'s `language_code`).
    language: String(collection.language_code || ''),
    level: String(collection.level_range || collection.level || ''),
    description: '', // rule 40: no description field exists on VocabularyCollection
    wordCount,
    metInSources: 0, // rule 40: no source-encounter aggregate exists for a collection
    percent,
    savedCount: new Set(items.filter((card) => card.saved).map(collectionWordKey)).size,
    missingCount: new Set(items.filter((card) => !card.saved && card.headword).map(collectionWordKey)).size,
    words: items.map((card) => wordRow(card, support)),
  };
}
