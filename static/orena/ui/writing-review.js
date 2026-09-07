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

function dimensions(c, result) {
  const source = result.dimensions || {};
  const keys = [...new Set([...RUBRIC, ...Object.keys(source)])].filter(
    (key) => number(source[key]) !== null,
  );
  if (!keys.length) return '';
  return `<section class="review-dimensions"><h3>${esc(c.reviewDimensions)}</h3><dl>${keys
    .map((key) => {
      const value = Math.round(number(source[key]));
      return `<div class="review-dimension"><dt>${esc(c[`rubric_${key}`] || key)}</dt><dd><span class="review-bar" aria-hidden="true"><i style="inline-size:${Math.max(0, Math.min(100, value))}%"></i></span><b>${value}</b></dd></div>`;
    })
    .join('')}</dl></section>`;
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

function strengths(c, result, language) {
  const items = (result.strengths || []).filter((x) => x && x.quote);
  if (!items.length) return '';
  return `<section class="review-strengths"><h3>${esc(c.reviewStrengths)}</h3>${items
    .map(
      (item) =>
        `<article><blockquote lang="${esc(language)}">${esc(item.quote)}</blockquote>${item.why ? `<p>${esc(item.why)}</p>` : ''}<small>${esc(c[`rubric_${item.category}`] || item.category)}</small></article>`,
    )
    .join('')}</section>`;
}

/* An issue carries the learner's own wording, what to write instead, why it is
   a problem, and the rule behind it. Each one can be taken further through the
   shared explanation surface, which is what `data-why` is for. */
function issues(c, result, language, text) {
  const items = (result.issues || []).filter(
    (x) => x && x.quote && text.includes(x.quote),
  );
  if (!items.length) return '';
  return `<section class="review-issues"><h3>${esc(c.reviewIssues)}</h3>${items
    .map(
      (item, index) =>
        `<article class="correction" data-priority="${esc(item.priority || 'medium')}"><small>${esc(c[`rubric_${item.category}`] || item.category)}</small><del lang="${esc(language)}">${esc(item.quote)}</del>${item.suggestion ? `<p lang="${esc(language)}">${esc(item.suggestion)}</p>` : ''}${item.why ? `<p class="review-why">${esc(item.why)}</p>` : ''}${item.how ? `<p class="meta">${esc(item.how)}</p>` : ''}<button class="quiet" data-why="${index}">${esc(c.askWhy)} ↗</button></article>`,
    )
    .join('')}</section>`;
}

function priorities(c, result) {
  const items = (result.next_actions || []).filter(Boolean);
  if (!items.length) return '';
  return `<section class="review-next"><h3>${esc(c.reviewNext)}</h3><ol>${items
    .map((item) => `<li>${esc(item)}</li>`)
    .join('')}</ol></section>`;
}

/* The issues this render actually offered, in the order shown, so the caller
   can bind "why?" to the right one without re-deriving the filter. */
export function shownIssues(result, text) {
  return (result.issues || []).filter((x) => x && x.quote && text.includes(x.quote));
}

export function writingReview(c, result, { language, text }) {
  const overall = number(result.overall);
  const level = typeof result.app_cefr === 'string' ? result.app_cefr : '';
  const nothing =
    !shownIssues(result, text).length &&
    !(result.strengths || []).length &&
    !result.corrected_text;
  return `<h2>${esc(c.review)}</h2>${
    result.evaluator === 'fallback-demo'
      ? `<p class="notice">${esc(c.demoMeasurement)}</p>`
      : ''
  }${
    overall === null
      ? ''
      : `<div class="review-headline"><b>${Math.round(overall)}</b>${level ? `<span>${esc(level)}</span>` : ''}${movement(c, result)}</div>`
  }${
    result.summary?.interpretation
      ? `<p class="review-summary">${esc(result.summary.interpretation)}</p>`
      : ''
  }${nothing ? `<p>${esc(c.noCorrections)}</p>` : ''}${
    result.corrected_text
      ? `<blockquote lang="${esc(language)}">${esc(result.corrected_text)}</blockquote>`
      : ''
  }${dimensions(c, result)}${strengths(c, result, language)}${issues(c, result, language, text)}${priorities(c, result)}<p class="meta">${esc(c.reviewNotOneAnswer)}</p><p>${esc(c.persisted)}</p><div class="button-row"><button class="outline" data-revise>${esc(c.revision)} ↗</button><button class="quiet" data-registers>${esc(c.registerExplore)} ↗</button></div>`;
}
