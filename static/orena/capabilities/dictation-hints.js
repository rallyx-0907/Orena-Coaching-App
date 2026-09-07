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

/* The leading characters a learner has already typed correctly for a word they
   have not finished.

   Showing these is not revealing anything: they came from the learner, and
   seeing their own correct start is what lets them reason about the rest of the
   word instead of staring at an undifferentiated run of marks. The comparison
   is on character units, so Chinese counts characters and English counts
   letters, and case is ignored because dictation is not a spelling-case test. */
export function earnedPrefix(word, attempt) {
  const target = [...String(word ?? '')];
  const typed = [...String(attempt ?? '')];
  let shared = 0;
  while (
    shared < target.length &&
    shared < typed.length &&
    target[shared].toLowerCase() === typed[shared].toLowerCase()
  )
    shared += 1;
  // The whole word is never given back this way: that would be a reveal
  // wearing a hint's clothes.
  return Math.min(shared, Math.max(0, target.length - 1));
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
    /* What the learner has already earned on this word: their own correct
       start, plus the opening character the deeper hint level offers. */
    const earned = earnedPrefix(token.text, entry.attempt);
    const offered = step >= 2 && characters.length > 1 ? 1 : 0;
    const shown = Math.max(earned, offered);
    if (earned > 0) partial += 1;
    return {
      text: characters.slice(0, shown).join('') + MASK.repeat(characters.length - shown),
      kind: earned > 0 ? 'partial' : 'slot',
      length: characters.length,
      // How much of this word is standing, so the surface can show progress
      // within a word rather than only between words.
      known: shown,
      earned,
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
