/* Dictation as the Canonical UI Baseline draws it (D-066): the shape of the line with a
   reading under each character, and the result as a score, a count and marks.

   Nothing here scores or aligns anything itself. The comparison, the score and the
   words the learner has earned come from the evaluator and the hint module that already
   existed; this module only puts them in the baseline's shapes (`DictationResult` in
   docs/design/canonical-ui/data-contracts), so the screen has one honest source and the
   contract has one place to be held to. */
import { listeningReconstructionDiff, evaluateListeningReconstruction } from './dictation-evaluator.js';
import { hintTokens, wordProgress, earnedCharacters } from './dictation-hints.js';

/* The baseline's hint has three levels, and never shows the whole line. Level 0 is
   "no hint": only what the learner has earned by typing is shown. */
export const HINT_LEVELS = 3;
const REVEALED = [0, 0.2, 0.45, 0.7];

/* How many leading units a level shows, out of `count`. At least one once a hint is
   asked for, and always at least one still hidden. */
export function revealedCount(level, count) {
  const step = Math.max(0, Math.min(HINT_LEVELS, Math.round(Number(level) || 0)));
  if (step === 0 || count < 2) return 0;
  return Math.min(count - 1, Math.max(1, Math.round(count * REVEALED[step])));
}

const isHan = (text) => /^\p{Script=Han}$/u.test(text);
const MASK = '＊';

/* The readings of a spoken line when the written line has more in it than is said (a
   speaker label: "金妮：他们是谁？" is said as "他们是谁？"). The spoken characters are found
   inside the written ones; if they are not there, the line has no readings rather than
   somebody else's. */
export function readingsFor(spoken, original, readings) {
  const said = [...String(spoken || '')].filter(isHan);
  const written = [...String(original || '')].filter(isHan);
  if (!said.length || !readings?.length || readings.length !== written.length) return [];
  if (said.length === written.length) return said.join('') === written.join('') ? readings : [];
  const at = written.join('').indexOf(said.join(''));
  return at < 0 ? [] : readings.slice(at, at + said.length);
}

/* The whole-line reading for the spoken part: the label and its colon are not said. */
export function readingLineFor(spoken, original, reading) {
  const line = String(reading || '').trim();
  if (!line || String(spoken || '') === String(original || '')) return line;
  const label = /^[^:：]+[:：]\s*/;
  return label.test(line) && label.test(String(original || '')) ? line.replace(label, '') : line;
}

/* The line as cells. In Chinese a cell is a character with its reading beneath (the
   aligned reading from the catalogue, or none); in other languages a cell is a word,
   masked one mark per letter still to be found. */
export function dictationHintView({ expected, answer = '', language, level = 0, readings = [] }) {
  const zh = language === 'zh';
  const tokens = hintTokens(expected, language);
  const progress = wordProgress({ expected, answer, source_language: language });
  const words = tokens.filter((token) => token.word);
  const reveal = revealedCount(level, words.length);
  let wordIndex = 0;
  let readingIndex = 0;
  let charTotal = 0;
  let charRevealed = 0;
  const revealed = [];
  const cells = [];
  let leading = '';
  for (const token of tokens) {
    if (!token.word) {
      // Punctuation is the shape of a sentence: it stays, trailing the word it follows (or
      // leading the first one). Spacing is the gap between cells. A reading row has neither.
      const mark = token.text.trim();
      if (!zh && mark) {
        if (cells.length) cells[cells.length - 1].after = (cells[cells.length - 1].after || '') + mark;
        else leading = mark;
      }
      continue;
    }
    const index = wordIndex;
    wordIndex += 1;
    const characters = [...token.text];
    charTotal += characters.length;
    const reading = zh && isHan(token.text) ? readings[readingIndex++]?.pinyin || '' : '';
    const known = index < reveal || progress[index]?.found;
    if (known) {
      charRevealed += characters.length;
      revealed.push(token.text);
      cells.push({ kind: 'shown', text: token.text, reading, before: cells.length ? '' : leading });
      continue;
    }
    const earned = zh ? characters.map(() => false) : earnedCharacters(token.text, progress[index]?.attempt);
    const got = earned.filter(Boolean).length;
    charRevealed += got;
    cells.push({
      kind: got ? 'partial' : 'hidden',
      text: characters.map((ch, i) => (earned[i] ? ch : zh ? MASK : '*')).join(''),
      reading: '',
      before: cells.length ? '' : leading,
    });
  }
  return { level: Math.max(0, Math.min(HINT_LEVELS, Math.round(Number(level) || 0))), maxLevel: HINT_LEVELS, cells, revealed, charTotal, charRevealed };
}

/* A substitution is one mistake, not two: the evaluator reports a wrong character as a
   missing one beside an extra one, and the baseline marks it as one wrong place. */
export function diffMarks(diff) {
  const marks = [];
  for (let i = 0; i < diff.length; i += 1) {
    const here = diff[i];
    const next = diff[i + 1];
    const pair =
      next && ((here.status === 'missing' && next.status === 'extra') || (here.status === 'extra' && next.status === 'missing'));
    if (pair) {
      const missing = here.status === 'missing' ? here : next;
      const extra = here.status === 'extra' ? here : next;
      marks.push({ kind: 'wrong', from: extra.actual, to: missing.expected });
      i += 1;
    } else if (here.status === 'wrong') marks.push({ kind: 'wrong', from: here.actual, to: here.expected });
    else if (here.status === 'missing') marks.push({ kind: 'missing', from: null, to: here.expected });
    else if (here.status === 'extra') marks.push({ kind: 'extra', from: here.actual, to: null });
    else marks.push({ kind: 'correct', from: here.actual, to: here.expected });
  }
  return marks;
}

/* `DictationResult`, from the real comparison. `note` says the mistake in words; the
   caller supplies the wording in the learner's language. */
export function dictationResult({
  lineIndex,
  lineTotal,
  expected,
  spoken = expected,
  answer,
  language,
  reading = '',
  readings = [],
  level = 0,
  note = (mark) => [mark.from, mark.to].filter(Boolean).join(' → '),
}) {
  const scored = evaluateListeningReconstruction({ source_language: language, expected: spoken, answer });
  const marks = diffMarks(listeningReconstructionDiff({ source_language: language, expected: spoken, answer }));
  const view = dictationHintView({ expected, answer: '', language, level, readings });
  return {
    lineIndex,
    lineTotal,
    original: expected,
    originalPinyin: reading,
    attempt: answer,
    score: scored.accuracy_percent,
    exact: scored.exact,
    // The count the score is made of: the units of the line, less the edits still to make.
    correctCount: Math.max(0, scored.expected_unit_count - scored.edit_distance),
    totalCount: scored.expected_unit_count,
    hint: { level: view.level, revealed: view.revealed, charTotal: view.charTotal, charRevealed: view.charRevealed },
    marks,
    diffs: marks.filter((mark) => mark.kind !== 'correct').map((mark) => ({ ...mark, note: note(mark) })),
  };
}

/* What the result says first: right, close, or not yet - and how many places are left. */
export function verdictOf(result) {
  const counts = { wrong: 0, missing: 0, extra: 0 };
  for (const diff of result.diffs) counts[diff.kind] += 1;
  const places = result.diffs.length;
  return { key: result.exact ? 'exact' : result.score >= 60 ? 'close' : 'again', places, counts };
}
