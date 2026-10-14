/* The word under a pointer, without a tagger: one shared, DOM-free rule for every room that turns
   a character offset into a word span (capabilities/lexical.js for Reading/Listening's old rooms,
   screens/reader/lexical.js for the new Reader). Deliberately the smallest honest unit - guessing a
   longer Chinese word here would hand a lookup something the learner did not point at, so a script
   written without spaces (Han, Hiragana, Katakana) answers with exactly the one character under the
   pointer, never a guessed boundary. An alphabet is the run of letters/marks/digits (and an
   apostrophe or hyphen inside it) around the pointer.

   Moved out of capabilities/lexical.js and screens/reader/lexical.js, which had drifted into two
   copies of the same function (Wave B finish pass): both now import this one. */

export function plainWordAt(text, offset) {
  const at = Math.min(Math.max(0, offset), Math.max(0, text.length - 1));
  if (!/[\p{L}\p{N}]/u.test(text[at] || '')) return null;
  if (/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u.test(text[at]))
    return { start: at, end: at + 1 };
  let start = at;
  let end = at + 1;
  const wordish = /[\p{L}\p{M}\p{N}'’-]/u;
  while (start > 0 && wordish.test(text[start - 1])) start -= 1;
  while (end < text.length && wordish.test(text[end])) end += 1;
  return { start, end };
}

/* The tagged word that covers character offset `at` of a sentence's text, as `{ text, start, end }`, or null when
   there are no tokens or none covers it. A tap on a script written without spaces that was not tagged yet (the
   tagger answered late, or not at all) names one character; once the tagger has segmented the sentence, the word
   under that character is what the learner pointed at. `expect` (the tapped character) guards a stale offset. */
export function wordSpanAt(text, tokens, at, expect = '') {
  const value = String(text ?? '');
  if (!Array.isArray(tokens) || !Number.isInteger(at) || at < 0 || at >= value.length) return null;
  if (expect && value.slice(at, at + expect.length) !== expect) return null;
  for (const token of tokens) {
    if (token.start <= at && at < token.end && token.end <= value.length && token.end > token.start) {
      return { text: value.slice(token.start, token.end), start: token.start, end: token.end };
    }
  }
  return null;
}
