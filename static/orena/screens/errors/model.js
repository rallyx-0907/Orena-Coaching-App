/* From Your Errors' pure data mapping (frame 50, D-091). Practice outcomes only (2026-09-28 human
   decision: Grammar Lab, not R5, is the only grammar source going forward - this screen reads no
   `/api/library/grammar*`/`/api/grammar/*` route and no `capabilities/grammar-pedagogy.js`).

   Two real endpoints, joined client-side because neither alone carries what the frame needs:
   - `GET /api/practice-outcomes` (`writing_coach/becoming_outcomes.py`) says WHICH of the
     learner's own targeted Writing practice attempts had real recorded issues, with up to three
     truncated fragment strings as `error_evidence` - not enough to grade an edit against (no
     correction, no explanation).
   - `GET /api/essays/{id}` (detail) carries the full `issues[]` for that essay - `{quote, suggestion,
     why, how, examples}` - the real correction and explanation `error_evidence` cannot itself
     supply, per essay.
   `error_evidence` fragments are truncated to 260 chars server-side (`becoming_outcomes.py`); an
   essay's own `issues[].quote` is not, so a fragment is matched to its issue as a real prefix, not
   only real equality.

   Rule 40 throughout: a fragment with no matching issue, or an issue with no real `suggestion`, is
   never turned into a drill item - there is no invented correction to grade against. This is
   Writing-only by construction (the only capability `/api/practice-outcomes` covers) - the design's
   `ERR_DRILLS` sample data draws from Speaking sources too; that cross-capability sourcing has no
   real endpoint here and is recorded as a backend gap in the surface report, not simulated. */

function text(value) {
  return String(value ?? '').trim();
}

/* Outcomes worth a drill card: a real, recorded issue exists to review. Server order (most recent
   practice first) is kept - never re-sorted by a guess at importance. */
export function outcomesWithIssues(payload, limit = 10) {
  // GET /api/practice-outcomes answers {items, latest} (becoming_outcomes.py#list_practice_outcomes).
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items.filter((row) => row && Number(row.issue_count) > 0 && text(row.focus_label) && Array.isArray(row.error_evidence) && row.error_evidence.length).slice(0, Math.max(0, limit));
}

export function essayIdsOf(outcomes) {
  return [...new Set(outcomes.map((row) => Number(row.essay_id)).filter((id) => Number.isFinite(id)))];
}

/* The one real issue this fragment came from, matched by prefix (the fragment may be a truncated
   prefix of the essay's own untruncated `quote`) - never the first issue on the essay regardless of
   text, which would silently pair a fragment with someone else's correction. */
export function matchIssue(fragment, issues) {
  const wanted = text(fragment);
  if (!wanted) return null;
  const list = Array.isArray(issues) ? issues : [];
  return list.find((issue) => {
    const quote = text(issue?.quote);
    return quote && (quote === wanted || quote.startsWith(wanted) || wanted.startsWith(quote));
  }) || null;
}

/* One drill card per (outcome, fragment) pair with a real correction to grade against - the
   editable "bad" sentence, the real "good" correction, and the real "why". An item whose correction
   is empty or identical to the original text is never built (nothing to fix, nothing to grade). */
export function buildDrillItems(outcomes, issuesByEssay) {
  const items = [];
  for (const outcome of outcomes) {
    const essayId = Number(outcome.essay_id);
    const issues = issuesByEssay?.[essayId] || [];
    for (const fragment of outcome.error_evidence || []) {
      const issue = matchIssue(fragment, issues);
      const bad = text(issue?.quote) || text(fragment);
      const good = text(issue?.suggestion);
      if (!good || good === bad) continue;
      items.push({
        essayId,
        pattern: text(outcome.focus_label),
        createdAt: text(outcome.created_at),
        bad,
        good,
        why: text(issue?.why),
      });
    }
  }
  return items;
}

/* The learner's own reviewed writing: the issues of their recent essays (`GET /api/essays/{id}` detail), each with the
   real quote, the real suggestion and the real "why" the review gave. A review that found issues is a source of
   drills whether or not the learner then ran a targeted practice (`/api/practice-outcomes` only lists those) - a
   learner who reviewed a draft with three fixes is not told there are no recent errors. An issue with no suggestion,
   or whose suggestion is the quote itself, has nothing to grade against and is never turned into a drill. `labelOf`
   turns an issue's category into the words of the interface; `languageOf` marks the sentence's language. */
export function buildEssayDrillItems(essays, { labelOf = (category) => category, limit = 12 } = {}) {
  const items = [];
  for (const essay of Array.isArray(essays) ? essays : []) {
    for (const issue of Array.isArray(essay?.issues) ? essay.issues : []) {
      const bad = text(issue?.quote);
      const good = text(issue?.suggestion);
      if (!bad || !good || good === bad) continue;
      items.push({
        essayId: Number(essay.id),
        pattern: text(labelOf(text(issue?.category))) || text(issue?.category),
        createdAt: text(essay.created_at),
        bad,
        good,
        why: text(issue?.why),
        language: text(essay.language_code),
      });
      if (items.length >= limit) return items;
    }
  }
  return items;
}

/* Drills from targeted practice and from reviews, once each (the same sentence of the same essay is one drill). */
export function mergeDrillItems(fromOutcomes, fromEssays, limit = 12) {
  const seen = new Set();
  const out = [];
  for (const item of [...fromOutcomes, ...fromEssays]) {
    const key = `${item.essayId}|${normalize(item.bad)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
    if (out.length >= limit) break;
  }
  return out;
}

/* Forgiving of case, spacing and punctuation - in any script (a Chinese "，。" is punctuation too) -
   and never of the words themselves. */
function normalize(value) {
  return text(value)
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[\p{P}\p{S}]/gu, '')
    .replace(/\s+/g, ' ')
    // Chinese is written without spaces, so a space beside a Han character (left where a comma was
    // taken out) is not part of the answer.
    .replace(/\s*([㐀-鿿])\s*/g, '$1')
    .trim();
}

export function isCorrect(input, good) {
  const a = normalize(input);
  return Boolean(a) && a === normalize(good);
}

/* What became of each sentence, as the frame's own state machine has it (`ef.results`): `null`
   (not cleared yet - unanswered, or only wrong so far), `first` (right on the first check),
   `later` (right after at least one wrong check), `shown` (the learner asked for the answer). A
   settled sentence is never re-graded, and asking for the answer forfeits any credit. (The
   prototype's own `efCheck` can never reach "later" - its first line credits "first" on any right
   answer - while its copy, "fixed on the first try" / "fixed after a retry", says what was meant;
   this follows the copy.) */
export function initialResults(items) {
  return items.map(() => null);
}

export function recordCheck(current, { correct, wrongBefore }) {
  if (current) return current;
  if (!correct) return null;
  return wrongBefore > 0 ? 'later' : 'first';
}

export function recordReveal(current) {
  return current || 'shown';
}

/* "X of Y fixed on the first try" - real, from what actually happened this session. */
export function score(results) {
  return { firstTry: results.filter((r) => r === 'first').length, total: results.length };
}

/* The summary's rows: one per sentence, in the order they were asked (the frame's `efRows` maps
   the drill list, it does not group by pattern). */
export const ROW_STATES = Object.freeze({ first: 'cleared', later: 'later' });
export function summaryRows(items, results) {
  return items.map((item, index) => ({ pattern: item.pattern, state: ROW_STATES[results[index]] || 'keep' }));
}
