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
  const meta = [item.level, item.time].filter(Boolean).join(' · ');
  return `<a class="discover-content-card discover-reading-card" data-reading-card href="${esc(link('encounter', { id: item.id, intent: 'reading' }))}"><span class="discover-reading-card__visual">${art(item)}</span><span class="discover-content-card__body"><strong lang="${esc(item.language || ctx.language)}">${esc(item.title)}</strong><small>${esc(meta || origin(item, ctx.c))}</small></span></a>`;
}

function listeningCard(item, ctx) {
  const length = Number(item.duration_ms) > 0 ? duration(item.duration_ms) : '';
  const meta = [item.level, item.source_label].filter(Boolean).join(' · ');
  return `<a class="discover-content-card discover-listening-card" data-listening-card href="${esc(link('encounter', { id: item.id, intent: 'follow' }))}"><span class="discover-listening-card__visual">${art(item)}${length ? `<span class="discover-listening-card__duration">${esc(length)}</span>` : ''}<span class="discover-listening-card__play" aria-hidden="true">${icon('play', { filled: true, size: 14 })}</span></span><span class="discover-content-card__body"><strong lang="${esc(item.language || ctx.language)}">${esc(item.title)}</strong>${meta ? `<small>${esc(meta)}</small>` : ''}</span></a>`;
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
  /* The thing itself, then what the learner was doing to it. A row of white
     cards carrying only a word and a title was the SaaS grammar D-057 names;
     the cover makes a resumed item recognisable at a glance. */
  return `<a class="discover-continuation-card" href="${esc(continuationLink(item))}"><span class="discover-continuation-card__visual" aria-hidden="true">${art(item)}</span><small>${entryIcon(continuationIcons[experience] || 'return')}${esc(label)}</small><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong></a>`;
}

function rail(ctx, { id, title, icon, items, href = '' }) {
  const r = referenceCopy[ctx.ui];
  return contentRail({
    id,
    title,
    icon,
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

/* The doors. Skill names are valid navigation vocabulary (D-057) and a learner
   who already knows they want to listen today deserves one. They are a compact
   row of marks, not the structure of the surface: content comes first above
   them and continues below. */
function doors(ctx) {
  const r = referenceCopy[ctx.ui];
  /* Each door wears its design-system domain in a small tile (D-059 rule 32).
     On a desk the rail already carries these rooms, so the row is a phone's
     way into Practice and CSS keeps it to narrow screens. */
  const entries = [
    ['reading', 'book-open', 'reading', link('practice', { intent: 'reading' })],
    ['listening', 'headphones', 'listening', link('practice', { intent: 'follow' })],
    ['speaking', 'microphone', 'speaking', link('practice', { intent: 'speaking' })],
    ['dictation', 'keyboard', 'dictation', link('practice', { intent: 'dictation' })],
    ['writing', 'pencil-simple', 'writing', link('expression')],
    ['vocabulary', 'cards', 'vocabulary', link('language')],
  ];
  return `<nav class="discover-doors" aria-label="${esc(r.browseAll)}">${entries
    .map(([key, glyph, domain, href]) => `<a class="discover-door" data-discover-door="${esc(key)}" data-domain="${esc(domain)}" href="${esc(href)}"><span class="discover-door__mark" aria-hidden="true">${icon(glyph, { size: 16 })}</span>${esc(r[key])}</a>`)
    .join('')}</nav>`;
}

/* The first action, and only ever one of them.

   A learner who has never used a language-learning app must see what to do
   within a few seconds, and a learner with history must see the way back
   (D-057, Product Constitution §10). Both are the same block in two states, so
   neither can be pushed under the other by a rail that happened to load. */
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
    : '';
  /* One primary action on the page: the most recent thread carries it, the
     second one is a quiet way in. */
  const action = lead
    ? `<a class="primary" href="${href}">${icon('play', { filled: true, size: 16 })}<span>${esc(r.continueAction)}</span></a>`
    : `<a class="icon-button continue-card__action" href="${href}" aria-label="${esc(`${r.continueAction}: ${item.title}`)}">${icon('caret-right', { size: 20 })}</a>`;
  return `<article class="continue-card"${lead ? ' data-live' : ''} data-domain="${domain}"><span class="continue-card__visual" aria-hidden="true">${art(item)}</span><span class="continue-card__body"><small class="domain-label">${icon(glyph, { size: 14 })}${esc(label)}</small><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong>${progress}</span>${action}</article>`;
}
function startBlock(ctx, { first, resume, next }) {
  const r = referenceCopy[ctx.ui];
  if (resume) {
    return `<section class="discover-start discover-start--resume" aria-labelledby="homeContinue"><h2 class="home-label" id="homeContinue">${esc(r.continue)}</h2><div class="continue-cards">${continueCard(resume, ctx, true)}${next ? continueCard(next, ctx, false) : ''}</div></section>`;
  }
  if (!first)
    return `<section class="discover-start discover-start--begin"><div class="discover-start__body"><h2>${esc(r.startTitle)}</h2></div>${scene('discovery', { size: 'hero' })}</section>`;
  const destination = first.kind === 'audio' || first.kind === 'video'
    ? link('encounter', { id: first.id, intent: 'follow' })
    : link('encounter', { id: first.id, intent: 'reading' });
  const length = minutes(first);
  return `<section class="discover-start discover-start--begin"><div class="discover-start__body"><h2>${esc(r.startTitle)}</h2><a class="primary" href="${esc(destination)}">${esc(r.startAction)} <span aria-hidden="true">→</span></a><small lang="${esc(first.language || ctx.language)}">${esc(first.title)}${length ? ` · ${length} ${esc(r.railMinutes)}` : ''}</small></div>${scene('discovery', { size: 'hero' })}</section>`;
}

/* Discover distributes real domain content, and organises it by what the
   content is rather than by which skill it trains (D-057). A rail is built from
   the data it was handed; a rail with nothing real in it does not appear, and
   nothing here invents an item to fill a shape. */
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

  const rails = [];
  /* The two most recent threads are the cards at the top of the page; this
     shelf holds only the rest, so nothing on Home is shown twice (rule 20). */
  if (continuation.length > 2)
    rails.push(rail(ctx, {
      id: 'continue',
      title: r.continueLearning,
      icon: 'return',
      items: continuation.slice(2).map((item) => continuationCard(item, ctx)),
      href: link('continue'),
    }));

  /* Voices first, then stories: the order the design system's Home gives
     them, artwork leading each shelf. */
  const voices = heard;
  if (voices.length)
    rails.push(rail(ctx, {
      id: 'voices',
      title: r.railVoices,
      icon: 'sound',
      items: voices.map((item) => listeningCard(item, ctx)),
      href: link('practice', { intent: 'follow' }),
    }));

  const stories = texts.filter(
    (item) => STORY_MATERIAL.test(String(item.material || '')) || item.kind === 'story' || item.kind === 'text',
  );
  if (stories.length)
    rails.push(rail(ctx, {
      id: 'stories',
      title: r.railStories,
      icon: 'book',
      items: stories.map((item) => readingCard(item, ctx)),
      href: link('practice', { intent: 'reading' }),
    }));

  /* A lens, not a shelf. It deliberately looks back across everything above and
     may repeat an item, which is what makes it useful to a learner with five
     minutes at a bus stop. It sits after the shelves it draws from, and stays
     small, so it can never become the page. */
  const SHORT_LIMIT = 4;
  const isShort = (item) => minutes(item) > 0 && minutes(item) <= 5;
  // Interleaved, not concatenated: a shelf that answers "what can I finish
  // now?" has to show both kinds inside the first few cards, and a 3:4 cover
  // beside a 16:9 thumbnail is the rhythm the Art Bible asks a shelf for.
  const shortTexts = texts.filter(isShort);
  const shortHeard = heard.filter(isShort);
  const short = [];
  for (let index = 0; short.length < SHORT_LIMIT && (shortTexts[index] || shortHeard[index]); index += 1) {
    if (shortTexts[index]) short.push(shortTexts[index]);
    if (short.length < SHORT_LIMIT && shortHeard[index]) short.push(shortHeard[index]);
  }
  if (short.length > 1)
    rails.push(rail(ctx, {
      id: 'short',
      title: r.railShort,
      icon: 'focus',
      items: short.map((item) => (heard.includes(item) ? listeningCard(item, ctx) : readingCard(item, ctx))),
    }));

  const say = [...speaking, ...writing];
  if (say.length)
    rails.push(rail(ctx, {
      id: 'say',
      title: r.railSay,
      icon: 'voice',
      items: [
        ...speaking.map((item) => speakingCard(item, ctx)),
        ...writing.map((item) => writingCard(item, ctx)),
      ],
      href: link('expression'),
    }));

  if (vocabulary.length)
    rails.push(rail(ctx, {
      id: 'words',
      title: r.railWords,
      icon: 'leaf',
      items: vocabulary.map((item, index) => vocabularyCard({ ...item, __discoverIndex: index }, ctx)),
      href: link('language'),
    }));

  /* The heading names the page for assistive technology; the learner is told
     where they are by the start block and the content beneath it, not by a
     headline the width of the screen. */
  return `<h1 class="sr-only">${esc(r.discover)}</h1>${startBlock(ctx, {
    first: texts.find((item) => minutes(item) > 0 && minutes(item) <= 5) || texts[0] || heard[0] || null,
    resume: continuation[0] || null,
    next: continuation[1] || null,
  })}${doors(ctx)}${catalogError || ''}<div class="discover-feed">${rails.join('')}</div>`;
}
