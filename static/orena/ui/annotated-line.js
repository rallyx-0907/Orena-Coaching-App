import { esc } from './html.js';
import { wordSpans } from '../capabilities/word-timeline.js';

// An optional reading lens over the canonical transcript. Annotation offsets
// are Python code points; playback offsets are JS string indices. Convert once
// and keep timed spans inside the tokens so Follow continues to work.
export function annotatedLine(segment, result, { pinyin = false, labels = {} } = {}) {
  const text = segment.original_text;
  if (result?.text !== text.trim() || !Array.isArray(result.annotations) || !result.annotations.length) return null;
  const source = Array.from(result.text);
  const leading = text.length - text.trimStart().length;
  const spans = wordSpans(segment) || [];
  let cursor = 0, html = '', count = 0;
  const timed = (start, end) => {
    let at = start, out = '';
    for (const [index, span] of spans.entries()) {
      const a = Math.max(start, span.start), b = Math.min(end, span.end);
      if (a >= b) continue;
      out += esc(text.slice(at, a));
      out += `<span class="word" data-word="${index}">${esc(text.slice(a, b))}</span>`;
      at = b;
    }
    return out + esc(text.slice(at, end));
  };
  for (const token of result.annotations) {
    if (!Number.isInteger(token.start) || !Number.isInteger(token.end) ||
      token.start < 0 || token.end <= token.start || token.end > source.length ||
      source.slice(token.start, token.end).join('') !== token.fragment) continue;
    const start = leading + source.slice(0, token.start).join('').length;
    const end = leading + source.slice(0, token.end).join('').length;
    if (start < cursor) continue;
    html += timed(cursor, start);
    const reading = pinyin && result.reading_aid === 'pinyin' && token.pronunciation
      ? ` data-reading="${esc(token.pronunciation)}"` : '';
    const role = ['noun','proper_noun'].includes(token.pos) ? 'noun' : token.pos === 'verb' ? 'verb' : ['adjective','adverb'].includes(token.pos) ? 'detail' : '';
    const hint = labels[role] ? ` title="${esc(labels[role])}" aria-description="${esc(labels[role])}"` : '';
    /* A token is marked-up text, not a control.

       It used to be a <button>, from when the line being looked at sat in a
       panel of its own. The line is now the transcript row, and the row is the
       control that takes the learner to it - so a button here would be a
       button inside a button, which is not valid, and an inline-block box in
       the middle of a sentence, which wrapped the line differently and cost it
       a whole extra row the moment the voice arrived. Pointing at a word is
       answered by the shared lexical layer from where the pointer landed
       (`ui/lexical.js`), which needs text, not a control. */
    html += `<span class="token" data-token="${esc(text.slice(start,end))}" data-pos="${esc(token.pos || 'other')}"${reading}${hint}><span class="token-text">${timed(start,end)}</span></span>`;
    cursor = end;
    count++;
  }
  return count ? html + timed(cursor, text.length) : null;
}
