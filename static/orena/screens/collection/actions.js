/* Shared collection action/read orchestration. No providers or storage of its own.
   Opening reads; only the explicit keep action calls the existing saved-word API. */
export const collectionWordKey = (card) => card.identity?.normalized || String(card.headword || '').trim().toLowerCase();
export async function readCollection(id, read, { includeReview = false } = {}) {
  let offset = 0;
  let result;
  const items = [];
  const reviewItems = [];
  do {
    const page = await read(id, { limit: 5000, offset, includeReview });
    result ||= { ...page };
    const rows = Array.isArray(page.items) ? page.items : [];
    if (page.has_more && !rows.length) throw new Error('Collection page made no progress');
    items.push(...rows);
    reviewItems.push(...(page.review_items || []));
    offset += rows.length;
    if (!page.has_more) break;
  } while (true);
  return { ...result, items, progress: { ...result.progress,
    learned_count: items.filter((card) => card.saved).length },
    ...(includeReview ? { review_items: [...new Map(reviewItems.map((row) => [row.word, row])).values()] } : {}) };
}

export function collectionSavePayload(card) {
  const language = card.identity?.language;
  const meanings = card.meanings || [];
  const primary = meanings.find((entry) => entry.language === language);
  const vi = meanings.find((entry) => entry.language === 'vi');
  const example = (card.examples || []).find((entry) => entry.language === language);
  const reading = card.readings?.[0];
  return {
    word: card.headword,
    phonetic: card.pronunciation || '',
    reading: (typeof reading === 'string' ? reading : reading?.text) || card.pronunciation || '',
    part_of_speech: card.part_of_speech || '',
    definition: primary?.text || '',
    translation_vi: vi?.text || '',
    source_fragment: example?.text || '',
    source_kind: 'collection',
  };
}

export async function keepCollectionWords(collection, { language, save, onProgress = () => {}, isCurrent = () => true }) {
  if (collection.language_code !== language) throw new Error('Collection language changed');
  const missing = [...new Map((collection.items || []).filter((card) => !card.saved && card.headword)
    .map((card) => [collectionWordKey(card), card])).values()];
  let added = 0;
  let error = null;
  for (const card of missing) {
    if (!isCurrent()) break;
    if (card.saved) continue;
    try {
      const response = await save(collectionSavePayload(card));
      if (!response?.saved) throw new Error('Word was not saved');
      for (const match of collection.items.filter((entry) =>
        collectionWordKey(entry) === collectionWordKey(card))) {
        match.saved = true;
        match.review_stage = response.item?.review_stage || 0;
        match.due = Boolean(response.item?.due);
      }
      added += 1;
      onProgress(added, missing.length);
    } catch (failure) {
      error = failure;
      break;
    }
  }
  return { added, remaining: missing.filter((card) => !card.saved).length, error };
}
