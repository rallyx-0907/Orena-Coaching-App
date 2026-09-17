import { esc, safeExternal } from './html.js';

// Content presentation is shared by discovery, practice and the encounter.
export const duration = (ms) => {
  const seconds = Math.round((Number(ms) || 0) / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
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
/* A shelf of texts without cover images used to be a shelf of one cover: every
   passage drew the same "Aa 字" on the same ground, so five spines read as one
   block of colour. A text still has something of its own to show - its first
   letter - and a stable identity to vary the ground with, so the fallback is
   controlled variation over real data rather than a repeated placeholder. */
const COVER_VARIANTS = 6;
function coverVariant(item) {
  const seed = String(item.id || item.title || '');
  let total = 0;
  for (let index = 0; index < seed.length; index += 1)
    total = (total + seed.charCodeAt(index)) % COVER_VARIANTS;
  return total;
}
function coverMark(item) {
  if (item.art === 'table') return '◡ ◡';
  if (item.art === 'street') return '↗';
  return [...String(item.title || '').trim()][0] || 'Aa';
}
export function art(item) {
  const poster = safeExternal(item.poster_url);
  if (poster)
    return `<img src="${esc(poster)}" alt="" loading="lazy" referrerpolicy="no-referrer">`;
  if (item.art === 'train')
    return '<img src="/orena-assets/assets/last-train.png" alt="" loading="lazy">';
  if (
    item.kind === 'text' ||
    item.kind === 'story' ||
    item.origin === 'generated'
  )
    return `<div class="text-art" data-cover-variant="${coverVariant(item)}" aria-hidden="true"><span>${esc(coverMark(item))}</span></div>`;
  return '<div class="sound-art" aria-hidden="true"><div class="sound-orbit"></div><span class="sound-wave">▂ ▅ ▃ ▇ ▂ ▆ ▄ ▅ ▂</span><span class="sound-note">♪</span></div>';
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

export function audioIdentity(item, c) {
  return `<div class="audio-identity"><div class="voice-orbit" aria-hidden="true"><span></span></div><div><small>${esc(c.audio)}</small><p>${esc(item.source?.creator || c.audioMoment)}</p><span>${esc(c.audioMoment)}</span></div></div>`;
}
