/* A surface that is not a room of its own: Today's words, which Home carries under its rails. The
   Practice map that also lived here is retired (D-078): `#/practice` goes Home.

   Home itself is `ui/home.js` now, built to the design's own frames (D-067); the composition that used
   to live here - the greeting, the hero pair, the "for you" and "saved" shelves - is deleted with it. */
import { esc } from './html.js';
import { link } from '../product/intent.js';
import { icon } from './phosphor.js';
import { referenceCopy } from './reference.js';
import {
  compactSupportMeaning,
  masteryStars,
  vocabularyLevel,
  vocabularyLevelSkin,
  vocabularyRank,
  vocabularyRankToken,
  vocabularyStatus,
} from './vocabulary-experience.js';


/* Today's words: the approved compact stack - one flashcard on top of the
   next few, a counter, tap to flip. The front is the word and its reading;
   the back is its meaning and the two actions (study, keep). Every card is in
   the DOM, so the counter, the keyboard and a screen reader all see the same
   five words; only the top one is shown. */
function wordCard(card, ctx, index, total) {
  const targetLanguage = card.identity?.language || ctx.language;
  const meaning = compactSupportMeaning(card, ctx.support, 72);
  const level = vocabularyLevel(card);
  const skin = vocabularyLevelSkin(card);
  const stars = masteryStars(card);
  const filled = (stars.match(/★/g) || []).length;
  const state = vocabularyStatus(card);
  const stateKey = { new: 'vocabularyNew', learning: 'vocabularyLearningState', due: 'vocabularyDueState', mastered: 'vocabularyMasteredState' }[state];
  const stateLabel = ctx.c[stateKey] || state;
  const r = referenceCopy[ctx.ui];
  const starRow = `<span class="vocabulary-stars" aria-label="${esc(stars)}">${[0, 1, 2].map((n) => icon('star', { filled: n < filled, size: 12, className: n < filled ? 'is-earned' : '' })).join('')}</span>`;
  return `<article class="discover-vocabulary-card" data-vocabulary-card data-word-index="${index}" data-vocabulary-level="${esc(level || 'unknown')}" data-vocabulary-rank="${esc(vocabularyRank(card))}" data-vocabulary-skin="${esc(skin)}" data-vocabulary-state="${esc(state)}"${index ? ' hidden' : ''}><button class="word-card__face word-card__front" type="button" data-word-flip aria-label="${esc(`${card.headword} · ${r.flipCard}`)}"><span class="word-card__word" lang="${esc(targetLanguage)}">${esc(card.headword)}</span>${card.pronunciation ? `<span class="word-card__reading" lang="${esc(targetLanguage)}">${esc(card.pronunciation)}</span>` : ''}<span class="word-card__foot"><span class="word-card__hint">${icon('hand-tap', { size: 14 })}${esc(r.flipCard)}</span>${starRow}</span></button><div class="word-card__face word-card__back" hidden><div class="discover-vocabulary-card__top">${level ? `<small>${esc(level)}</small>` : '<small>—</small>'}${vocabularyRankToken(ctx.c, card)}</div><strong lang="${esc(targetLanguage)}">${esc(card.headword)}</strong>${meaning ? `<span class="discover-vocabulary-card__meaning" lang="${esc(ctx.support || '')}">${esc(meaning)}</span>` : ''}<span class="vocabulary-state vocabulary-state--${esc(state)}">${esc(stateLabel)}</span><div class="discover-vocabulary-card__actions"><a class="quiet" data-vocabulary-study="${index}" href="${esc(link('language'))}">${esc(ctx.c.vocabularyStudy || ctx.c.lookCloser)}</a>${card.saved ? `<span class="quiet" data-vocabulary-saved>${esc(ctx.c.vocabularySaved || ctx.c.saved)} ✓</span>` : `<button class="quiet" type="button" data-discover-vocabulary-save="${index}">${esc(ctx.c.vocabularySave || ctx.c.keep)} ＋</button>`}<button class="quiet" type="button" data-word-flip>${esc(r.flipBack)}</button></div></div></article>`;
}

export function todayWords(ctx, vocabulary) {
  const r = referenceCopy[ctx.ui];
  const total = vocabulary.length;
  const cards = vocabulary.map((card, index) => wordCard(card, ctx, index, total)).join('');
  return `<section class="today-words" data-today-words aria-labelledby="todayWordsTitle"><header class="home-rail-head"><h2 id="todayWordsTitle">${esc(r.todayWords)}</h2><span class="home-rail-meta" data-word-counter aria-live="polite">1 / ${total}</span></header><div class="today-words__stack" data-word-stack tabindex="0" aria-roledescription="${esc(r.todayWords)}">${cards}<span class="today-words__under" aria-hidden="true"></span><span class="today-words__under today-words__under--far" aria-hidden="true"></span></div><div class="today-words__nav"><button class="icon-button" type="button" data-word-prev aria-label="${esc(r.railPrevious)}">${icon('caret-right', { size: 18, className: 'is-flipped' })}</button><button class="icon-button" type="button" data-word-next aria-label="${esc(r.railNext)}">${icon('caret-right', { size: 18 })}</button></div></section>`;
}

/* The stack's behaviour: flip the top card, step through with the buttons,
   the arrow keys or a horizontal swipe. Pure DOM over the markup above. */
export function bindTodayWords(root) {
  const section = root?.querySelector?.('[data-today-words]');
  if (!section) return () => {};
  const cards = [...section.querySelectorAll('[data-vocabulary-card]')];
  const counter = section.querySelector('[data-word-counter]');
  let index = 0;
  const show = (next) => {
    if (!cards.length) return;
    index = (next + cards.length) % cards.length;
    cards.forEach((card, n) => {
      card.hidden = n !== index;
      card.querySelector('.word-card__front').hidden = false;
      card.querySelector('.word-card__back').hidden = true;
    });
    counter.textContent = `${index + 1} / ${cards.length}`;
  };
  const flip = (card) => {
    const front = card.querySelector('.word-card__front');
    const back = card.querySelector('.word-card__back');
    const toBack = back.hidden;
    back.hidden = !toBack;
    front.hidden = toBack;
    (toBack ? back.querySelector('a,button') : front)?.focus({ preventScroll: true });
  };
  section.querySelectorAll('[data-word-flip]').forEach((button) =>
    button.addEventListener('click', () => flip(button.closest('[data-vocabulary-card]'))),
  );
  section.querySelector('[data-word-prev]')?.addEventListener('click', () => show(index - 1));
  section.querySelector('[data-word-next]')?.addEventListener('click', () => show(index + 1));
  const stack = section.querySelector('[data-word-stack]');
  stack.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowRight') show(index + 1);
    else if (event.key === 'ArrowLeft') show(index - 1);
    else return;
    event.preventDefault();
  });
  let startX = null;
  stack.addEventListener('pointerdown', (event) => (startX = event.clientX));
  stack.addEventListener('pointerup', (event) => {
    if (startX === null) return;
    const dx = event.clientX - startX;
    startX = null;
    if (Math.abs(dx) > 40) show(index + (dx < 0 ? 1 : -1));
  });
  return () => {};
}
