/* What a list already knows about a word when it opens Word Detail (LEX-066).

   A catalogue card (a collection row, a Daily-feed card) carries the sense's reading and its
   localizations. Word Detail opens by headword alone, and its lookup is context-based: for a word
   that is not saved and has no sentence it can answer without a reading or a meaning. The list
   leaves the card here, in memory for this visit only (nothing stored, nothing sent), and Word Detail
   reads it back as the fallback for the reading and the meaning. A page opened directly, with no
   list before it, has no seed and asks the catalogue instead. */
const seeds = new Map();
const keyOf = (word) => String(word ?? '').trim().toLowerCase();

export function rememberWordSeed(card) {
  const word = keyOf(card?.headword || card?.word);
  if (!word) return;
  seeds.set(word, {
    pronunciation: String(card.pronunciation || card.readings?.[0]?.text || '').trim(),
    short_meanings: Array.isArray(card.short_meanings) && card.short_meanings.length ? card.short_meanings : (Array.isArray(card.meanings) ? card.meanings : []),
    identity: card.identity || null,
  });
  if (seeds.size > 600) seeds.delete(seeds.keys().next().value);
}

export function wordSeed(word) {
  return seeds.get(keyOf(word)) || null;
}
