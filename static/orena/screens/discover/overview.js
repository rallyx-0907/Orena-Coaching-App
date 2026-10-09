/* The All tab's markup (D-16V): four sections, each kit's section heading with its "See all" and a
   row of the very cards the section's own tab draws. DOM-free (markup in, markup out) so
   scripts/test_orena_screen_discover.mjs can render it; screen.js supplies `card` (entry -> card
   markup, the one function every tab uses) and the translate function. */
import { html } from '../../kit/html.js';
import { sectionHead } from '../../kit/components.js';

// Each section's heading is its tab's own label; `seeAll` is the button the screen listens to.
const HEADING_KEY = Object.freeze({ read: 'tabRead', listen: 'tabListen', collections: 'tabCollections', imported: 'tabImported' });

export function overviewMarkup(sections, { card, t }) {
  return html`<div class="s-discover__sections">${sections.map(
    (section) => html`<section class="s-discover__section" data-section="${section.tab}">
      ${sectionHead({ title: t(HEADING_KEY[section.tab]), action: { label: t('seeAll'), dataset: { 'see-all': section.tab } } })}
      <div class="s-discover__grid s-discover__grid--overview">${section.entries.map(card)}</div>
    </section>`,
  )}</div>`;
}
