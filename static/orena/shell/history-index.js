/* Where the current history entry sits among the app's own: each entry the router renders is stamped with an index
   in its history state (`orenaIdx`), the first entry of a tab being 0. In-app Back may call history.back() only when
   the entry has an app entry before it (index > 0); the browser's own Back and Forward, a reload and an address typed
   by hand all leave the stamp (or its absence) telling the truth, which a counter kept in step with go() did not.

   - an entry that already carries a stamp keeps it (Back, Forward, reload, a retry of the same address);
   - the app's own replace keeps the index of the entry it replaces;
   - any other unstamped entry is new, one past the entry before it (a go() push, or a hash the browser pushed);
   - the first entry the page ever renders is 0. */

const KEY = 'orenaIdx';

export const readIndex = (historyState) => (Number.isInteger(historyState?.[KEY]) && historyState[KEY] >= 0 ? historyState[KEY] : null);

/* `previous`: the index of the entry the page showed before this one (null at the first render). */
export function entryIndex({ stamped = null, replaced = false, previous = null } = {}) {
  if (Number.isInteger(stamped) && stamped >= 0) return stamped;
  if (previous === null || previous === undefined) return 0;
  return replaced ? previous : previous + 1;
}

export const withIndex = (historyState, index) => ({ ...(historyState && typeof historyState === 'object' ? historyState : {}), [KEY]: index });

/* In-app Back steps through the browser's history only when an app entry precedes this one. */
export const canStepBack = (index) => Number.isInteger(index) && index > 0;
