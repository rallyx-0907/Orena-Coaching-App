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
