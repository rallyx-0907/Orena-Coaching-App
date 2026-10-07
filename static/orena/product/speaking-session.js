/* A real, session-scoped ledger of speaking tasks just finished, feeding Speaking Summary (frame
   42, `#/speak-summary`). Device memory by design (AGENTS.md §7 - there is no server schema for
   "what a learner did this session"; the source's own `S.sess`/`logSpeak()` were in-memory only
   and reset on reload, which this keeps: `sessionStorage`, gone when the tab closes, not a
   learner-data persistence decision). Every entry is a fact that already happened (a real measured
   take, `pronunciationView().measured`), never a guessed score - `screens/speak` is this wave's
   only writer; any later speaking screen (Free Talk, Situation Reaction, ...) may log to the same
   ledger once it exists. When the server keeps the practice session (D-142, ORENA_PRACTICE_SESSION on), Speaking
   Summary reads that session instead and this ledger only adds the tab's own tasks that have no server record. */

const KEY = 'orena.speaking.session.v1';
const MAX_ENTRIES = 50;
let activeScope = '';

// Use the existing account/language identity; the ledger remains tab-only.
// Unscoped older entries cannot establish ownership and are never read.
export function setSpeakingSessionScope(scope) {
  activeScope = String(scope || '');
}

function read() {
  try {
    if (!activeScope) return [];
    const parsed = JSON.parse(window.sessionStorage.getItem(`${KEY}:${activeScope}`) || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(list) {
  try {
    if (activeScope) window.sessionStorage.setItem(`${KEY}:${activeScope}`, JSON.stringify(list.slice(-MAX_ENTRIES)));
  } catch {
    /* A browser that refuses storage just does not remember this session's tasks. */
  }
}

/* `kind`: a stable key a caller's copy.js turns into a label (never display text itself).
   `facts`: [{ label, value }] - the same rule-40 shape `screens/lesson-complete/sheet.js`'s
   `openLessonComplete` already takes: only real, measured facts. */
export function logSpeakingTask({ kind, contentId = '', takeRef = '', facts = [] }) {
  if (!kind) return;
  write([...read(), { kind, contentId, takeRef, facts, at: Date.now() }]);
}

export function noteSpeakingTaskAttempt(takeRef, attemptId) {
  if (!takeRef || !attemptId) return;
  write(read().map((entry) => entry.takeRef === takeRef ? { ...entry, attemptId: String(attemptId) } : entry));
}

export function readSpeakingSession() {
  return read();
}

export function clearSpeakingSession() {
  write([]);
}
