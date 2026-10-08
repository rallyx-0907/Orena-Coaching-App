/* DOM-free logic for the Notifications sheet. There is no notification backend (no feed, no
   per-item timestamp, no server read/unread flag - UI_BACKEND_GAPS): this sheet is built only over
   two real signals the shell already has - words due for review (shell/context.js's `due`) and the
   learner's own unfinished work (product/memory.js's device-memory `continuation[]`). Anything the
   design's prototype notification rows show that has no source here (a "writing review ready" line,
   a "new best pronunciation attempt" line, a relative timestamp, a read/unread flag) is left out
   rather than invented (rule 40) - recorded in SCRATCH/reports/sheets.md, not resolved by guessing. */

import { tidyTitle } from '../../product/tidy-title.js';

/* Which new-shell route a continuation entry's id resolves to, by the same id-prefix contract
   product/intent.js and static/orena/ui/encounter.js already use - only the three experiences whose
   old and new routes take the identical `id` (reader, listening, writing) are surfaced; an entry
   this sheet cannot route correctly (speaking, grammar, recall) is left out rather than sent
   somewhere wrong, which is worse than not listing it. */
export function continuationRoute(item) {
  const id = String(item?.id || '');
  if (/^(published|book|article|story|text):/.test(id)) return { routeId: 'reader', kind: 'reading' };
  if (/^(url|upload):/.test(id)) return { routeId: 'listening', kind: 'listening' };
  if (/^(expression|essay):/.test(id)) return { routeId: 'writingDraft', kind: 'writing' };
  return null;
}

/* The rows this sheet can honestly draw, in the design's own order (review first, then unfinished
   work, most recent first - product/memory.js already keeps `continuation` newest-first). `due` and
   `continuation` are exactly shell/context.js#context().due and .memory.value.continuation. */
export function notificationRows({ due = 0, continuation = [] } = {}) {
  const rows = [];
  if (due > 0) rows.push({ type: 'due', due });
  for (const item of continuation) {
    const target = continuationRoute(item);
    if (!target) continue;
    // A finished item is not something to continue (P-12, HP-2): it leaves the list.
    if (item.place && Number.isFinite(item.place.within) && item.place.within >= 100) continue;
    rows.push({
      at: typeof item.at === 'string' ? item.at : '',
      type: 'continue',
      kind: target.kind,
      routeId: target.routeId,
      id: item.id,
      title: tidyTitle(item.title),
      context: tidyTitle(item.context),
      percent: item.place && Number.isFinite(item.place.within) ? item.place.within : null,
    });
  }
  return rows;
}

/* "2 hours ago" in the interface language, for an ISO time the record carries; '' when there is none or it is
   not a time (a device-made place has no time - nothing is invented). */
export function whenLabel(at, locale, now = Date.now()) {
  const stamp = Date.parse(at);
  if (!Number.isFinite(stamp)) return '';
  const seconds = Math.round((stamp - now) / 1000);
  if (seconds > 60) return '';
  const format = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
  for (const [unit, size] of [['day', 86400], ['hour', 3600], ['minute', 60]]) {
    if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit);
  }
  return format.format(0, 'minute');
}
