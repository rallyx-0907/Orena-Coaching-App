import { esc, dialog } from './html.js';
import { openUnderstanding } from './understanding.js';
import { applyRevision } from '../product/revision.js';

// Observation -> reason -> learner experiment -> next submitted revision.
// This teaches how feedback becomes an action without a second writing engine.
export function bindRevisionWorkbench(
  root,
  ctx,
  { issues, reviewedText, draft, id, title },
) {
  const { c, memory, language } = ctx;
  root.querySelectorAll('[data-try-revision]').forEach(
    (button) =>
      (button.onclick = () => {
        const issue = issues[Number(button.dataset.tryRevision)];
        if (!issue) return;
        const sheet = dialog({
          title: c.revisionTry,
          body: `<p class="meta">${esc(c.revisionTryNote)}</p><blockquote lang="${language}">${esc(issue.quote)}</blockquote><p>${esc(issue.why || '')}</p><label for="revisionExperiment">${esc(c.revisionYourVersion)}</label><textarea id="revisionExperiment" maxlength="12000" rows="3" lang="${language}">${esc(issue.quote)}</textarea><div class="button-row"><button class="outline" data-experiment>${esc(c.revisionExplore)} ↗</button><button class="primary" data-apply-revision>${esc(c.revisionUse)}</button></div><p role="status" data-revision-state></p>`,
        });
        const input = sheet.querySelector('textarea');
        sheet.querySelector('[data-experiment]').onclick = () => {
          if (!input.value.trim()) return;
          const offset = Math.max(0, reviewedText.indexOf(issue.quote) - 400);
          openUnderstanding(ctx, {
            selection: input.value.slice(0, 1600),
            context: reviewedText.slice(offset, offset + 2400),
            title,
            question: `${c.revisionQuestion} ${issue.quote}`.slice(0, 400),
          });
        };
        sheet.querySelector('[data-apply-revision]').onclick = () => {
          const changed = applyRevision(draft.value, issue.quote, input.value);
          if (changed === null) {
            sheet.querySelector('[data-revision-state]').textContent =
              c.revisionAmbiguous;
            return;
          }
          if (changed !== draft.value)
            memory.recordRevision(id, { text: draft.value });
          draft.value = changed;
          draft.dispatchEvent(new Event('input', { bubbles: true }));
          sheet.close();
          draft.focus();
        };
      }),
  );
}
