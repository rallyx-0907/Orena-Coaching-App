/* The order onboarding writes in when the account has no learning language yet (D-16R): the language is stored BEFORE
   anything is written to the profile, because the profile is per learning language and the server refuses a learner
   write for an account that has not chosen one (409 `learning_language_required`) - it must never make the default
   (English) the learner's language just because they tapped a support language first.

   A support language picked before a learning language is stored is shown at once and written once a language is
   stored (`stage` / `flush`). The state outlives the remount a support pick causes (the whole app repaints in it), so one
   instance is kept for the page by the screen, not in the mounted screen's state. Pure logic: the screen hands in what
   reads the account and what writes. */

export function createTargetFirst({ account, storeTarget, writeSupport }) {
  let pending = '';

  /* The account has a settings row but no learning language. (No row at all - local development without an account
     store - has nowhere to keep one, so nothing is waited for.) */
  function needsTarget() {
    const row = account();
    return row?.stored === true && !String(row.learning_language || '').trim();
  }

  async function flush() {
    if (!pending) return;
    const code = pending;
    pending = '';
    await writeSupport(code);
  }

  return {
    needsTarget,
    pending: () => pending,
    /* A support pick while no language is stored: remembered, not written. False when it can be written now. */
    stage(code) {
      if (!needsTarget()) return false;
      pending = code;
      return true;
    },
    flush,
    /* The learner moves on with `language` (the one the screen shows, English unless they chose another): store it, then
       write what was waiting. Throws what storing threw, leaving the pick pending. */
    async ensure(language) {
      if (!needsTarget()) return;
      await storeTarget(language);
      await flush();
    },
    /* The learner picked a language: store it (the caller adopts its profile), the waiting pick is flushed by `flush`
       once the profile is the new language's. */
    store: (language) => storeTarget(language),
  };
}
