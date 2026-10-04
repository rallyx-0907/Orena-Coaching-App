/* Which imports this device knows were deleted (D-107). A deleted import is gone for good: a device that has
   learned of the deletion - because the learner deleted it here, or the account's list says it was deleted
   elsewhere - never opens a stale cached copy of it, on any route. The active learner memory
   (product/memory.js) keeps this set; every room that could open an import by id asks it, so no room needs to
   know how the deletion was learned. The ids are membership ids (`text:<id>`, `url:<link>`, `upload:<media id>`),
   never content. */
const scopes = new Map(); // "owner:language" -> Set of membership ids
let active = '';
const listeners = new Set();
export function onRemovedImports(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
function notify() { for (const listener of listeners) listener(active, removedSet()); }

/* The set a learner memory keeps for ITS owner and language. The memory registers it under its scope; the shell
   makes one scope active (activateRemovedScope) when that memory becomes the room's. Another language's memory being
   built (a language switch) therefore never replaces the active room's set. Called with no scope, the one default
   scope is used and made active (tests, tools). */
export function setRemovedImports(ids, scope = '') {
  scopes.set(scope, new Set(Array.isArray(ids) ? ids.map(String) : []));
  if (!scope || !scopes.has(active)) active = scope;
  if (scope === active) notify();
}

export function activateRemovedScope(scope) {
  if (!scopes.has(scope)) scopes.set(scope, new Set());
  active = scope;
  notify();
}

function removedSet() {
  return scopes.get(active) || new Set();
}

export function isImportRemoved(id) {
  return removedSet().has(String(id || ''));
}

/* The error a room sees when it is asked to open one: the same 404 an unknown media id gets. */
export function removedImportError() {
  const error = new Error('This import was deleted.');
  error.status = 404;
  error.category = 'media_not_found';
  return error;
}

/* The membership id of the import a content route id names, or '' when it names no import. A text import's route
   id is its membership id (`text:<id>`); a link or file import travels as `upload:` + its membership id
   (`upload:url:<link>`, `upload:upload:<media id>`), and a stored upload may also arrive as `upload:<media id>`. */
export function importMemberId(contentId) {
  const value = String(contentId || '');
  if (value.startsWith('text:')) return value;
  if (value.startsWith('upload:url:')) return value.slice(7);
  if (value.startsWith('upload:upload:')) return value.slice(7);
  if (value.startsWith('upload:')) return value;
  if (value.startsWith('url:')) return value;
  return '';
}

/* Whether a route/content/media id names an import this device knows was deleted. */
export function isRemovedContent(contentId) {
  const member = importMemberId(contentId);
  if (member && removedSet().has(member)) return true;
  // A stored upload is opened by its bare media id too.
  return removedSet().has(`upload:${contentId}`);
}
