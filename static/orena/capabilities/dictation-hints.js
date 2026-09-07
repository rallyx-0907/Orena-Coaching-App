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

const MASK = '*'; // One mark per character still to be found.

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

/* How far the learner has got with each expected word, in order. Uses the same
   alignment as the comparison they are shown, so an anchor here and a matched
   word there can never disagree.

   A word they attempted and got wrong still carries what they wrote, which is
   what makes partial credit possible. */
export function wordProgress({ expected, answer, source_language }) {
  const words = listeningUnits(expected, source_language);
  const progress = words.map((word) => ({ word, found: false, attempt: '' }));
  if (!String(answer ?? '').trim()) return progress;
  let index = 0;
  for (const entry of listeningReconstructionDiff({
    source_language,
    expected,
    answer,
  })) {
    if (entry.status === 'extra') continue;
    if (progress[index]) {
      progress[index].found = entry.status === 'correct';
      progress[index].attempt = entry.status === 'wrong' ? entry.actual || '' : '';
    }
    index += 1;
  }
  return progress;
}

export function confirmedWords(input) {
  return wordProgress(input).map((entry) => entry.found);
}

/* Which characters of a word the learner has actually produced.

   A prefix is not enough: someone who writes "Undar" for "Under" has earned the
   "Und" and the "r", and a model that stops at the first mistake hides the "r"
   they got right. So the comparison is an alignment, not a walk - the longest
   common subsequence between the target and what they typed, which is what
   keeps a missing letter, an extra letter or a swapped pair from shifting every
   character after it.

   Case is ignored: dictation is not a spelling-case test. */
export function earnedCharacters(word, attempt) {
  const target = [...String(word ?? '')];
  const typed = [...String(attempt ?? '')].map((c) => c.toLowerCase());
  const lower = target.map((c) => c.toLowerCase());
  const earned = target.map(() => false);
  if (!target.length || !typed.length) return earned;

  // Longest common subsequence, then walk it back to mark which of the
  // learner's characters landed on which of the target's.
  const grid = Array.from({ length: target.length + 1 }, () =>
    new Uint16Array(typed.length + 1),
  );
  for (let row = target.length - 1; row >= 0; row -= 1)
    for (let column = typed.length - 1; column >= 0; column -= 1)
      grid[row][column] =
        lower[row] === typed[column]
          ? grid[row + 1][column + 1] + 1
          : Math.max(grid[row + 1][column], grid[row][column + 1]);

  let row = 0;
  let column = 0;
  while (row < target.length && column < typed.length) {
    if (lower[row] === typed[column]) {
      earned[row] = true;
      row += 1;
      column += 1;
    } else if (grid[row + 1][column] >= grid[row][column + 1]) row += 1;
    else column += 1;
  }
  return earned;
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
  const progress = wordProgress({ expected, answer, source_language });
  let wordIndex = 0;
  let remaining = 0;
  let partial = 0;
  const slots = tokens.map((token) => {
    if (!token.word) return { text: token.text, kind: 'structure' };
    const entry = progress[wordIndex] || { found: false, attempt: '' };
    wordIndex += 1;
    if (entry.found) return { text: token.text, kind: 'anchor' };
    remaining += 1;
    const characters = [...token.text];
    // Every character the learner has actually produced for this word shows;
    // every position they have not stays masked.
    const earned = earnedCharacters(token.text, entry.attempt);
    /* The deeper level offers one character the learner has not earned - the
       first still-masked one - and never the last, so a hint cannot finish a
       word for them. */
    if (step >= 2 && characters.length > 1) {
      const next = earned.indexOf(false);
      if (next >= 0 && earned.filter(Boolean).length < characters.length - 1)
        earned[next] = true;
    }
    const known = earned.filter(Boolean).length;
    if (known > 0) partial += 1;
    return {
      text: characters.map((c, i) => (earned[i] ? c : MASK)).join(''),
      kind: known > 0 ? 'partial' : 'slot',
      length: characters.length,
      // Which positions are standing, so the surface can mark them individually
      // rather than assuming everything known is at the front.
      earned,
      known,
    };
  });
  const anchors = progress.filter((entry) => entry.found).length;
  return {
    level: step,
    maxLevel: MAX_HINT_LEVEL,
    slots,
    remaining,
    anchors,
    partial,
    total: progress.length,
    // A hint is never a reveal: every unfound word withholds at least its last
    // character, however much the learner has earned.
    complete: remaining === 0,
  };
}
