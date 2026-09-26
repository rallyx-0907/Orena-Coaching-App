/* One learner flow per capability (D-078). An old address still works; it arrives in the flow that
   replaced the screen it used to draw, and the old screen is never rendered again.

   - `#/practice` with no intention was the Practice hub; its ways in now live on Home.
   - Shadowing without a lesson was a list of moments; Speaking has its own library.
   - Dictation is a way to work on a Listening lesson: its way in is the Listening library.
   - Writing's way in is its own library, `#/writing`.
   - Shadowing or speaking a Listening lesson was a panel over the encounter; it is the Speaking
     workspace, opened on the lesson (where the learner last was), before the encounter draws.

   Returns the place to go instead, as `link()` arguments, or null when the address is current. */
export function legacyRedirect(location) {
  if (!location) return null;
  const { intent, id } = location;
  if (location.page === 'encounter')
    return (intent === 'shadowing' || intent === 'speaking') && /^media:/.test(id || '') ? ['practice', { intent: 'shadowing', id }] : null;
  if (location.page !== 'practice') return null;
  if (!intent) return ['discover'];
  if (intent === 'shadowing' && !id) return ['practice', { intent: 'speaking' }];
  if (intent === 'dictation') return id ? ['encounter', { id, intent: 'dictation' }] : ['practice', { intent: 'follow' }];
  if (intent === 'writing') return ['writing'];
  return null;
}
