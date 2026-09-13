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
