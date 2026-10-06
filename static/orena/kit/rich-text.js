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

/* A whole answer as blocks: headings, lists (bulleted and numbered), quotes and paragraphs; a single line
   break inside a paragraph stays a line break. */
export function richText(text, { streaming = false } = {}) {
  const lines = String(text ?? '').replace(/\r\n?/g, '\n').split('\n');
  const out = [];
  let paragraph = [];
  // { tag: 'ul'|'ol', start, items: [{ lines: [], sub: [] }] }. An item holds its own continuation lines and an
  // indented sub-list, so a numbered example with its reading and translation is one unit (LEX-006).
  let list = null;
  let quote = [];

  const flushParagraph = () => {
    if (paragraph.length) out.push(`<p class="o-rich__p">${paragraph.map((line) => richInline(line, { streaming })).join('<br>')}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (list) {
      const items = list.items.map((item) => {
        const body = item.lines.map((line) => richInline(line, { streaming })).join('<br>');
        const sub = item.sub.length ? `<ul class="o-rich__list">${item.sub.map((line) => `<li>${richInline(line, { streaming })}</li>`).join('')}</ul>` : '';
        return `<li>${body}${sub}</li>`;
      });
      // The number the answer wrote first stands, so "2." after a break is not drawn as 1 again.
      const start = list.tag === 'ol' && list.start > 1 ? ` start="${list.start}"` : '';
      out.push(`<${list.tag} class="o-rich__list"${start}>${items.join('')}</${list.tag}>`);
    }
    list = null;
  };
  const flushQuote = () => {
    if (quote.length) out.push(`<blockquote class="o-rich__quote">${quote.map((line) => richInline(line, { streaming })).join('<br>')}</blockquote>`);
    quote = [];
  };
  const flush = () => {
    flushParagraph();
    flushList();
    flushQuote();
  };

  for (const line of lines) {
    const heading = /^\s*(#{1,6})\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*+•]\s+(.*)$/.exec(line);
    const numbered = /^\s*(\d+)[.)]\s+(.*)$/.exec(line);
    const indented = /^(\s{2,}|	)/.test(line);
    const quoted = /^\s*>\s?(.*)$/.exec(line);
    if (!line.trim()) {
      flush();
    } else if (heading) {
      flush();
      out.push(`<p class="o-rich__h">${richInline(heading[2], { streaming })}</p>`);
    } else if (list && indented && (bullet || numbered)) {
      // An indented marker under an item is that item's own sub-list.
      list.items[list.items.length - 1].sub.push(bullet ? bullet[1] : numbered[2]);
    } else if (bullet || numbered) {
      flushParagraph();
      flushQuote();
      const tag = bullet ? 'ul' : 'ol';
      if (list && list.tag !== tag) flushList();
      if (!list) list = { tag, start: numbered ? Number(numbered[1]) : 1, items: [] };
      list.items.push({ lines: [bullet ? bullet[1] : numbered[2]], sub: [] });
    } else if (quoted) {
      flushParagraph();
      flushList();
      quote.push(quoted[1]);
    } else if (list) {
      // A plain line right under an item continues it (CommonMark's lazy continuation): the example's reading
      // and translation stay with the example.
      list.items[list.items.length - 1].lines.push(line.trim());
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

