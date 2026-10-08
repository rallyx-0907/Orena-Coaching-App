/* The Platform Admin's progress tray: the memory of what was submitted and how far it has got.

   The design's rule is that nothing waits in a modal: submitting hands the work to the engine, the
   form goes away, and what is in flight follows the operator around the console until it is done.
   So the tray cannot live inside the view that started it. This module holds what was submitted,
   not what the server thinks: the label is the title the operator typed, because the job list does
   not carry it and "ingest_text · 9395779c" is not what they submitted.

   Shared by the old console (admin/tray.js re-exports it and draws it) and the new UI's Admin
   (screens/admin/tray.js). A finished job stays visible for `SETTLED_MS` so its outcome can be
   read, then leaves. The tray is about work in flight; Imports is the history. */

/* One clock for the whole console. */
export const POLL_MS = 5000;
export const SETTLED_MS = 60000;
/* Every stage the engine reports, in order, so progress is the engine's own position rather than a
   number invented here. */
export const STAGES = ['queued', 'fetching', 'normalizing', 'deduplicating', 'analyzing', 'building_candidate', 'done'];

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

/* Whether the tray still has work to do - which is not the same as work in flight. A finished job
   is still the tray's business until its settle window closes, and the clock has to keep running
   for it to ever leave. */
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

/* One pass over what is being watched. Errors are swallowed per job: a tray that cannot reach one
   job still tells the truth about the others. */
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
      articleId: latest.result_article_id || '',
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

/* The tone of a job: what a state colours as. */
export function jobTone(job) {
  if (job.status === 'failed') return 'bad';
  if (job.status === 'completed') return 'ok';
  return 'info';
}
