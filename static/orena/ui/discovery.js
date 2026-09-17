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
  const meta = [item.level, item.time].filter(Boolean).join(' · ');
  return `<a class="discover-content-card discover-reading-card" data-reading-card href="${esc(link('encounter', { id: item.id, intent: 'reading' }))}"><span class="discover-reading-card__visual">${art(item)}</span><span class="discover-content-card__body"><strong lang="${esc(item.language || ctx.language)}">${esc(item.title)}</strong><small>${esc(meta || origin(item, ctx.c))}</small></span></a>`;
}

function listeningCard(item, ctx) {
  const length = Number(item.duration_ms) > 0 ? duration(item.duration_ms) : '';
  const meta = [item.level, item.source_label].filter(Boolean).join(' · ');
  return `<a class="discover-content-card discover-listening-card" data-listening-card href="${esc(link('encounter', { id: item.id, intent: 'follow' }))}"><span class="discover-listening-card__visual">${art(item)}${length ? `<span class="discover-listening-card__duration">${esc(length)}</span>` : ''}<span class="discover-listening-card__play" aria-hidden="true">▶</span></span><span class="discover-content-card__body"><strong lang="${esc(item.language || ctx.language)}">${esc(item.title)}</strong>${meta ? `<small>${esc(meta)}</small>` : ''}</span></a>`;
}

/* Speaking and Writing are both invitations to produce language, which is why
   they kept collapsing into one card with a different icon. They are told apart
   by what the learner is being handed: Speaking opens a situation and gives the
   opening turn to say something into; Writing hands over the prompt itself,
   with the passage it came from kept quiet underneath. Both read real authored
   fields - neither invents a line to fill its shape. */
function speakingCard(item, ctx) {
  const opening = String(item.cue || item.prompt || '').trim();
  return `<a class="discover-prompt-card discover-speaking-card" data-speaking-card href="${esc(link('practice', { id: `voice:${item.key}`, intent: 'speaking' }))}"><span class="discover-prompt-card__icon" aria-hidden="true">${entryIcon('voice')}</span><span class="discover-prompt-card__body"><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong>${opening ? `<span class="discover-speaking-card__turn" lang="${esc(ctx.language)}">${esc(opening)}</span>` : ''}</span></a>`;
}

function writingCard(item, ctx) {
  const prompt = String(item.prompt || item.title || '').trim();
  const source = String(item.prompt ? item.title || '' : '').trim();
  return `<a class="discover-prompt-card discover-writing-card" data-writing-card href="${esc(link('expression', { id: item.id }))}"><span class="discover-prompt-card__icon" aria-hidden="true">${entryIcon('pen')}</span><span class="discover-prompt-card__body"><strong lang="${esc(ctx.language)}">${esc(prompt)}</strong>${source && source !== prompt ? `<small class="discover-writing-card__source" lang="${esc(item.language || ctx.language)}">${esc(source)}</small>` : ''}</span></a>`;
}

function vocabularyCard(card, ctx) {
  const targetLanguage = card.identity?.language || ctx.language;
  const meaning = compactSupportMeaning(card, ctx.support, 72);
  const level = vocabularyLevel(card);
  const skin = vocabularyLevelSkin(card);
  const stars = masteryStars(card);
  const state = vocabularyStatus(card);
  const index = Number(card.__discoverIndex) || 0;
  const stateKey = { new: 'vocabularyNew', learning: 'vocabularyLearningState', due: 'vocabularyDueState', mastered: 'vocabularyMasteredState' }[state];
  const stateLabel = ctx.c[stateKey] || state;
  /* The word is the anchor; the level and the rank material it is cut from sit
     above it as metadata, and the meaning, pronunciation, mastery and review
     state read in descending weight beneath it. */
  return `<article class="discover-vocabulary-card" data-vocabulary-card data-vocabulary-level="${esc(level || 'unknown')}" data-vocabulary-rank="${esc(vocabularyRank(card))}" data-vocabulary-skin="${esc(skin)}" data-vocabulary-state="${esc(state)}"><div class="discover-vocabulary-card__top">${level ? `<small>${esc(level)}</small>` : '<small>—</small>'}${vocabularyRankToken(ctx.c, card)}</div><strong lang="${esc(targetLanguage)}">${esc(card.headword)}</strong>${meaning ? `<span class="discover-vocabulary-card__meaning" lang="${esc(ctx.support || '')}">${esc(meaning)}</span>` : ''}${card.pronunciation ? `<small class="discover-vocabulary-card__pronunciation" lang="${esc(targetLanguage)}">${esc(card.pronunciation)}</small>` : ''}<div class="discover-vocabulary-card__footer"><span class="vocabulary-stars" aria-label="${esc(stars)}">${esc(stars)}</span><span class="vocabulary-state vocabulary-state--${esc(state)}">${esc(stateLabel)}</span></div><div class="discover-vocabulary-card__actions"><a class="quiet" data-vocabulary-study="${index}" href="${esc(link('language'))}">${esc(ctx.c.vocabularyStudy || ctx.c.lookCloser)}</a>${card.saved ? `<span class="quiet" data-vocabulary-saved>${esc(ctx.c.vocabularySaved || ctx.c.saved)} ✓</span>` : `<button class="quiet" type="button" data-discover-vocabulary-save="${index}">${esc(ctx.c.vocabularySave || ctx.c.keep)} ＋</button>`}</div></article>`;
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
  return `<a class="discover-continuation-card" href="${esc(continuationLink(item))}"><span aria-hidden="true">${entryIcon(continuationIcons[experience] || 'return')}</span><small>${esc(label)}</small><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong></a>`;
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
    railCopy(ctx, 'vocabulary', 'leaf', vocabulary.map((item, index) => vocabularyCard({ ...item, __discoverIndex: index }, ctx)), link('language')),
  );
  return `<header class="discover-hero"><h1>${esc(r.discover)}</h1>${scene('discovery',{size:'hero'})}</header>${catalogError || ''}<div class="discover-feed">${rails.join('')}</div>`;
}
