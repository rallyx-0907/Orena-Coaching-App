import { esc } from './html.js';
import { scene } from './brand.js';
import { art, duration, origin } from './content.js';
import {
  continuationExperience,
  continuationLink,
  link,
} from '../product/intent.js';
import { continuationEntries } from './patterns.js';
import { referenceCopy } from './reference.js';
import { entryIcon } from './icons.js';
import {
  compactSupportMeaning,
  vocabularyLevel,
} from './vocabulary-experience.js';

const RAIL_PREVIEW_LIMIT = 12;

export function practiceOverview(ctx) {
  const { c } = ctx, r = referenceCopy[ctx.ui];
  const intentions = [
    ['dictation','focus'], ['shadowing','sound'], ['speaking','voice'],
    ['writing','pen'], ['grammar','spark'], ['recall','return'],
  ];
  return `<section class="practice-workbench" aria-label="${esc(r.direct)}"><div class="workbench-note">${scene('focus',{size:'medium'})}<small>${esc(r.direct)}</small><p>${esc(c.practiceContext)}</p></div><div class="practice-options">${intentions.map(([intent,icon],i)=>`<a href="${intent==='writing'?link('expression'):link('practice',{intent})}"><span class="option-number" aria-hidden="true">0${i+1}</span>${entryIcon(icon)}<div><h2>${esc(c[intent+'Name'])}</h2><p>${esc(c[intent+'Note'])}</p></div><span aria-hidden="true">↗</span></a>`).join('')}</div></section>`;
}

/* The rail owns browsing behaviour only. Domain renderers keep their own
   shapes and information hierarchy, while every shelf gets the same visible
   overflow affordance, controls, snap behaviour and keyboard entry point. */
export function contentRail({
  id,
  title,
  icon,
  items = [],
  seeAllHref,
  seeAllLabel,
  previousLabel,
  nextLabel,
  emptyLabel = '',
}) {
  const safeId = String(id || 'content').replace(/[^a-z0-9_-]/gi, '-');
  const headingId = `content-rail-${safeId}-title`;
  const trackId = `content-rail-${safeId}-track`;
  const cards = items.length
    ? items.map((item) => `<div class="content-rail__item" role="listitem">${item}</div>`).join('')
    : `<div class="content-rail__item content-rail__item--empty" role="listitem"><p class="content-rail__empty" role="status">${esc(emptyLabel)}</p></div>`;
  return `<section class="content-rail content-rail--${esc(safeId)}" data-content-rail="${esc(safeId)}" aria-labelledby="${esc(headingId)}"><header class="content-rail__header"><div class="content-rail__heading"><span class="content-rail__icon" aria-hidden="true">${entryIcon(icon)}</span><h2 id="${esc(headingId)}">${esc(title)}</h2></div><a class="content-rail__all" href="${esc(seeAllHref)}">${esc(seeAllLabel)} <span aria-hidden="true">→</span></a></header><div class="content-rail__viewport"><button type="button" class="content-rail__control content-rail__control--previous" data-content-rail-prev aria-controls="${esc(trackId)}" aria-label="${esc(previousLabel)}"${items.length < 2 ? ' disabled' : ''}>←</button><div id="${esc(trackId)}" class="content-rail__track" data-content-rail-track role="list" tabindex="0">${cards}</div><button type="button" class="content-rail__control content-rail__control--next" data-content-rail-next aria-controls="${esc(trackId)}" aria-label="${esc(nextLabel)}"${items.length < 2 ? ' disabled' : ''}>→</button></div></section>`;
}

function readingCard(item, ctx) {
  const meta = [item.level, item.time].filter(Boolean).join(' · ');
  return `<a class="discover-content-card discover-reading-card" data-reading-card href="${esc(link('encounter', { id: item.id, intent: 'reading' }))}"><span class="discover-reading-card__visual">${art(item)}</span><span class="discover-content-card__body"><strong lang="${esc(item.language || ctx.language)}">${esc(item.title)}</strong><small>${esc(meta || origin(item, ctx.c))}</small></span></a>`;
}

function listeningCard(item, ctx) {
  const length = Number(item.duration_ms) > 0 ? duration(item.duration_ms) : '';
  const meta = [item.level, item.source_label].filter(Boolean).join(' · ');
  return `<a class="discover-content-card discover-listening-card" data-listening-card href="${esc(link('encounter', { id: item.id, intent: 'follow' }))}"><span class="discover-listening-card__visual">${art(item)}${length ? `<span class="discover-listening-card__duration">${esc(length)}</span>` : ''}<span class="discover-listening-card__play" aria-hidden="true">▶</span></span><span class="discover-content-card__body"><strong lang="${esc(item.language || ctx.language)}">${esc(item.title)}</strong>${meta ? `<small>${esc(meta)}</small>` : ''}</span></a>`;
}

function speakingCard(item, ctx) {
  return `<a class="discover-prompt-card discover-speaking-card" data-speaking-card href="${esc(link('practice', { id: `voice:${item.key}`, intent: 'speaking' }))}"><span class="discover-prompt-card__icon" aria-hidden="true">${entryIcon('voice')}</span><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong><span aria-hidden="true">→</span></a>`;
}

function writingCard(item, ctx) {
  return `<a class="discover-prompt-card discover-writing-card" data-writing-card href="${esc(link('expression', { id: item.id }))}"><span class="discover-prompt-card__icon" aria-hidden="true">${entryIcon('pen')}</span><strong lang="${esc(ctx.language)}">${esc(item.prompt || item.title)}</strong><span aria-hidden="true">→</span></a>`;
}

function vocabularyCard(card, ctx) {
  const targetLanguage = card.identity?.language || ctx.language;
  const meaning = compactSupportMeaning(card, ctx.support, 72);
  const level = vocabularyLevel(card);
  return `<a class="discover-vocabulary-card" data-vocabulary-card href="${esc(link('language'))}"><span class="discover-vocabulary-card__top">${level ? `<small>${esc(level)}</small>` : ''}<span aria-hidden="true">↗</span></span><strong lang="${esc(targetLanguage)}">${esc(card.headword)}</strong>${meaning ? `<span lang="${esc(ctx.support || '')}">${esc(meaning)}</span>` : ''}${card.pronunciation ? `<small lang="${esc(targetLanguage)}">${esc(card.pronunciation)}</small>` : ''}</a>`;
}

const continuationIcons = {
  listening: 'sound',
  reading: 'book',
  speaking: 'voice',
  writing: 'pen',
  understanding: 'spark',
  practice: 'focus',
  recall: 'return',
};

function continuationCard(item, ctx) {
  const experience = continuationExperience(item);
  const label = experience === 'listening'
    ? ctx.c.followName
    : ctx.c[`${experience}Name`] || ctx.c.resume;
  return `<a class="discover-continuation-card" href="${esc(continuationLink(item))}"><span aria-hidden="true">${entryIcon(continuationIcons[experience] || 'return')}</span><small>${esc(label)}</small><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong><span aria-hidden="true">→</span></a>`;
}

function railCopy(ctx, id, icon, items, href) {
  const r = referenceCopy[ctx.ui];
  return contentRail({
    id,
    title: r[id] || ctx.c[`${id}Name`] || id,
    icon,
    items,
    seeAllHref: href,
    seeAllLabel: r.collectionViewAll,
    previousLabel: `${r.railPrevious}: ${r[id] || id}`,
    nextLabel: `${r.railNext}: ${r[id] || id}`,
    emptyLabel: r.railEmpty,
  });
}

/* Discover distributes real domain content. Vertical movement changes domain;
   horizontal movement stays inside that domain. Continue is the only mixed
   shelf because its purpose is to return to unfinished learner work. */
export function discoverySpread(
  ctx,
  {
    media = [],
    reading = [],
    speaking = [],
    writing = [],
    vocabulary = [],
    catalogError = '',
  },
) {
  const r = referenceCopy[ctx.ui];
  const continuation = continuationEntries(ctx.memory).slice(0, 8);
  const rails = [];
  if (continuation.length) {
    rails.push(contentRail({
      id: 'continue',
      title: r.continueLearning,
      icon: 'return',
      items: continuation.map((item) => continuationCard(item, ctx)),
      seeAllHref: link('continue'),
      seeAllLabel: r.collectionViewAll,
      previousLabel: `${r.railPrevious}: ${r.continueLearning}`,
      nextLabel: `${r.railNext}: ${r.continueLearning}`,
    }));
  }
  rails.push(
    railCopy(ctx, 'reading', 'book', reading.slice(0, RAIL_PREVIEW_LIMIT).map((item) => readingCard(item, ctx)), link('practice', { intent: 'reading' })),
    railCopy(ctx, 'listening', 'sound', media.slice(0, RAIL_PREVIEW_LIMIT).map((item) => listeningCard(item, ctx)), link('practice', { intent: 'follow' })),
    railCopy(ctx, 'speaking', 'voice', speaking.map((item) => speakingCard(item, ctx)), link('practice', { intent: 'speaking' })),
    railCopy(ctx, 'writing', 'pen', writing.map((item) => writingCard(item, ctx)), link('expression')),
    railCopy(ctx, 'vocabulary', 'leaf', vocabulary.map((item) => vocabularyCard(item, ctx)), link('language')),
  );
  return `<header class="discover-hero"><h1>${esc(r.discover)}</h1>${scene('discovery',{size:'hero'})}</header>${catalogError || ''}<div class="discover-feed">${rails.join('')}</div>`;
}

export function bindContentRails(root) {
  if (!root?.querySelectorAll) return () => {};
  const reducedMotion = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const observers = [];
  root.querySelectorAll('[data-content-rail]').forEach((rail) => {
    const track = rail.querySelector('[data-content-rail-track]');
    const previous = rail.querySelector('[data-content-rail-prev]');
    const next = rail.querySelector('[data-content-rail-next]');
    if (!track) return;
    const step = (direction) => {
      const card = track.querySelector('.content-rail__item');
      const width = card?.getBoundingClientRect().width || track.clientWidth * 0.72;
      track.scrollBy({ left: direction * (width + 16), behavior: reducedMotion ? 'auto' : 'smooth' });
    };
    const update = () => {
      if (previous) previous.disabled = track.scrollLeft <= 2;
      if (next) next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
      rail.classList.toggle('is-at-end', track.scrollLeft + track.clientWidth >= track.scrollWidth - 2);
    };
    previous?.addEventListener('click', () => step(-1));
    next?.addEventListener('click', () => step(1));
    track.addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      step(event.key === 'ArrowLeft' ? -1 : 1);
    });
    let startX = 0;
    let startY = 0;
    let startScroll = 0;
    let pointerId = null;
    let dragged = false;
    let dragAxis = '';
    track.addEventListener('pointerdown', (event) => {
      if (event.button !== 0) return;
      pointerId = event.pointerId;
      startX = event.clientX;
      startY = event.clientY;
      startScroll = track.scrollLeft;
      dragged = false;
      dragAxis = '';
    });
    track.addEventListener('pointermove', (event) => {
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
      event.preventDefault();
      track.scrollLeft = startScroll - distance;
    });
    const release = (event) => {
      if (pointerId !== event.pointerId) return;
      if (track.hasPointerCapture?.(pointerId)) track.releasePointerCapture(pointerId);
      pointerId = null;
      track.classList.remove('is-dragging');
    };
    track.addEventListener('pointermove', () => track.classList.toggle('is-dragging', dragged));
    track.addEventListener('pointerup', release);
    track.addEventListener('pointercancel', release);
    track.addEventListener('click', (event) => {
      if (!dragged) return;
      event.preventDefault();
      event.stopPropagation();
      dragged = false;
    }, true);
    track.addEventListener('scroll', update, { passive: true });
    const resizeObserver = globalThis.ResizeObserver
      ? new globalThis.ResizeObserver(update)
      : null;
    resizeObserver?.observe(track);
    if (resizeObserver) observers.push(resizeObserver);
    update();
  });
  return () => observers.forEach((resizeObserver) => resizeObserver?.disconnect());
}
