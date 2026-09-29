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

/* One row per logged task, oldest first (the order the session happened in). */
export function tasksFor(session) {
  return session.map((entry) => ({
    kind: entry.kind,
    note: (entry.facts || []).map((fact) => `${fact.label} ${fact.value}`).join(' · '),
    at: entry.at,
  }));
}

/* The one real "worth mentioning" number: the lowest measured fact across the whole session,
   only when it is genuinely low (a session of high scores has nothing to flag - rule 50, no
   forced "you're doing great" filler either). `threshold` is the same "weak" band
   `screens/speak/model.js#bandOf` already uses (<70), so this reads the same way that band does
   everywhere else in the room. */
export function keyImprovement(session, threshold = 70) {
  let worst = null;
  for (const entry of session) {
    for (const fact of entry.facts || []) {
      if (typeof fact.value === 'number' && (!worst || fact.value < worst.value)) worst = fact;
    }
  }
  if (!worst || worst.value >= threshold) return null;
  return worst;
}
