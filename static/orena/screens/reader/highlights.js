/* The sentences a learner highlighted in a text (frame 14's selection toolbar "Highlight" and the
   green "highlight" rows of "Notes & highlights"): device memory, exactly like the notes the
   Sentence Quick Sheet's Note tab keeps (screens/quick-sheet/model.js, AGENTS.md section 7 -
   learner-owned data with no schema decision yet is device memory by design). DOM-free and
   storage-injected so scripts/test_orena_screen_reader.mjs can run it against a plain object.

   One store per learner (`owner`), one list per content id ("article:x", "book:b:c", "text:x"),
   each entry the sentence's segment id ("p{paragraph}s{sentence}", the same id a note is keyed by)
   plus its own text, so a highlight follows the sentence it was made on and is dropped, not
   misapplied, when the text has since changed. Bounded: never more than MAX_PER_TEXT entries for
   one text, MAX_TEXTS texts. */

/* The bounds follow the server's (D4 I10): at most 80 highlights of 400 characters per text, so a
   device never holds what the account would refuse. */
export const MAX_PER_TEXT = 80;
export const MAX_SENTENCE_CHARS = 400;
export const MAX_TEXTS = 60;

const squash = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();

function storageKey(owner) {
  return `orena.reader.highlights.v1:${encodeURIComponent(squash(owner) || 'local')}`;
}

function readStore(storage, owner) {
  try {
    const parsed = JSON.parse(storage.getItem(storageKey(owner)) || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(storage, owner, store) {
  try {
    storage.setItem(storageKey(owner), JSON.stringify(store));
    return true;
  } catch {
    /* A device out of storage keeps the highlight only for this visit. */
    return false;
  }
}

/* The identity of a highlight: where it is and what it says. */
export function highlightKey(segment, sentence) {
  return `${String(segment || '')}|${squash(sentence).slice(0, 200).toLowerCase()}`;
}

export function loadHighlights(storage, owner, contentId) {
  const list = readStore(storage, owner)[contentId];
  return Array.isArray(list) ? list.filter((item) => item && typeof item.segment === 'string' && typeof item.sentence === 'string') : [];
}

export function isHighlighted(list, segment, sentence) {
  const key = highlightKey(segment, sentence);
  return list.some((item) => highlightKey(item.segment, item.sentence) === key);
}

/* Highlight the sentence, or take the highlight off. Returns { on, list } - the sentence's new
   state and the text's whole list after the change. */
export function toggleHighlight(storage, owner, contentId, { segment, sentence }) {
  const store = readStore(storage, owner);
  const list = loadHighlights(storage, owner, contentId);
  const text = squash(sentence);
  if (!text || !contentId) return { on: false, list };
  const key = highlightKey(segment, text);
  const exists = list.some((item) => highlightKey(item.segment, item.sentence) === key);
  const next = exists
    ? list.filter((item) => highlightKey(item.segment, item.sentence) !== key)
    : [...list, { id: `${Date.now()}:${Math.random().toString(36).slice(2, 8)}`, segment: String(segment || ''), sentence: text.slice(0, MAX_SENTENCE_CHARS), at: new Date().toISOString() }].slice(-MAX_PER_TEXT);
  // Oldest texts fall off first so one device never grows without bound.
  const rest = Object.entries(store).filter(([id]) => id !== contentId);
  const kept = Object.fromEntries([...rest.slice(-(MAX_TEXTS - 1)), [contentId, next]]);
  writeStore(storage, owner, kept);
  return { on: !exists, list: next };
}

/* The account's highlights for a text merged into this device's (a union by id; the device's own come
   first). Returns the text's list after the merge. */
export function mergeHighlights(storage, owner, contentId, incoming) {
  const store = readStore(storage, owner);
  const list = loadHighlights(storage, owner, contentId);
  const known = new Set(list.map((item) => item.id));
  const extra = (Array.isArray(incoming) ? incoming : []).filter(
    (item) => item && item.id && !known.has(item.id) && typeof item.segment === 'string' && typeof item.sentence === 'string',
  );
  if (!extra.length || !contentId) return list;
  const next = [...list, ...extra].slice(-MAX_PER_TEXT);
  const rest = Object.entries(store).filter(([id]) => id !== contentId);
  writeStore(storage, owner, Object.fromEntries([...rest.slice(-(MAX_TEXTS - 1)), [contentId, next]]));
  return next;
}

/* The text's highlights replaced by exactly this set (the account's merged answer after a conflict, or the account's
   removals applied): a highlight the account no longer holds must leave this device too. */
export function setHighlights(storage, owner, contentId, list) {
  if (!contentId) return [];
  const store = readStore(storage, owner);
  const next = (Array.isArray(list) ? list : [])
    .filter((item) => item && item.id && typeof item.segment === 'string' && typeof item.sentence === 'string')
    .slice(-MAX_PER_TEXT);
  const rest = Object.entries(store).filter(([id]) => id !== contentId);
  writeStore(storage, owner, Object.fromEntries([...rest.slice(-(MAX_TEXTS - 1)), [contentId, next]]));
  return next;
}
