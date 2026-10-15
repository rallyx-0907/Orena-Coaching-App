/* The administrator's preview of a held import (`#/content/media:preview:<id>`, D-206) is read-only (D-210).

   Opening the learner player on an item that is not published must leave nothing of the administrator behind on it:
   no place, no progress, no practice attempt, no saved word, note, highlight or response, and no record of where a
   word was met. The Listening room does not draw the controls that would write (no Save, no link into a room that
   saves) and passes `readOnly` to the line practice, the word sheet and the Vocabulary Focus; this module is the
   second, independent wall. While a preview is open, `request` (infrastructure/api.js) refuses every call that stores
   learner state, whichever code makes it. The server is the third wall: it refuses the same writes for a media id
   that is not published and visible to the learner (writing_coach/listening_api.py `media_state_writable`).

   Only calls that STORE learner state are listed. A lookup, a translation, a tag or a read is not, and keeps working.
   A new route that stores learner state against content belongs here and in the gate that lists them. */

let open = 0;

/* A preview is open until the returned function is called. Re-entrant: two previews need two releases. */
export function enterPreview() {
  open += 1;
  let released = false;
  return () => {
    if (released) return;
    released = true;
    open = Math.max(0, open - 1);
  };
}

/* Open AND still on a preview address: a room that threw before it could release cannot leave the app read-only.
   (No `location`, as in a Node gate: the open count alone decides.) */
export function previewActive() {
  if (open <= 0) return false;
  const hash = typeof location === 'object' && location ? String(location.hash || '') : null;
  return hash === null || hash.includes('preview:') || hash.includes('preview%3A');
}

/* The learner-state writers. Each is a path prefix; a method other than GET/HEAD on it is a write. */
const STATE_PATHS = [
  '/api/continue/',
  '/api/listening/progress',
  '/api/listening/shadowing-progress',
  '/api/library/vocabulary',
  '/api/library/items',
  '/api/library/collections',
  '/api/annotations/',
  '/api/responses/',
  '/api/vocabulary/decks',
];

export function isLearnerStateWrite(method, url) {
  const verb = String(method || 'GET').toUpperCase();
  if (verb === 'GET' || verb === 'HEAD' || verb === 'OPTIONS') return false;
  const path = String(url || '').split('?')[0];
  return STATE_PATHS.some((prefix) => (prefix.endsWith('/') ? path.startsWith(prefix) : path === prefix || path.startsWith(`${prefix}/`)));
}

/* Whether a request must be refused now. */
export function previewRefuses(method, url) {
  return previewActive() && isLearnerStateWrite(method, url);
}

export function previewRefusal() {
  const error = new Error('This is a preview; nothing is saved.');
  error.category = 'preview_read_only';
  error.retryable = false;
  error.status = 409;
  return error;
}
