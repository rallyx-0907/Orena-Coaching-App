/* A line's attempts (Orena Speaking 06, "Các lần thử"), under D-076's retention rule:

   - By default a recording lives in this tab only and is gone when the session ends.
   - "Keep recent recordings" is the learner's opt-in: then the last five recordings of each line
     are also kept on this device (IndexedDB), never sent anywhere. Turning it off deletes them.
   - Nothing here reaches the server. The score history the server keeps is the audio-free
     attempt record (`speaking_attempts`), which is a different thing.

   The best attempt is the one with the highest overall score the provider measured; that is a
   ranking of real numbers, not a threshold. */

export const MAX_PER_LINE = 5;
const PREFERENCE = 'orena.speaking.keepRecent';

/* Only what a later view needs; the provider's full answer is not kept. */
function stored(attempt) {
  return {
    id: attempt.id,
    at: attempt.at,
    ms: attempt.ms,
    blob: attempt.blob,
    overall: attempt.overall,
    flagged: attempt.flagged,
    words: (attempt.words || []).map((word) => ({ text: word.text, flagged: word.flagged, offsetMs: word.offsetMs, durationMs: word.durationMs })),
  };
}

export function bestOf(attempts) {
  return attempts.reduce((best, item) => (typeof item.overall === 'number' && (!best || item.overall > best.overall) ? item : best), null);
}

export function createAttemptStore({ storage = globalThis.localStorage, local = null, urls = globalThis.URL } = {}) {
  const session = new Map();
  const readPreference = () => {
    try {
      return storage?.getItem(PREFERENCE) === 'on';
    } catch {
      return false;
    }
  };
  let keepRecent = readPreference();

  const withUrl = (attempt) => (attempt.url || !attempt.blob || !urls?.createObjectURL ? attempt : { ...attempt, url: urls.createObjectURL(attempt.blob) });

  return {
    get keepRecent() {
      return keepRecent;
    },
    async setKeepRecent(on) {
      keepRecent = Boolean(on);
      try {
        storage?.setItem(PREFERENCE, keepRecent ? 'on' : 'off');
      } catch {}
      if (!keepRecent) await local?.clear?.();
      else for (const [key, list] of session) await local?.save?.(key, list.map(stored));
    },
    async add(key, attempt) {
      const list = [withUrl(attempt), ...(session.get(key) || [])].slice(0, MAX_PER_LINE);
      for (const dropped of (session.get(key) || []).slice(MAX_PER_LINE - 1)) {
        if (dropped.url && !list.includes(dropped)) urls?.revokeObjectURL?.(dropped.url);
      }
      session.set(key, list);
      if (keepRecent) await local?.save?.(key, list.map(stored));
      return list;
    },
    /* This session's attempts, then this device's kept ones that are not already here. */
    async list(key) {
      const mine = session.get(key) || [];
      if (!keepRecent || !local?.load) return mine;
      const kept = (await local.load(key)) || [];
      const seen = new Set(mine.map((item) => item.id));
      const merged = [...mine, ...kept.filter((item) => !seen.has(item.id)).map(withUrl)];
      return merged.sort((a, b) => b.at - a.at).slice(0, MAX_PER_LINE);
    },
    release() {
      for (const list of session.values()) for (const item of list) if (item.url) urls?.revokeObjectURL?.(item.url);
      session.clear();
    },
  };
}

/* The device store: one IndexedDB record per line, holding at most five recordings. */
export function indexedDbAttempts({ indexedDB = globalThis.indexedDB, name = 'orena-speaking', store = 'attempts' } = {}) {
  if (!indexedDB) return null;
  const open = () =>
    new Promise((resolve, reject) => {
      const request = indexedDB.open(name, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(store);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  const run = async (mode, action) => {
    const db = await open();
    try {
      return await new Promise((resolve, reject) => {
        const tx = db.transaction(store, mode);
        const request = action(tx.objectStore(store));
        tx.oncomplete = () => resolve(request?.result);
        tx.onerror = () => reject(tx.error);
      });
    } finally {
      db.close();
    }
  };
  return {
    load: (key) => run('readonly', (s) => s.get(key)).catch(() => []),
    save: (key, list) => run('readwrite', (s) => s.put(list.slice(0, MAX_PER_LINE), key)).catch(() => {}),
    clear: () => run('readwrite', (s) => s.clear()).catch(() => {}),
  };
}
