import { esc } from './html.js';

/* The evaluator has always returned a full review - weighted dimensions, a
   CEFR estimate, strengths quoted from the learner's own text, issues carrying
   the reason and the rule behind them, priorities, and a delta against the
   previous revision. The surface showed a corrected sentence and a list of
   struck-out fragments.

   This renders what is already there. It adds no score, infers no dimension,
   and shows nothing the payload did not carry. */

// The rubric the evaluator weights. Anything else it returns is shown too, so
// a new dimension appears rather than being silently dropped.
export const RUBRIC = [
  'grammar',
  'vocabulary',
  'coherence',
  'task_achievement',
  'naturalness',
];

const number = (value) => (typeof value === 'number' && Number.isFinite(value) ? value : null);

/* One rubric dimension, as one row.

   Label, bar, score, change - four things on one line. They were a three
   column grid holding four items, so the change wrapped onto a line of its
   own under every dimension: five rubric rows became ten, each one twice as
   tall as it needed to be, and the numbers read as something appended rather
   than as part of the row.

   The bar shows where the learner was and where they are now, which is the
   whole point of a second review. The previous score is not invented: the
   evaluator returns the change, so the score before it is the score now minus
   that change - arithmetic on data it gave us, not a guess. With no previous
   review there is no change and the bar is simply the score.

   Improving and slipping are drawn differently on purpose. A gain is the
   stretch the learner added, past where they were. A loss is the ground they
   held and no longer do, marked back from where they were to where they are -
   so a drop cannot read as though zero-to-here were progress. */
function dimensionRow(c, key, value, change) {
  const label = esc(c[`rubric_${key}`] || key);
  const now = Math.max(0, Math.min(100, value));
  const moved = change !== null && Math.round(change) !== 0 ? Math.round(change) : null;
  const before = moved === null ? null : Math.max(0, Math.min(100, value - moved));
  const direction = moved === null ? 'none' : moved > 0 ? 'up' : 'down';
  // The bar is two segments: what was held, and what changed since.
  const held = before === null ? now : Math.min(before, now);
  const shift = before === null ? 0 : Math.abs(now - before);
  return `<div class="review-dimension" data-direction="${direction}"><dt>${label}</dt><dd class="review-dimension__bar"><span class="review-bar" aria-hidden="true"><i class="review-bar__held" style="inline-size:${held}%"></i><i class="review-bar__shift" style="inline-size:${shift}%"></i></span></dd><dd class="review-dimension__score"><b>${Math.round(value)}</b></dd><dd class="review-dimension__move">${
    moved === null
      ? ''
      : `<span class="dimension-move" data-direction="${direction}">${moved > 0 ? '+' : ''}${moved}</span>`
  }</dd></div>`;
}

function dimensions(c, result) {
  const source = result.dimensions || {};
  const keys = [...new Set([...RUBRIC, ...Object.keys(source)])].filter(
    (key) => number(source[key]) !== null,
  );
  if (!keys.length) return '';
  const delta = result.delta && typeof result.delta === 'object' ? result.delta : null;
  return `<section class="review-dimensions"><dl>${keys
    .map((key) => dimensionRow(c, key, number(source[key]), delta ? number(delta[key]) : null))
    .join('')}</dl></section>`;
}

/* What changed between two versions. The evaluator has always worked this out -
   which problems the learner fixed, which are still there, which arrived with
   the rewrite, and which changed shape - and the surface showed one number.

   Revising is where writing is actually learned, so this is the part worth
   seeing: a score that went up while the same problem persists is a different
   story from one that went up because the problem is gone. */
function comparison(c, result, text) {
  const issues = result.delta?.issues;
  if (!issues || typeof issues !== 'object') return '';
  const quoted = (item) =>
    item && item.fragment
      ? `<li><q lang="${esc(result.language || '')}">${esc(item.fragment)}</q>${item.mini_rule_vi ? ` <small>${esc(item.mini_rule_vi)}</small>` : ''}</li>`
      : '';
  const group = (key, labelKey, tone) => {
    const items = (issues[key] || []).map(quoted).filter(Boolean);
    if (!items.length) return '';
    return `<div class="review-change" data-tone="${tone}"><h4>${esc(c[labelKey])} <span>${items.length}</span></h4><ul>${items.join('')}</ul></div>`;
  };
  const changed = (issues.changed || [])
    .filter((pair) => pair?.before?.fragment && pair?.after?.fragment)
    .map(
      (pair) =>
        `<li><del>${esc(pair.before.fragment)}</del> <ins>${esc(pair.after.fragment)}</ins></li>`,
    );
  const blocks = [
    group('removed', 'reviewFixed', 'good'),
    group('persistent', 'reviewStill', 'watch'),
    group('new', 'reviewArrived', 'watch'),
    changed.length
      ? `<div class="review-change" data-tone="neutral"><h4>${esc(c.reviewReworked)} <span>${changed.length}</span></h4><ul>${changed.join('')}</ul></div>`
      : '',
  ].filter(Boolean);
  if (!blocks.length) return '';
  return `<section class="review-comparison"><p class="meta">${esc(c.reviewSinceLastNote)}</p><div class="review-changes">${blocks.join('')}</div></section>`;
}

/* A revision is only worth a number if there is something to compare it with.
   The evaluator supplies the delta; nothing is computed here. */
function movement(c, result) {
  const delta = result.delta;
  if (!delta || typeof delta !== 'object') return '';
  const overall = number(delta.overall);
  if (overall === null || overall === 0) return '';
  const better = overall > 0;
  return `<p class="review-delta" data-direction="${better ? 'up' : 'down'}">${esc(
    better ? c.reviewImproved : c.reviewSlipped,
  )} ${better ? '+' : ''}${Math.round(overall)}</p>`;
}

function strengths(c, result, language, text) {
  const items = shownStrengths(result, text);
  if (!items.length) return '';
  return `<section class="review-strengths">${items
    .map(
      (item) =>
        `<article class="strength"><blockquote lang="${esc(language)}">${esc(item.quote)}</blockquote>${item.why ? `<p>${esc(item.why)}</p>` : ''}<small>${esc(c[`rubric_${item.category}`] || item.category)}</small></article>`,
    )
    .join('')}</section>`;
}

/* An issue carries the learner's own wording, what to write instead, why it is
   a problem, and the rule behind it. Each one can be taken further through the
   shared explanation surface, which is what `data-why` is for - and located in
   the learner's own text, which is what `data-locate` is for: nobody should
   have to read their own paragraph hunting for a quoted phrase.

   `index` is the issue's position in `shownIssues`, and stays that whether it
   is shown in the focus or behind the fold, because that is the number the
   room binds its handlers to. */
const PRIORITY = { high: 0, critical: 0, medium: 1, low: 2 };

function correction(c, item, index, language, canLocate = true) {
  return `<article class="correction" data-issue="${index}" data-priority="${esc(item.priority || 'medium')}"><small class="correction__category">${esc(c[`rubric_${item.category}`] || item.category)}</small><p class="correction__row correction__wrote"><span class="correction__label">${esc(c.reviewYouWrote)}</span><del lang="${esc(language)}">${esc(item.quote)}</del></p>${item.suggestion ? `<p class="correction__row correction__fix"><span class="correction__label">${esc(c.reviewCorrection)}</span><strong lang="${esc(language)}">${esc(item.suggestion)}</strong></p>` : ''}${item.why ? `<p class="correction__row correction__why"><span class="correction__label">${esc(c.reviewWhy)}</span><span>${esc(item.why)}</span></p>` : ''}${item.how ? `<p class="correction__rule"><span class="correction__label">${esc(c.reviewRule)}</span><span>${esc(item.how)}</span></p>` : ''}<div class="button-row">${canLocate ? `<button class="quiet" data-locate="${index}">${esc(c.reviewLocate)}</button>` : ''}<button class="quiet" data-why="${index}">${esc(c.askWhy)} ↗</button><button class="outline" data-try-revision="${index}">${esc(c.revisionTry)} ↗</button></div></article>`;
}

/* Ten findings shown as equals is a wall, and a beginner reads none of them.
   The few worth doing now lead; the rest are a fold away, still whole. */
export function orderedIssues(result, text) {
  return shownIssues(result, text)
    .map((item, index) => ({ item, index, anchored: anchored(item, text) }))
    /* Most useful first, and an anchored finding before an unanchored one of
       the same priority: the learner can act on it immediately. */
    .sort(
      (a, b) =>
        (PRIORITY[a.item.priority] ?? 1) - (PRIORITY[b.item.priority] ?? 1) ||
        Number(b.anchored) - Number(a.anchored),
    );
}

const FOCUS = 3;

/* Where to begin. Never folded: a learner who opens a review and finds only a
   score and some accordions has been given a report, not coaching. */
function issues(c, result, language, text) {
  const focus = orderedIssues(result, text).slice(0, FOCUS);
  if (!focus.length) return '';
  return `<section class="review-issues"><h3>${esc(c.reviewFocus)}</h3>${focus
    .map(({ item, index, anchored: found }) => correction(c, item, index, language, found))
    .join('')}</section>`;
}

/* Everything else the evaluator found, as its own step rather than a fold
   inside the first three. This is where a learner goes when they have done the
   urgent things and want the rest - word choice, naturalness, structure - and
   it keeps every finding the payload carried. */
function deeper(c, result, language, text) {
  const rest = orderedIssues(result, text).slice(FOCUS);
  if (!rest.length) return '';
  return `<section class="review-deeper">${rest
    .map(({ item, index, anchored: found }) => correction(c, item, index, language, found))
    .join('')}</section>`;
}

function priorities(c, result) {
  const items = (result.next_actions || []).filter(Boolean);
  if (!items.length) return '';
  return `<section class="review-next"><ol>${items
    .map((item) => `<li>${esc(item)}</li>`)
    .join('')}</ol></section>`;
}

/* The issues this render actually offered, in the order shown, so the caller
   can bind "why?" to the right one without re-deriving the filter. */
/* Every finding the review carried, and whether each one can be pointed at.

   These used to be one question: a finding whose quote was not verbatim in
   the learner text was not shown at all. That is the right answer for
   highlighting - pointing at the wrong words is worse than pointing at
   nothing - and the wrong answer for keeping it, because a learner then never
   heard that the verb form was wrong.

   So: `shownIssues` is every trustworthy finding, and `anchored` says which
   of them "find it in my text" may be offered for. An unanchored finding is
   real guidance about a real mistake; it simply cannot promise a span, so it
   is never given a control that would jump to the wrong one. */
export function anchored(issue, text) {
  return Boolean(issue && issue.quote && text.includes(issue.quote));
}

export function shownIssues(result, text) {
  return (result.issues || []).filter((x) => x && (x.quote || x.fragment));
}

export function shownStrengths(result, text) {
  return (result.strengths || []).filter((x) => x && x.quote && text.includes(x.quote));
}

/* Preserve the capability envelope's answer about whether another request can
   help. A network/provider interruption offers one explicit retry; a disabled
   or invalid capability tells the truth without presenting a dead action.

   It is one compact line, wherever it is put. A provider that is not
   configured used to take half the workspace to say so, which is a lot of
   screen for news that changes nothing about the writing: the draft is safe
   and the room still works. */
export function writingReviewFailure(c, error) {
  const retryable = error?.retryable !== false;
  return `<p class="notice review-trouble" role="alert"><span>${esc(
    retryable ? c.reviewFailed : c.reviewUnavailable,
  )}</span>${
    retryable
      ? `<button type="button" class="quiet" data-retry-review>${esc(c.retry)}</button>`
      : ''
  }</p>`;
}

/* The whole-piece rewrite, when the evaluator offered one. It is one way to
   say it rather than the answer, so it sits after the individual corrections. */
function corrected(c, result, language) {
  if (!result.corrected_text) return '';
  return `<section class="review-corrected"><blockquote lang="${esc(language)}">${esc(result.corrected_text)}</blockquote></section>`;
}

/* Before the first review the result region stays quiet: it names what will
   appear there without spending the workspace on prompt copy. */
export function writingReviewWaiting(c) {
  return `<div class="review-waiting"><small>${esc(c.review)}</small><p>${esc(c.reviewWaiting)}</p></div>`;
}

/* What a learner needs first, and in this order: where they are, then what to
   do about it, then what is already working, then the history.

   The review once ran headline, summary, every dimension, every change since
   the last version, every strength and every issue as equals, ending in a
   whole-piece rewrite. That is a report, and the corrections were moved to the
   front of it. But "what should I fix?" is the second question a learner asks;
   the first is "how am I doing?" - and the measurement that answers it was
   then the thing buried, several folds down, after the corrections.

   So the overview leads: the score the evaluator gave, the level it read, the
   movement since the last version, and the dimensions it scored - compactly,
   as a few rows of numbers rather than a dashboard. Then the two or three
   things worth doing now. Then everything else, kept whole behind a fold.

   Nothing is dropped and nothing is invented: the payload decides what exists,
   and this only decides what is met first (DESIGN_CONTRACT rule 27). */
function fold(summary, body, { open = false } = {}) {
  return body
    ? `<details class="review-fold"${open ? ' open' : ''}><summary>${esc(summary)}</summary>${body}</details>`
    : '';
}

export function writingReview(c, result, { language, text }) {
  const overall = number(result.overall);
  const level = typeof result.app_cefr === 'string' ? result.app_cefr : '';
  const nothing =
    !shownIssues(result, text).length &&
    !shownStrengths(result, text).length &&
    !result.corrected_text;
  const measurement = dimensions(c, result);
  return `<div class="review">${
    result.evaluator === 'fallback-demo'
      ? `<p class="notice">${esc(c.demoMeasurement)}</p>`
      : ''
  }<section class="review-overview">${
    overall === null
      ? ''
      : `<div class="review-headline"><b>${Math.round(overall)}</b>${level ? `<span>${esc(level)}</span>` : ''}${movement(c, result)}</div>`
  }${
    result.summary?.interpretation
      ? `<p class="review-summary">${esc(result.summary.interpretation)}</p>`
      : ''
  }${measurement}</section>${nothing ? `<p class="review-none">${esc(c.noCorrections)}</p>` : ''}${issues(c, result, language, text)}${fold(c.reviewStrengths, strengths(c, result, language, text), { open: true })}${fold(c.reviewNext, priorities(c, result), { open: true })}${fold(c.reviewDeeper, deeper(c, result, language, text))}${fold(c.reviewSinceLast, comparison(c, result, text))}${fold(c.reviewWholePiece, corrected(c, result, language))}<p class="meta">${esc(c.reviewNotOneAnswer)}</p><p class="meta review-persisted">${esc(c.persisted)}</p><div class="button-row"><button class="outline" data-revise>${esc(c.revision)} ↗</button><button class="quiet" data-registers>${esc(c.registerExplore)} ↗</button></div></div>`;
}
