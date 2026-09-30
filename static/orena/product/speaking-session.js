/* A real, session-scoped ledger of speaking tasks just finished, feeding Speaking Summary (frame
   42, `#/speak-summary`). Device memory by design (AGENTS.md §7 - there is no server schema for
   "what a learner did this session"; the source's own `S.sess`/`logSpeak()` were in-memory only
   and reset on reload, which this keeps: `sessionStorage`, gone when the tab closes, not a
   learner-data persistence decision). Every entry is a fact that already happened (a real measured
   take, `pronunciationView().measured`), never a guessed score - `screens/speak` is this wave's
   only writer; any later speaking screen (Free Talk, Situation Reaction, ...) may log to the same
   ledger once it exists. */

const KEY = 'orena.speaking.session.v1';
const MAX_ENTRIES = 50;

function read() {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(KEY) || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(list) {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(list.slice(-MAX_ENTRIES)));
  } catch {
    /* A browser that refuses storage just does not remember this session's tasks. */
  }
}

/* `kind`: a stable key a caller's copy.js turns into a label (never display text itself).
   `facts`: [{ label, value }] - the same rule-40 shape `screens/lesson-complete/sheet.js`'s
   `openLessonComplete` already takes: only real, measured facts. */
export function logSpeakingTask({ kind, contentId = '', facts = [] }) {
  if (!kind) return;
  write([...read(), { kind, contentId, facts, at: Date.now() }]);
}

export function readSpeakingSession() {
  return read();
}

export function clearSpeakingSession() {
  write([]);
}
