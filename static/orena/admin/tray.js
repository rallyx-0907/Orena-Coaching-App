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

/* One clock for the whole console. The shell polls on `POLL_MS` and a finished
   job leaves after `SETTLED_MS`; both live here so the tray's behaviour is one
   number each rather than a constant per module that can drift apart. */
export const POLL_MS = 5000;
export const SETTLED_MS = 60000;
/* Every stage the engine reports, in order, so progress is the engine's own
   position rather than a number this file invents. */
const STAGES = ['queued', 'fetching', 'normalizing', 'deduplicating', 'analyzing', 'building_candidate', 'done'];

const jobs = new Map();
const listeners = new Set();

function changed() {
  for (const listener of listeners) listener();
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function watch({ id, label }) {
  if (!id) return;
  jobs.set(id, { id, label: label || '', status: 'queued', stage: 'queued', error: '', settledAt: 0 });
  changed();
}

export function items() {
  return [...jobs.values()];
}

export function inFlight() {
  return items().filter((job) => job.status !== 'completed' && job.status !== 'failed').length;
}

/* Whether the tray still has work to do - which is not the same as work in
   flight. A finished job is still the tray's business until its settle window
   closes, and the clock has to keep running for it to ever leave. Stopping at
   `inFlight() === 0` is why the tray used to sit there forever showing a job
   that had ended. */
export function ticking() {
  return items().length > 0;
}

export function forget(id) {
  if (jobs.delete(id)) changed();
}

export function clear() {
  if (!jobs.size) return;
  jobs.clear();
  changed();
}

/* One pass over what is being watched. Errors are swallowed per job: a tray
   that cannot reach one job still tells the truth about the others, and the
   console has its own error surfaces for a server that is down. */
export async function refresh(api, now = Date.now()) {
  const watched = items();
  if (!watched.length) return false;
  let moved = false;
  await Promise.all(watched.map(async (job) => {
    if (job.settledAt && now - job.settledAt > SETTLED_MS) {
      jobs.delete(job.id);
      moved = true;
      return;
    }
    if (job.settledAt) return;
    let latest = null;
    try {
      latest = await api.readingJob(job.id);
    } catch {
      return;
    }
    if (!latest) return;
    const settled = latest.status === 'completed' || latest.status === 'failed';
    const next = {
      ...job,
      status: latest.status,
      stage: latest.stage,
      error: latest.last_error_code || '',
      resultKind: latest.result_kind || '',
      settledAt: settled ? now : 0,
    };
    if (next.status !== job.status || next.stage !== job.stage) moved = true;
    jobs.set(job.id, next);
  }));
  if (moved) changed();
  return moved;
}

export function progress(job) {
  const reached = STAGES.indexOf(job.stage);
  if (job.status === 'completed') return 100;
  if (job.status === 'failed') return 100;
  return reached <= 0 ? 8 : Math.round((reached / (STAGES.length - 1)) * 100);
}

function tone(job) {
  if (job.status === 'failed') return 'bad';
  if (job.status === 'completed') return 'ok';
  return 'info';
}

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
