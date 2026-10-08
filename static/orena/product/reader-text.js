/* Reading content shaping: the blocks a text is read as, chapter neighbours, and what a learner's
   selection means (word / phrase / passage) with the sentence context around it. Pure and DOM-free
   - the same rules whichever screen renders them.

   Moved out of static/orena/ui/reading-room.js (old presentation, D-091) so the new Reader screen
   (static/orena/screens/reader/) can shape a document's text and a learner's selection without
   importing old UI (the surface-agent brief's hard limit). Nothing about the values or the logic
   changed in the move; static/orena/ui/reading-room.js re-exports these same names unchanged for
   its own existing callers (ui/reader.js, ui/lexical.js, scripts/test_orena_reading_room.mjs). */

/* What each endpoint accepts, named once so a request is shaped to fit rather than refused. */
export const LOOKUP_LIMITS = Object.freeze({ selection: 80, context: 1200 });
export const TRANSLATE_LIMITS = Object.freeze({ text: 5900 });
export const EXPLAIN_LIMITS = Object.freeze({ selection: 1600, context: 2400 });

const tidy = (value) =>
  String(value ?? '')
    .split('\n')
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .join('\n');

/* The blocks a text is read as. A structured chapter keeps its headings, paragraphs and section
   breaks; a text that only has paragraphs reads as paragraphs. Anything else - an unknown block, an
   empty one, a break with nothing on one side of it - is dropped rather than shown. */
export function blocksFrom(item = {}) {
  const source =
    Array.isArray(item.blocks) && item.blocks.length
      ? item.blocks
      : (item.paragraphs || []).map((text) => ({ type: 'paragraph', text }));
  const blocks = [];
  for (const block of source) {
    if (!block || typeof block !== 'object') continue;
    if (block.type === 'break') {
      if (blocks.length && blocks[blocks.length - 1].type !== 'break')
        blocks.push({ type: 'break' });
      continue;
    }
    if (block.type !== 'heading' && block.type !== 'paragraph') continue;
    const text = tidy(block.text);
    if (!text) continue;
    blocks.push(
      block.type === 'heading'
        ? {
            type: 'heading',
            level: Math.min(6, Math.max(1, Number.parseInt(block.level, 10) || 2)),
            text,
          }
        : { type: 'paragraph', text },
    );
  }
  while (blocks.length && blocks[blocks.length - 1].type === 'break') blocks.pop();
  return blocks;
}

/* --- Chapters --------------------------------------------------------------------------------- */

const byPosition = (chapters) =>
  [...(chapters || [])].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

export function chapterNeighbours(chapters, chapterId) {
  const ordered = byPosition(chapters);
  const index = ordered.findIndex((chapter) => String(chapter.id) === String(chapterId));
  if (index < 0) return null;
  return {
    index,
    total: ordered.length,
    previous: ordered[index - 1] || null,
    next: ordered[index + 1] || null,
  };
}

/* --- Selection ---------------------------------------------------------------------------------- */

/* What the learner selected: a word (looked up), a phrase (translated, and worth keeping), or a
   passage (translated or explained). Too much to act on is nothing. */
export function selectionKind(text, language) {
  const value = String(text ?? '').replace(/\s+/g, ' ').trim();
  if (!value || value.length > EXPLAIN_LIMITS.selection) return null;
  if (language === 'zh') {
    if (/[。！？；…!?;]/.test(value) || value.length > 24) return 'passage';
    if (value.length <= 4 && !/[\s，、,.：:“”"'‘’（）()]/.test(value)) return 'word';
    return 'phrase';
  }
  const words = value.split(' ');
  if (words.length === 1 && value.length <= 40 && /^[\p{L}\p{M}'’-]+$/u.test(value))
    return 'word';
  if (words.length <= 6 && value.length <= LOOKUP_LIMITS.selection && !/[.!?;:]/.test(value))
    return 'phrase';
  return 'passage';
}

/* --- Context -------------------------------------------------------------------------------------- */

const SENTENCE_END = /[.!?…。！？]+["'”’」』）)\]]*\s*|\n+/gu;

/* A paragraph's text, split into sentence spans. Exported (unlike its old ui/reading-room.js form)
   because the Reader's own sentence-level markup - one `<span>` per sentence, tappable/selectable on
   its own (D-088 frame 14) - needs the same spans the context-window logic below already computes,
   not a second regex reinventing the same boundaries. */
export function sentenceSpans(text) {
  const spans = [];
  let start = 0;
  for (const match of text.matchAll(SENTENCE_END)) {
    const end = match.index + match[0].length;
    if (end > start) spans.push({ start, end });
    start = end;
  }
  if (start < text.length) spans.push({ start, end: text.length });
  return spans;
}

// The sentence a selection sits in, so a meaning is asked about its own use.
export function sentenceAround(text, start, end, limit = LOOKUP_LIMITS.context) {
  const value = String(text ?? '');
  const spans = sentenceSpans(value);
  let from = (spans.find((s) => s.start <= start && start < s.end) || { start: 0 }).start;
  let to = (spans.find((s) => s.start < end && end <= s.end) || { end: value.length }).end;
  if (to - from > limit) {
    const room = Math.max(0, limit - (end - start));
    from = Math.max(0, start - Math.floor(room / 2));
    to = Math.min(value.length, from + limit);
    if (to < end) {
      to = end;
      from = Math.max(0, to - limit);
    }
  }
  return value.slice(from, to).trim();
}
