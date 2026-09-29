// Feedback is an observation about a submitted version. Applying an experiment
// to today's draft requires one unambiguous, still-existing source quotation.
export function revisionTarget(text, quote) {
  if (typeof quote !== 'string' || !quote) return null;
  const start = text.indexOf(quote);
  return start >= 0 && text.indexOf(quote, start + 1) < 0
    ? { start, end: start + quote.length, quote }
    : null;
}
export function applyRevision(text, quote, replacement) {
  const target = revisionTarget(text, quote);
  if (!target || !replacement.trim()) return null;
  const changed =
    text.slice(0, target.start) + replacement.trim() + text.slice(target.end);
  return changed.length <= 12000 ? changed : null;
}

/* Where an applied fix goes (moved from `ui/writing-feedback.js`, D-091: the new learner UI's
   Writing screen needs this pure logic too, which lived only in the old UI's own tree - that
   module now re-exports it). The words must be in the draft exactly once - a repeated quotation
   leaves the learner to choose - and the result must fit the writing limit; otherwise nothing is
   replaced and the finding stays guidance, never auto-applied. */
export function applyFix(text, issue) {
  const target = revisionTarget(text, issue.fragment);
  const changed = target ? applyRevision(text, issue.fragment, issue.correction || '') : null;
  if (changed === null) return null;
  const replacement = issue.correction.trim();
  return { text: changed, start: target.start, end: target.start + replacement.length };
}
