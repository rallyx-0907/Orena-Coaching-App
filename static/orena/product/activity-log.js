/* Pure day-grouping and time-windowing for a learner's own activity log. Moved out of
   ui/history.js (D-091 migration) so it can be node-tested without DOM/copy coupling and reused
   by the new learner UI's Progress screen (screens/progress/model.js) for the same "History" tab
   the design nests inside Progress. ui/history.js keeps calling the four APIs itself and still
   reads and formats the result; only the pure grouping moved here. No copy, no markup, no API
   calls - callers pass already-fetched `{ at, ... }` items. */

/* Items with a parseable `at` no older than `windowDays`, relative to `now` (ms epoch or Date). */
export function withinWindow(items, windowDays, now = Date.now()) {
  const nowMs = typeof now === 'number' ? now : now.getTime();
  const since = nowMs - windowDays * 86400000;
  return items.filter((item) => item.at && Date.parse(item.at) >= since);
}

/* Most recent first. Items with an unparseable `at` sort last (NaN comparisons push them down). */
export function sortByRecency(items) {
  return [...items].sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
}

/* 'today' | 'yesterday' | an ISO 'YYYY-MM-DD' for anything older, relative to `now`. The caller
   turns the key into a localized label (Intl.DateTimeFormat); this module holds no locale/copy. */
export function dayBucket(at, now = new Date()) {
  const date = new Date(at);
  const today = now instanceof Date ? now : new Date(now);
  if (date.toDateString() === today.toDateString()) return 'today';
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return 'yesterday';
  return date.toISOString().slice(0, 10);
}

/* Items already sorted most-recent-first, grouped into consecutive day buckets (each `{ key,
   items }`, `key` from dayBucket). Grouping only merges adjacent same-day items, so callers must
   sort first (sortByRecency) - it does not re-sort. */
export function groupByDay(items, now = new Date()) {
  const groups = [];
  let current = null;
  for (const item of items) {
    const key = dayBucket(item.at, now);
    if (!current || current.key !== key) {
      current = { key, items: [] };
      groups.push(current);
    }
    current.items.push(item);
  }
  return groups;
}
