/* Reading Transfer (design route `rtransfer`, frame 39, D-091): pure data mapping, DOM-free so
   scripts/test_orena_screen_reading-transfer.mjs can test it without a browser.

   The frame's own scoring (`rxSubmit`: a client-side content-word overlap ratio and an answer-length
   check that never judges plausibility) is prototype-internal and is NOT behaviour to copy (D-068).
   The real contract this screen can honestly stand on is `POST /api/dictionary/spoken-response`
   (writing_coach/media_interaction.py `coach_spoken_response`) - the same coaching the React / Reuse
   screen reads for its own "say it in a new context" answer: it reads what the learner wrote or
   said against a stated `situation`, and answers with the words that carried the meaning, the words
   that would land differently (each grounded in a quotation of the learner's own text), one thing
   to try next and one alternative way to say it. It measures nothing the frame's "Meaning preserved?
   / Missing important idea?" tiles claim to measure, so those verdicts are not drawn; the two tiles
   hold the endpoint's own two lists instead (docs/project/UI_BACKEND_GAPS.md, "Reading Transfer").

   The source sentence is a real sentence of the text the learner is reading - the same paragraph
   and sentence boundaries the Reader renders (product/reader-text.js) - never a sample. */
import { blocksFrom, sentenceSpans } from '../../product/reader-text.js';

/* The three modes the frame's chip row draws, in its order. `task` is the plain-English brief the
   coaching request carries as its `situation` (the endpoint's own field for "what the learner was
   asked to do"; without it the coach has to guess and marks ordinary choices as omissions). It is
   request shaping, never shown to the learner - the learner reads the localized prompt in copy.js. */
export const MODES = Object.freeze([
  { key: 'paraphrase', task: 'The learner was asked to say the idea of the source sentence again in their own words.' },
  { key: 'inference', task: 'The learner was asked what the writer is implying in the source sentence, beyond its literal words.' },
  { key: 'context_shift', task: 'The learner was asked to say the source sentence again as they would to their manager instead of to a close friend.' },
]);

export function modeKeys() {
  return MODES.map((mode) => mode.key);
}

/* What the coaching endpoint accepts (writing_coach/media_interaction.py `SpokenResponseIn`),
   named once so a request is shaped to fit rather than refused. */
export const COACH_LIMITS = Object.freeze({ transcript: 2400, situation: 1200 });

/* A source sentence worth working on: enough of a thought to paraphrase or infer from (a one-word
   "Yes." or a heading fragment is not), and short enough to travel inside the coaching request's
   `situation` beside its task. Words for English; Han characters for Chinese, which has no
   spaces to count words by. */
export const SENTENCE_LIMITS = Object.freeze({ minWords: 4, minHan: 6, maxChars: 400 });

/* "article:abc" / "book:b1:c2" / "text:t1" is Content Detail's own scheme and contract
   (screens/content/model.js); this screen only ever reads the three sources that are text. */
export const READABLE_KINDS = Object.freeze(['article', 'book', 'text']);

/* An article's body and a learner's own imported text are one string; the Reader reads both as
   paragraphs split on a blank line (screens/reader/model.js `paragraphsFromText`). A book chapter
   already carries blocks or paragraphs. Only paragraphs are sentences to work on - a heading or a
   section break is not. */
export function paragraphsOf(kind, raw) {
  if (kind === 'book') return blocksFrom({ blocks: raw?.blocks, paragraphs: raw?.paragraphs }).filter((block) => block.type === 'paragraph').map((block) => block.text);
  const value = kind === 'article' ? raw?.body : raw?.text;
  const parts = String(value ?? '').split(/\n{2,}/).map((part) => part.trim()).filter(Boolean);
  return blocksFrom({ paragraphs: parts }).filter((block) => block.type === 'paragraph').map((block) => block.text);
}

const HAN = /\p{Script=Han}/gu;

export function unitsIn(sentence, language) {
  const text = String(sentence ?? '');
  if (language === 'zh') return (text.match(HAN) || []).length;
  return text.split(/\s+/).filter((word) => /[\p{L}\p{N}]/u.test(word)).length;
}

export function isWorkableSentence(sentence, language) {
  const text = String(sentence ?? '').trim();
  if (!text || text.length > SENTENCE_LIMITS.maxChars) return false;
  return unitsIn(text, language) >= (language === 'zh' ? SENTENCE_LIMITS.minHan : SENTENCE_LIMITS.minWords);
}

/* Every workable sentence of the text, in reading order. */
export function workableSentences(paragraphs, language) {
  const out = [];
  for (const paragraph of paragraphs || []) {
    for (const span of sentenceSpans(paragraph)) {
      const sentence = paragraph.slice(span.start, span.end).trim();
      if (isWorkableSentence(sentence, language)) out.push(sentence);
    }
  }
  return out;
}

/* "Another sentence" moves on in reading order and wraps at the end. With one workable sentence
   there is no other one to move to, so the control is not offered (see `canMoveOn`). */
export function nextIndex(index, count) {
  if (count <= 1) return 0;
  return (index + 1) % count;
}

export function canMoveOn(count) {
  return count > 1;
}

export function canCheck(text, busy) {
  const value = String(text ?? '').trim();
  return value.length > 0 && value.length <= COACH_LIMITS.transcript && !busy;
}

/* The coaching request. `source_language` must be the learner's current learning language - the
   endpoint answers 409 for any other - so it is passed in, never derived from the text. */
export function coachRequest({ answer, mode, sentence, language, support }) {
  const task = MODES.find((item) => item.key === mode)?.task || '';
  return {
    transcript: String(answer ?? '').trim(),
    source_language: language,
    target_language: support,
    situation: `${task}\nSource sentence: ${sentence}`.slice(0, COACH_LIMITS.situation),
  };
}

const list = (items, withInstead) =>
  (Array.isArray(items) ? items : [])
    .filter((item) => item && String(item.quote || '').trim() && String(item.why || '').trim())
    .map((item) => ({
      quote: String(item.quote).trim(),
      why: String(item.why).trim(),
      ...(withInstead ? { instead: String(item.instead || '').trim() } : {}),
    }));

/* The coaching answer reduced to what the Result state draws: the two lists (each item a real
   quotation of the learner's own words with its reason) and the one thing to try. `available` is
   the endpoint's own honesty flag (false when the model found nothing worth naming - never padded
   to look non-empty). The callout is `next_attempt` ("one concrete thing to try") - the frame's
   "One useful improvement" - and falls back to `another_way`; an empty one is not drawn. */
export function mapCoaching(raw) {
  const carried = list(raw?.carried, false);
  const landed = list(raw?.landed_differently, true);
  const improvement = String(raw?.next_attempt || '').trim() || String(raw?.another_way || '').trim();
  return { available: Boolean(raw?.available) && Boolean(carried.length || landed.length), carried, landed, improvement };
}
