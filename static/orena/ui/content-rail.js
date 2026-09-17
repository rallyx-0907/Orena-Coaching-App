import { esc } from './html.js';
import { entryIcon } from './icons.js';

/* Shared shelf mechanics only. Each domain supplies its own card composition;
   the rail supplies one accessible, touch-first way to browse it. */
export function contentRail({
  id,
  title,
  icon = '',
  items = [],
  seeAllHref = '',
  seeAllLabel = '',
  previousLabel = '',
  nextLabel = '',
  emptyLabel = '',
  showHeader = true,
  className = '',
}) {
  const safeId = String(id || 'content').replace(/[^a-z0-9_-]/gi, '-');
  const headingId = `content-rail-${safeId}-title`;
  const trackId = `content-rail-${safeId}-track`;
  const cards = items.length
    ? items.map((item) => `<div class="content-rail__item" role="listitem">${item}</div>`).join('')
    : `<div class="content-rail__item content-rail__item--empty" role="listitem"><p class="content-rail__empty" role="status">${esc(emptyLabel)}</p></div>`;
  const header = showHeader
    ? `<header class="content-rail__header"><div class="content-rail__heading">${icon ? `<span class="content-rail__icon" aria-hidden="true">${entryIcon(icon)}</span>` : ''}<h2 id="${esc(headingId)}">${esc(title)}</h2></div>${seeAllHref ? `<a class="content-rail__all" href="${esc(seeAllHref)}">${esc(seeAllLabel)} <span aria-hidden="true">→</span></a>` : ''}</header>`
    : `<h2 class="sr-only" id="${esc(headingId)}">${esc(title)}</h2>`;
  return `<section class="content-rail content-rail--${esc(safeId)}${className ? ` ${esc(className)}` : ''}" data-content-rail="${esc(safeId)}" aria-labelledby="${esc(headingId)}">${header}<div class="content-rail__viewport"><button type="button" class="content-rail__control content-rail__control--previous" data-content-rail-prev aria-controls="${esc(trackId)}" aria-label="${esc(previousLabel)}">←</button><div id="${esc(trackId)}" class="content-rail__track" data-content-rail-track role="list" tabindex="0">${cards}</div><button type="button" class="content-rail__control content-rail__control--next" data-content-rail-next aria-controls="${esc(trackId)}" aria-label="${esc(nextLabel)}">→</button></div></section>`;
}

export function bindContentRails(root) {
  if (!root?.querySelectorAll) return () => {};
  const reducedMotion = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const cleanups = [];
  root.querySelectorAll('[data-content-rail]').forEach((rail) => {
    const track = rail.querySelector('[data-content-rail-track]');
    const previous = rail.querySelector('[data-content-rail-prev]');
    const next = rail.querySelector('[data-content-rail-next]');
    if (!track) return;
    const step = (direction) => {
      const card = track.querySelector('.content-rail__item');
      const styles = globalThis.getComputedStyle?.(track);
      const gap = Number.parseFloat(styles?.columnGap || styles?.gap || '0') || 0;
      const width = card?.getBoundingClientRect().width || track.clientWidth * 0.72;
      track.scrollBy({ left: direction * (width + gap), behavior: reducedMotion ? 'auto' : 'smooth' });
    };
    const update = () => {
      const atStart = track.scrollLeft <= 2;
      const atEnd = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
      if (previous) {
        previous.disabled = atStart;
        previous.hidden = atStart;
      }
      if (next) {
        next.disabled = atEnd;
        next.hidden = atEnd;
      }
      rail.classList.toggle('is-at-start', atStart);
      rail.classList.toggle('is-at-end', atEnd);
    };
    const onPrevious = () => step(-1);
    const onNext = () => step(1);
    const onKeydown = (event) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      step(event.key === 'ArrowLeft' ? -1 : 1);
    };
    previous?.addEventListener('click', onPrevious);
    next?.addEventListener('click', onNext);
    track.addEventListener('keydown', onKeydown);

    let startX = 0;
    let startY = 0;
    let startScroll = 0;
    let pointerId = null;
    let dragged = false;
    let dragAxis = '';
    const onPointerDown = (event) => {
      if (event.button !== 0) return;
      pointerId = event.pointerId;
      startX = event.clientX;
      startY = event.clientY;
      startScroll = track.scrollLeft;
      dragged = false;
      dragAxis = '';
    };
    const onPointerMove = (event) => {
      if (pointerId !== event.pointerId) return;
      const distance = event.clientX - startX;
      const horizontalDistance = Math.abs(distance);
      const verticalDistance = Math.abs(event.clientY - startY);
      if (!dragAxis && Math.max(horizontalDistance, verticalDistance) > 6) {
        dragAxis = horizontalDistance > verticalDistance ? 'horizontal' : 'vertical';
        if (dragAxis === 'horizontal') track.setPointerCapture?.(pointerId);
      }
      if (dragAxis !== 'horizontal') return;
      dragged = true;
      track.classList.add('is-dragging');
      event.preventDefault();
      track.scrollLeft = startScroll - distance;
    };
    const release = (event) => {
      if (pointerId !== event.pointerId) return;
      if (track.hasPointerCapture?.(pointerId)) track.releasePointerCapture(pointerId);
      pointerId = null;
      track.classList.remove('is-dragging');
    };
    const preventDraggedClick = (event) => {
      if (!dragged) return;
      event.preventDefault();
      event.stopPropagation();
      dragged = false;
    };
    track.addEventListener('pointerdown', onPointerDown);
    track.addEventListener('pointermove', onPointerMove);
    track.addEventListener('pointerup', release);
    track.addEventListener('pointercancel', release);
    track.addEventListener('click', preventDraggedClick, true);
    track.addEventListener('scroll', update, { passive: true });
    const resizeObserver = globalThis.ResizeObserver ? new globalThis.ResizeObserver(update) : null;
    resizeObserver?.observe(track);
    update();
    cleanups.push(() => {
      previous?.removeEventListener('click', onPrevious);
      next?.removeEventListener('click', onNext);
      track.removeEventListener('keydown', onKeydown);
      track.removeEventListener('pointerdown', onPointerDown);
      track.removeEventListener('pointermove', onPointerMove);
      track.removeEventListener('pointerup', release);
      track.removeEventListener('pointercancel', release);
      track.removeEventListener('click', preventDraggedClick, true);
      track.removeEventListener('scroll', update);
      resizeObserver?.disconnect();
    });
  });
  return () => cleanups.forEach((cleanup) => cleanup());
}
