/* React / Reuse (design route `react`, frame 33, D-091): pure data mapping, DOM-free so
   scripts/test_orena_screen_react.mjs can test it without a browser.

   Source payload: the same `GET /api/listening/library/{lessonId}` as Listening
   (scripts/fixtures/api/listening_library_lesson.{en,zh}.json), plus the real coaching answer of
   `POST /api/dictionary/spoken-response` (writing_coach/media_interaction.py `coach_spoken_response`
   - captured live from this sandbox's own local model, `scripts/fixtures/api/spoken_response.en.json`;
   this sandbox has no cloud AI provider key, but the text-generation routes answer through a local
   Ollama model, confirmed live end to end on the running app during the finish pass, 2026-09-29 -
   the shape below is read field-for-field from that function's own `return {...}`, matching the
   fixture). */
import { situationJudgements } from '../situation/model.js';


/* This lesson's own real vocabulary term found inside one segment - the same real match
   screens/listening/model.js#vocabularyForSegment makes, duplicated here (not imported: a
   screen's own model.js is private to it, not a shared module) so the Reveal/New-Context steps
   can point at a real phrase from the segment instead of inventing one. Null when no real term
   matches - the step still works, just without a named phrase (see screen.js). */
export function usefulPhrase(vocabulary, text) {
  const lower = String(text).toLowerCase();
  for (const term of vocabulary || []) {
    const word = String(term).toLowerCase();
    if (!word) continue;
    if (lower.includes(word)) return term;
    const stem = word.length > 4 ? word.slice(0, -1) : word;
    if (lower.includes(stem)) return term;
  }
  return null;
}

/* A real multiple-choice Understand check built entirely from this lesson's own real segment
   translations: the correct option is the current segment's own real translation, the wrong
   options are two other real segments' own real translations from the same lesson. Null when
   fewer than 2 other segments have a real translation to serve as honest distractors - never a
   generated or guessed wrong answer (rule 40). `order` is a deterministic shuffle keyed off the
   segment id so the correct position does not always land in the same slot, without a random
   source that would make this impure. */
export function buildUnderstandCheck(segments, currentId, meaningOf, order = 0) {
  const others = segments.filter((seg) => seg.segment_id !== currentId);
  const correctText = meaningOf(currentId);
  if (!correctText) return null;
  const wrongTexts = [];
  for (const seg of others) {
    const text = meaningOf(seg.segment_id);
    if (text && !wrongTexts.includes(text)) wrongTexts.push(text);
    if (wrongTexts.length >= 2) break;
  }
  if (wrongTexts.length < 2) return null;
  const options = [correctText, ...wrongTexts];
  const rotated = options.map((_, i) => options[(i + order) % options.length]);
  return { options: rotated, correctIndex: rotated.indexOf(correctText) };
}

/* The frame's "Phrase reused?" tile is a fact the learner's own words settle, not a judgement:
   whether the line's catalogued phrase (same stem tolerance as usefulPhrase) appears in what they
   said or wrote. null when the line has no catalogued phrase to reuse (rule 40: the tile then
   renders its 0 fallback, never a guessed yes/no). */
export function phraseReused(phrase, answer) {
  const word = String(phrase ?? '').trim().toLowerCase();
  if (!word) return null;
  const lower = String(answer ?? '').toLowerCase();
  if (lower.includes(word)) return true;
  const stem = word.length > 4 ? word.slice(0, -1) : word;
  return lower.includes(stem);
}

/* The Listen step's bars, exactly the frame's own arithmetic (`waveBars`: a height between 30% and
   100% from a sine of the bar's index and the line's number, a delay from 0 to 600ms) - decoration
   whose only real signal is its opacity: dim until the line is playing. */
export function waveBars(count, seed) {
  return Array.from({ length: count }, (_, i) => ({
    height: Math.round(30 + Math.abs(Math.sin(i * 1.7 + seed)) * 70),
    delay: (i * 37) % 600,
  }));
}

/* Which of the two new-context prompts a "New context" tap lands on (the frame alternates two per
   phrase). */
export function promptKey(hasPhrase, contextIndex) {
  return `${hasPhrase ? 'promptWithPhrase' : 'promptGeneric'}${Math.abs(Number(contextIndex) || 0) % 2 ? '2' : ''}`;
}

/* The real coaching answer (`POST /api/dictionary/spoken-response`), reduced to what the Result
   step draws. `available` is the endpoint's own honesty flag (false when the model found nothing
   worth naming - never invented to look non-empty). */
export function mapCoaching(raw) {
  return {
    available: Boolean(raw?.available),
    carried: Array.isArray(raw?.carried) ? raw.carried : [],
    landedDifferently: Array.isArray(raw?.landed_differently) ? raw.landed_differently : [],
    anotherWay: String(raw?.another_way || ''),
    nextAttempt: String(raw?.next_attempt || ''),
    sayAgain: String(raw?.say_again || ''),
    // The coaching's own intent verdict, only when the provider returned a valid one (S-26); never a default.
    intent: situationJudgements(raw).intent,
  };
}

/* The Result's two tiles, only the ones with a real measurement (X-03, HX-2 A): "Intent achieved?" when the
   coaching returned a verdict, "Phrase reused?" when the line has a catalogued phrase. A bare 0 is never shown. */
export function resultTiles(reused, intent) {
  const tiles = [];
  if (intent) tiles.push({ key: 'intentAchieved', verdict: intent.verdict });
  if (reused != null) tiles.push({ key: 'phraseReused', good: reused === true, valueKey: reused ? 'yes' : 'notThisTime' });
  return tiles;
}

