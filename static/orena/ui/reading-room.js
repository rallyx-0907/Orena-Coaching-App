/* The reader, as markup and rules. Reading first; learning tools on demand.

   A text is read as continuous prose in one column: headings where the text
   has headings, paragraphs as the text wrote them, nothing interleaved. Tools
   appear only for something the learner selected, and only the tools that make
   sense for what was selected. Everything here is a pure function of its
   arguments; `reader.js` owns the DOM, the requests and the events. */
import { esc, safeExternal } from './html.js';
import { symbol } from './symbols.js';
import { link } from '../product/intent.js';
import {
  READER_DEFAULTS,
  CHOICES,
  READER_SIZE,
  LEADING,
  MEASURE,
  readerSettings,
  readerPresentation,
} from '../product/reader-settings.js';
import {
  LOOKUP_LIMITS,
  TRANSLATE_LIMITS,
  EXPLAIN_LIMITS,
  blocksFrom as sharedBlocksFrom,
  chapterNeighbours as sharedChapterNeighbours,
  selectionKind as sharedSelectionKind,
  sentenceAround as sharedSentenceAround,
  sentenceSpans,
} from '../product/reader-text.js';
/* Re-exported unchanged: ui/reader.js, ui/lexical.js and
   scripts/test_orena_reading_room.mjs import these names from this module. The values and the
   clamping now live in product/reader-settings.js (moved there so the new Settings screen can use
   them without importing old UI); nothing about them changed. */
export { READER_DEFAULTS, READER_SIZE, readerSettings, readerPresentation };

/* What each endpoint accepts, named once so a request is shaped to fit rather
   than refused. Moved to product/reader-text.js (moved there so the new Reader screen can shape
   text and selections without importing old UI); re-exported unchanged. */
export { LOOKUP_LIMITS, TRANSLATE_LIMITS, EXPLAIN_LIMITS };

const lines = (value) => esc(value).replace(/\n/g, '<br>');
const tidy = (value) =>
  String(value ?? '')
    .split('\n')
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .join('\n');
const flat = (value) => tidy(value).replace(/\n/g, ' ').toLowerCase();

/* --- Content ------------------------------------------------------------- */

/* Moved to product/reader-text.js (so the new Reader screen can shape a document's text without
   importing old UI); re-exported unchanged for this module's own callers below. */
export const blocksFrom = sharedBlocksFrom;

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

/* Moved to product/reader-text.js (so the new Reader screen can find chapter neighbours without
   importing old UI); re-exported unchanged. */
export const chapterNeighbours = sharedChapterNeighbours;

/* The bar names the chapter and nothing more - "chương 3" - because that
   is what the frame writes there, beside what is left to read. How many
   chapters there are in all is the book's page, where the list is. */
export const chapterLabel = (c, index) =>
  String(c.readerChapter || '').replace('{n}', String(index + 1));

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
/* READER_DEFAULTS, CHOICES, READER_SIZE, LEADING, MEASURE, readerSettings() and
   readerPresentation() now live in product/reader-settings.js (imported and re-exported above). */

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

/* Moved to product/reader-text.js (so the new Reader screen can classify a selection without
   importing old UI); re-exported unchanged. */
export const selectionKind = sharedSelectionKind;

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

/* sentenceSpans now lives in product/reader-text.js (exported there for the new Reader screen's
   own sentence-level markup); chunkSpans below still needs it, so it is imported, not redefined. */

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

// Moved to product/reader-text.js (so the new Reader screen can find a selection's sentence
// context without importing old UI); re-exported unchanged.
export const sentenceAround = sharedSentenceAround;

