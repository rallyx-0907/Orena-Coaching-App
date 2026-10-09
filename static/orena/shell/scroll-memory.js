/* Where the learner was on a page, so Back returns to it (the browser's own behaviour for a page that renders
   after its data arrives; the router rebuilds the main column on every address and used to reset it to the top).

   - The place is the address: the hash with its query, so a library filtered to one category is its own place and
     the same library unfiltered is another. Screens keep their choices in the address (history.replaceState), so
     the address at the moment the learner leaves is the one to save under.
   - Only a history traversal (Back, Forward, a reload) restores. Opening a page from a link or a card is a new
     arrival and starts at the top, as before.
   - The positions live in sessionStorage (per tab), newest last, capped, and every storage access is guarded: with
     storage blocked the memory just holds nothing.
   - `restoreScrollWhenReady` is the one DOM part: the page's data may still be arriving when the screen's mount
     returns, so the target is applied as the content grows to it, and given up on when the learner touches the page
     or after a short time. */

const STORAGE_KEY = 'orena.next.scroll';
export const SCROLL_LIMIT = 40;

/* "http://host/#/grammar?cat=x" and "#/grammar?cat=x" are the same place. */
export function addressOf(url) {
  const text = String(url ?? '');
  const at = text.indexOf('#');
  return at < 0 ? '' : text.slice(at);
}

function defaultStorage() {
  try {
    return globalThis.window?.sessionStorage ?? null;
  } catch {
    return null;
  }
}

export function createScrollMemory(storage = defaultStorage(), limit = SCROLL_LIMIT) {
  const entries = new Map();
  try {
    const stored = JSON.parse(storage?.getItem(STORAGE_KEY) || '[]');
    if (Array.isArray(stored)) {
      for (const pair of stored) {
        if (Array.isArray(pair) && typeof pair[0] === 'string' && Number.isFinite(pair[1]) && pair[1] > 0) entries.set(pair[0], pair[1]);
      }
    }
  } catch {
    entries.clear();
  }

  function persist() {
    try {
      storage?.setItem(STORAGE_KEY, JSON.stringify([...entries]));
    } catch {
      /* storage full or blocked: the memory still serves this page's life */
    }
  }

  return {
    /* A position of 0 is the top: nothing to remember, and it forgets an older, deeper one. */
    remember(address, top) {
      const key = addressOf(address);
      if (!key) return;
      const value = Math.round(Number(top));
      entries.delete(key);
      if (Number.isFinite(value) && value > 0) {
        entries.set(key, value);
        while (entries.size > limit) entries.delete(entries.keys().next().value);
      }
      persist();
    },
    recall(address) {
      return entries.get(addressOf(address)) || 0;
    },
    size: () => entries.size,
  };
}

/* Puts `scroller` at `top`, and keeps trying as `host` grows until it can be reached. Returns a function that stops
   it (the router calls it when the next page starts). The learner's own wheel, touch, key or pointer ends it. */
export function restoreScrollWhenReady(scroller, top, host, { timeoutMs = 1500 } = {}) {
  let done = false;
  let observer = null;
  let timer = 0;
  const intents = ['wheel', 'touchstart', 'pointerdown', 'keydown'];

  function stop() {
    if (done) return;
    done = true;
    observer?.disconnect();
    clearTimeout(timer);
    for (const name of intents) scroller.removeEventListener(name, stop);
  }

  function apply() {
    if (done) return;
    const reach = scroller.scrollHeight - scroller.clientHeight;
    scroller.scrollTo({ top: Math.max(0, Math.min(top, reach)), behavior: 'instant' });
    if (reach >= top - 1) stop();
  }

  for (const name of intents) scroller.addEventListener(name, stop, { passive: true });
  timer = setTimeout(stop, timeoutMs);
  if (typeof ResizeObserver === 'function' && host) {
    observer = new ResizeObserver(apply);
    observer.observe(host);
  }
  apply();
  return stop;
}
