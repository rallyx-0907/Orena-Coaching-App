import { esc } from './html.js';
import { scene } from './brand.js';
import { art, duration, origin } from './content.js';
import {
  continuationExperience,
  continuationLink,
  link,
} from '../product/intent.js';
import { continuationEntries, continuationPlace } from './patterns.js';
import { icon } from './phosphor.js';
import { referenceCopy } from './reference.js';
import { entryIcon } from './icons.js';
import {
  compactSupportMeaning,
  masteryStars,
  vocabularyLevel,
  vocabularyLevelSkin,
  vocabularyRank,
  vocabularyRankToken,
  vocabularyStatus,
} from './vocabulary-experience.js';
import { bindContentRails, contentRail } from './content-rail.js';

export { bindContentRails, contentRail } from './content-rail.js';

const RAIL_PREVIEW_LIMIT = 12;

export function practiceOverview(ctx) {
  const { c } = ctx, r = referenceCopy[ctx.ui];
  const intentions = [
    ['dictation','focus'], ['shadowing','sound'], ['speaking','voice'],
    ['writing','pen'], ['grammar','spark'], ['recall','return'],
  ];
  return `<section class="practice-workbench" aria-label="${esc(r.direct)}"><div class="workbench-note">${scene('focus',{size:'medium'})}<small>${esc(r.direct)}</small><p>${esc(c.practiceContext)}</p></div><div class="practice-options">${intentions.map(([intent,icon],i)=>`<a href="${intent==='writing'?link('expression'):link('practice',{intent})}"><span class="option-number" aria-hidden="true">0${i+1}</span>${entryIcon(icon)}<div><h2>${esc(c[intent+'Name'])}</h2><p>${esc(c[intent+'Note'])}</p></div><span aria-hidden="true">↗</span></a>`).join('')}</div></section>`;
}

function readingCard(item, ctx) {
  // The approved card: the cover, the title, one line of metadata (level).
  const meta = item.level || item.time || '';
  return `<a class="discover-content-card discover-reading-card" data-reading-card href="${esc(link('encounter', { id: item.id, intent: 'reading' }))}"><span class="discover-reading-card__visual">${art(item)}</span><span class="discover-content-card__body"><strong lang="${esc(item.language || ctx.language)}">${esc(item.title)}</strong>${meta ? `<small>${esc(meta)}</small>` : ''}</span></a>`;
}

function listeningCard(item, ctx, { lead = false } = {}) {
  // The approved card: artwork 16:9 inside a surface, title and length below,
  // and the play control on the first card of the shelf.
  const length = Number(item.duration_ms) > 0 ? duration(item.duration_ms) : '';
  const meta = [item.level, length].filter(Boolean).join(' · ');
  return `<a class="discover-content-card discover-listening-card" data-listening-card href="${esc(link('encounter', { id: item.id, intent: 'follow' }))}"><span class="discover-listening-card__visual">${art(item)}${lead ? `<span class="discover-listening-card__play" aria-hidden="true">${icon('play', { filled: true, size: 14 })}</span>` : ''}</span><span class="discover-content-card__body"><strong lang="${esc(item.language || ctx.language)}">${esc(item.title)}</strong>${meta ? `<small>${esc(meta)}</small>` : ''}</span></a>`;
}

/* Speaking and Writing are both invitations to produce language, which is why
   they kept collapsing into one card with a different icon. They are told apart
   by what the learner is being handed: Speaking opens a situation and gives the
   opening turn to say something into; Writing hands over the prompt itself,
   with the passage it came from kept quiet underneath. Both read real authored
   fields - neither invents a line to fill its shape. */
function speakingCard(item, ctx) {
  const opening = String(item.cue || item.prompt || '').trim();
  return `<a class="discover-prompt-card discover-speaking-card" data-speaking-card data-domain="speaking" href="${esc(link('practice', { id: `voice:${item.key}`, intent: 'speaking' }))}"><span class="discover-prompt-card__icon" aria-hidden="true">${icon('microphone', { size: 18 })}</span><span class="discover-prompt-card__body"><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong>${opening ? `<span class="discover-speaking-card__turn" lang="${esc(ctx.language)}">${esc(opening)}</span>` : ''}</span></a>`;
}

function writingCard(item, ctx) {
  const prompt = String(item.prompt || item.title || '').trim();
  const source = String(item.prompt ? item.title || '' : '').trim();
  return `<a class="discover-prompt-card discover-writing-card" data-writing-card data-domain="writing" href="${esc(link('expression', { id: item.id }))}"><span class="discover-prompt-card__icon" aria-hidden="true">${icon('pencil-simple', { size: 18 })}</span><span class="discover-prompt-card__body"><strong lang="${esc(ctx.language)}">${esc(prompt)}</strong>${source && source !== prompt ? `<small class="discover-writing-card__source" lang="${esc(item.language || ctx.language)}">${esc(source)}</small>` : ''}</span></a>`;
}

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

function todayWords(ctx, vocabulary) {
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

function rail(ctx, { id, title, items, href = '', meta = '' }) {
  const r = referenceCopy[ctx.ui];
  return contentRail({
    id,
    title,
    meta,
    items,
    seeAllHref: href,
    seeAllLabel: r.collectionViewAll,
    previousLabel: `${r.railPrevious}: ${title}`,
    nextLabel: `${r.railNext}: ${title}`,
    emptyLabel: r.railEmpty,
  });
}

/* How long a thing takes, in whole minutes, from whatever field its domain
   authored. Unknown stays unknown: an item with no stated length is never
   guessed into a shelf that promises five minutes. */
function minutes(item) {
  if (Number(item?.duration_ms) > 0) return Math.round(Number(item.duration_ms) / 60000);
  const stated = /(\d+)/.exec(String(item?.time || ''));
  return stated ? Number(stated[1]) : 0;
}

const STORY_MATERIAL = /fable|story|fiction|tale|classical/i;

/* Continue (D-060): the approved composition - a small "Continue" label and
   the two most recent threads as lit cards, each with its artwork, room,
   title, a progress rail and one round action. The progress rail always has
   its place; where the thread records no position it is the unavailable
   track, never an invented number (GAP-006). */
const CONTINUE_DOMAIN = {
  listening: ['listening', 'headphones'],
  reading: ['reading', 'book-open'],
  speaking: ['speaking', 'microphone'],
  writing: ['writing', 'pencil-simple'],
  understanding: ['neutral', 'sparkle'],
  practice: ['dictation', 'keyboard'],
  recall: ['vocabulary', 'cards'],
};
function continueCard(item, ctx, lead) {
  const r = referenceCopy[ctx.ui];
  const experience = continuationExperience(item);
  const label = experience === 'listening' ? ctx.c.followName : ctx.c[`${experience}Name`] || ctx.c.resume;
  const [domain, glyph] = CONTINUE_DOMAIN[experience] || ['neutral', 'clock-counter-clockwise'];
  const place = continuationPlace(item);
  const href = esc(continuationLink(item));
  const progress = place
    ? `<span class="continue-card__progress"><span class="progress-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${place.percent}" aria-label="${esc(item.title)}"><span style="width:${place.percent}%"></span></span><small>${place.percent}%</small></span>`
    : `<span class="continue-card__progress"><span class="progress-bar" data-unavailable aria-hidden="true"></span></span>`;
  /* The page's one primary action is the most recent thread's round play
     button; the second thread has a quiet round way in. */
  const action = lead
    ? `<a class="primary continue-card__play" href="${href}" aria-label="${esc(`${r.continueAction}: ${item.title}`)}">${icon('play', { filled: true, size: 18 })}</a>`
    : `<a class="icon-button continue-card__go" href="${href}" aria-label="${esc(`${r.continueAction}: ${item.title}`)}">${icon('caret-right', { size: 18 })}</a>`;
  return `<article class="continue-card" data-live${lead ? ' data-lead' : ''} data-domain="${domain}"><span class="continue-card__visual" aria-hidden="true">${art(item)}</span><span class="continue-card__body"><small class="domain-label">${icon(glyph, { size: 13 })}${esc(label)}</small><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong>${progress}</span>${action}</article>`;
}
function startBlock(ctx, { first, resume, next, more }) {
  const r = referenceCopy[ctx.ui];
  if (resume) {
    return `<section class="discover-start discover-start--resume" aria-labelledby="homeContinue"><header class="home-label-row"><h2 class="home-label" id="homeContinue">${esc(r.continue)}</h2>${more ? `<a class="home-rail-all" href="${esc(link('continue'))}">${esc(r.collectionViewAll)}${icon('caret-right', { size: 14 })}</a>` : ''}</header><div class="continue-cards">${continueCard(resume, ctx, true)}${next ? continueCard(next, ctx, false) : ''}</div></section>`;
  }
  if (!first)
    return `<section class="discover-start discover-start--begin"><div class="discover-start__body"><h2>${esc(r.startTitle)}</h2></div></section>`;
  const destination = first.kind === 'audio' || first.kind === 'video'
    ? link('encounter', { id: first.id, intent: 'follow' })
    : link('encounter', { id: first.id, intent: 'reading' });
  const length = minutes(first);
  return `<section class="discover-start discover-start--begin"><span class="continue-card__visual" aria-hidden="true">${art(first)}</span><div class="discover-start__body"><h2>${esc(r.startTitle)}</h2><small lang="${esc(first.language || ctx.language)}">${esc(first.title)}${length ? ` · ${length} ${esc(r.railMinutes)}` : ''}</small></div><a class="primary" href="${esc(destination)}">${esc(r.startAction)}${icon('arrow-right', { size: 16 })}</a></section>`;
}

/* Home (D-060): the approved composition, in its order - Continue, the
   Listening shelf, then the Reading shelf beside Today's words. The
   speaking-and-writing shelf follows: the design's checklist lists it as a
   Home rail it has not drawn yet, and it is the phone's only way to those
   prompts, so it stays - in the shelf's approved shape. A shelf with nothing
   real in it does not appear, and nothing here invents an item. */
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
  const texts = reading.slice(0, RAIL_PREVIEW_LIMIT);
  const heard = media.slice(0, RAIL_PREVIEW_LIMIT);
  const countLabel = (n) => r.itemCount.replace('{n}', String(n));

  const blocks = [];
  if (heard.length)
    blocks.push(rail(ctx, {
      id: 'voices',
      title: r.listening,
      meta: countLabel(media.length),
      items: heard.map((item, index) => listeningCard(item, ctx, { lead: index === 0 })),
      href: link('practice', { intent: 'follow' }),
    }));

  const stories = texts.filter(
    (item) => STORY_MATERIAL.test(String(item.material || '')) || item.kind === 'story' || item.kind === 'text',
  );
  const readingRail = stories.length
    ? rail(ctx, {
        id: 'stories',
        title: r.reading,
        items: stories.map((item) => readingCard(item, ctx)),
        href: link('practice', { intent: 'reading' }),
      })
    : '';
  const words = vocabulary.length ? todayWords(ctx, vocabulary.slice(0, 5)) : '';
  if (readingRail || words)
    blocks.push(`<div class="home-pair">${readingRail}${words}</div>`);

  const say = [...speaking, ...writing];
  if (say.length)
    blocks.push(rail(ctx, {
      id: 'say',
      title: r.railSay,
      items: [
        ...speaking.map((item) => speakingCard(item, ctx)),
        ...writing.map((item) => writingCard(item, ctx)),
      ],
      href: link('expression'),
    }));

  /* The heading names the page for assistive technology; the learner is told
     where they are by the rail and the content beneath it. */
  return `<h1 class="sr-only">${esc(r.home)}</h1>${startBlock(ctx, {
    first: texts.find((item) => minutes(item) > 0 && minutes(item) <= 5) || texts[0] || heard[0] || null,
    resume: continuation[0] || null,
    next: continuation[1] || null,
    more: continuation.length > 2,
  })}${catalogError || ''}<div class="discover-feed">${blocks.join('')}</div>`;
}
