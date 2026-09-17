/* The reading room: a passage read inside its own scrolling frame, one numbered
   block per paragraph, each paragraph's meaning on demand, and every word a tap
   away from what it means in its sentence.

   Everything here is a pure function of its arguments - markup and the shape of
   requests. The encounter owns state, requests and events. Paragraphs stay the
   ones the text was written in: a block is never a sentence group the product
   invented. */
import { esc } from './html.js';
import { symbol } from './symbols.js';

/* What each endpoint accepts, named once so a request is shaped to fit rather
   than refused. Annotation takes 1200 characters and tags at most 160 words a
   call; a Chinese word is one or two characters, so Chinese chunks are shorter. */
export const ANNOTATE_LIMITS = Object.freeze({ en: 900, zh: 220 });
export const TRANSLATE_BATCH = Object.freeze({ segments: 24, chars: 5000, paragraph: 5900 });
export const EXPLAIN_LIMITS = Object.freeze({ selection: 1600, context: 2400 });
export const GLOSS_LIMITS = Object.freeze({ selection: 120, context: 1200 });

const lines = (value) => esc(value).replace(/\n/g, '<br>');

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

// Contiguous spans of whole sentences, each at most `max` long. A sentence
// longer than that is cut at the last space that fits, or at the limit for
// text written without spaces - never inside a surrogate pair.
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

/* The pieces of a paragraph to send to the shared tagger, each with where it
   starts in the paragraph. The tagger trims what it is sent, so chunks are sent
   trimmed and their offsets account for it. */
export function annotationChunks(text, language) {
  const value = String(text ?? '');
  const max = language === 'zh' ? ANNOTATE_LIMITS.zh : ANNOTATE_LIMITS.en;
  return chunkSpans(value, max).flatMap(({ start, end }) => {
    const raw = value.slice(start, end);
    const trimmed = raw.trim();
    return trimmed ? [{ start: start + (raw.length - raw.trimStart().length), text: trimmed }] : [];
  });
}

/* Tagger offsets count code points; the page indexes JavaScript strings. Only
   tokens whose fragment really sits at their offsets survive, in order. */
export function tokensFromAnnotation(chunkText, chunkStart, result) {
  if (!result || result.text !== chunkText || !Array.isArray(result.annotations)) return [];
  const points = Array.from(chunkText);
  const tokens = [];
  let cursor = 0;
  for (const token of result.annotations) {
    if (
      !Number.isInteger(token?.start) ||
      !Number.isInteger(token?.end) ||
      token.start < 0 ||
      token.end <= token.start ||
      token.end > points.length ||
      points.slice(token.start, token.end).join('') !== token.fragment
    )
      continue;
    const start = points.slice(0, token.start).join('').length;
    if (start < cursor) continue;
    const end = start + token.fragment.length;
    tokens.push({ start: chunkStart + start, end: chunkStart + end, pos: String(token.pos || 'other') });
    cursor = end;
  }
  return tokens;
}

/* A paragraph's text: escaped, its own line breaks kept, each tagged word a tap
   target, and the evidence a question pointed at marked - even when the mark
   begins inside a word. */
export function paragraphHtml(text, tokens = [], mark = null) {
  const value = String(text ?? '');
  const length = value.length;
  const range =
    mark && Number.isInteger(mark.start) && Number.isInteger(mark.end) && mark.end > mark.start
      ? { start: Math.max(0, mark.start), end: Math.min(length, mark.end) }
      : null;
  const cuts = new Set([0, length]);
  for (const token of tokens) {
    cuts.add(token.start);
    cuts.add(token.end);
  }
  if (range) {
    cuts.add(range.start);
    cuts.add(range.end);
  }
  const points = [...cuts].filter((n) => n >= 0 && n <= length).sort((a, b) => a - b);
  let html = '';
  let marked = false;
  let next = 0;
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    const inside = Boolean(range) && a >= range.start && b <= range.end;
    if (inside !== marked) {
      html += inside ? '<mark>' : '</mark>';
      marked = inside;
    }
    while (next < tokens.length && tokens[next].end <= a) next += 1;
    const token = tokens[next] && tokens[next].start <= a && b <= tokens[next].end ? tokens[next] : null;
    const piece = lines(value.slice(a, b));
    html += token
      ? `<span class="reading-word" data-start="${token.start}" data-end="${token.end}" data-pos="${esc(token.pos)}">${piece}</span>`
      : piece;
  }
  if (marked) html += '</mark>';
  return html;
}

// The sentence a selection sits in, so a meaning is asked about its own use.
export function sentenceAround(text, start, end, limit = GLOSS_LIMITS.context) {
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

// A paragraph to explain, within what the explanation accepts.
export function explainBounds(paragraph) {
  const value = String(paragraph ?? '').trim();
  if (value.length <= EXPLAIN_LIMITS.selection) return { selection: value, context: value };
  const [first] = chunkSpans(value, EXPLAIN_LIMITS.selection);
  return {
    selection: value.slice(first.start, first.end).trim(),
    context: value.slice(0, EXPLAIN_LIMITS.context).trim(),
  };
}

/* Paragraph meaning requested in turns one provider batch can hold, so the
   first meanings arrive while the rest are on their way. */
export function translationRequests(paragraphs, indices, limits = TRANSLATE_BATCH) {
  const requests = [];
  let current = null;
  let chars = 0;
  for (const index of indices) {
    const text = String(paragraphs[index] ?? '');
    if (!text.trim()) continue;
    if (
      !current ||
      current.segments.length >= limits.segments ||
      (current.segments.length && chars + text.length > limits.chars)
    ) {
      current = { segments: [], indices: [] };
      chars = 0;
      requests.push(current);
    }
    current.segments.push({ segment_id: `p${index}`, text });
    current.indices.push(index);
    chars += text.length;
  }
  return requests;
}

function meaningHtml(c, index, translation, support) {
  const state = translation?.state || 'loading';
  if (state === 'ready')
    return `<p class="reading-block__meaning" data-meaning="${index}" lang="${esc(support)}"><span class="sr-only">${esc(c.readingTranslationLabel)}: </span>${lines(translation.text)}</p>`;
  if (state === 'too_large')
    return `<p class="reading-block__meaning" data-meaning="${index}" data-state="too_large">${esc(c.readingTranslationTooLarge)}</p>`;
  if (state === 'unavailable')
    return `<p class="reading-block__meaning" data-meaning="${index}" data-state="unavailable">${esc(c.readingTranslationUnavailable)} <button type="button" class="quiet" data-retry-translate="${index}">${esc(c.retry)}</button></p>`;
  return `<p class="reading-block__meaning" data-meaning="${index}" data-state="loading" role="status">${esc(c.readingTranslating)}</p>`;
}

export function readingBlock(
  c,
  index,
  { paragraph, tokens = [], mark = null, language, support, translatable, open, translation },
) {
  const number = index + 1;
  const which = `<span class="sr-only"> · ${esc(c.readingParagraph)} ${number}</span>`;
  const translate = translatable
    ? `<button type="button" class="reading-tool" data-translate="${index}" aria-pressed="${open ? 'true' : 'false'}">${symbol('meaning', 16)}<span>${esc(open ? c.readingHideTranslation : c.readingTranslate)}</span>${which}</button>`
    : '';
  return `<div class="reading-block" data-block="${index}"><span class="reading-block__number" aria-hidden="true">${number}</span><div class="reading-block__body"><p class="reading-block__text" data-text="${index}" lang="${esc(language)}">${paragraphHtml(paragraph, tokens, mark)}</p>${open && translatable ? meaningHtml(c, index, translation, support) : ''}<div class="reading-block__tools">${translate}<button type="button" class="reading-tool" data-explain="${index}">${symbol('words', 16)}<span>${esc(c.readingExplain)}</span>${which}</button></div></div></div>`;
}

export function positionLabel(c, current, total) {
  return String(c.readingPosition || '')
    .replace('{current}', String(current))
    .replace('{total}', String(total));
}

/* The frame the passage scrolls in. The page keeps its place; the text moves
   inside its own region, so what comes after reading stays one step away. */
export function readingFrame(c, { title, blocks, after = '', total, tools = '', dialogue = false }) {
  return `<div class="reading-frame"><div class="reading-frame__bar"><span class="reading-frame__position" data-reading-position aria-label="${esc(positionLabel(c, 1, total))}">1 / ${total}</span><div class="reading-frame__tools">${tools}</div></div><div class="reading-frame__scroll" data-reading-scroll tabindex="0" role="region" aria-label="${esc(title)}"><article class="passage${dialogue ? ' dialogue' : ''}">${blocks}${after}</article></div></div>`;
}
