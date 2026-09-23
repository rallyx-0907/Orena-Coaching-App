/* One learner flow per capability (D-078). An old address still works; it arrives in the flow that
   replaced the screen it used to draw, and the old screen is never rendered again.

   - `#/practice` with no intention was the Practice hub; its ways in now live on Home.
   - Shadowing without a lesson was a list of moments; Speaking has its own library.
   - Dictation is a way to work on a Listening lesson: its way in is the Listening library.
   - Writing's way in is its own library, `#/writing`.

   Returns the place to go instead, as `link()` arguments, or null when the address is current. */
export function legacyRedirect(location) {
  if (!location || location.page !== 'practice') return null;
  const { intent, id } = location;
  if (!intent) return ['discover'];
  if (intent === 'shadowing' && !id) return ['practice', { intent: 'speaking' }];
  if (intent === 'dictation') return id ? ['encounter', { id, intent: 'dictation' }] : ['practice', { intent: 'follow' }];
  if (intent === 'writing') return ['writing'];
  return null;
}
