/* Respond to Content (design route `respond`, frame 45, D-091): pure data mapping, DOM-free so
   scripts/test_orena_screen_respond.mjs can test it without a browser.

   The content-id parsing mirrors screens/discussion/model.js#parseContentId exactly (the same
   "<kind>:<id>" scheme every screen shares, screens/content/model.js#contentIdFor) - duplicated
   here rather than imported, since a screen's own model.js is private to it (surface brief §2).

   `mapFeedback` reads the real `POST /api/evaluate` create response (writing_coach/
   writing_evaluation.py `_issue_envelope`/`result["issues"]`, app.py `_run_review`'s own
   `return {..., **result}`) - captured live from this sandbox's own local model,
   `scripts/fixtures/api/essay_evaluate.json`. This sandbox has no cloud AI provider key, but the
   text-generation routes (this one included) answer through a local Ollama model; confirmed live
   end to end on the running app during the finish pass, 2026-09-29 (a real Opinion response about
   the Listening lesson, graded and returned in under a minute). Fields read: `id`, `overall`,
   `issues[].quote/.suggestion/.why`, `next_actions[]` - every one of them present in that
   function's own `return` statement, read field-for-field, nothing guessed. */

import { meetsMinimum } from '../../capabilities/writing-limits.js';

export function parseContentId(raw) {
  const value = String(raw || '');
  const first = value.indexOf(':');
  if (first === -1) return { kind: '', id: '' };
  const kind = value.slice(0, first);
  const rest = value.slice(first + 1);
  if (kind === 'book') {
    const second = rest.indexOf(':');
    if (second === -1) return { kind, id: rest, chapterId: '' };
    return { kind, id: rest.slice(0, second), chapterId: rest.slice(second + 1) };
  }
  return { kind, id: rest };
}

/* The frame's own two prompt/copy variants (E3 §4: "a kind→prompt map with two variants, media vs.
   article copy") - a media/upload source is the `media` variant, every text source (article, book
   chapter, a learner's own import) is the `reading` variant. Same media/upload grouping
   screens/discussion/model.js#discussionSourceFor already uses for the same "<kind>:<id>" scheme. */
export function respondVariantFor(kind) {
  return kind === 'media' || kind === 'upload' ? 'media' : 'reading';
}

/* Paragraph text -> up to `max` real sentences, using the same sentence-boundary spans
   screens/reader/model.js#sentencesOf renders one span per (product/reader-text.js#sentenceSpans) -
   never an invented excerpt, just a bounded prefix of the real source text. */
export function sourceLinesFromText(sentenceSpans, text, max = 4) {
  const value = String(text || '');
  if (!value) return [];
  return sentenceSpans(value)
    .map(({ start, end }) => value.slice(start, end).trim())
    .filter(Boolean)
    .slice(0, max);
}

/* A media source's own real transcript segments read as lines directly - no sentence-splitting
   needed, each segment already is one line (D4/E3 shared convention). */
export function sourceLinesFromSegments(segments, max = 4) {
  return (Array.isArray(segments) ? segments : [])
    .slice(0, max)
    .map((seg) => String(seg?.original_text || '').trim())
    .filter(Boolean);
}

/* Words the way a reader counts them (Intl.Segmenter, correct for Chinese too - the same idiom
   screens/writing/model.js#wordCountOf uses), duplicated here for the same "private model.js"
   reason as parseContentId above. */
export function wordCountOf(value, language) {
  const text = String(value || '');
  if (!text.trim()) return 0;
  try {
    return [...new Intl.Segmenter(language || 'en', { granularity: 'word' }).segment(text)].filter((part) => part.isWordLike).length;
  } catch {
    return text.trim().split(/\s+/).filter(Boolean).length;
  }
}

/* The server's own real floor AND ceiling for `POST /api/evaluate` (the learning language's own
   minimum, `writing-limits.js#meetsMinimum` - the table `writing_coach/writing_limits.py` holds it
   to; and that file's bytes/characters/lines bounds, read through `measureWriting` - the same
   function screens/writing/model.js#reviewGate uses for the same request) - the button agrees
   with the request it is about to make on both ends, never a guessed number and never a
   silently-ignored tap once a paste is too long. `language` is the language the request is made
   in (the request's own `learning_language`). */
export function canGetFeedback(value, measureWriting, language) {
  if (!meetsMinimum(String(value || '').trim(), language)) return false;
  return measureWriting ? measureWriting(value).withinLimits : true;
}

/* The real `POST /api/evaluate` create response -> what the Result state draws. `issues` is
   already the per-finding envelope (`quote`/`suggestion`/`why`/`how`), the same shape
   screens/writing/model.js#mapIssue reads from the read-back route - built once here since Respond
   never fetches a review separately. `nextStep` is the evaluator's own first priority
   (`result["next_actions"]`, real per-response guidance) - omitted, not guessed, when the
   evaluator returned none (rule 40: no canned "keep writing" filler). */
export function mapFeedback(raw) {
  const issues = (Array.isArray(raw?.issues) ? raw.issues : [])
    .map((item) => ({
      quote: String(item?.quote || ''),
      suggestion: String(item?.suggestion || ''),
      why: String(item?.why || ''),
    }))
    .filter((item) => item.quote);
  const nextSteps = Array.isArray(raw?.next_actions) ? raw.next_actions : [];
  return {
    id: Number(raw?.id) || null,
    overall: Number.isFinite(raw?.overall) ? Math.round(raw.overall) : null,
    issues,
    nextStep: nextSteps.length ? String(nextSteps[0]) : '',
  };
}
