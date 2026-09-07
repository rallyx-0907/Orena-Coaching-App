import { esc, safeExternal } from './html.js';

// Content presentation is shared by discovery, practice and the encounter.
export const duration = (ms) => {
  const seconds = Math.round((Number(ms) || 0) / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
};
export function origin(item, c) {
  return item.is_development_candidate
    ? c.candidate
    : item.origin === 'imported'
      ? c.imported
      : item.origin === 'generated'
        ? c.generated
        : c.provided;
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
    return `<div class="text-art" aria-hidden="true"><span>${item.art === 'table' ? '◡ ◡' : item.art === 'street' ? '↗' : 'Aa 字'}</span></div>`;
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
