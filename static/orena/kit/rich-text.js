/* Orena's written answers, read as the learner should see them (LEX-006): the Markdown a reply carries -
   headings, bold, italic, lists, quotes, inline code and web links - rendered as their meaning, never as the
   syntax. Everything is escaped first (kit/html.js); only the markup made here is trusted.

   A link that is not a web link (`command:navigate?{…}` and the like) is not shown at all - neither its label nor
   its payload: the action it names is offered as a real, named action card beside the answer
   (AGENT_CONTRACT §4 actions), not as link text.

   While a reply streams, a bold or italic marker whose closing half has not arrived yet is held back, so the
   learner never sees a stray `**` that the next chunk would have closed. */

import { raw, esc } from './html.js';

const WEB_LINK = /^(https?:\/\/|mailto:)/i;

/* `[label](target)` with a balanced target, found by scanning rather than one regex: a payload may hold
   brackets, braces and quotes. Returns [{ type: 'text'|'link', … }]. */
function splitLinks(text) {
  const parts = [];
  let at = 0;
  let cursor = 0;
  while (cursor < text.length) {
    const open = text.indexOf('[', cursor);
    if (open < 0) break;
    const close = text.indexOf('](', open + 1);
    if (close < 0) break;
    const label = text.slice(open + 1, close);
    if (label.includes('\n') || label.includes('[')) {
      cursor = open + 1;
      continue;
    }
    let depth = 1;
    let end = close + 2;
    for (; end < text.length && depth; end += 1) {
      if (text[end] === '(') depth += 1;
      else if (text[end] === ')') depth -= 1;
      else if (text[end] === '\n') break;
    }
    if (depth) {
      cursor = open + 1;
      continue;
    }
    if (open > at) parts.push({ type: 'text', value: text.slice(at, open) });
    parts.push({ type: 'link', label, target: text.slice(close + 2, end - 1).trim() });
    at = end;
    cursor = end;
  }
  if (at < text.length) parts.push({ type: 'text', value: text.slice(at) });
  return parts;
}

/* Emphasis and code inside escaped text. `streaming` holds back an unclosed trailing marker. */
function marks(escaped, streaming) {
  let text = escaped;
  if (streaming) {
    if ((text.match(/\*\*/g) || []).length % 2) text = text.replace(/\*\*(?!.*\*\*)/s, '');
    if ((text.match(/`/g) || []).length % 2) text = text.replace(/`(?!.*`)/s, '');
  }
  return text
    .replace(/`([^`\n]+)`/g, '<code class="o-rich__code">$1</code>')
    .replace(/\*\*([^*\n](?:[^\n]*?[^*\n])?)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_\n](?:[^\n]*?[^_\n])?)__/g, '<strong>$1</strong>')
    .replace(/(^|[^*\w])\*([^*\s](?:[^*\n]*?[^*\s])?)\*(?!\*)/g, '$1<em>$2</em>')
    .replace(/(^|[^_\w])_([^_\s](?:[^_\n]*?[^_\s])?)_(?![_\w])/g, '$1<em>$2</em>');
}

/* One line's inline content as markup. */
export function richInline(text, { streaming = false } = {}) {
  return raw(
    splitLinks(String(text ?? ''))
      .map((part) => {
        if (part.type === 'text') return marks(esc(part.value), streaming);
        if (!WEB_LINK.test(part.target)) return ''; // an app command is an action card, not link text
        return `<a class="o-rich__link" href="${esc(part.target)}" target="_blank" rel="noopener noreferrer">${marks(esc(part.label), false)}</a>`;
      })
      .join(''),
  );
}

const BLOCK = /^\s*(#{1,6}\s|[-*+•]\s|\d+[.)]\s|>\s?)/m;

/* Whether a text needs block layout (headings, lists, quotes or more than one paragraph). */
export function hasBlocks(text) {
  const value = String(text ?? '');
  return BLOCK.test(value) || /\n/.test(value.trim());
}

/* A whole answer as blocks: headings, lists (bulleted and numbered, nested to any depth by indentation), quotes and
   paragraphs; a single line break inside a paragraph stays a line break.

   Lists follow CommonMark closely enough for a tutor's answer (LEX-006): an item's depth is its marker's indent;
   an item may be only a marker ("1." with its content on the indented lines under it); a plain line right under
   an item continues it; a blank line between items does not end the list - only a line back at the margin that is
   not a list item does. So a numbered example keeps its number and holds its reading and translation, however the
   answer nests them. */
const LIST_LINE = /^([ \t]*)([-*+•]|\d+[.)])(?:[ \t]+(.*))?$/;
const indentOf = (space) => [...space].reduce((width, ch) => width + (ch === '\t' ? 4 : 1), 0);

export function richText(text, { streaming = false } = {}) {
  const lines = String(text ?? '').replace(/\r\n?/g, '\n').split('\n');
  const out = [];
  let paragraph = [];
  let quote = [];
  // The open lists, outermost first: { indent, tag, start, items: [{ lines: [], children: [list] }] }.
  let stack = [];
  let roots = [];
  let blankInList = false;

  const inline = (line) => richInline(line, { streaming });
  const renderList = (list) => {
    const start = list.tag === 'ol' && list.start > 1 ? ` start="${list.start}"` : '';
    const items = list.items.map((item) => `<li>${item.lines.map(inline).join('<br>')}${item.children.map(renderList).join('')}</li>`);
    return `<${list.tag} class="o-rich__list"${start}>${items.join('')}</${list.tag}>`;
  };
  const flushParagraph = () => {
    if (paragraph.length) out.push(`<p class="o-rich__p">${paragraph.map(inline).join('<br>')}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    for (const list of roots) out.push(renderList(list));
    roots = [];
    stack = [];
    blankInList = false;
  };
  const flushQuote = () => {
    if (quote.length) out.push(`<blockquote class="o-rich__quote">${quote.map(inline).join('<br>')}</blockquote>`);
    quote = [];
  };
  const flush = () => {
    flushParagraph();
    flushList();
    flushQuote();
  };
  const deepestItem = () => {
    const list = stack[stack.length - 1];
    return list ? list.items[list.items.length - 1] : null;
  };

  for (const line of lines) {
    const heading = /^\s*(#{1,6})\s+(.*)$/.exec(line);
    const listLine = LIST_LINE.exec(line);
    const quoted = /^\s*>\s?(.*)$/.exec(line);
    if (!line.trim()) {
      if (stack.length) blankInList = true;
      else {
        flushParagraph();
        flushQuote();
      }
      continue;
    }
    if (heading) {
      flush();
      // A real heading element (LEX-006): # to ### is the answer's own heading, #### and below a sub-heading.
      const level = heading[1].length <= 3 ? 3 : 4;
      out.push(`<h${level} class="o-rich__h o-rich__h${level}">${richInline(heading[2], { streaming })}</h${level}>`);
      continue;
    }
    if (listLine) {
      flushParagraph();
      flushQuote();
      const indent = indentOf(listLine[1]);
      const marker = listLine[2];
      const tag = /\d/.test(marker) ? 'ol' : 'ul';
      const content = (listLine[3] || '').trim();
      // Close the lists deeper than this line.
      while (stack.length && stack[stack.length - 1].indent > indent) stack.pop();
      let list = stack[stack.length - 1];
      if (!list || indent > list.indent) {
        // A new, deeper list: under the last item of the list it sits in, or a new top-level list.
        list = { indent, tag, start: tag === 'ol' ? Number.parseInt(marker, 10) : 1, items: [] };
        const parent = deepestItem();
        if (parent) parent.children.push(list);
        else roots.push(list);
        stack.push(list);
      } else if (list.tag !== tag) {
        // The same depth, the other kind of list: a sibling list beside it.
        const sibling = { indent, tag, start: tag === 'ol' ? Number.parseInt(marker, 10) : 1, items: [] };
        stack.pop();
        const parent = deepestItem();
        if (parent) parent.children.push(sibling);
        else roots.push(sibling);
        stack.push(sibling);
        list = sibling;
      }
      list.items.push({ lines: content ? [content] : [], children: [] });
      blankInList = false;
      continue;
    }
    if (stack.length) {
      const indented = /^[ \t]{2,}/.test(line);
      if (!blankInList || indented) {
        // A plain line under an item continues it (lazy continuation), even across a blank line when indented.
        deepestItem().lines.push(line.trim());
        blankInList = false;
        continue;
      }
      flushList();
    }
    if (quoted) {
      flushParagraph();
      quote.push(quoted[1]);
    } else {
      flushQuote();
      paragraph.push(line.trim());
    }
  }
  flush();
  return raw(`<div class="o-rich">${out.join('')}</div>`);
}

/* The same answer as plain words, for the voice: no syntax read aloud, no command link. */
export function plainText(text) {
  return splitLinks(String(text ?? ''))
    .map((part) => (part.type === 'text' ? part.value : WEB_LINK.test(part.target) ? part.label : ''))
    .join('')
    .replace(/^\s*(#{1,6}|[-*+•]|\d+[.)]|>)\s+/gm, '')
    .replace(/(\*\*|__|`)/g, '')
    .replace(/(^|\s)[*_](\S)/g, '$1$2')
    .replace(/(\S)[*_](?=\s|$|[.,;:!?])/g, '$1')
    .replace(/[ \t]+\n/g, '\n')
    .trim();
}

/* A whole reply as one Markdown document, whatever its language runs (LEX-006). The server splits a reply into
   segments by language (AGENT_CONTRACT §5.1), so one Markdown line - "1. **Hanzi:** 我喜欢吃花生。", or a
   heading naming a Chinese word - arrives in several segments. Rendered one by one they broke apart (an empty
   numbered item, an orphan sub-list, a heading cut in two). The segments are joined first; each run in another
   language than the reply's own (and each `reference` segment) is wrapped in invisible private-use markers that
   survive the Markdown pass, and become `<span lang>` afterwards. A marked run never holds a line break, so its
   span always closes where it opened. Returns { lang: the reply's own language, markup }. */
const RUN_OPEN = '\uE000';
const RUN_CLOSE = '\uE001';
const RUN_BASE = 0xe100;

export function richSegments(segments, { streaming = false, langOf = (segment) => segment.lang, refClass = '' } = {}) {
  const all = (Array.isArray(segments) ? segments : []).filter((segment) => segment && String(segment.text ?? ''));
  // A `reference` segment is not part of the prose: the server sends it after the answer, a word to hear
  // (add_reference). Joined into the document it ran on from the last sentence ("…。花生"), so it stands on its
  // own line under the answer instead.
  const references = all.filter((segment) => segment.voice_style === 'reference');
  const list = all.filter((segment) => segment.voice_style !== 'reference');
  const own = (list[0] || all[0])?.lang || '';
  const runs = [];
  const joined = list
    .map((segment) => {
      const text = String(segment.text);
      if (!segment.lang || segment.lang === own || text.includes('\n')) return text;
      runs.push(segment);
      return RUN_OPEN + String.fromCharCode(RUN_BASE + runs.length - 1) + text + RUN_CLOSE;
    })
    .join('');
  // With a reference line to add, the answer is laid out as blocks so the line has a place under it.
  const body = String(hasBlocks(joined) || references.length ? richText(joined, { streaming }) : richInline(joined, { streaming }));
  const html = body
    .replace(new RegExp(`${RUN_OPEN}([\\uE100-\\uEFFF])`, 'g'), (whole, code) => {
      const segment = runs[code.charCodeAt(0) - RUN_BASE];
      if (!segment) return '';
      const cls = segment.voice_style === 'reference' && refClass ? ` class="${esc(refClass)}"` : '';
      return `<span lang="${esc(langOf(segment))}"${cls}>`;
    })
    .replace(new RegExp(RUN_CLOSE, 'g'), '</span>');
  const refs = references.length
    ? `<p class="o-rich__p o-rich__refs">${references
        .map((segment) => `<span lang="${esc(langOf(segment))}"${refClass ? ` class="${esc(refClass)}"` : ''}>${esc(segment.text)}</span>`)
        .join(' ')}</p>`
    : '';
  return { lang: own, markup: raw(refs && html ? html.replace(/<\/div>$/, `${refs}</div>`) : html || refs) };
}

