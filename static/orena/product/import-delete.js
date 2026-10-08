/* Deleting a learner's own import (D-107): from My Library and from the import's Content Detail, never from Discover.

   One action, one lifecycle. The import leaves this device at once (its lists, its saved place and its kept mark) and is deleted from the account: the account keeps a content-free
   tombstone, an uploaded file's stored copy goes with it, and a link's external source is never touched. Another
   device learns of it on its next sync (shell/context.js syncImports) and a deleted import is never opened again
   (product/import-removed.js). Returns whether the account has confirmed the deletion; if it could not be reached,
   the deletion stays recorded on this device and is sent again at the next sync. */
/* The membership ids a route/content id can name, as product/memory.js knows them. */
export { importMemberId } from './import-removed.js';

export function isOwnImport(memberId) {
  return /^(text|url|upload):/.test(String(memberId || ''));
}

export async function deleteOwnImport(memory, memberId) {
  if (!memory || !isOwnImport(memberId)) return false;
  return Boolean(await memory.remove(memberId));
}
