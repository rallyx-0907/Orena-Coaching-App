/* The legal pages (completion plan item 5): Terms of Use, Privacy Policy, Refund Policy.

   The design draws no legal page; by the human's decision (D-128) they are built from existing kit
   pieces only - the page header (o-h1 + o-sub) and the section heading - with the drafts' text as data
   (legal/content.js, generated from docs/legal/DRAFT_*.md). They are read before signing in, so main.js
   draws them before it asks who the learner is, with no learner frame. They are linked from nowhere
   until the human approves the text.

   Language: the interface language (or `?lang=` on the address, for review). English and Vietnamese
   have their own text; Chinese reads the English text, marked lang="en", until a Chinese text is
   approved. */
import { html, mount } from '../kit/html.js';
import { pageHeader, sectionHead } from '../kit/components.js';
import { useStyles } from '../kit/styles.js';
import { LOCALES, languages, setLanguages } from '../copy/index.js';
import { legalCopy as t } from '../copy/legal.js';
import { LEGAL } from './content.js';

export const LEGAL_PAGES = Object.freeze(Object.keys(LEGAL));

/* "#/legal/terms?lang=vi" -> { page: 'terms', lang: 'vi' }; anything else -> null. */
export function legalAddress(hash = '') {
  const [pathPart, queryPart = ''] = String(hash).replace(/^#\/?/, '').split('?');
  const found = /^legal\/(\w+)\/?$/.exec(pathPart);
  if (!found || !LEGAL_PAGES.includes(found[1])) return null;
  const lang = new URLSearchParams(queryPart).get('lang') || '';
  return { page: found[1], lang: LOCALES.includes(lang) ? lang : '' };
}

function segments(list) {
  return list.map((part) => {
    if (part.b) return html`<strong>${part.t}</strong>`;
    if (part.i) return html`<em>${part.t}</em>`;
    if (part.c) return html`<code>${part.t}</code>`;
    return part.t;
  });
}

function block(item) {
  if (item.p) return html`<p class="o-legal__p">${segments(item.p)}</p>`;
  if (item.ul) return html`<ul class="o-legal__list">${item.ul.map((entry) => html`<li>${segments(entry)}</li>`)}</ul>`;
  if (item.table) {
    return html`<div class="o-legal__table"><table>
      <thead><tr>${item.table.head.map((cell) => html`<th scope="col">${segments(cell)}</th>`)}</tr></thead>
      <tbody>${item.table.rows.map((row) => html`<tr>${row.map((cell) => html`<td>${segments(cell)}</td>`)}</tr>`)}</tbody>
    </table></div>`;
  }
  return '';
}

/* The page's markup for one document in one interface language. */
export function legalMarkup(page, ui) {
  const own = ui === 'vi' ? 'vi' : 'en';
  const doc = LEGAL[page][own];
  const meta = ui === 'zh' ? t('draftEnglish') : t('draft');
  return html`<main class="o-legal" data-legal="${page}">
    ${pageHeader({ title: t(page), meta })}
    <article class="o-legal__body" lang="${own}">
      ${doc.intro.map(block)}
      ${doc.sections.map((section) => html`<section class="o-legal__section">${sectionHead({ title: section.heading })}${section.blocks.map(block)}</section>`)}
    </article>
  </main>`;
}

export async function renderLegal(element, address) {
  if (address.lang) setLanguages({ ui: address.lang });
  await useStyles('legal/legal.css');
  const ui = languages().ui;
  document.title = `${t(address.page)} · Orena`;
  mount(element, legalMarkup(address.page, ui));
  window.scrollTo?.(0, 0);
}
