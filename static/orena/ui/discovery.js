import { esc } from './html.js';
import { art, duration, origin } from './content.js';
import { scene } from './brand.js';
import { link } from '../product/intent.js';
import { continuationShelf } from './patterns.js';
import { referenceCopy, editorialIntro, entryIcon } from './reference.js';

export function practiceOverview(ctx) {
  const { c } = ctx, r = referenceCopy[ctx.ui];
  const intentions = [
    ['dictation','focus'], ['shadowing','sound'], ['speaking','voice'],
    ['writing','pen'], ['grammar','spark'], ['recall','return'],
  ];
  return `<section class="practice-workbench" aria-label="${esc(r.direct)}"><div class="workbench-note">${scene('focus',{size:'medium'})}<small>${esc(r.direct)}</small><p>${esc(c.practiceContext)}</p></div><div class="practice-options">${intentions.map(([intent,icon],i)=>`<a href="${intent==='writing'?link('expression'):link('practice',{intent})}"><span class="option-number" aria-hidden="true">0${i+1}</span>${entryIcon(icon)}<div><h2>${esc(c[intent+'Name'])}</h2><p>${esc(c[intent+'Note'])}</p></div><span aria-hidden="true">↗</span></a>`).join('')}</div></section>`;
}

export function discoverySpread(ctx, {media, text, catalogError}) {
  const {c,language} = ctx, r = referenceCopy[ctx.ui];
  const feature = media.find(x=>x.kind==='video') || media[0], story = text[0];
  const at = id=>link('encounter',{id});
  return `${editorialIntro(ctx,{title:r.invitation,note:r.welcome,state:'discovery',eyebrow:r.fieldNote})}
    <nav class="wayfinding" aria-label="${esc(r.browseAll)}">
      <a href="${link('practice',{intent:'reading'})}">${entryIcon('book')}<span>${esc(r.goRead)}</span><span aria-hidden="true">↗</span></a>
      <a href="${link('practice',{intent:'follow'})}">${entryIcon('sound')}<span>${esc(r.goListen)}</span><span aria-hidden="true">↗</span></a>
      <a href="${link('practice',{intent:'speaking'})}">${entryIcon('voice')}<span>${esc(r.goSpeak)}</span><span aria-hidden="true">↗</span></a>
    </nav>
    <section class="editorial-spread" aria-label="${esc(r.featured)}">
      ${feature ? `<article class="feature-window"><a class="feature-image" href="${at(feature.id)}" aria-label="${esc(feature.title)}">${art(feature)}<span class="play-disc" aria-hidden="true">▶</span>${Number(feature.duration_ms)>0?`<span class="duration">${duration(feature.duration_ms)}</span>`:''}</a><div class="feature-caption"><small>${esc(r.featured)} · ${esc(feature.level || c.audio)}</small><h2 lang="${language}"><a href="${at(feature.id)}">${esc(feature.title)} ↗</a></h2><p>${esc(feature.description || '')}</p><span class="byline">${esc(origin(feature,c))} · ${esc(feature.source?.creator || '')}</span></div></article>` : `<section class="feature-window">${catalogError}<h2>${esc(c.noCatalog)}</h2></section>`}
      <article class="reading-window"><small>${esc(r.readNext)}</small><a href="${at(story.id)}"><div class="reading-window-art">${art(story)}</div><h2 lang="${language}">${esc(story.title)} ↗</h2><p lang="${language}">${esc(story.subtitle)}</p></a><span class="byline">${esc(origin(story,c))}</span></article>
    </section>
    ${continuationShelf(ctx,2)}
    <section class="studio-spread" aria-label="${esc(r.studio)}"><article class="practice-poster"><small>${esc(r.practice)}</small><h2>${esc(r.practiceInvite)}</h2><p>${esc(r.practiceDetail)}</p><a class="primary" href="${link('practice')}">${esc(c.practice)} →</a>${scene('focus',{size:'medium'})}</article><article class="writing-poster"><small>${esc(r.writing)}</small><h2>${esc(r.writingInvite)}</h2><p>${esc(r.writingDetail)}</p><a class="outline" href="${link('expression')}">${esc(c.writingName)} →</a>${scene('creating',{size:'medium'})}</article></section>
    <section class="story-walk"><div class="section-head"><div><small>${esc(r.fieldNote)}</small><h2>${esc(c.stories)}</h2></div><a class="quiet" href="${link('practice',{intent:'reading'})}">${esc(r.reading)} ↗</a></div>${text.slice(1).map((x,i)=>`<a class="story-path" href="${at(x.id)}"><span class="path-number" aria-hidden="true">0${i+1}</span><div><h3 lang="${language}">${esc(x.title)}</h3><p lang="${language}">${esc(x.subtitle)}</p><small>${esc(origin(x,c))}</small></div><span aria-hidden="true">↗</span></a>`).join('')}</section>
    <section class="bring-invitation"><span aria-hidden="true">＋</span><div><h2>${esc(c.bring)}</h2><p>${esc(c.emptyNote)}</p></div><button class="outline" data-bring>${esc(c.importAction)} ↗</button></section>`;
}
