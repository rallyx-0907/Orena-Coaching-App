/* Frame "Coming soon" (pinned design, frame 51): a place the design draws whose service Orena does
   not have yet, or a screen of the new UI not built yet during the migration (D-091). It says
   what the place is and nothing more (rule 50): the frame's reviewer note and its sample
   "Would resume at" block are not carried (UI_BACKEND_GAPS N-3). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { shellCopy as t } from '../../copy/shell.js';

export default async function comingSoon(element, ctx) {
  await useStyles('screens/coming/coming.css');
  const key = ctx.params?.key || '';
  const title = key && t.has(key) ? t(key) : t('comingSoon');
  mount(
    element,
    html`<div class="o-coming">
      <button type="button" class="o-iconbtn" data-back aria-label="${t('back')}">${raw(icon('arrow-left', { size: 19 }))}</button>
      <div class="o-coming__card">
        <div class="o-coming__icon">${raw(icon('lock', { size: 28 }))}</div>
        <span class="o-coming__badge">${t('comingSoon')}</span>
        <h1 class="o-coming__title">${title}</h1>
      </div>
    </div>`,
  );
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
}
