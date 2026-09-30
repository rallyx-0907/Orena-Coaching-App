/* Notes and highlights of one text, between this device and the account (D4 I10).

   The device stores stay the cache (`highlights.js`, `quick-sheet/model.js`): the account's set is merged
   into them when a text opens, and this device's set is written to the account shortly after it changes.
   Nothing here decides anything about the words: the two sets are unioned by id (product/account-records.js),
   a removal is remembered for the visit so a union cannot bring it back, and a deployment that does not keep
   work with the account leaves both calls as no-ops. */
import { pullAnnotations, pushAnnotations, noteRemoved } from '../../product/account-records.js';
import { loadHighlights, mergeHighlights } from './highlights.js';
import { notesForContent, mergeNotes } from '../quick-sheet/model.js';

const PUSH_DELAY_MS = 1200;
const timers = new Map();

/* Merge what the account holds for this text into the device. Returns whether anything arrived. */
export async function pullIntoDevice(storage, owner, contentId) {
  if (!storage || !contentId) return false;
  const server = await pullAnnotations(contentId);
  if (!server || server.cleared) return false;
  const before = loadHighlights(storage, owner, contentId).length;
  const highlights = mergeHighlights(storage, owner, contentId, server.highlights);
  const arrived = mergeNotes(storage, owner, contentId, server.notes);
  return highlights.length !== before || arrived > 0;
}

/* Write the device's set for this text to the account once the learner has stopped changing it. */
export function scheduleAnnotationPush(storage, owner, contentId, { delay = PUSH_DELAY_MS } = {}) {
  if (!storage || !contentId) return;
  clearTimeout(timers.get(contentId));
  timers.set(contentId, setTimeout(() => {
    timers.delete(contentId);
    void pushAnnotations(contentId, {
      highlights: loadHighlights(storage, owner, contentId),
      notes: notesForContent(storage, owner, contentId),
    });
  }, delay));
}

export { noteRemoved };
