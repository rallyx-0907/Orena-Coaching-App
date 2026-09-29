/* Pure data for the Lesson complete modal (frame 63, E3 §7). No DOM - what
   scripts/test_orena_screen_lesson-complete.mjs exercises directly.

   Rule 40: a fact the caller could not actually measure must never be padded in as a placeholder -
   the caller simply does not include it, and `sanitizeFacts` drops anything that slips through
   without a real label or a real value (`0` is a real value and is kept; `''`/`null`/`undefined`
   are not facts). This is why the modal's own export takes a flat `facts` list rather than the
   source's fixed `xp`/`words`/`wordsLabel`/`min` trio (E3's own finding: `xp` there is a pure
   client-side formula, `Math.max(5, score*0.4)`, with no backend measurement behind it - never
   reproduced here; a caller with a real measured number passes it as a fact, one that does not
   have one simply omits it). */

export function sanitizeFacts(facts) {
  return (Array.isArray(facts) ? facts : [])
    .map((fact) => ({ label: String(fact?.label ?? '').trim(), value: fact?.value }))
    .filter((fact) => fact.label && fact.value != null && String(fact.value).trim() !== '');
}
