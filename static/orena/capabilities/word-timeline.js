/* Word-level Follow is optional evidence, not a guarantee. An asset either
   ships word timings that genuinely describe the canonical line, or it does
   not - and then the segment is the honest unit. Nothing here invents a
   position, and anything that fails to reconcile is rejected wholesale rather
   than half-applied, because a highlight on the wrong word is worse than no
   highlight at all. */

// Number(null) is 0 and Number('') is 0, so coercing here would turn a missing
// timing into a confident position at the start of the clip. Only an actual
// number counts as a timing.
const finite = (value) => typeof value === 'number' && Number.isFinite(value);

/* Map the timed words onto the canonical line so the highlight marks the text
   the learner is actually reading, punctuation and spacing intact. Returns null
   whenever the timing cannot be reconciled with the line. */
export function wordSpans(segment) {
  const line = String(segment?.original_text ?? '');
  const words = (Array.isArray(segment?.words) ? segment.words : []).filter(
    (word) =>
      word &&
      typeof word.text === 'string' &&
      word.text.trim() &&
      finite(word.start_ms) &&
      finite(word.end_ms) &&
      Number(word.end_ms) > Number(word.start_ms),
  );
  if (!words.length || !line) return null;

  const spans = [];
  let cursor = 0;
  for (const word of words) {
    const text = word.text.trim();
    const at = line.indexOf(text, cursor);
    // A word the line does not contain, in order, means this timing belongs to
    // different text - a re-transcription, or the spoken form of a line that
    // carries a speaker label.
    if (at < 0) return null;
    spans.push({
      start: at,
      end: at + text.length,
      start_ms: Number(word.start_ms),
      end_ms: Number(word.end_ms),
    });
    cursor = at + text.length;
  }
  for (let i = 1; i < spans.length; i += 1) {
    if (spans[i].start_ms < spans[i - 1].start_ms) return null;
  }
  return spans;
}

/* The index of the word being spoken, or -1 between words and outside the
   segment. Gaps are real: a pause is not the previous word continuing. */
export function activeWordIndex(spans, timeMs) {
  const time = Number(timeMs);
  if (!Array.isArray(spans) || !spans.length || !Number.isFinite(time)) return -1;
  let low = 0,
    high = spans.length - 1,
    found = -1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (spans[mid].start_ms <= time) {
      found = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  if (found < 0) return -1;
  return time < spans[found].end_ms ? found : -1;
}

/* Split the canonical line into the pieces a renderer needs: timed words and
   the untimed text between them. The caller escapes; this only decides shape. */
export function linePieces(segment) {
  const line = String(segment?.original_text ?? '');
  const spans = wordSpans(segment);
  if (!spans) return null;
  const pieces = [];
  let cursor = 0;
  spans.forEach((span, index) => {
    if (span.start > cursor)
      pieces.push({ text: line.slice(cursor, span.start), index: -1 });
    pieces.push({ text: line.slice(span.start, span.end), index });
    cursor = span.end;
  });
  if (cursor < line.length) pieces.push({ text: line.slice(cursor), index: -1 });
  return pieces;
}
