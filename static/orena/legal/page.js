/* The legal pages (completion plan item 5): Refund Policy in the app; Terms and Privacy are the public pages.

   The design draws no legal page; by the human's decision (D-128) they are built from existing kit
   pieces only - the page header (o-h1 + o-sub) and the section heading - with the drafts' text as data
   (legal/content.js, generated from docs/legal/DRAFT_*.md). They are read before signing in, so main.js
   draws them before it asks who the learner is, with no learner frame.

   Language: legal documents exist in English only (D-238). Every interface language reads the English
   text, marked lang="en"; `?lang=` on the address is tolerated and ignored. */
import { html, mount } from '../kit/html.js';
import { pageHeader, sectionHead } from '../kit/components.js';
import { useStyles } from '../kit/styles.js';
import { LEGAL } from './content.js';

export const LEGAL_PAGES = Object.freeze(Object.keys(LEGAL));
const TITLES = Object.freeze({ terms: 'Terms of Use', privacy: 'Privacy Policy', refund: 'Refund Policy' });
const DRAFT_LINE = 'Draft, awaiting approval';

/* "#/legal/terms?lang=vi" -> { page: 'terms' } (the language is ignored); anything else -> null. */
export function legalAddress(hash = '') {
  const [pathPart] = String(hash).replace(/^#\/?/, '').split('?');
  const found = /^legal\/(\w+)\/?$/.exec(pathPart);
  if (!found || !LEGAL_PAGES.includes(found[1])) return null;
  return { page: found[1] };
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/* The drafts' "Last updated: [DATE]." is the deploy-stamped effective date (GET /api/platform/languages
   `legal_effective_date`, the value the public pages show). With no date the whole sentence is left out: a
   placeholder never reaches a learner. */
export function datedText(text, isoDate) {
  const found = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(isoDate || ''));
  const label = found && MONTHS[Number(found[2]) - 1] ? `${MONTHS[Number(found[2]) - 1]} ${Number(found[3])}, ${found[1]}` : null;
  return String(text).replace(/Last updated: \[DATE\]\. ?/g, label ? `Last updated: ${label}. ` : '');
}

let effectiveDate = null;

function segments(list) {
  return list.map((part) => {
    if (part.t && !part.b && !part.i && !part.c) return datedText(part.t, effectiveDate);
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

/* The page's markup for one document: English, whatever the interface language. */
export function legalMarkup(page, _ui, isoDate = null) {
  effectiveDate = isoDate;
  const doc = LEGAL[page];
  return html`<main class="o-legal" data-legal="${page}">
    ${pageHeader({ title: TITLES[page], meta: DRAFT_LINE })}
    <article class="o-legal__body" lang="en">
      ${doc.intro.map(block)}
      ${doc.sections.map((section) => html`<section class="o-legal__section">${sectionHead({ title: section.heading })}${section.blocks.map(block)}</section>`)}
    </article>
  </main>`;
}

export async function renderLegal(element, address) {
  await useStyles('legal/legal.css');
  document.title = `${TITLES[address.page]} · Orena`;
  let isoDate = null;
  try {
    const response = await fetch('/api/platform/languages', { headers: { Accept: 'application/json' } });
    isoDate = response.ok ? (await response.json()).legal_effective_date || null : null;
  } catch { /* no date: the date sentence is left out */ }
  mount(element, legalMarkup(address.page, 'en', isoDate));
  window.scrollTo?.(0, 0);
}
