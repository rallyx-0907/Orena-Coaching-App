/* Pure data (no DOM): the tile a card without a cover draws, by what the content is (HP-3 A). Semantic tokens only. */
export const COVER_VISUALS = Object.freeze({
  read: { icon: 'book-open', tint: 'var(--skill-read)' },
  listen: { icon: 'headphones', tint: 'var(--skill-listen)' },
  watch: { icon: 'play', tint: 'var(--skill-listen)' },
  speak: { icon: 'mic', tint: 'var(--skill-speak)' },
  write: { icon: 'notebook-pen', tint: 'var(--skill-write)' },
  grammar: { icon: 'puzzle', tint: 'var(--skill-grammar)' },
  vocab: { icon: 'whole-word', tint: 'var(--skill-vocab)' },
  collection: { icon: 'library-big', tint: 'var(--skill-vocab)' },
  upload: { icon: 'upload', tint: 'var(--skill-grammar)' },
});
