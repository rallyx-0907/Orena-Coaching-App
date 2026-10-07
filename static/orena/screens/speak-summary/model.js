/* Speaking Summary (frame 42, `#/speak-summary`) - pure data shaping over this session's own
   speaking ledger (`product/speaking-session.js`). No back button, no forward nav besides
   Practice Hub (confirmed against the source, D5/E2 §7 - the frame draws neither).

   The source's own "N Use item(s) · M Transfer" evidence split and its per-mode "next task"
   recommendation both need evidence this build does not produce for Speaking (no Use/Transfer
   ledger exists anywhere in `product/evidence.js`, and every other speaking mode the source's
   `ssNext` can name - Timed Reaction, Conversation, ... - is outside this wave's scope, so
   recommending one it cannot show real availability for would be a guess). Both are left out
   here rather than invented (rule 40) and recorded as backend/product gaps in this wave's report,
   not resolved by a guess. */

/* The tasks of this speaking session, oldest first: what this tab logged (`product/speaking-session.js`) AND what the
   account holds for the last seven days (`product/speaking-history.js#loadAttemptsSince`) - so the summary comes back in a fresh
   browser. Each server attempt is a Scripted Pronunciation task; its facts
   are only the VERIFIED accuracy and fluency (an unverified attempt is still a task done, with no figure). A tab entry
   for the same task is the same task: a server attempt with the same persisted ID as a logged entry is not listed twice. */
export function tasksFor(session, serverRows = [], labels = { accuracy: 'Accuracy', fluency: 'Fluency' }, { sessionOnly = false } = {}) {
  const sameAttempt = (entry, row) => (entry.attemptId && String(entry.attemptId) === row.id) || (entry.takeRef && entry.takeRef === row.takeId);
  const factsFor = row => row?.verified ? [
    ...(row.accuracy != null ? [{ label: labels.accuracy, value: row.accuracy }] : []),
    ...(row.fluency != null ? [{ label: labels.fluency, value: row.fluency }] : []),
  ] : [];
  const ledger = (session || []).map((entry) => {
    const facts = factsFor((serverRows || []).find(row => sameAttempt(entry, row)));
    return {
      kind: entry.kind,
      note: facts.map((fact) => `${fact.label} ${fact.value}`).join(' · '),
      facts,
      at: entry.at,
      attemptId: entry.attemptId,
      takeRef: entry.takeRef,
    };
  });
  /* While this session has tasks (D-139 HD-8) only those are listed; the account's other attempts of the
     window are read for the scores of the session's own tasks, never listed. */
  const fromServer = sessionOnly ? [] : (serverRows || [])
    .filter((row) => !ledger.some((entry) => sameAttempt(entry, row)))
    .map((row) => {
      const facts = factsFor(row);
      return { kind: 'scripted_pronunciation', note: facts.map((fact) => `${fact.label} ${fact.value}`).join(' · '), facts, at: row.at };
    });
  return [...ledger, ...fromServer].sort((a, b) => (a.at || 0) - (b.at || 0));
}

/* The one real "worth mentioning" number: the lowest measured fact across the whole session,
   only when it is genuinely low (a session of high scores has nothing to flag - rule 50, no
   forced "you're doing great" filler either). `threshold` is the same "weak" band
   `screens/speak/model.js#bandOf` already uses (<70), so this reads the same way that band does
   everywhere else in the room. */
export function keyImprovement(tasks, threshold = 70) {
  let worst = null;
  for (const entry of tasks) {
    for (const fact of entry.facts || []) {
      if (typeof fact.value === 'number' && (!worst || fact.value < worst.value)) worst = fact;
    }
  }
  if (!worst || worst.value >= threshold) return null;
  return worst;
}

/* D-142: with a live server session, the tasks of THIS session are the attempts the server holds for it (any device) and
   nothing else. A tab-only entry with no durable server record (a typed task, an unsaved take) is NOT counted: D-142 gives
   text-only activity no new persistence, so the persisted session is the only authority and reads the same on every tab and
   device. A ledger entry is read only to name the kind of an attempt the server already holds. */
export function tasksForServerSession(ledger, current, labels) {
  const rows = current?.rows || [];
  const sameAttempt = (entry, row) => (entry.attemptId && String(entry.attemptId) === row.id) || (entry.takeRef && entry.takeRef === row.takeId);
  const known = (ledger || []).filter((entry) => rows.some((row) => sameAttempt(entry, row)));
  return tasksFor(known, rows, labels);
}

/* Which notion of "this session" Speaking Summary uses. `current` is `loadCurrentSession`'s answer: null only when the
   server explicitly says the feature is off (the client ledger then applies, as before); otherwise the server is
   authoritative, and `meta: null` (no live session) never falls back to the tab ledger - it shows the seven-day view. */
export function sessionScope(current, ledger) {
  const serverSession = current && current.meta && current.rows.length > 0 ? current : null;
  const useLedger = current === null && (ledger || []).length > 0;
  return { serverSession, useLedger };
}
