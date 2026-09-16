import { esc } from './html.js';
import { art, duration, origin } from './content.js';
import { scene } from './brand.js';
import { link } from '../product/intent.js';
import { continuationShelf } from './patterns.js';
import { referenceCopy, entryIcon } from './reference.js';

export function practiceOverview(ctx) {
  const { c } = ctx, r = referenceCopy[ctx.ui];
  const intentions = [
    ['dictation','focus'], ['shadowing','sound'], ['speaking','voice'],
    ['writing','pen'], ['grammar','spark'], ['recall','return'],
  ];
  return `<section class="practice-workbench" aria-label="${esc(r.direct)}"><div class="workbench-note">${scene('focus',{size:'medium'})}<small>${esc(r.direct)}</small><p>${esc(c.practiceContext)}</p></div><div class="practice-options">${intentions.map(([intent,icon],i)=>`<a href="${intent==='writing'?link('expression'):link('practice',{intent})}"><span class="option-number" aria-hidden="true">0${i+1}</span>${entryIcon(icon)}<div><h2>${esc(c[intent+'Name'])}</h2><p>${esc(c[intent+'Note'])}</p></div><span aria-hidden="true">↗</span></a>`).join('')}</div></section>`;
}

export function discoverySpread(ctx, {media, text, catalogError, vocabularyFeed = ''}) {
  const {c,language} = ctx, r = referenceCopy[ctx.ui];
  const feature = media.find(x=>x.kind==='video') || media[0], story = text[0];
  const at = id=>link('encounter',{id});
  const actionItem = (href, icon, title) => `<a class="discover-action" href="${href}">${entryIcon(icon)}<strong>${esc(title)}</strong><span aria-hidden="true">↗</span></a>`;
  const actions = `<nav class="discover-actions" aria-label="${esc(r.browseAll)}">${actionItem(link('practice',{intent:'reading'}),'book',r.reading)}${actionItem(link('practice',{intent:'follow'}),'sound',r.listening)}${actionItem(link('practice',{intent:'speaking'}),'voice',r.speaking)}${actionItem(link('expression'),'pen',r.writing)}${actionItem(link('practice'),'focus',r.practice)}${actionItem(link('language'),'leaf',c.vocabularyTitle)}</nav>`;
  const featured = feature
    ? `<article class="feature-window"><a class="feature-image" href="${at(feature.id)}" aria-label="${esc(feature.title)}">${art(feature)}<span class="play-disc" aria-hidden="true">▶</span>${Number(feature.duration_ms)>0?`<span class="duration">${duration(feature.duration_ms)}</span>`:''}</a><div class="feature-caption"><small>${esc(r.featured)} · ${esc(feature.level || c.audio)}</small><h2 lang="${language}"><a href="${at(feature.id)}">${esc(feature.title)} ↗</a></h2><span class="byline">${esc(origin(feature,c))}${feature.source?.creator ? ` · ${esc(feature.source.creator)}` : ''}</span></div></article>`
    : `<section class="feature-window discover-feature-empty">${catalogError}<h2>${esc(c.noCatalog)}</h2></section>`;
  const reading = story
    ? `<article class="reading-window"><a class="reading-window__link" href="${at(story.id)}"><div class="reading-window-art">${art(story)}</div><span><small>${esc(r.readNext)}</small><h2 lang="${language}">${esc(story.title)} ↗</h2><span class="byline">${esc(origin(story,c))}</span></span></a></article>`
    : '';
  return `<header class="discover-hero"><h1>${esc(r.discover)}</h1>${scene('discovery',{size:'hero'})}</header>
    <section class="discover-overview">${actions}${continuationShelf(ctx,2,{title:r.continueLearning,compact:true})}</section>
    <section class="editorial-spread discover-content" aria-label="${esc(r.featured)}">${featured}<aside class="discover-content__rail">${reading}${vocabularyFeed}</aside></section>
    <section class="bring-invitation"><span aria-hidden="true">＋</span><h2>${esc(c.bring)}</h2><button class="outline" data-bring>${esc(c.importAction)} ↗</button></section>`;
}
