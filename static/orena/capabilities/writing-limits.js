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

/* --- The request minimum ----------------------------------------------------

   The other end of the range, and the same table as `writing_coach/writing_limits.py`
   (`MINIMUM_BY_LANGUAGE`, `DEFAULT_MINIMUM`). It answers "is this an attempt at
   writing at all?" and nothing more: whether an attempt is enough to grade is the
   evaluator's own question (`band_status: insufficient_evidence`), and a short
   attempt still earns its review. So it refuses only what is not writing -
   nothing, whitespace, punctuation, a stray character.

   Counted in what the learning language is written in, one row per language, so
   the same number means the same amount of writing. A code point is not that: an
   HSK 1 sentence, `我是学生。`, is five of them.

     han    Han characters. Ideographic punctuation such as 。 is not one, so
            `你好。` is two. Stated ranges, not `\p{Script=Han}`, so the server can
            state the same ones: CJK Unified Ideographs and Extension A, the
            compatibility ideographs, and Extensions B onward. Radicals are left out.
     kana_han  What Japanese is written in: the Han characters above, the iteration
            mark 々, hiragana, katakana (with the long-vowel mark ー) and halfwidth
            katakana. Japanese punctuation such as 。 and the middle dot ・ are not
            characters of writing, nor are the voicing marks, which belong to the
            kana before them.
     words  Runs of letters and digits, joined by an apostrophe or a hyphen inside
            a word, that hold at least one letter. A number alone is not a word of
            writing; punctuation, whitespace and emoji are not words. Normalised
            first, so a word typed with combining marks is one word, not two.

   `words` counts spaced text: a language written without spaces needs a row of its
   own before it is taught, since the default would count a sentence as one word.

   This is not the number a learner is shown, and it is not meant to be. The count under a
   draft (`Intl.Segmenter`, `wordCountOf` in each screen's model) and the stored `word_count`
   (`writing_unit_count` on the server) answer "how long is this piece?"; this answers "is
   it writing at all?". They part where a token is not a word of writing: a bare number is a
   word to both of those and not to this (`3 cats` shows 2 words and counts 1 here), a
   hyphenated compound is one word here and two to the Segmenter, and for Chinese the shown
   count is Segmenter words while this counts Han characters. Neither can be reused as it
   stands - the server's counter reads the request's language from its context, this is
   pure and is handed one - so the difference is stated rather than hidden, and the cases
   that pin it are in the shared fixture below.

   `tests/fixtures/writing_minimum_cases.json` states the table and the counts once;
   the server's tests and `scripts/test_orena_writing_workspace.mjs` both read it, and
   either side fails when it stops producing them. */

export const MINIMUM_BY_LANGUAGE = Object.freeze({
  en: Object.freeze({ unit: 'words', minimum: 2 }),
  zh: Object.freeze({ unit: 'han', minimum: 2 }),
  ja: Object.freeze({ unit: 'kana_han', minimum: 2 }),
});

/* What a language with no row of its own is held to. */
export const DEFAULT_MINIMUM = Object.freeze({ unit: 'words', minimum: 2 });

const HAN = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u{20000}-\u{2fa1f}\u{30000}-\u{323af}]/gu;
const KANA_HAN =
  /[\u3005\u3041-\u3096\u309d-\u309f\u30a1-\u30fa\u30fc-\u30ff\u31f0-\u31ff\uff66-\uff9d\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u{20000}-\u{2fa1f}\u{30000}-\u{323af}]/gu;
const WORD = /[\p{L}\p{N}]+(?:['\u2019-][\p{L}\p{N}]+)*/gu;
const LETTER = /\p{L}/u;

export function countHan(text) {
  return (String(text ?? '').match(HAN) || []).length;
}

export function countKanaHan(text) {
  return (String(text ?? '').match(KANA_HAN) || []).length;
}

export function countWords(text) {
  let count = 0;
  for (const match of String(text ?? '').normalize('NFC').matchAll(WORD)) {
    if (LETTER.test(match[0])) count += 1;
  }
  return count;
}

const COUNTERS = Object.freeze({ han: countHan, kana_han: countKanaHan, words: countWords });

/* The language a code names, without its region: `zh-CN` and `zh_TW` are `zh`. */
export function languageKey(code) {
  return String(code ?? '').trim().toLowerCase().replace(/_/g, '-').split('-')[0];
}

export function minimumFor(language) {
  const key = languageKey(language);
  return Object.prototype.hasOwnProperty.call(MINIMUM_BY_LANGUAGE, key) ? MINIMUM_BY_LANGUAGE[key] : DEFAULT_MINIMUM;
}

/* What a piece of writing counts to, against the minimum of its language. The shape
   mirrors the server's `MinimumCheck`. */
export function measureMinimum(text, language) {
  const { unit, minimum } = minimumFor(language);
  const count = COUNTERS[unit](text);
  return { language: languageKey(language), unit, minimum, count, met: count >= minimum };
}

export const meetsMinimum = (text, language) => measureMinimum(text, language).met;
