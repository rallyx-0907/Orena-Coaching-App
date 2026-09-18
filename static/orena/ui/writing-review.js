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

// A dimension that moved says by how much, so progress is visible where it
// happened rather than only in the single overall number.
function moved(c, delta, key) {
  const change = delta && typeof delta === 'object' ? number(delta[key]) : null;
  if (change === null || Math.round(change) === 0) return '';
  const up = change > 0;
  return `<span class="dimension-move" data-direction="${up ? 'up' : 'down'}">${up ? '+' : ''}${Math.round(change)}</span>`;
}

function dimensions(c, result) {
  const source = result.dimensions || {};
  const keys = [...new Set([...RUBRIC, ...Object.keys(source)])].filter(
    (key) => number(source[key]) !== null,
  );
  if (!keys.length) return '';
  return `<section class="review-dimensions"><dl>${keys
    .map((key) => {
      const value = Math.round(number(source[key]));
      return `<div class="review-dimension"><dt>${esc(c[`rubric_${key}`] || key)}</dt><dd><span class="review-bar" aria-hidden="true"><i style="inline-size:${Math.max(0, Math.min(100, value))}%"></i></span><b>${value}</b>${moved(c, result.delta, key)}</dd></div>`;
    })
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

function correction(c, item, index, language) {
  return `<article class="correction" data-issue="${index}" data-priority="${esc(item.priority || 'medium')}"><small class="correction__category">${esc(c[`rubric_${item.category}`] || item.category)}</small><p class="correction__row correction__wrote"><span class="correction__label">${esc(c.reviewYouWrote)}</span><del lang="${esc(language)}">${esc(item.quote)}</del></p>${item.suggestion ? `<p class="correction__row correction__fix"><span class="correction__label">${esc(c.reviewCorrection)}</span><strong lang="${esc(language)}">${esc(item.suggestion)}</strong></p>` : ''}${item.why ? `<p class="correction__row correction__why"><span class="correction__label">${esc(c.reviewWhy)}</span><span>${esc(item.why)}</span></p>` : ''}${item.how ? `<p class="correction__rule"><span class="correction__label">${esc(c.reviewRule)}</span><span>${esc(item.how)}</span></p>` : ''}<div class="button-row"><button class="quiet" data-locate="${index}">${esc(c.reviewLocate)}</button><button class="quiet" data-why="${index}">${esc(c.askWhy)} ↗</button><button class="outline" data-try-revision="${index}">${esc(c.revisionTry)} ↗</button></div></article>`;
}

/* Ten findings shown as equals is a wall, and a beginner reads none of them.
   The few worth doing now lead; the rest are a fold away, still whole. */
export function orderedIssues(result, text) {
  return shownIssues(result, text)
    .map((item, index) => ({ item, index }))
    .sort((a, b) => (PRIORITY[a.item.priority] ?? 1) - (PRIORITY[b.item.priority] ?? 1));
}

const FOCUS = 3;

function issues(c, result, language, text) {
  const ordered = orderedIssues(result, text);
  if (!ordered.length) return '';
  const focus = ordered.slice(0, FOCUS);
  const rest = ordered.slice(FOCUS);
  return `<section class="review-issues"><h3>${esc(c.reviewFocus)}</h3>${focus
    .map(({ item, index }) => correction(c, item, index, language))
    .join('')}${
    rest.length
      ? `<details class="review-fold"><summary>${esc(c.reviewMore)} <span>${rest.length}</span></summary>${rest
          .map(({ item, index }) => correction(c, item, index, language))
          .join('')}</details>`
      : ''
  }</section>`;
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
export function shownIssues(result, text) {
  return (result.issues || []).filter((x) => x && x.quote && text.includes(x.quote));
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

/* What a learner needs first, and in this order: what to do about this piece,
   then what is already working, then the measurement, then the history.

   The review used to run headline, summary, every dimension, every change
   since the last version, every strength and every issue as equals, ending in
   a whole-piece rewrite. That is a report. A learner revising wants two or
   three things to fix and their own words to fix them in, so the corrections
   lead and everything else is kept, whole, behind a fold. Nothing is dropped:
   the payload still decides what exists, and this only decides what is met
   first (DESIGN_CONTRACT rule 27). */
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
  }<div class="review-head">${
    overall === null
      ? ''
      : `<div class="review-headline"><b>${Math.round(overall)}</b>${level ? `<span>${esc(level)}</span>` : ''}${movement(c, result)}</div>`
  }${
    result.summary?.interpretation
      ? `<p class="review-summary">${esc(result.summary.interpretation)}</p>`
      : ''
  }</div>${nothing ? `<p class="review-none">${esc(c.noCorrections)}</p>` : ''}${issues(c, result, language, text)}${fold(c.reviewStrengths, strengths(c, result, language, text))}${fold(c.reviewNext, priorities(c, result))}${fold(c.reviewDimensions, measurement)}${fold(c.reviewSinceLast, comparison(c, result, text))}${fold(c.reviewWholePiece, corrected(c, result, language))}<p class="meta">${esc(c.reviewNotOneAnswer)}</p><p class="meta review-persisted">${esc(c.persisted)}</p><div class="button-row"><button class="outline" data-revise>${esc(c.revision)} ↗</button><button class="quiet" data-registers>${esc(c.registerExplore)} ↗</button></div></div>`;
}
