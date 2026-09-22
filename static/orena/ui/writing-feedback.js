/* The Writing room's review and revision (D-066), from the canonical baseline:
   FeedbackPanel, the error sheet and RevisionCompare. It reads the two contracts
   the backend serves - WritingReview (GET /api/essays/{id}/review) and
   RevisionCompare (GET /api/essays/{id}/revision) - and shows only what they
   carry. It adds no score, infers no dimension and writes no sentence about the
   learner that the evaluator did not say.

   A finding is kept; a highlight is earned. An issue whose words cannot be found
   in the learner's text (`anchored: false`) is still real guidance, so it is
   shown; it is never offered "apply", which would replace the wrong words. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { applyRevision, revisionTarget } from '../product/revision.js';
import { markedHtml } from './draft-marks.js';

// The four dimensions the baseline draws, in its order. The evaluator scores a
// fifth (task achievement) and keeps it; the baseline does not draw it.
export const DIMENSIONS = ['naturalness', 'grammar', 'vocabulary', 'coherence'];
export const KINDS = ['register', 'grammar', 'punctuation', 'vocabulary', 'naturalness'];
const KIND_CAMEL = {
  register: 'Register',
  grammar: 'Grammar',
  punctuation: 'Punctuation',
  vocabulary: 'Vocabulary',
  naturalness: 'Naturalness',
};
// Punctuation is struck through in the baseline's blue, everything else in its warm amber.
const strike = (kind) => (kind === 'punctuation' ? 'info' : 'warm');

const number = (value) => (typeof value === 'number' && Number.isFinite(value) ? value : null);
const label = (text, tone = '') => `<span class="wf-label${tone ? ` wf-label--${tone}` : ''}">${text}</span>`;
const chip = (action, text, attrs = '') =>
  `<button type="button" class="qs-chip qs-chip--ask wf-chip" data-wf="${action}"${attrs ? ` ${attrs}` : ''}>${esc(text)}</button>`;
const fill = (text, values) => Object.entries(values).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), text);

export const kindLabel = (c, kind) => c[`writingKind${KIND_CAMEL[kind] || KIND_CAMEL.grammar}`] || '';

function dimensionRow(c, name, value, from = null) {
  const now = Math.max(0, Math.min(100, value));
  const moved = from === null ? null : Math.round(value) - Math.round(from);
  const shown = from === null ? `${Math.round(value)}` : `${Math.round(from)} → ${Math.round(value)}`;
  return `<div class="wf-dimension"><dt>${esc(c[`rubric_${name}`] || name)}</dt><dd class="wf-bar" aria-hidden="true"><i style="inline-size:${now}%"></i></dd><dd class="wf-score" data-move="${moved === null ? 'none' : moved > 0 ? 'up' : moved < 0 ? 'down' : 'same'}"><b>${shown}</b></dd></div>`;
}

export function dimensionsHtml(c, dimensions, previous = null) {
  const rows = (dimensions || [])
    .filter((item) => number(item?.value) !== null)
    .map((item) => dimensionRow(c, item.name, item.value, previous ? number(previous[item.name]) : null));
  return rows.length ? `<section class="wf-section">${label(esc(c.writingDimensions))}<dl class="wf-dimensions">${rows.join('')}</dl></section>` : '';
}

function issueCard(c, issue, index, language, applied) {
  const kind = KINDS.includes(issue.kind) ? issue.kind : 'grammar';
  const chips = [
    issue.rule ? chip('rule', c.writingRuleChip, `data-issue="${index}"`) : '',
    issue.grammarRef ? `<a class="qs-chip qs-chip--ask wf-chip" href="#/grammar?id=${encodeURIComponent(issue.grammarRef)}">${esc(c.writingGrammarChip)}</a>` : '',
    chip('ask', c.quickChipAskMore, `data-issue="${index}"`),
  ].join('');
  return `<article class="wf-issue" data-issue="${index}" data-kind="${esc(kind)}"${applied ? ' data-applied="true"' : ''}><div class="wf-fix"><span class="wf-was wf-was--${strike(kind)}" lang="${esc(language)}">${esc(issue.fragment)}</span>${icon('arrow-right', { size: 15 })}<span class="wf-now" lang="${esc(language)}">${esc(issue.correction)}</span></div>${issue.why ? `<p class="wf-why">${esc(issue.why)}</p>` : ''}<div class="wf-chips">${chips}</div></article>`;
}

/* The review beside the draft: the overview, what went well, the findings, the dimensions. */
export function feedbackHtml(c, review, { language, applied = new Set() } = {}) {
  const issues = review.issues || [];
  const pending = issues.filter((issue) => !applied.has(issue.id));
  const overview = review.summary
    ? `<section class="wf-overview">${label(esc(c.writingOverview), 'soft')}<p>${esc(review.summary)}</p></section>`
    : '';
  const strengths = review.strengths
    ? `<section class="wf-section">${label(`${icon('check-circle', { filled: true, size: 14 })}${esc(c.writingStrengths)}`, 'good')}<p class="wf-text">${esc(review.strengths)}</p></section>`
    : '';
  const findings = issues.length
    ? `<section class="wf-section">${label(`${icon('warning-circle', { filled: true, size: 14 })}${esc(fill(c.writingIssuesCount, { n: pending.length }))}`, 'warn')}${
        pending.length
          ? issues.map((issue, index) => (applied.has(issue.id) ? '' : issueCard(c, issue, index, language, false))).join('')
          : `<p class="wf-text wf-done" role="status">${icon('check-circle', { filled: true, size: 16 })}${esc(c.writingAllApplied)}</p>`
      }</section>`
    : `<p class="wf-text" role="status">${esc(c.noCorrections)}</p>`;
  return `<div class="wf" data-review-version="${review.version}">${overview}${strengths}${findings}${dimensionsHtml(c, review.dimensions)}</div>`;
}

/* One finding, opened: the wording, what to write instead, why, the rule that
   carries over to other sentences, an example when the evaluator gave one, and
   the way to apply it. */
export function issueSheetHtml(c, issue, { language, support, thread = [], canApply = true } = {}) {
  const kind = KINDS.includes(issue.kind) ? issue.kind : 'grammar';
  const turns = thread.length
    ? `<div class="qs-thread" aria-live="polite">${thread
        .map(
          (turn) =>
            `<div class="qs-turn"><p class="qs-turn__q" lang="${esc(support)}">${esc(turn.question)}</p><p class="qs-turn__a qs-muted" lang="${esc(support)}">${esc(turn.state === 'loading' ? c.quickThinking : turn.state === 'failed' ? c.lookupFailed : turn.answer || c.quickNothing)}</p></div>`,
        )
        .join('')}</div>`
    : '';
  return `<button type="button" class="qs-x" data-wf="close" aria-label="${esc(c.quickClose)}">${icon('x', { size: 18 })}</button><div class="wf-sheet-head"><strong class="wf-sheet-fragment" lang="${esc(language)}">${esc(issue.fragment)}</strong><span class="qs-verdict__label qs-tone--${kind === 'punctuation' ? 'info' : 'warn'}">${esc(kindLabel(c, kind))}</span></div><div class="wf-fix wf-fix--sheet">${icon('arrow-down', { size: 16 })}<span class="wf-now" lang="${esc(language)}">${esc(issue.correction)}</span></div><hr class="qs-rule">${issue.why ? `<p class="qs-text">${esc(issue.why)}</p>` : ''}${issue.rule ? `<div class="qs-well">${label(esc(c.writingRuleLabel))}<p class="wf-rule">${esc(issue.rule)}</p></div>` : ''}${(issue.examples || []).length ? `<div class="wf-example">${label(esc(c.quickExamples))}<p lang="${esc(language)}">${esc(issue.examples[0])}</p></div>` : ''}${turns}<form class="qs-composer" data-wf-form><label class="sr-only" for="wf-question">${esc(c.quickChipAskMore)}</label><span class="qs-composer__field">${icon('chat-teardrop-text', { size: 18 })}<input id="wf-question" name="question" autocomplete="off" maxlength="400" placeholder="${esc(c.quickFreeQuestion)}"></span><button type="submit" class="qs-send" aria-label="${esc(c.quickSend)}">${icon('arrow-up', { filled: true, size: 19 })}</button></form><div class="qs-actions"><button type="button" class="qs-btn" data-wf="save-concept" aria-disabled="true" title="${esc(c.quickExplanationSoon)}">${icon('bookmark-simple', { size: 18 })}${esc(c.writingSaveConcept)}</button>${canApply ? `<button type="button" class="qs-btn qs-btn--primary" data-wf="apply">${icon('check', { size: 18 })}${esc(c.writingApply)}</button>` : ''}</div>`;
}

const column = (name, meta, body, tone = '') =>
  `<section class="wf-col${tone ? ` wf-col--${tone}` : ''}"><header>${label(esc(name))}<span class="wf-meta">${esc(meta)}</span></header>${body}</section>`;

/* The version beside the one before it: what was fixed, what is left, what is
   new, and how each dimension moved (a drop is a drop). The words of each
   change are the evaluator's own. */
export function revisionHtml(c, compare, { language } = {}) {
  const { previous, current } = compare;
  const fixed = compare.fixed || [];
  const remaining = compare.remaining || [];
  const added = compare.added || [];
  const total = fixed.length + remaining.length;
  const headline = total
    ? fill(c.writingFixedOf, { a: fixed.length, b: total })
    : added.length
      ? fill(c.writingNewCount, { n: added.length })
      : c.writingNoChanges;
  const counts = [
    [fixed.length, c.writingFixedCount, 'good', 'check-circle'],
    [remaining.length, c.writingRemainingCount, 'warn', 'warning-circle'],
    [added.length, c.writingNewCount, 'info', 'plus'],
  ]
    .filter(([n]) => n > 0)
    .map(([n, text, tone, glyph]) => `<span class="wf-count qs-tone--${tone}">${icon(glyph, { filled: glyph !== 'plus', size: 14 })}${esc(fill(text, { n }))}</span>`)
    .join('');
  const change = (item, state) =>
    `<li class="wf-change" data-state="${state}"><span class="wf-change__state qs-tone--${state === 'fixed' ? 'good' : state === 'added' ? 'info' : 'warn'}">${icon(state === 'fixed' ? 'check-circle' : state === 'added' ? 'plus' : 'warning-circle', { filled: state !== 'added', size: 16 })}</span><span><strong lang="${esc(language)}">${esc(item.title)}</strong><small>${esc(kindLabel(c, item.kind))}</small>${item.detail ? `<em lang="${esc(language)}">${esc(item.detail)}</em>` : ''}</span></li>`;
  const changes = [...fixed.map((i) => change(i, 'fixed')), ...remaining.map((i) => change(i, 'remaining')), ...added.map((i) => change(i, 'added'))];
  const deltas = (compare.dimensionDeltas || []).map((d) => ({ name: d.name, value: d.to }));
  // The words each change is about, marked in the versions they are found in: what was fixed and what is
  // still there in the earlier one, what is still there and what is new in the later one.
  const words = (list, tone) => list.map((item) => ({ fragment: item.title, tone }));
  const legend = [
    [fixed.length, c.writingLegendFixed, 'good'],
    [remaining.length, c.writingLegendRemaining, 'warm'],
    [added.length, c.writingLegendNew, 'info'],
  ]
    .filter(([n]) => n > 0)
    .map(([, text, tone]) => `<span class="wf-key"><i data-tone="${tone}"></i>${esc(text)}</span>`)
    .join('');
  const before = Object.fromEntries((compare.dimensionDeltas || []).map((d) => [d.name, d.from]));
  return `<div class="wf-revision"><header class="wf-banner">${label(esc(c.writingVsPrevious), 'soft')}<p class="wf-headline">${esc(headline)}</p><div class="wf-counts">${counts}</div></header>${legend ? `<div class="wf-legend">${legend}</div>` : ''}<div class="wf-cols">${column(fill(c.writingVersion, { n: previous.version }), fill(c.writingWords, { n: previous.wordCount }), `<p class="wf-draft" lang="${esc(language)}">${markedHtml(previous.text, [...words(fixed, 'good'), ...words(remaining, 'warm')])}</p>`)}${column(fill(c.writingVersion, { n: current.version }), fill(c.writingWords, { n: current.wordCount }), `<p class="wf-draft" lang="${esc(language)}">${markedHtml(current.text, [...words(remaining, 'warm'), ...words(added, 'info')])}</p>`, 'now')}${column(c.writingChanges, '', `${changes.length ? `<ul class="wf-changes">${changes.join('')}</ul>` : `<p class="wf-text">${esc(c.writingNoChanges)}</p>`}${dimensionsHtml(c, deltas, before)}`, 'changes')}</div></div>`;
}

/* A review that did not arrive is news about the review, not about the writing:
   one line, with a retry only when another request could help. */
export function writingReviewFailure(c, error) {
  const retryable = error?.retryable !== false;
  return `<p class="notice review-trouble" role="alert"><span>${esc(retryable ? c.reviewFailed : c.reviewUnavailable)}</span>${retryable ? `<button type="button" class="quiet" data-retry-review>${esc(c.retry)}</button>` : ''}</p>`;
}

/* Before the first review the result region stays quiet: it names what will appear there. */
export function writingReviewWaiting(c) {
  return `<div class="review-waiting"><small>${esc(c.review)}</small><p>${esc(c.reviewWaiting)}</p></div>`;
}

/* Where an applied fix goes. The words must be in the draft exactly once - a
   repeated quotation leaves the learner to choose - and the result must fit the
   writing limit; otherwise nothing is replaced and the finding stays guidance.
   The rule is the shared one (`product/revision.js`), not a second copy of it. */
export function applyFix(text, issue) {
  const target = revisionTarget(text, issue.fragment);
  const changed = target ? applyRevision(text, issue.fragment, issue.correction || '') : null;
  if (changed === null) return null;
  const replacement = issue.correction.trim();
  return { text: changed, start: target.start, end: target.start + replacement.length };
}

/* The controller: opens a finding as a sheet, asks about it, and applies it to
   the draft. The host owns the two regions (the feedback, the draft); this owns
   what the buttons in them do. */
export function bindWritingFeedback({ ctx, host, review, draft, language, alive, onApplied = () => {} }) {
  const { api, c } = ctx;
  const support = ctx.support;
  const applied = new Set();
  let sheet = null;
  let open = null;
  let scrim = null;
  let turns = 0;

  const paintFeedback = () => {
    host.innerHTML = feedbackHtml(c, review, { language, applied });
  };
  const closeSheet = () => {
    sheet?.remove();
    scrim?.remove();
    sheet = scrim = open = null;
  };
  const paintSheet = () => {
    if (!open || !alive()) return;
    if (!sheet) {
      sheet = document.createElement('div');
      sheet.setAttribute('role', 'dialog');
      sheet.setAttribute('aria-modal', 'false');
      sheet.tabIndex = -1;
      sheet.addEventListener('click', (event) => {
        const control = event.target.closest('[data-wf]');
        if (!control) return;
        if (control.dataset.wf === 'close') closeSheet();
        else if (control.dataset.wf === 'apply') apply();
      });
      sheet.addEventListener('submit', (event) => {
        const form = event.target.closest('[data-wf-form]');
        if (!form) return;
        event.preventDefault();
        const question = form.elements.question?.value.trim();
        form.reset();
        if (question) ask(question);
      });
      document.body.append(sheet);
      if (window.matchMedia('(max-width: 700px)').matches) {
        scrim = document.createElement('div');
        scrim.className = 'qs-scrim';
        scrim.addEventListener('click', closeSheet);
        document.body.append(scrim);
      }
    }
    sheet.className = 'qs qs--issue';
    sheet.setAttribute('aria-label', open.issue.fragment);
    // What the learner is typing survives the repaint that an answer causes.
    const typing = sheet.querySelector('input[name="question"]');
    const kept = typing ? { value: typing.value, focused: document.activeElement === typing, at: typing.selectionStart } : null;
    sheet.innerHTML = issueSheetHtml(c, open.issue, { language, support, thread: open.thread, canApply: applyFix(draft.value, open.issue) !== null });
    const typed = sheet.querySelector('input[name="question"]');
    if (kept && typed) {
      typed.value = kept.value;
      if (kept.focused) {
        typed.focus({ preventScroll: true });
        try {
          typed.setSelectionRange(kept.at, kept.at);
        } catch {
          // A caret that cannot be restored is not worth failing the paint for.
        }
      }
    }
    sheet.querySelector('.qs-turn:last-child')?.scrollIntoView({ block: 'nearest' });
  };
  const openIssue = (index) => {
    const issue = review.issues[index];
    if (!issue) return;
    if (sheet) closeSheet();
    open = { issue, thread: [] };
    paintSheet();
    sheet.focus({ preventScroll: true });
  };
  async function ask(question) {
    const { issue } = open;
    const text = draft.value;
    const sentence = text.split(/(?<=[.!?。！？])\s+/).find((part) => part.includes(issue.fragment)) || text;
    const turn = { id: ++turns, question, state: 'loading', answer: '' };
    open.thread.push(turn);
    paintSheet();
    try {
      const value = await api.sentenceSheet({
        text: issue.fragment.slice(0, 1600),
        context: sentence.slice(0, 2400),
        source_language: language,
        target_language: support,
        question,
      });
      turn.answer = value?.answer || '';
      turn.state = value?.available ? 'ready' : 'failed';
    } catch {
      turn.state = 'failed';
    }
    paintSheet();
  }
  function apply() {
    const { issue } = open;
    const fixed = applyFix(draft.value, issue);
    if (!fixed) return;
    draft.value = fixed.text;
    draft.dispatchEvent(new Event('input', { bubbles: true }));
    applied.add(issue.id);
    closeSheet();
    paintFeedback();
    draft.focus({ preventScroll: true });
    draft.setSelectionRange(fixed.start, fixed.end);
    onApplied(issue, applied.size);
  }

  paintFeedback();
  host.addEventListener('click', (event) => {
    const control = event.target.closest('[data-wf]');
    if (control && (control.dataset.wf === 'rule' || control.dataset.wf === 'ask')) openIssue(Number(control.dataset.issue));
  });
  // Tapping the finding itself opens it as well, as the baseline draws.
  host.addEventListener('click', (event) => {
    const card = event.target.closest('.wf-issue');
    if (card && !event.target.closest('a, button')) openIssue(Number(card.dataset.issue));
  });
  const onKey = (event) => {
    if (event.key === 'Escape' && sheet) closeSheet();
  };
  document.addEventListener('keydown', onKey);
  // The sheet belongs to the screen it was opened on: going anywhere else closes it.
  window.addEventListener('hashchange', closeSheet);
  return {
    applied: () => new Set(applied),
    close: closeSheet,
    destroy() {
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('hashchange', closeSheet);
      closeSheet();
    },
  };
}
