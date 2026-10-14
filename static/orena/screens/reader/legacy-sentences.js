/* Read-side compatibility for saved notes and highlights (D-201).

   A note or a highlight is keyed by its sentence's index in the paragraph plus the sentence's text
   (`p{pi}s{si}` + text). Before D-201 every full stop ended a sentence, so a paragraph with "USD 4.77
   billion", "Mr. Smith" or "U.S." was cut in the middle and its later sentences were numbered one too high.
   The splitter is fixed; the learner's stored keys are not rewritten (learner data, owner gate). Instead the
   Reader also looks a sentence up under the keys the OLD segmentation gave the text it now holds: each
   old sentence belongs to the one new sentence that contains it, so an existing note or highlight still
   shows on the right sentence. New notes and highlights are written under the new key only. */
import { sentenceSpans, legacySentenceSpans } from '../../product/reader-text.js';
import { segmentId } from './model.js';
import { loadNotesAcross, noteKeysFor } from '../quick-sheet/model.js';
import { loadHighlights, isHighlighted } from './highlights.js';

const squash = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();

function trimmedRanges(text, spans) {
  const out = [];
  for (const { start, end } of spans) {
    const raw = text.slice(start, end);
    const lead = raw.length - raw.trimStart().length;
    const value = raw.trim();
    if (value) out.push({ start: start + lead, end: start + lead + value.length, text: value });
  }
  return out;
}

/* For a paragraph's text: an array indexed by the NEW sentence index, each entry the old
   `{ segment, sentence }` pairs that sit inside that sentence and whose key differs from its own (a sentence
   segmented the same way before has nothing extra to look up). */
export function legacyAliases(text, pi) {
  const value = String(text ?? '');
  const now = trimmedRanges(value, sentenceSpans(value));
  const before = trimmedRanges(value, legacySentenceSpans(value));
  const aliases = now.map(() => []);
  const own = now.map((s, ni) => `${segmentId(pi, ni)}|${squash(s.text)}`);
  before.forEach((old, oi) => {
    const ni = now.findIndex((s) => old.start >= s.start && old.start < s.end);
    if (ni < 0) return;
    const segment = segmentId(pi, oi);
    const id = `${segment}|${squash(old.text)}`;
    if (own[ni] === id) return;
    if (own.includes(id)) return; // it is another sentence's own key: it would show there twice
    aliases[ni].push({ segment, sentence: squash(old.text) });
  });
  return aliases;
}

/* How many saved notes and highlights a text holds, counted through the aliases (the completion room's figure).
   `paragraphs`: [{ pi, text }]. */
export function countSavedMarks(paragraphs, { storage, owner, contentId, sentencesOf }) {
  const highlights = loadHighlights(storage, owner, contentId);
  let count = 0;
  for (const block of paragraphs) {
    const aliases = legacyAliases(block.text, block.pi);
    sentencesOf(block.text).forEach((sentence, si) => {
      const seg = segmentId(block.pi, si);
      const text = squash(sentence);
      const legacy = aliases[si];
      count += loadNotesAcross(storage, owner, noteKeysFor(text, { kind: 'reading', content_id: contentId, segment: seg, legacy })).length;
      if (isHighlighted(highlights, seg, text, legacy)) count += 1;
    });
  }
  return count;
}
