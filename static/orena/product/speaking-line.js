/* A spoken line as tappable units, and where an assessed word sits inside it. Moved (not copied,
   D-091 migration) out of `ui/speaking-workspace-line.js`, which now imports these back - the old
   Speaking room and the new `screens/speak`/`screens/compare` both tokenize a line the same way,
   and neither should own the other's copy. No DOM, no markup: both functions were already
   presentation-free (the old file's own `esc()`/HTML building lives in its `sentenceHtml`, not
   here). */

const isHan = (text) => /^\p{Script=Han}$/u.test(text);

/* Chinese: one unit per Han character, and a run of Latin letters or digits inside the line (a name, "Vector")
   is one word, not one cell per letter (L-03). Other languages: one unit per word. Punctuation and spaces stay as
   they are written. Each unit knows its character range, so an assessed word can be laid over it to mark the ones
   a provider flagged. */
const isWordChar = (ch) => /^[\p{L}\p{N}]$/u.test(ch);

export function lineUnits(text, language) {
  const units = [];
  const value = String(text || '');
  if (language === 'zh') {
    let at = 0;
    let run = null; // the Latin/digit word being gathered
    const close = () => {
      if (run) units.push(run);
      run = null;
    };
    for (const ch of value) {
      if (isHan(ch)) {
        close();
        units.push({ text: ch, start: at, end: at + ch.length, unit: true });
      } else if (isWordChar(ch)) {
        if (!run) run = { text: '', start: at, end: at, unit: true };
        run.text += ch;
        run.end = at + ch.length;
      } else {
        close();
        units.push({ text: ch, start: at, end: at + ch.length, unit: false });
      }
      at += ch.length;
    }
    close();
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
