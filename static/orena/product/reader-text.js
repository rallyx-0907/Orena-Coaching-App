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
    if (!endsSentence(text, match)) continue;
    const end = match.index + match[0].length;
    if (end > start) spans.push({ start, end });
    start = end;
  }
  if (start < text.length) spans.push({ start, end: text.length });
  return spans;
}

/* The splitter before D-201: every full stop ended a sentence, so "USD 4.77 billion" was cut in two. Saved
   notes and highlights are keyed by sentence index and sentence text, so a note made under that segmentation
   is still read through it (screens/reader/legacy-sentences.js). Frozen: it is never used to write. */
export function legacySentenceSpans(text) {
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

/* A full stop is not always a sentence end: the "." inside "4.77", "U.S.", "e.g." or "Mr." is part of
   the word. Only a bare run of dots is ambiguous - "!", "?", "。", "！", "？" and a newline always end
   a sentence. Rules, in order, for a dot followed by whitespace or the end:
   - no whitespace after it ("4.77", "U.S", "a.b"): not an end;
   - an ellipsis ends a sentence unless a lowercase word follows;
   - a domain or file name ("nasa.gov", "report.pdf"): an end;
   - a dotted abbreviation ("U.S.", "a.m.", "e.g."): "e.g." / "i.e." never end; the others end only before
     a word that plainly starts a sentence ("The", "He", ...), or the end of the text; a.m./p.m. before any capital;
   - a title ("Mr.", "Dr.", "St."): never an end; "etc.", "Inc.", month names: an end before a capital;
   - a single capital letter: "I." always ends; any other is an initial ("J. Smith") only when a name
     follows - a capitalised word that is not a common sentence starter ("Plan B. Next." ends);
   - "No." / "Vol." / "Fig." / "Apt." before a digit: not an end;
   - any other word before a lowercase word ("Dept. of Health"): not an end. Only a bounded window around the dot
     is read, so the cost is linear in the text. */
const HARD_ABBREVIATIONS = new Set(['mr', 'mrs', 'ms', 'mx', 'dr', 'prof', 'sr', 'jr', 'st', 'mt', 'vs', 'cf', 'gen', 'col', 'lt', 'sgt', 'capt', 'rep', 'sen', 'gov', 'rev', 'hon']);
const SOFT_ABBREVIATIONS = new Set(['etc', 'inc', 'ltd', 'co', 'corp', 'approx', 'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec']);
const NUMBERED = new Set(['no', 'nos', 'vol', 'fig', 'p', 'pp', 'ch', 'art', 'sec', 'apt', 'ste', 'rm', 'bldg', 'dept']);
const WINDOW = 64; // a word longer than this is never an abbreviation: only this much around a dot is read
const STARTERS = new Set(['The', 'A', 'An', 'This', 'That', 'These', 'Those', 'It', 'Its', 'He', 'She', 'They', 'We', 'You', 'I', 'There', 'Here', 'Then', 'Next', 'Also', 'And', 'But', 'So', 'Or', 'If', 'When', 'While', 'After', 'Before', 'In', 'On', 'At', 'For', 'As', 'By', 'With', 'From', 'Once', 'Now', 'However', 'Still', 'Yet', 'Not', 'No', 'Yes', 'What', 'Why', 'How', 'Who', 'Where', 'One', 'Some', 'Many', 'Most', 'All', 'Each', 'His', 'Her', 'Their', 'Our', 'My', 'Your']);
const TERMINATORS = /^[.!?…。！？]+/u;
const DOMAIN = /^[\p{L}\d-]+(\.[\p{L}\d-]+)*\.\p{Ll}{2,}$/u;

function endsSentence(text, match) {
  const lead = match[0];
  if (lead.startsWith(String.fromCharCode(10))) return true;
  const core = TERMINATORS.exec(lead)[0];
  if (/[!?。！？]/u.test(core)) return true;
  const after = match.index + lead.length;
  if (after < text.length && !/\s$/u.test(lead)) return false; // "4.77", "U.S.", "a.b": no space after the dot
  const ahead = text.slice(after, after + WINDOW + WINDOW);
  const nextWord = /^\s*([\p{L}\p{N}]+)/u.exec(ahead)?.[1] ?? '';
  const next = nextWord[0] ?? '';
  if (core.length > 1 || core === '…') return !/\p{Ll}/u.test(next); // an ellipsis before a lowercase word goes on
  if (lead.includes(String.fromCharCode(10))) return true; // the dot ends the line
  const word = /([\p{L}\d][\p{L}\d.-]*)$/u.exec(text.slice(Math.max(0, match.index - WINDOW), match.index))?.[1] ?? '';
  if (!word) return true;
  const lower = word.toLowerCase();
  if (word.includes('.')) {
    if (DOMAIN.test(word)) return true; // "nasa.gov. Next", "report.pdf. Then"
    if (['e.g', 'i.e', 'c.f'].includes(lower)) return false;
    if (['a.m', 'p.m'].includes(lower)) return !next || /\p{Lu}/u.test(next);
    return !next || STARTERS.has(nextWord); // "the U.S. The ..." ends; "the U.S. Army" does not
  }
  if (/^\p{Lu}$/u.test(word)) {
    if (word === 'I') return true;
    if (nextWord.length === 1 && /\p{Lu}/u.test(nextWord) && /^\s*\p{Lu}\./u.test(ahead)) return false; // "J. K. Rowling"
    return !(/^\p{Lu}\p{Ll}+$/u.test(nextWord) && !STARTERS.has(nextWord)); // "J. Smith" is an initial
  }
  if (HARD_ABBREVIATIONS.has(lower)) return false;
  if (SOFT_ABBREVIATIONS.has(lower)) return !next || /\p{Lu}/u.test(next);
  if (NUMBERED.has(lower) && /\d/u.test(next)) return false; // "No. 5"
  return !/\p{Ll}/u.test(next); // an unlisted abbreviation before a lowercase word ("Dept. of Health") goes on
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
