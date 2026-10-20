/* A Plus article opened by a Free learner (D-248 §4, G8): the server answered 403 `plan_required` with the article's
   preview, and the Reader shows it instead of an error. Owner's rule: the title, the cover and the first paragraph are
   never blurred or hidden. Below them sits a soft end-of-preview block, the Coming-soon frame's card (`.o-coming__card`:
   the lock in a well, the plan's tag, one line) with one button that opens the light upgrade sheet. No fade-out, no
   blur, no gradient.

   The Reader's own frame parts are reused as they are (its toolbar row with the back button and title block, its scroll
   region, its article column and paragraph type), so the preview reads as the start of the article it is. A learning
   workspace never scrolls as a page (rule 49): only the Reader's scroll region does. The end-of-preview card sits
   below that region, as the workspace's fixed bottom row (like the toolbar above it), so Unlock is in the viewport
   at 360x740 however long the title or paragraph is (#472); the preview scrolls in its region above it. Content Detail shows the same
   view for the same refusal, filling its column the same way (reader.css `.o-screen:has(> .s-reader-locked)`, #474). The server has already counted `locked_view` where it refused. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { langAttr } from '../../kit/lang.js';
import { planTag } from '../../kit/components.js';
import { shellCopy, planName } from '../../copy/shell.js';
import { imageOf } from '../../product/provenance.js';
import { readReaderSettings } from '../../product/reader-settings.js';
import { t as planT } from '../plan/copy.js';
import { openUpgradeSheet } from '../plan/upgrade-sheet.js';
import { readerSizePx } from './model.js';

export function lockedPreviewMarkup({ preview = {}, tier = 'plus', sizePx = null } = {}) {
  const plan = planName({ id: tier }) || tier;
  const lang = langAttr(String(preview.language || ''));
  const image = imageOf(preview);
  const title = String(preview.title || '');
  const paragraph = String(preview.first_paragraph || '');
  return html`<div class="s-reader s-reader-locked">
    <div class="s-reader__top"><div class="s-reader__toolbar">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-locked-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-reader__titleblock"><div class="s-reader__title" lang="${lang}">${title}</div></div>
    </div></div>
    <div class="s-reader__scroll" data-scroll-region>
      <div class="s-reader__grid">
        <article class="s-reader__article"${sizePx ? raw(` style="font-size:${Number(sizePx)}px"`) : ''}>
          ${image ? html`<figure class="s-reader-locked__figure"><span class="s-reader-locked__cover" role="img" aria-label="${image.alt || title}" style="background-image:${image.cssUrl}"></span>${image.credit ? html`<figcaption class="s-reader__meta">${image.credit}</figcaption>` : ''}</figure>` : ''}
          <h1 class="s-reader__heading s-reader-locked__title" lang="${lang}">${title}</h1>
          ${paragraph ? html`<p class="s-reader__paragraph" lang="${lang}"${lang === 'zh' ? raw(' data-tl="zh"') : ''}>${paragraph}</p>` : ''}
        </article>
      </div>
    </div>
    <div class="s-reader-locked__foot">
      <div class="o-coming__card s-reader-locked__end">
        <div class="o-coming__icon">${raw(icon('lock', { size: 28 }))}</div>
        ${planTag(plan)}
        <div class="s-reader-locked__end-title">${planT('previewEnd', { plan })}</div>
        <button type="button" class="o-btn o-btn--primary" data-locked-unlock>${planT('previewUnlock')}</button>
      </div>
    </div>
  </div>`;
}

/* Draw the locked preview into the room's element. `refusal` is kit/access.js `planRequired(error)`. */
export async function mountLockedPreview(element, ctx, refusal, { source = 'reader' } = {}) {
  await Promise.all(['screens/reader/reader.css', 'screens/coming/coming.css'].map((sheet) => useStyles(sheet)));
  if (ctx.isCurrent && !ctx.isCurrent()) return undefined;
  const tier = refusal?.requiredTier || 'plus';
  let sizePx = null;
  try {
    sizePx = readerSizePx(readReaderSettings().size);
  } catch {
    sizePx = null;
  }
  mount(element, lockedPreviewMarkup({ preview: refusal?.preview || {}, tier, sizePx }));
  if (refusal?.preview?.title) ctx.setCrumb?.(String(refusal.preview.title));
  element.querySelector('[data-locked-back]')?.addEventListener('click', () => ctx.back());
  element.querySelector('[data-locked-unlock]')?.addEventListener('click', () => {
    void openUpgradeSheet({ source, kind: 'reading', tier, go: (to) => ctx.go(to) });
  });
  return undefined;
}
