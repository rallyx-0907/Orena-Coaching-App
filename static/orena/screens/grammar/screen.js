/* Frame "Grammar Library" (pinned design, frame 44; route "grammarlib"). A browsing place (Design
   Contract rule 47): shell drawn, rail/tab bar present.

   Data: the grammar content contract's catalogue projection for the learning language, through
   the one seam product/grammar-source.js (D-100). No API exists yet, so the catalogue is empty and
   the frame draws its heading and the design's empty state (kit/states.js).

   Rule 50: the frame's subtitle under the "Grammar" heading ("Concepts grouped by what matters
   for you right now.") only restates the group headings below it and is dropped. See model.js for
   what each card draws and what is left out for want of learner state. */
import { html, mount } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { pageHeader, listRow } from '../../kit/components.js';
import { langSpan } from '../../kit/lang.js';
import { emptyMarkup } from '../../kit/states.js';
import { shellCopy as shell } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { t } from './copy.js';
import { grammarCatalog } from '../../product/grammar-source.js';
import { buildLibraryGroups } from './model.js';
import { hanziMarkup } from './hanzi.js';

function levelTile(text) {
  return html`<span class="s-grammar__tile">${text}</span>`;
}

function cardTitle(item) {
  return langSpan(item.lang === 'zh' ? hanziMarkup(item.title, item.titlePinyin) : item.title, item.lang);
}

export default async function grammarLibrary(element, ctx) {
  await useStyles('screens/grammar/grammar.css');
  const target = ctx.context.language === 'zh' ? 'zh' : 'en';
  const rows = await grammarCatalog(target);
  if (!ctx.isCurrent()) return;
  const groups = buildLibraryGroups(rows, languages().support, t);

  mount(
    element,
    html`<div class="s-grammar">
      ${pageHeader({ back: { label: shell('back'), dataset: { back: '1' } }, title: t('title') })}
      ${
        groups.length
          ? groups.map(
              (group) => html`<div class="s-grammar__group">
                <div class="s-grammar__ghead">
                  <h2 class="s-grammar__gname">${group.heading}</h2>
                  <span class="s-grammar__ghint">${t.plural('topics', group.topics)}</span>
                </div>
                <div class="s-grammar__grid">
                  ${group.items.map((item) =>
                    listRow({
                      radius: 20,
                      pad: '16px',
                      leading: levelTile(item.tile),
                      title: cardTitle(item),
                      titleLineHeight: 20,
                      sub: item.note,
                      dataset: { open: item.id },
                    }),
                  )}
                </div>
              </div>`,
            )
          : emptyMarkup({ text: t('empty'), iconName: 'inbox' })
      }
    </div>`,
  );

  element.querySelector('[data-back]')?.addEventListener('click', () => ctx.back());
  element.querySelector('.s-grammar')?.addEventListener('click', (event) => {
    const target = event.target.closest('[data-open]');
    if (!target) return;
    ctx.go(ctx.href('gconcept', { id: target.dataset.open }));
  });
}
