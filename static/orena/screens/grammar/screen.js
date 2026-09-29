/* Frame "Grammar Library" (pinned design, frame 44; route "grammarlib"). A browsing place (Design
   Contract rule 47): shell drawn, rail/tab bar present.

   Rule 50: the frame's subtitle under the "Grammar" heading ("Concepts grouped by what matters
   for you right now.") only restates the group headings immediately below it and is dropped.
   Rule 40 / grouping: see model.js's header comment for why the groups are the catalogue's real
   level/family fields rather than the frame's four sample groupings. */
import { html, mount } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { pageHeader, listRow } from '../../kit/components.js';
import { langSpan } from '../../kit/lang.js';
import { emptyMarkup } from '../../kit/states.js';
import { shellCopy as shell } from '../../copy/shell.js';
import { t } from './copy.js';
import { api } from '../../infrastructure/api.js';
import { supportLanguage } from '../../product/languages.js';
import { buildLibraryGroups } from './model.js';

function levelTile(level) {
  return html`<span class="s-grammar__tile">${level}</span>`;
}

function statusTag(item) {
  return html`<span class="${item.completed ? 's-grammar__tag s-grammar__tag--done' : 's-grammar__tag'}">${item.completed ? t('done') : t('open')}</span>`;
}

export default async function grammarLibrary(element, ctx) {
  await useStyles('screens/grammar/grammar.css');
  const context = ctx.context;
  const support = supportLanguage(context.profile);
  const library = await api.grammarLibrary();
  if (!ctx.isCurrent()) return;
  const groups = buildLibraryGroups(library, support, t);

  mount(
    element,
    html`<div class="s-grammar">
      ${pageHeader({ back: { label: shell('back'), dataset: { back: '1' } }, title: t('title') })}
      ${
        groups.length
          ? groups.map(
              (group) => html`<div class="s-grammar__group">
                <div class="s-grammar__ghead">
                  <h2 class="s-grammar__gname">${group.levelName}</h2>
                  <span class="s-grammar__ghint">${t.plural('topics', group.topics, { done: group.completed, total: group.total })}</span>
                </div>
                <div class="s-grammar__grid">
                  ${group.items.map((item) =>
                    listRow({
                      radius: 20,
                      pad: '16px',
                      leading: levelTile(item.level),
                      title: langSpan(item.title, group.titleLang),
                      titleLineHeight: 20,
                      sub: item.note,
                      trailing: statusTag(item),
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
