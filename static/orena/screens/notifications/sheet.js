/* Notifications overlay (pinned design frame 59, opened from the shell bell). There is no
   notification backend - no feed, no per-item timestamp, no server read/unread flag - so this sheet
   is built only over the two real signals the shell already carries (Design Contract rule 40):
   words due for review (shell/context.js's `due`) and the learner's own unfinished work
   (product/memory.js's device-memory `continuation[]`), or the empty state when neither has
   anything to say. Recorded as a backend gap (SCRATCH/reports/sheets.md), not resolved by
   inventing a feed.

   Dropped, and why: "Mark all read" and the per-row unread dot (no real read/unread state to act
   on - rule 40); the row's own trailing chevron (the frame draws none on this screen). The frame's
   row is a three-line shape - kind + when / title / sub (59-Notifications.html) - and the "· when"
   half is dropped (no timestamp exists for a continuation entry or for the due count); the kind
   itself is real and stable, so it fills kit/components.js#listRow's own `kind` slot (D-091 kit
   fidelity pass) rather than being folded into the sub line as a workaround. */
import { openSheet, fillSheet } from '../../kit/overlay.js';
import { html, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { listRow } from '../../kit/components.js';
import { langSpan } from '../../kit/lang.js';
import { emptyMarkup } from '../../kit/states.js';
import { useStyles } from '../../kit/styles.js';
import { shellCopy as s } from '../../copy/shell.js';
import { href } from '../../shell/routes.js';
import { t } from './copy.js';
import { notificationRows } from './model.js';

const KIND_LABEL = { reading: 'continueReadingKind', listening: 'continueListeningKind', writing: 'continueWritingKind' };

export async function openNotifications(ctx = {}) {
  await useStyles('screens/notifications/notifications.css');
  const context = ctx.context || {};
  const memory = context.memory;
  const rows = notificationRows({ due: context.due || 0, continuation: memory?.value?.continuation || [] });

  const navigate = (routeId, params) => {
    const target = href(routeId, params);
    if (typeof ctx.go === 'function') ctx.go(target);
    else window.location.hash = target;
  };

  function rowMarkup(row) {
    if (row.type === 'due') {
      // The frame's own due-analog row's sub is "All from <source>" (orena-script.js's own sample
      // data) - a per-word source breakdown this build has no source for (rule 40), so the row
      // keeps its real kind + title and leaves sub empty rather than inventing one.
      const title = t.plural('dueTitle', row.due);
      return listRow({ variant: 'outline', pad: '14px 18px', kind: t('reviewKind'), title, dataset: { row: 'due' } });
    }
    const sub = row.percent != null ? t('percentComplete', { n: row.percent }) : '';
    // languages-5 / finding A: `row.title` is the real content this continuation entry resumes -
    // always in the learner's active learning language (kit/lang.js's "the learner's learning
    // language the screen already read" source; no per-entry field exists on device memory).
    return listRow({ variant: 'outline', pad: '14px 18px', kind: t(KIND_LABEL[row.kind]), title: langSpan(row.title, context.language), sub, dataset: { row: 'continue', route: row.routeId, id: row.id } });
  }

  function bodyMarkup() {
    if (!rows.length) return emptyMarkup({ text: t('empty'), iconName: 'inbox' });
    return html`${rows.map(rowMarkup)}`;
  }

  const markup = html`<div class="o-sheet__head">
    <div>
      <div class="o-sheet__title">${s('notifications')}</div>
      <div class="s-notifications__sub">${t('subtitle')}</div>
    </div>
    <button type="button" class="o-iconbtn o-iconbtn--close" data-sheet-close aria-label="${s('close')}">${raw(icon('x', { size: 17 }))}</button>
  </div>
  <div class="o-sheet__body s-notifications__body">${bodyMarkup()}</div>`;

  const handle = openSheet({
    label: s('notifications'),
    className: 's-notifications',
    render(sheet, sheetHandle) {
      fillSheet(sheet, sheetHandle, markup);
      sheet.querySelector('[data-row="due"]')?.addEventListener('click', () => {
        sheetHandle.close();
        navigate('review');
      });
      for (const el of sheet.querySelectorAll('[data-row="continue"]')) {
        el.addEventListener('click', () => {
          sheetHandle.close();
          navigate(el.dataset.route, { id: el.dataset.id });
        });
      }
    },
  });
  return handle;
}
