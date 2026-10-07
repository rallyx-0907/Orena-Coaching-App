/* The Lesson complete modal (frame 63, E3 §7): a centred celebration card, not a route, not a
   docked sheet - the source itself: "No sheet vars used - this is a true centered modal on both
   devices... it's a celebratory interrupt, not a workspace." Reuses `kit/overlay.js#openSheet` for
   the one scrim/Escape/focus-trap/single-overlay-at-a-time machinery every overlay in this app
   already shares (never a second implementation of that), locally overriding the four `--sheet-*`
   device variables it reads so the same shell becomes a full-bleed, centred flex box instead of a
   docked panel - `lesson-complete.css`'s own comment says exactly which properties and why.

   In the source, this modal is reached from exactly two places (a due-review queue finishing, the
   Check Understanding quiz finishing) with a fixed `xp`/`words`/`wordsLabel`/`min` trio - one of
   which (`xp`) is a pure client formula with no backend measurement behind it (E3's own finding).
   The export here generalises that trio to a flat `facts: [{label, value}]` list precisely so a
   caller only ever passes what it actually measured (rule 40) - never a backend-less XP number,
   and never fabricated for a caller this pass did not anticipate. */
import { openSheet } from '../../kit/overlay.js';
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { t } from './copy.js';
import { measuredScore, sanitizeFacts } from './model.js';

function factMarkup(fact) {
  return html`<span class="s-lc__fact"><b>${fact.value}</b> ${fact.label}</span>`;
}

/* `next`, once Continue is pressed and the modal has closed: a route string (`ctx.go(next)`) or a
   callback - either is optional; the source's own Continue is a dismiss only (`lcClose`), so a
   caller that wants nothing further to happen simply omits it. `measured` ({correct, total}, the
   server's own counts) draws the frame's percentage; without it the percentage is not drawn. */
export async function openLessonComplete(ctx = {}, { title, facts, measured, next } = {}) {
  await useStyles('screens/lesson-complete/lesson-complete.css');
  if (ctx.isCurrent && !ctx.isCurrent()) return null;
  const realFacts = sanitizeFacts(facts);
  const score = measuredScore(measured);
  // A 0% is not a celebration: no success mark and no big number, the facts speak (LEX-065).
  const celebrate = score !== 0;
  const handle = openSheet({
    label: `${t('eyebrow')} · ${String(title || '')}`.trim(),
    className: 's-lc',
    scrim: true,
    render(element, sheetHandle) {
      mount(
        element,
        html`<div class="s-lc__card">
          <span class="s-lc__blob"></span>
          ${celebrate ? html`<div class="s-lc__icon">${raw(icon('check', { size: 30, stroke: 2.4 }))}</div>` : ''}
          <div class="s-lc__eyebrow">${t('eyebrow')}</div>
          ${title ? html`<div class="s-lc__title">${title}</div>` : ''}
          ${score == null || score === 0 ? '' : html`<div class="s-lc__score">${score}<span>%</span></div>`}
          ${realFacts.length ? html`<div class="s-lc__facts">${realFacts.map(factMarkup)}</div>` : ''}
          <button type="button" class="o-btn o-btn--primary o-btn--block s-lc__continue" data-continue>${t('continueLabel')}</button>
        </div>`,
      );
      element.querySelector('[data-continue]').addEventListener('click', () => {
        sheetHandle.close();
        if (typeof next === 'function') next();
        else if (typeof next === 'string' && next && typeof ctx.go === 'function') ctx.go(next);
      });
      return null;
    },
  });
  return handle;
}
