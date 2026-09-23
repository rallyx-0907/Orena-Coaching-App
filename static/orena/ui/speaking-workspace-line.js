/* The line as it is drawn in the Speaking views: tappable units, the provider's flagged words
   marked, a word being practised alone lit. Shared by the workspace and its other views. */
import { esc } from './html.js';

const isHan = (text) => /^\p{Script=Han}$/u.test(text);

/* --- The line as tappable units ---------------------------------------------------------------
   Chinese: one unit per Han character. Other languages: one unit per word. Punctuation and spaces
   stay as they are written. Each unit knows its character range, so the provider's words can be
   laid over it to mark the ones it flagged. */
export function lineUnits(text, language) {
  const units = [];
  const value = String(text || '');
  if (language === 'zh') {
    let at = 0;
    for (const ch of value) {
      units.push({ text: ch, start: at, end: at + ch.length, unit: isHan(ch) });
      at += ch.length;
    }
    return units;
  }
  const pattern = /[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu;
  let last = 0;
  for (const match of value.matchAll(pattern)) {
    if (match.index > last) units.push({ text: value.slice(last, match.index), start: last, end: match.index, unit: false });
    units.push({ text: match[0], start: match.index, end: match.index + match[0].length, unit: true });
    last = match.index + match[0].length;
  }
  if (last < value.length) units.push({ text: value.slice(last), start: last, end: value.length, unit: false });
  return units;
}

/* Where each assessed word sits in the line, found in order; a word that cannot be placed is not
   marked anywhere rather than marked somewhere wrong. */
export function placeWords(text, words, language) {
  const haystack = String(text || '').toLocaleLowerCase();
  let cursor = 0;
  return words.map((word) => {
    const needle = String(word.text || '').toLocaleLowerCase();
    if (!needle) return null;
    const at = haystack.indexOf(needle, cursor);
    if (at < 0) return null;
    // An English word must not be found inside a longer word.
    if (language !== 'zh') {
      const before = haystack[at - 1] || ' ';
      const after = haystack[at + needle.length] || ' ';
      if (/[\p{L}\p{N}]/u.test(before) || /[\p{L}\p{N}]/u.test(after)) return null;
    }
    cursor = at + needle.length;
    return { start: at, end: at + needle.length };
  });
}

export function sentenceHtml(text, language, view, focus = null) {
  const units = lineUnits(text, language);
  const placed = view?.measured ? placeWords(text, view.words, language) : [];
  const flagged = placed
    .map((range, index) => (range && view.words[index].flagged ? range : null))
    .filter(Boolean);
  const markOf = (unit) => {
    if (focus && unit.start < focus.end && unit.end > focus.start) return 'focus';
    const range = flagged.find((item) => unit.start < item.end && unit.end > item.start);
    return range ? `flag:${range.start}` : '';
  };
  /* A word the provider flagged is one mark, however many characters it has, as the frame marks
     it; each character or word inside stays its own tappable unit. */
  let html = '';
  let open = '';
  units.forEach((unit, index) => {
    const mark = unit.unit ? markOf(unit) : '';
    if (mark !== open) {
      if (open) html += '</span>';
      if (mark) html += `<span class="${mark === 'focus' ? 'sp-tok--focus' : 'sp-tok--flag'}">`;
      open = mark;
    }
    html += unit.unit ? `<span class="sp-tok" data-sp-tok="${index}">${esc(unit.text)}</span>` : esc(unit.text);
  });
  if (open) html += '</span>';
  return html;
}
