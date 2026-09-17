import { esc } from './html.js';
import { scene } from './brand.js';
import { link } from '../product/intent.js';
import { referenceCopy } from './reference.js';
import { entryIcon } from './icons.js';

export function practiceOverview(ctx) {
  const { c } = ctx, r = referenceCopy[ctx.ui];
  const intentions = [
    ['dictation','focus'], ['shadowing','sound'], ['speaking','voice'],
    ['writing','pen'], ['grammar','spark'], ['recall','return'],
  ];
  return `<section class="practice-workbench" aria-label="${esc(r.direct)}"><div class="workbench-note">${scene('focus',{size:'medium'})}<small>${esc(r.direct)}</small><p>${esc(c.practiceContext)}</p></div><div class="practice-options">${intentions.map(([intent,icon],i)=>`<a href="${intent==='writing'?link('expression'):link('practice',{intent})}"><span class="option-number" aria-hidden="true">0${i+1}</span>${entryIcon(icon)}<div><h2>${esc(c[intent+'Name'])}</h2><p>${esc(c[intent+'Note'])}</p></div><span aria-hidden="true">↗</span></a>`).join('')}</div></section>`;
}

function domainCard({ href, icon, label, title = '', language = '' }) {
  return `<a class="discover-domain-card" href="${esc(href)}" aria-label="${esc(label)}"><span class="discover-domain-card__icon">${entryIcon(icon)}</span><span class="discover-domain-card__copy">${title ? `<small>${esc(label)}</small>` : ''}<strong${language ? ` lang="${esc(language)}"` : ''}>${esc(title || label)}</strong></span><span class="discover-domain-card__arrow" aria-hidden="true">↗</span></a>`;
}

/* Discover is a compact map, not four destination pages rendered together.
   The rail stays one row at every width so touch, trackpad and keyboard users
   reveal more destinations without turning the phone page into a long stack. */
export function discoverySpread(ctx, { media = [], text = [], catalogError = '', newContent = [] }) {
  const { c, language } = ctx;
  const r = referenceCopy[ctx.ui];
  const listening = media[0];
  const reading = text[0];
  const newest = newContent.find((item) => item.id !== listening?.id) || newContent[0];
  const cards = [
    domainCard({
      href: link('practice', { intent: 'follow' }),
      icon: 'sound',
      label: r.listening,
      title: listening?.title || r.listening,
      language,
    }),
    domainCard({
      href: link('practice', { intent: 'reading' }),
      icon: 'book',
      label: r.reading,
      title: reading?.title || r.reading,
      language,
    }),
    domainCard({
      href: link('language'),
      icon: 'leaf',
      label: c.vocabularyTitle,
    }),
    domainCard({
      href: newest ? link('encounter', { id: newest.id, intent: 'follow' }) : link('practice', { intent: 'follow' }),
      icon: 'spark',
      label: r.newContent,
      title: newest?.title || r.newContentEmpty,
      language: newest ? language : '',
    }),
  ];
  return `<header class="discover-hero"><h1>${esc(r.discover)}</h1>${scene('discovery',{size:'hero'})}</header>${catalogError ? `<div class="notice" role="alert">${catalogError}</div>` : ''}<nav class="discover-domain-rail" aria-label="${esc(r.discover)}">${cards.join('')}</nav>`;
}
