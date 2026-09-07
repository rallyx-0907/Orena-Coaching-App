import {
  listeningUnits,
  listeningReconstructionDiff,
} from './dictation-evaluator.js';

/* A hint should let a learner keep working, not end the work. These build a
   slot view of the line: punctuation and spacing stay visible as structure,
   words the learner has already produced correctly become anchors they can
   read back, and everything still missing shows only its shape.

   Revealing the answer is a separate, deliberate act with its own evidence.
   Nothing here ever exposes a word the learner has not earned. */

export const MAX_HINT_LEVEL = 2;

const MASK = '▁'; // ▁ - one mark per character still to be found.

/* Split the canonical line into comparable words and the structure between
   them, keeping the surface spelling so a slot has the shape of the thing the
   learner actually has to type. */
export function hintTokens(expected, sourceLanguage) {
  const line = String(expected ?? '');
  const pattern =
    sourceLanguage === 'zh'
      ? /\p{Script=Han}|[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu
      : /[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu;
  const tokens = [];
  let cursor = 0;
  for (const match of line.matchAll(pattern)) {
    if (match.index > cursor)
      tokens.push({ text: line.slice(cursor, match.index), word: false });
    tokens.push({ text: match[0], word: true });
    cursor = match.index + match[0].length;
  }
  if (cursor < line.length) tokens.push({ text: line.slice(cursor), word: false });
  return tokens;
}

/* Which expected words the learner has already produced, in order. Uses the
   same alignment as the comparison the learner is shown, so an anchor here and
   a green word there can never disagree. */
export function confirmedWords({ expected, answer, source_language }) {
  const words = listeningUnits(expected, source_language);
  const confirmed = words.map(() => false);
  if (!String(answer ?? '').trim()) return confirmed;
  let index = 0;
  for (const entry of listeningReconstructionDiff({
    source_language,
    expected,
    answer,
  })) {
    if (entry.status === 'extra') continue;
    if (entry.status === 'correct') confirmed[index] = true;
    index += 1;
  }
  return confirmed;
}

/* level 1 shows the structure and the shape of every unfound word.
   level 2 additionally offers the first character of each one.
   An anchor the learner has earned is shown in full at any level. */
export function dictationHint({
  expected,
  answer = '',
  source_language,
  level = 1,
}) {
  const step = Math.max(1, Math.min(MAX_HINT_LEVEL, Math.round(Number(level) || 1)));
  const tokens = hintTokens(expected, source_language);
  const confirmed = confirmedWords({ expected, answer, source_language });
  let wordIndex = 0;
  let remaining = 0;
  const slots = tokens.map((token) => {
    if (!token.word) return { text: token.text, kind: 'structure' };
    const found = confirmed[wordIndex] === true;
    wordIndex += 1;
    if (found) return { text: token.text, kind: 'anchor' };
    remaining += 1;
    const characters = [...token.text];
    const masked =
      step >= 2 && characters.length > 1
        ? characters[0] + MASK.repeat(characters.length - 1)
        : MASK.repeat(characters.length);
    return { text: masked, kind: 'slot', length: characters.length };
  });
  return {
    level: step,
    maxLevel: MAX_HINT_LEVEL,
    slots,
    remaining,
    anchors: confirmed.filter(Boolean).length,
    total: confirmed.length,
    // A hint is never a reveal: at the deepest level a word longer than one
    // character still withholds everything after its first.
    complete: remaining === 0,
  };
}
