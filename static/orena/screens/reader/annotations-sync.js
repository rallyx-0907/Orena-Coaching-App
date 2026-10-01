/* Notes and highlights of one text, between this device and the account (D4 I10).

   The device stores stay the cache (`highlights.js`, `quick-sheet/model.js`). The account holds the truth, and it
   remembers what was REMOVED (a tombstone per removed id), so a removal made on one device leaves every device:
   - opening a text merges the account's set into the device AND drops from the device whatever the account has
     tombstoned, so an older device cannot keep, or re-upload, an item another device removed;
   - this device's set is written to the account shortly after it changes, against the version it read; a stale
     write is refused (409), the account's set is re-read and merged (its items plus this device's NEW items, never a
     tombstoned one), the device store is brought in line with the merge, and the write is made once more;
   - an item this learner removed in this visit stays removed even while that removal has not reached the account
     yet (a sentence sheet opening inside the debounce must not bring it back).
   A deployment that does not keep work with the account leaves all of it as a no-op. */
import { pullAnnotations, pushAnnotations, noteRemoved, removedIds } from '../../product/account-records.js';
import { loadHighlights, mergeHighlights, setHighlights } from './highlights.js';
import { notesForContent, mergeNotes, setNotesForContent } from '../quick-sheet/model.js';

const PUSH_DELAY_MS = 1200;
const timers = new Map();

/* Bring the device in line with what the account holds for this text. Returns whether anything changed. */
export async function pullIntoDevice(storage, owner, contentId) {
  if (!storage || !contentId) return false;
  const server = await pullAnnotations(contentId);
  if (!server) return false;
  const gone = new Set([...(server.tombstones || []), ...removedIds(contentId)]);
  const beforeHighlights = loadHighlights(storage, owner, contentId);
  const beforeNotes = notesForContent(storage, owner, contentId);
  const keptHighlights = beforeHighlights.filter((item) => !gone.has(item.id));
  const keptNotes = beforeNotes.filter((note) => !gone.has(note.id));
  let changed = keptHighlights.length !== beforeHighlights.length || keptNotes.length !== beforeNotes.length;
  if (changed) {
    setHighlights(storage, owner, contentId, keptHighlights);
    setNotesForContent(storage, owner, contentId, keptNotes);
  }
  if (!server.cleared) {
    const incomingHighlights = (server.highlights || []).filter((item) => !gone.has(item.id));
    const incomingNotes = (server.notes || []).filter((note) => !gone.has(note.id));
    const before = loadHighlights(storage, owner, contentId).length;
    const highlights = mergeHighlights(storage, owner, contentId, incomingHighlights);
    const arrived = mergeNotes(storage, owner, contentId, incomingNotes);
    changed = changed || highlights.length !== before || arrived > 0;
  }
  return changed;
}

/* Write the device's set for this text to the account once the learner has stopped changing it. */
export function scheduleAnnotationPush(storage, owner, contentId, { delay = PUSH_DELAY_MS } = {}) {
  if (!storage || !contentId) return;
  clearTimeout(timers.get(contentId));
  timers.set(contentId, setTimeout(() => {
    timers.delete(contentId);
    void pushAnnotations(
      contentId,
      { highlights: loadHighlights(storage, owner, contentId), notes: notesForContent(storage, owner, contentId) },
      {
        // The merge is the truth after a conflict: a removal made elsewhere leaves this device as well.
        onMerged: (merged) => {
          setHighlights(storage, owner, contentId, merged.highlights);
          setNotesForContent(storage, owner, contentId, merged.notes);
        },
      },
    );
  }, delay));
}

export { noteRemoved };
