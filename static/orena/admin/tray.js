/* The progress tray, study 04.

   The design's rule is that nothing waits in a modal: submitting hands the
   work to the engine, the form goes away, and what is in flight follows the
   operator around the console until it is done. So the tray cannot live inside
   the Reading view that started it - leaving that view is exactly when an
   operator wants to keep watching.

   This module is the tray's memory. It holds what was submitted, not what the
   server thinks: the label is the title the operator typed, because the job
   list does not carry it and "ingest_text · 9395779c" is not what they
   submitted. The shell renders it and owns the one interval that refreshes it.

   A finished job stays visible for `SETTLED_MS` so its outcome can be read,
   then leaves. The tray is about work in flight; Imports is the history. */
import { esc, fill, mono } from './format.js';
import {
  POLL_MS, SETTLED_MS, subscribe, watch, items, inFlight, ticking, forget, clear, refresh, progress, jobTone,
} from '../capabilities/admin-tray.js';

/* The tray's memory and its clock moved to capabilities/admin-tray.js, shared with the new UI's
   Admin (D-101 E); they are re-exported so every console module keeps its import. This file draws. */
export { POLL_MS, SETTLED_MS, subscribe, watch, items, inFlight, ticking, forget, clear, refresh, progress };

const tone = jobTone;

function message(job, t) {
  if (job.status === 'failed') return t[`error_${job.error}`] || t[`readingError_${job.error}`] || t.readingTrayFailed;
  if (job.status === 'completed') {
    return job.resultKind === 'duplicate' ? t.readingSubmitDuplicate : t.readingTrayDone;
  }
  return t[`readingStage_${job.stage}`] || t.readingTrayWorking;
}

/* The tray as the design draws it: a count, the way to the full list, and one
   row per job carrying its name, its state, how far it has got and what that
   means. Collapsed state is the caller's - the shell keeps it, so it survives
   a section change like everything else here. */
export function trayView(t, { href, collapsed = false } = {}) {
  const watched = items();
  if (!watched.length) return '';
  const rows = watched.map((job) => `<li class="ac-tray__job" data-state="${esc(job.status)}">
      <span class="ac-tray__line"><span class="ac-tray__name">${job.label ? esc(job.label) : mono(job.id.slice(0, 8))}</span><span class="ac-chip" data-tone="${esc(tone(job))}">${esc(t[`readingJobStatus_${job.status}`] || job.status)}</span></span>
      <span class="ac-tray__bar"><span class="ac-tray__fill" style="--at:${progress(job)}%" data-tone="${esc(tone(job))}"></span></span>
      <span class="ac-tray__note">${esc(message(job, t))}</span>
    </li>`).join('');
  return `<aside class="ac-tray" role="status" aria-live="polite" data-collapsed="${collapsed ? '1' : '0'}">
    <div class="ac-tray__head"><strong>${esc(inFlight() ? fill(t.readingTrayCount, { count: inFlight() }) : t.readingTraySettled)}</strong>
      <a class="ac-link" href="${esc(href('imports'))}">${esc(t.readingTrayOpenImports)}</a>
      <button type="button" class="ac-button ac-button--icon" data-ac-tray-toggle aria-expanded="${collapsed ? 'false' : 'true'}" aria-label="${esc(collapsed ? t.readingTrayExpand : t.readingTrayCollapse)}">${collapsed ? '▾' : '▴'}</button>
    </div>
    <ul class="ac-tray__jobs">${rows}</ul>
  </aside>`;
}
