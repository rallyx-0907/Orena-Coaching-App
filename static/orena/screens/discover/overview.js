/* The All tab's markup (D-16V): four sections, each kit's section heading with its "See all" and a
   row of the very cards the section's own tab draws. DOM-free (markup in, markup out) so
   scripts/test_orena_screen_discover.mjs can render it; screen.js supplies `card` (entry -> card
   markup, the one function every tab uses) and the translate function.

   The Imported section is always drawn. With nothing imported (`section.empty`) its row is one
   call to action - a short line and the page's own "+ Import" control, in the same VIP look
   (discover.css `s-discover__vip`) - and screen.js wires it to the same import flow. */
import { html } from '../../kit/html.js';
import { sectionHead } from '../../kit/components.js';

// Each section's heading is its tab's own label; `seeAll` is the button the screen listens to.
const HEADING_KEY = Object.freeze({ listen: 'tabListen', read: 'tabRead', collections: 'tabCollections', imported: 'tabImported' });

export function overviewMarkup(sections, { card, t }) {
  return html`<div class="s-discover__sections">${sections.map(
    (section) => html`<section class="s-discover__section" data-section="${section.tab}">
      ${sectionHead({ title: t(HEADING_KEY[section.tab]), action: section.empty ? null : { label: t('seeAll'), dataset: { 'see-all': section.tab } } })}
      ${section.empty
        ? html`<div class="o-card s-discover__importcta"><span class="s-discover__importcta-text">${t('importCta')}</span><button type="button" class="o-btn o-btn--primary s-discover__vip" data-import-cta>+ ${t('importAction')}</button></div>`
        : html`<div class="s-discover__grid s-discover__grid--overview">${section.entries.map(card)}</div>`}
    </section>`,
  )}</div>`;
}
