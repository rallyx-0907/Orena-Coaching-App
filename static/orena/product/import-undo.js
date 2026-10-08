/* "Delete from Orena" with an Undo, never a confirmation (D-108.1). The import is hidden at once and the design's
   toast offers Undo for as long as the toast stays (4s, kit/toast.js); the deletion is committed when that window ends,
   or when the page is hidden. Undo therefore needs no server revival and restores the import exactly. One window is
   open at a time: starting another commits the first. After a reload Undo is no longer offered; the deletion still
   happens (memory.flushStaged). */
export const UNDO_WINDOW_MS = 4000;

let pending = null; // { memory, id, timer }
const listeners = new Set();

/* A room that lists imports asks to be told when one comes back (or goes), so it can repaint. */
export function onImportsChanged(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function notify() {
  for (const listener of [...listeners]) {
    try {
      listener();
    } catch {
      /* a room that is gone */
    }
  }
}

export function pendingImportIds() {
  return pending ? [pending.id] : [];
}

/* Commit the open window now (a second delete, the page hiding). */
export function flushPendingDelete() {
  if (!pending) return Promise.resolve(false);
  const { memory, id, timer } = pending;
  pending = null;
  clearTimeout(timer);
  return Promise.resolve(memory.commitRemoval(id)).then((result) => {
    notify();
    return result;
  });
}

function undo() {
  if (!pending) return;
  const { memory, id, timer } = pending;
  pending = null;
  clearTimeout(timer);
  memory.undoRemoval(id);
  notify();
}

/* `toast(text, { undo, undoLabel })` is the design's toast (kit/toast.js). */
export function deleteWithUndo(memory, id, { toast, text, undoLabel }) {
  flushPendingDelete();
  if (!memory?.stageRemoval?.(id)) return false;
  pending = { memory, id, timer: setTimeout(flushPendingDelete, UNDO_WINDOW_MS) };
  notify();
  toast(text, { undo, undoLabel, iconName: 'check' });
  return true;
}
