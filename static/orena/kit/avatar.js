/* The learner's avatar: their account picture, or their initial in the design's round avatar (frame Profile, the
   rail and the phone header all draw the initial). A picture that does not load (a revoked or expired provider URL
   answers with an error, naturalWidth 0) falls back to the initial, so the avatar is never a broken image.

   The fallback is one capture-phase `error` listener on the document (an image's error does not bubble, and the
   page's script policy allows no inline `onerror`), plus a sweep for a picture that already failed before the
   listener was there. Each avatar image carries its initial in `data-avatar-initial`. */
import { html } from './html.js';

/* `<span class="{className}">` holding the picture (with its initial for the fallback), or the initial itself. */
export function avatarMarkup({ picture = '', initial = '' } = {}, className = 'o-avatar') {
  return picture
    ? html`<span class="${className}"><img src="${picture}" alt="" data-avatar-initial="${initial}"></span>`
    : html`<span class="${className}" aria-hidden="true">${initial}</span>`;
}

/* Replace a failed avatar picture with its initial. True when it did. */
export function fallBackToInitial(image) {
  if (!image || !image.hasAttribute?.('data-avatar-initial')) return false;
  const holder = image.parentElement;
  if (!holder) return false;
  holder.setAttribute('aria-hidden', 'true');
  holder.textContent = image.getAttribute('data-avatar-initial') || '';
  return true;
}

/* A picture that finished loading with nothing to show (naturalWidth 0) has failed. */
export function avatarFailed(image) {
  return Boolean(image?.complete) && !image.naturalWidth;
}

let installed = false;
export function installAvatarFallback(doc = globalThis.document) {
  if (installed || !doc?.addEventListener) return false;
  installed = true;
  doc.addEventListener('error', (event) => {
    const target = event.target;
    if (target?.tagName === 'IMG') fallBackToInitial(target);
  }, true);
  for (const image of doc.querySelectorAll?.('img[data-avatar-initial]') || []) if (avatarFailed(image)) fallBackToInitial(image);
  return true;
}
