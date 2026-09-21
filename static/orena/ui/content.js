import { esc, safeExternal } from './html.js';
import { contentCover } from './cover.js';

// Content presentation is shared by discovery, practice and the encounter.
export const duration = (ms) => {
  const seconds = Math.round((Number(ms) || 0) / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
};
export function origin(item, c) {
  if(item.rights?.status==='cleared')return c.publishedText;
  // A reading passage is labelled by how it actually came to exist. Without a
  // generator the API answers every request with the same built-in passage, and
  // calling that "written for you" would be the one lie the surface cannot
  // afford while asking the learner to trust its explanations.
  if (item.generation_mode)
    return item.generation_mode === 'generated'
      ? c.readingWritten
      : c.readingBuiltIn;
  return item.is_development_candidate
    ? c.candidate
    : item.origin === 'imported'
      ? c.imported
      : item.origin === 'generated'
        ? c.generated
        : c.provided;
}
/* Real imagery first, a designed cover second, a letter never.

   A shelf of texts without cover images used to draw the item's first character
   on a tinted rectangle, so five spines read as one block of colour with an
   alphabet on it. D-057 retires that: a production surface shows no single
   letter, no repeated `Aa 字` and no generic geometric block. When no real
   image exists the item gets a cover from the one deterministic system in
   `ui/cover.js`, drawn from its own identity and what it is. */
export function art(item) {
  const poster = safeExternal(item.poster_url);
  if (poster)
    return `<img src="${esc(poster)}" alt="" loading="lazy" referrerpolicy="no-referrer">`;
  if (item.art === 'train')
    return '<img src="/orena-assets/assets/last-train.png" alt="" loading="lazy">';
  return contentCover(item);
}
export function bindImages(root, c) {
  root.querySelectorAll('img').forEach((img) =>
    img.addEventListener(
      'error',
      () => {
        const el = document.createElement('div');
        el.className = 'image-unavailable';
        el.textContent = c.open;
        img.replaceWith(el);
      },
      { once: true },
    ),
  );
}
