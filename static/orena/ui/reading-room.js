/* The reader, as markup and rules. Reading first; learning tools on demand.

   A text is read as continuous prose in one column: headings where the text
   has headings, paragraphs as the text wrote them, nothing interleaved. Tools
   appear only for something the learner selected, and only the tools that make
   sense for what was selected. Everything here is a pure function of its
   arguments; `reader.js` owns the DOM, the requests and the events. */
import { esc, safeExternal } from './html.js';
import { symbol } from './symbols.js';
import { link } from '../product/intent.js';

/* What each endpoint accepts, named once so a request is shaped to fit rather
   than refused. */
export const LOOKUP_LIMITS = Object.freeze({ selection: 80, context: 1200 });
export const TRANSLATE_LIMITS = Object.freeze({ text: 5900 });
export const EXPLAIN_LIMITS = Object.freeze({ selection: 1600, context: 2400 });

const lines = (value) => esc(value).replace(/\n/g, '<br>');
const tidy = (value) =>
  String(value ?? '')
    .split('\n')
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .join('\n');
const flat = (value) => tidy(value).replace(/\n/g, ' ').toLowerCase();

/* --- Content ------------------------------------------------------------- */

/* The blocks a text is read as. A structured chapter keeps its headings,
   paragraphs and section breaks; a text that only has paragraphs reads as
   paragraphs. Anything else - an unknown block, an empty one, a break with
   nothing on one side of it - is dropped rather than shown. */
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

// A paragraph's text, escaped, with its own line breaks and an optional mark.
export function paragraphHtml(text, mark = null) {
  const value = String(text ?? '');
  if (
    !mark ||
    !Number.isInteger(mark.start) ||
    !Number.isInteger(mark.end) ||
    mark.end <= mark.start
  )
    return lines(value);
  const start = Math.max(0, mark.start);
  const end = Math.min(value.length, mark.end);
  return `${lines(value.slice(0, start))}<mark>${lines(value.slice(start, end))}</mark>${lines(value.slice(end))}`;
}

/* The page. A chapter whose first block is its own heading uses that heading
   as the page title rather than printing the title twice. */
export function readerArticleHtml(c, { title, language, blocks, marks = new Map() }) {
  const first = blocks[0];
  /* An imported chapter often opens by repeating its own title, sometimes as a
     heading and sometimes as a plain line. Either way it is the same words
     twice at the top of the page: the first is promoted to the page title, and
     a plain line saying the same thing is dropped rather than printed under
     the heading it duplicates. */
  const firstIsTitle = Boolean(first) && first.type !== 'break' && flat(first.text) === flat(title);
  const headingIsTitle = firstIsTitle && first.type === 'heading';
  const duplicateLine = firstIsTitle && first.type === 'paragraph';
  let html = `<article class="reader-page" lang="${esc(language)}" data-reader-page>`;
  if (!headingIsTitle) html += `<h1 class="reader-title">${lines(tidy(title))}</h1>`;
  blocks.forEach((block, index) => {
    if (index === 0 && duplicateLine) return;
    if (block.type === 'break') {
      html += '<hr class="reader-break">';
    } else if (block.type === 'heading') {
      if (index === 0 && headingIsTitle)
        html += `<h1 class="reader-title" data-block="0">${lines(block.text)}</h1>`;
      else {
        const level = Math.max(2, block.level);
        html += `<h${level} class="reader-heading" data-block="${index}">${lines(block.text)}</h${level}>`;
      }
    } else {
      html += `<p data-block="${index}">${paragraphHtml(block.text, marks.get(index))}</p>`;
    }
  });
  return `${html}</article>`;
}

/* --- Chapters ------------------------------------------------------------ */

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

export const chapterLabel = (c, index, total) =>
  String(c.readerChapterOf || '')
    .replace('{current}', String(index + 1))
    .replace('{total}', String(total));

export const progressLabel = (c, percent) =>
  String(c.readerProgress || '').replace('{percent}', String(percent));

export const chapterHref = (bookId, chapterId) =>
  link('encounter', { id: `book:${bookId}/${chapterId}`, intent: 'reading' });

/* The table of contents, with the chapter being read marked, and what is known
   about where the book came from - beside the text, never inside it. */
export function tocHtml(c, { bookId, chapters, currentId, provenance = null }) {
  const items = byPosition(chapters)
    .map((chapter) => {
      const current = String(chapter.id) === String(currentId);
      return `<li><a href="${esc(chapterHref(bookId, chapter.id))}"${current ? ' aria-current="true"' : ''}>${esc(tidy(chapter.title).replace(/\n/g, ' '))}</a></li>`;
    })
    .join('');
  const url = safeExternal(String(provenance?.source_url || ''));
  const publisher = String(provenance?.publisher || '').trim();
  const about =
    url || publisher
      ? `<section class="reader-about"><h3>${esc(c.readerAbout)}</h3><dl>${publisher ? `<dt>${esc(c.readerPublisher)}</dt><dd>${esc(publisher)}</dd>` : ''}${url ? `<dt>${esc(c.readerSource)}</dt><dd><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a></dd>` : ''}</dl></section>`
      : '';
  return `<ol class="reader-toc">${items}</ol>${about}`;
}

/* --- Settings ------------------------------------------------------------ */

export const READER_DEFAULTS = Object.freeze({
  size: 1,
  font: 'serif',
  spacing: 'normal',
  width: 'medium',
});
const CHOICES = {
  font: ['serif', 'sans'],
  spacing: ['compact', 'normal', 'relaxed'],
  width: ['narrow', 'medium', 'wide'],
};
export const READER_SIZE = Object.freeze({ min: 0.85, max: 1.4, step: 0.05 });
const LEADING = { compact: 1.55, normal: 1.75, relaxed: 2 };
const MEASURE = { narrow: '36rem', medium: '44rem', wide: '50rem' };
export function readerSettings(raw) {
  const value = raw && typeof raw === 'object' ? raw : {};
  const settings = { ...READER_DEFAULTS };
  const size = Number(value.size);
  if (Number.isFinite(size))
    settings.size =
      Math.round(Math.min(READER_SIZE.max, Math.max(READER_SIZE.min, size)) * 100) / 100;
  for (const [key, allowed] of Object.entries(CHOICES))
    if (allowed.includes(value[key])) settings[key] = value[key];
  return settings;
}

export function readerPresentation(settings) {
  const s = readerSettings(settings);
  return {
    style: `--reader-scale: ${s.size}; --reader-leading: ${LEADING[s.spacing]}; --reader-measure: ${MEASURE[s.width]};`,
    font: s.font,
  };
}

const choiceRow = (c, label, key, current, labels) =>
  `<div class="reader-setting"><span class="reader-setting__label">${esc(label)}</span><div class="reader-segmented">${CHOICES[key]
    .map(
      (value) =>
        `<button type="button" data-reader-${key}="${value}" aria-pressed="${value === current ? 'true' : 'false'}"><span>${esc(labels[value])}</span></button>`,
    )
    .join('')}</div></div>`;

export function settingsHtml(c, settings) {
  const s = readerSettings(settings);
  return `<div class="reader-settings" role="group" aria-label="${esc(c.readerSettings)}"><div class="reader-setting"><span class="reader-setting__label">${esc(c.readerTextSize)}</span><div class="reader-stepper"><button type="button" data-reader-size="-1" aria-label="${esc(c.readerSmaller)}"${s.size <= READER_SIZE.min ? ' disabled' : ''}>A−</button><output aria-live="polite">${Math.round(s.size * 100)}%</output><button type="button" data-reader-size="1" aria-label="${esc(c.readerLarger)}"${s.size >= READER_SIZE.max ? ' disabled' : ''}>A+</button></div></div>${choiceRow(c, c.readerTypeface, 'font', s.font, { serif: c.readerSerif, sans: c.readerSans })}${choiceRow(c, c.readerSpacing, 'spacing', s.spacing, { compact: c.readerSpacingCompact, normal: c.readerSpacingNormal, relaxed: c.readerSpacingRelaxed })}${choiceRow(c, c.readerWidth, 'width', s.width, { narrow: c.readerWidthNarrow, medium: c.readerWidthMedium, wide: c.readerWidthWide })}</div>`;
}

/* --- Selection ----------------------------------------------------------- */

/* What the learner selected: a word (looked up), a phrase (translated, and
   worth keeping), or a passage (translated or explained). Too much to act on
   is nothing. */
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

// A kept word carries its meaning and the sentence it was met in.
export function keepPayload({ selection, result = {}, context = '', title = '' }) {
  const found = result || {};
  const meaning = (found.meanings || []).find((item) => item?.text)?.text || found.translation || '';
  return {
    word: String(selection || '').trim().slice(0, 180),
    phonetic: String(found.pronunciation || '').slice(0, 180),
    part_of_speech: String(found.part_of_speech || '').slice(0, 120),
    definition: String(meaning).slice(0, 2400),
    source_kind: 'reading',
    source_fragment: String(context || '').slice(0, 1200),
    focus_note: String(title || '').slice(0, 2400),
  };
}

/* --- Context ------------------------------------------------------------- */

const SENTENCE_END = /[.!?…。！？]+["'”’」』）)\]]*\s*|\n+/gu;

function sentenceSpans(text) {
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

function chunkSpans(text, max) {
  const chunks = [];
  let current = null;
  const push = (start, end) => {
    if (current && end - current.start <= max) {
      current.end = end;
      return;
    }
    if (current) chunks.push(current);
    current = { start, end };
  };
  for (const span of sentenceSpans(text)) {
    let at = span.start;
    while (span.end - at > max) {
      const space = text.slice(at, at + max).lastIndexOf(' ');
      let cut = space > max / 2 ? at + space + 1 : at + max;
      if (/[\uD800-\uDBFF]/.test(text[cut - 1])) cut -= 1;
      push(at, cut);
      at = cut;
    }
    push(at, span.end);
  }
  if (current) chunks.push(current);
  return chunks;
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

