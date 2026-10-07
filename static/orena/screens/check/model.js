/* Check Understanding (design route `checku`, frame 20): pure data mapping, DOM-free so
   scripts/test_orena_screen_check.mjs can test it without a browser.

   The question set comes from the canonical Reading practice contract
   (writing_coach/reading_practice_api.py, writing_coach/persistence/reading_evidence_repository.py):
   `GET /api/reading/practice/articles/{articleId}` answers `{set, submit_enabled, support_language}`
   or 404 when the article has no approved set (Free Reading). `set.questions[]` carries
   `{id, rank, question_type, prompt, options}` - no answer key until a question is graded
   (`POST .../grade`), which is itself gated by the same `submit_enabled` flag (`ORENA_READING_PRACTICE_SUBMIT`)
   as the final `POST /attempts` - "the disabled state must be honest" (task brief): this screen
   reads `submit_enabled` once, up front, and never lets the learner tap into a 503. */

// Same "<kind>:<id>" scheme every content-linking screen shares (screens/content/model.js is the
// canonical description); Check Understanding only ever practises an 'article'.
export function parseContentId(raw) {
  const value = String(raw || '');
  const first = value.indexOf(':');
  if (first === -1) return { kind: '', id: '' };
  return { kind: value.slice(0, first), id: value.slice(first + 1) };
}

// The real backend question types (reading_evidence_repository.py QUESTION_TYPES) - never the
// frame's own sample "factual/inference/meaning/intent" wording (D-068).
export const QUESTION_TYPES = Object.freeze([
  'main_idea', 'detail', 'inference', 'vocabulary_in_context',
  'cause_effect', 'sequence', 'authors_purpose', 'reference',
]);

export function typeLabel(type, t) {
  const key = `qtype_${type}`;
  return t.has(key) ? t(key) : type;
}

export function letterFor(index) {
  return String.fromCharCode(65 + index);
}

/* An option's border/bg/color and its 22px mark badge's own bg/color, exactly the source's three
   states (`cuOptions` in the design script, D-088): once a question is graded the correct option
   is green, a wrongly-picked one is red and every other option is unchanged - the same look it had
   before (rule 40: no colour before a real verdict exists). The frame draws the mark's ink as
   literal white on a solid green/red disc; `--badge-ink` is the AA-checked ink for exactly that
   pairing (kit gate, D-093). The text colour never changes: the frame's `color` is `--text` in
   every state. */
export function optionStyle({ index, graded, correctIndex, selectedIndex }) {
  if (graded && index === correctIndex) {
    return { border: 'var(--green)', bg: 'var(--green-soft)', color: 'var(--text)', markBg: 'var(--green)', markColor: 'var(--badge-ink)' };
  }
  if (graded && index === selectedIndex) {
    return { border: 'var(--red)', bg: 'var(--red-soft)', color: 'var(--text)', markBg: 'var(--red)', markColor: 'var(--badge-ink)' };
  }
  return { border: 'var(--border)', bg: 'var(--surface)', color: 'var(--text)', markBg: 'transparent', markColor: 'var(--muted)' };
}

export function markFor({ index, graded, correctIndex, selectedIndex }) {
  if (graded && index === correctIndex) return '✓';
  if (graded && index === selectedIndex) return '×';
  return letterFor(index);
}

/* "question {n} of {total}" - the header's own progress line, position not score. */
export function progressLabel(index, total, t) {
  return t('progress', { n: index + 1, total });
}

/* 0-100, how far through the set the learner is - the thin bar under the header. Like the source
   (`cuPct` = the index of the current question over the count) it moves when the learner moves on
   to the next question, not the moment one is answered, and it reads 100 on the result. */
export function progressPercent(index, total) {
  if (!total) return 0;
  return Math.round((Math.min(Math.max(index, 0), total) / total) * 100);
}

/* The done card's score line and its summary chips, built only from real grade results collected
   this session (never a fabricated tally). The source draws one chip per question, in order -
   "<type> · Correct" or "<type> · Missed" - not a per-type tally, so two questions of one type give
   two chips. `graded` is `{[questionId]: result}`, `result` the exact shape `POST .../grade` and
   `POST /attempts` both return (`{correct, question_id, ...}`). A question with no grade result
   contributes no chip. */
export function scoreSummary(questions, graded, t) {
  const total = questions.length;
  const correctCount = questions.reduce((n, q) => n + (graded[q.id]?.correct ? 1 : 0), 0);
  const chips = questions
    .map((question, index) => ({ question, index }))
    .filter(({ question }) => graded[question.id])
    .map(({ question, index }) => {
      const ok = Boolean(graded[question.id].correct);
      return { label: typeLabel(question.question_type, t), result: ok ? t('correctLabel') : t('missedLabel'), ok, index };
    });
  return { correctCount, total, chips };
}

/* "Next question" while questions remain, "See result" on the last one - a real difference in what
   the button does, not just its label. */
export function nextLabel(index, total, t) {
  return index + 1 < total ? t('nextQuestion') : t('seeResult');
}
