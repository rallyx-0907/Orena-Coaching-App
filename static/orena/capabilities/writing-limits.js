/* How much writing Orena accepts, in the browser.

   The same three numbers as `writing_coach/writing_limits.py`, which is the
   product decision; a gate fails if the two ever drift. The browser is not
   where this is enforced - the server decides, and would decide the same thing
   if this file did not exist - but a learner who pastes a book should be told
   so before the page spends a second laying it out and a request spends a
   round trip being refused.

   Nothing here truncates. A paste that does not fit is refused whole, and what
   the learner already wrote is left exactly as it was: silently keeping the
   first twelve thousand characters of somebody's document is a worse answer
   than saying it will not fit. */

export const MAX_CHARACTERS = 12000;
export const MAX_BYTES = 60000;
export const MAX_LINES = 1000;

const encoder = typeof TextEncoder === 'function' ? new TextEncoder() : null;

/* Code points, not UTF-16 units: an emoji is one character to a learner and
   two to `String.length`, and the server counts it the way a learner does. A
   long string is measured without building an array of every character. */
function codePoints(value) {
  let count = 0;
  for (let index = 0; index < value.length; index += 1) {
    count += 1;
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff && index + 1 < value.length) {
      const next = value.charCodeAt(index + 1);
      if (next >= 0xdc00 && next <= 0xdfff) index += 1;
    }
  }
  return count;
}

function utf8Bytes(value) {
  if (encoder) return encoder.encode(value).length;
  // A browser without TextEncoder still gets an honest count.
  let bytes = 0;
  for (const character of value) {
    const code = character.codePointAt(0);
    bytes += code < 0x80 ? 1 : code < 0x800 ? 2 : code < 0x10000 ? 3 : 4;
  }
  return bytes;
}

/* What a piece of writing measures, and which bound it breaks if any. The
   shape mirrors the server's `Measurement` so a message can be written once. */
export function measureWriting(text) {
  const value = String(text ?? '');
  const characters = codePoints(value);
  const bytes = utf8Bytes(value);
  // \r\n is one separator, so writing from a Windows editor is not penalised.
  const lines = value ? value.replace(/\r\n/g, '\n').split('\n').length : 0;
  const limitExceeded =
    characters > MAX_CHARACTERS
      ? 'characters'
      : bytes > MAX_BYTES
        ? 'bytes'
        : lines > MAX_LINES
          ? 'lines'
          : '';
  return { characters, bytes, lines, limitExceeded, withinLimits: !limitExceeded };
}

export const fitsWriting = (text) => measureWriting(text).withinLimits;

/* Would this edit fit?

   Asked before the edit happens, with the text the box would end up holding,
   so an enormous paste is refused instead of being inserted and then
   complained about. The caller supplies the current value and what the edit
   would put in place of the selection - which is exactly what a paste is. */
export function editWouldFit(current, replacement, selectionStart, selectionEnd) {
  const value = String(current ?? '');
  const next =
    value.slice(0, selectionStart) + String(replacement ?? '') + value.slice(selectionEnd);
  return measureWriting(next);
}
