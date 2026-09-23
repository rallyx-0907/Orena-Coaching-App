/* Reading: the content engine's operator surface.

   Six views behind one section - the review queue, what is published, what was
   rejected, what is archived, where content comes from, and the form that adds
   some. They are views of one catalog rather than six screens: the same table,
   the same preview, one status filter.

   The rules this file keeps, because they are the ones an operator would be
   hurt by:

   * **Nothing here decides.** Every action is a call to a server route that
     already exists; publishing is one of them, and it is never a side effect of
     opening, editing or approving anything.
   * **A list is a list.** The table renders what the list endpoint returns; the
     body, the source snapshot and the processing evidence arrive only when an
     operator opens Preview.
   * **Polling belongs to the console, not to a modal.** Submitting hands the
     work to `tray.js`, which the shell renders above every section and
     refreshes on one timer; this view keeps its own jobs table current while
     it is open. A learner never polls anything here - none of this code is in
     their module graph.
   * **Nothing rendered here is trusted markup.** Every value from the server
     goes through `esc`; a title an admin pasted from a hostile page is text. */
import { adminApi } from './api.js';
import { openDrawer } from './drawer.js';
import { errorBlock, failureDetail, loadingBlock, pending } from './states.js';
import { subscribe as onTrayChange, watch as watchJob } from './tray.js';
import { chip, dateTime, esc, fill, kv, mono, notice, num, panel, select, table } from './format.js';

export const VIEWS = ['queue', 'published', 'rejected', 'archived', 'sources', 'add'];
export const VIEW_STATUS = {
  queue: 'draft,processing,needs_review,ready',
  published: 'published',
  rejected: 'rejected',
  archived: 'archived,unpublished',
};
const INPUT_KINDS = ['text', 'url', 'file'];
const LANGUAGES = ['en', 'zh'];

export function cursorPager({ next = null, back = false, t }) {
  /* Keyset pagination, so the controls can only say what the server actually
     told us: there is another page, or there is not. No total, no page number
     - the server counts nothing to answer a list, and a page whose rows moved
     under it still lands on a stable boundary. */
  if (!next && !back) return '';
  return `<div class="ac-pager" role="group" aria-label="${esc(t.readingPager)}"><span class="ac-pager__buttons">`
    + `<button type="button" class="ac-button" data-ac-page="prev"${back ? '' : ' disabled'}>${esc(t.previous)}</button>`
    + `<button type="button" class="ac-button" data-ac-page="next" data-ac-cursor="${esc(next || '')}"${next ? '' : ' disabled'}>${esc(t.next)}</button>`
    + '</span></div>';
}

export function isUnavailable(error) {
  /* The engine's own "not active yet", whichever shape the client surfaced it
     in. Matched on the category the server sends, never on a message an
     operator's language would change. */
  const text = `${error?.category || ''} ${error?.message || ''} ${error?.body?.detail?.category || ''}`;
  return text.includes('reading_engine_unavailable') || text.includes('reading_articles_unavailable');
}

export function viewFrom(params) {
  const value = String(params?.view || '');
  return VIEWS.includes(value) ? value : 'queue';
}

export function viewTabs({ view, t, href }) {
  return `<nav class="ac-subtabs" aria-label="${esc(t.readingViewsLabel)}">${VIEWS.map((id) => {
    // Reading lives inside Content (canonical design), so its own views are
    // addresses within that section rather than a section of their own.
    const target = href('content', id === 'queue' ? { kind: 'reading' } : { kind: 'reading', view: id });
    return `<a class="ac-tab" href="${esc(target)}"${id === view ? ' aria-current="page"' : ''}>${esc(t[`readingView_${id}`])}</a>`;
  }).join('')}</nav>`;
}

export function articleRows(items, t, ui) {
  return items.map((item) => ({
    cells: [
      `<div class="ac-cell-stack"><strong>${esc(item.title || t.readingUntitled)}</strong><span class="ac-muted">${esc(item.topic || t.readingNoTopic)}</span></div>`,
      esc(t[`lang_${item.language}`] || item.language || ''),
      `<div class="ac-cell-stack">${esc(item.level || '—')}${item.reviewed_level ? `<span class="ac-muted">${esc(t.readingLevelReviewed)}</span>` : ''}</div>`,
      num(item.word_count, ui),
      esc(readingTime(item.reading_time_seconds, t)),
      chip(item.status || 'published', t),
      `<button type="button" class="ac-button" data-ac-open="${esc(item.id)}">${esc(t.actionPreview)}</button>`,
    ],
  }));
}

export function readingTime(seconds, t) {
  const minutes = Math.max(1, Math.round(Number(seconds || 0) / 60));
  return fill(t.readingMinutes, { count: minutes });
}

/* The design's target list: kept and dropped are both visible - a dropped
   target stays in place, dimmed, with the way back - and the reviewer sets the
   order the learner meets them in. Order moves one step at a time rather than
   by drag alone: a keyboard and a phone have to be able to do it too, and the
   rows become stacked cards below 600px where nothing can be dragged. */
export function targetRows(targets, t) {
  const last = targets.length - 1;
  return targets.map((target, index) => ({
    attributes: target.admin_rejected ? ' data-ac-dropped="1"' : '',
    cells: [
      `<div class="ac-order"><button type="button" class="ac-button ac-button--icon" data-ac-move="${esc(target.id)}" data-ac-direction="up"${index === 0 ? ' disabled' : ''} aria-label="${esc(fill(t.readingTargetMoveUp, { text: target.text }))}">↑</button><button type="button" class="ac-button ac-button--icon" data-ac-move="${esc(target.id)}" data-ac-direction="down"${index === last ? ' disabled' : ''} aria-label="${esc(fill(t.readingTargetMoveDown, { text: target.text }))}">↓</button></div>`,
      `<div class="ac-cell-stack"><strong>${esc(target.text)}</strong><span class="ac-muted">${esc(target.context || '')}</span></div>`,
      esc(t[`readingTargetType_${target.target_type}`] || target.target_type),
      target.admin_approved ? chip('ok', t, { label: t.readingTargetApproved })
        : target.admin_rejected ? chip('invalid', t, { label: t.readingTargetRejected })
        : chip('pending_review', t, { label: t.readingTargetSuggested }),
      target.admin_rejected
        ? `<div class="ac-actions"><button type="button" class="ac-button" data-ac-target="${esc(target.id)}" data-ac-decision="approve">${esc(t.readingTargetRestore)}</button></div>`
        : `<div class="ac-actions"><button type="button" class="ac-button" data-ac-target="${esc(target.id)}" data-ac-decision="approve">${esc(t.readingApprove)}</button><button type="button" class="ac-button" data-ac-target="${esc(target.id)}" data-ac-decision="reject">${esc(t.readingReject)}</button></div>`,
    ],
  }));
}

export function targetSummary(targets, t) {
  const dropped = targets.filter((target) => target.admin_rejected).length;
  return fill(t.readingTargetSummary, { kept: targets.length - dropped, dropped });
}

/* One job, as study 02-C reads it: what failed, at which stage, how many
   attempts are left, and the technical detail collapsed underneath rather than
   removed. The two actions are the two things an operator can do about it. */
export function jobDetailView(job, t, ui) {
  const stages = ['queued', 'fetching', 'normalizing', 'deduplicating', 'analyzing', 'building_candidate', 'done'];
  const reached = stages.indexOf(job.stage);
  const progress = `<ol class="ac-steps">${stages.map((stage, index) => `<li data-state="${index < reached ? 'done' : index === reached ? 'current' : 'todo'}">${esc(t[`readingStage_${stage}`] || stage)}</li>`).join('')}</ol>`;
  const failure = job.last_error_code
    ? `<div class="ac-problem" data-tone="warn"><strong>${esc(t[`error_${job.last_error_code}`] || job.last_error_code)}</strong>${
        job.last_error ? `<p class="ac-muted">${esc(job.last_error)}</p>` : ''
      }<p class="ac-muted">${esc(fill(t.readingJobAttempts, { attempt: job.attempt, max: job.max_attempts }))}</p></div>`
    : '';
  return `<div class="ac-stack">${failure}${kv([
    [t.readingColJob, esc(t[`readingJobType_${job.job_type}`] || job.job_type)],
    [t.colStatus, chip(job.status === 'completed' ? 'ok' : job.status === 'failed' ? 'invalid' : 'info', t, { label: t[`readingJobStatus_${job.status}`] || job.status })],
    [t.readingColStage, esc(t[`readingStage_${job.stage}`] || job.stage)],
    [t.colDate, esc(dateTime(job.created_at, ui))],
    [t.readingJobFinished, esc(job.finished_at ? dateTime(job.finished_at, ui) : '—')],
    [t.readingJobSubmittedBy, esc(job.submitted_by || '—')],
  ])}<section><h3>${esc(t.readingJobProgress)}</h3>${progress}</section><details class="ac-details"><summary>${esc(t.readingJobTechnical)}</summary>${kv([
    [t.readingJobId, mono(job.id)],
    [t.readingJobWorker, esc(job.claimed_by || '—')],
    [t.readingJobHeartbeat, esc(job.heartbeat_at ? dateTime(job.heartbeat_at, ui) : '—')],
    [t.readingJobNextRetry, esc(job.next_retry_at ? dateTime(job.next_retry_at, ui) : '—')],
    [t.readingJobResult, esc(job.result_kind || '—')],
  ])}</details></div>`;
}

export function jobDetailFooter(job, t) {
  const article = job.result_article_id
    ? `<a class="ac-button" href="#/admin?id=content&kind=reading">${esc(t.readingJobOpenArticle)}</a>`
    : '';
  const retry = job.status === 'failed'
    ? `<button type="button" class="ac-button ac-button--primary" data-ac-retry="${esc(job.id)}">${esc(t.readingRetry)}</button>`
    : '';
  return `${article}${retry}`;
}

export function qualityNote(analysis, t) {
  const issues = analysis?.quality_issues || [];
  if (!issues.length) return '';
  return notice(`${t.readingQualityTitle} ${issues.map((issue) => t[`readingIssue_${issue}`] || issue).join(', ')}`, 'warn');
}

/* Three answers, shown as three: `false` is a refusal and an absent answer is
   a question nobody asked, and an admin about to publish needs to know which
   one they are looking at. The tone follows that reading - an unanswered
   right is a review task, a refusal is a stop. */
const RIGHTS_TONE = {
  allowed: 'ok', denied: 'invalid', unknown: 'pending_review',
  required: 'info', not_required: 'ok',
};
const RIGHTS_QUESTIONS = ['can_republish', 'can_adapt', 'automation_allowed', 'attribution_required'];

export function rightsChips(state, t) {
  if (!state) return chip('pending_review', t, { label: t.readingRightsUnknown });
  return `<span class="ac-chips">${RIGHTS_QUESTIONS.map((question) => {
    const answer = state[question] || 'unknown';
    return chip(RIGHTS_TONE[answer] || 'pending_review', t, {
      label: fill(t.rightsAnswer, {
        question: t[`rightsQ_${question}`] || question,
        answer: t[`rightsA_${answer}`] || answer,
      }),
    });
  }).join('')}</span>`;
}

/* Rights help an operator decide; they do not decide for them. The engine has
   never gated publication on this and it still does not - what changes here is
   that the console says which of the three answers it is looking at, in the
   weight each deserves, next to the button that acts on it. */
export function rightsAdvice(state, t) {
  const answers = RIGHTS_QUESTIONS.map((question) => (state || {})[question] || 'unknown');
  if (answers.includes('denied')) return notice(t.rightsAdviceDenied, 'bad');
  if (answers.includes('unknown')) return notice(t.rightsAdviceUnknown, 'warn');
  return notice(t.rightsAdviceAllowed, 'ok');
}

export function previewBody(article, t, ui) {
  const source = article.source || {};
  const facts = kv([
    [t.readingFactLevel, `${esc(article.effective_level || '—')}${article.reviewed_level ? ` <span class="ac-muted">${esc(fill(t.readingFactEstimated, { value: article.estimated_level || '—' }))}</span>` : ''}`],
    [t.readingFactWords, esc(num(article.word_count, ui))],
    [t.readingFactTime, esc(readingTime(article.reading_time_seconds, t))],
    [t.readingFactStatus, chip(article.status, t)],
    [t.readingFactSource, esc(source.canonical_url || source.metadata?.input_kind || t.readingSourcePasted)],
    [t.readingFactAuthor, esc(source.author || '—')],
    [t.readingFactRights, rightsChips(source.rights_state, t)],
    [t.readingFactHash, mono(String(source.content_hash || '').slice(0, 12))],
  ]);
  /* The same bytes under another source is legitimate - rights are the
     source's - so this names the source rather than counting copies. A count
     tells an admin something is wrong; a name tells them what to decide. */
  const duplicates = (article.duplicates || []).length
    ? `${notice(t.readingDuplicateWarning, 'warn')}<ul class="ac-duplicates">${
        article.duplicates.map((copy) => `<li><strong>${esc(copy.source_name || copy.source_slug || copy.source_id)}</strong>${
          copy.title ? ` <span class="ac-muted">${esc(copy.title)}</span>` : ''
        }</li>`).join('')
      }</ul>`
    : '';
  const events = table({
    head: [t.colDate, t.readingEventAction, t.readingEventActor],
    rows: (article.events || []).map((event) => [
      esc(dateTime(event.created_at, ui)),
      esc(t[`readingEvent_${event.action}`] || event.action),
      esc(event.actor || '—'),
    ]),
    empty: t.readingNoEvents,
  });
  return [
    qualityNote(article.analysis, t),
    duplicates,
    facts,
    panel({ title: t.readingTargetsTitle, note: targetSummary(article.targets || [], t), body: table({
      head: [{ label: t.readingTargetOrder, hidden: true }, t.readingTargetText, t.readingTargetKind, t.readingTargetState, { label: t.colActions, hidden: true }],
      rows: targetRows(article.targets || [], t),
      empty: t.readingNoTargets,
    }) }),
    panel({ title: t.readingBodyTitle, body: `<div class="ac-reading-body">${esc(article.body || '').split('\n\n').map((para) => `<p>${esc(para)}</p>`).join('')}</div>` }),
    panel({ title: t.readingHistoryTitle, body: events }),
    rightsAdvice(article.source?.rights_state, t),
    `<form class="ac-form" data-ac-review>
      ${select({ name: 'reviewed_level', label: t.readingLevelOverride, options: [['', t.readingLevelKeep], ...levelOptions(article.language)], value: article.reviewed_level || '' })}
      <label class="ac-field"><span>${esc(t.readingTopic)}</span><input type="text" name="topic" value="${esc(article.topic || '')}" maxlength="120"></label>
      <label class="ac-field"><span>${esc(t.readingReason)}</span><input type="text" name="reason" maxlength="240" placeholder="${esc(t.readingReasonHint)}"></label>
      <div class="ac-actions">
        <button type="submit" class="ac-button" data-ac-action="save">${esc(t.readingSave)}</button>
        ${article.status === 'published'
          ? `<button type="button" class="ac-button" data-ac-action="unpublished">${esc(t.readingUnpublish)}</button>`
          : `<button type="button" class="ac-button ac-button--primary" data-ac-action="published">${esc(t.readingPublish)}</button>`}
        <button type="button" class="ac-button" data-ac-action="rejected">${esc(t.readingRejectArticle)}</button>
        <button type="button" class="ac-button" data-ac-action="archived">${esc(t.readingArchive)}</button>
      </div>
    </form>`,
  ].join('');
}

export function levelOptions(language) {
  const levels = language === 'zh'
    ? ['HSK1', 'HSK2', 'HSK3', 'HSK4', 'HSK5', 'HSK6']
    : ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
  return levels.map((level) => [level, level]);
}

export function sourceRows(sources, t, ui) {
  return sources.map((source) => ({
    cells: [
      `<div class="ac-cell-stack"><strong>${esc(source.name)}</strong><span class="ac-muted">${esc(source.base_url || source.slug)}</span></div>`,
      esc(t[`readingSourceType_${source.source_type}`] || source.source_type),
      chip(source.state === 'active' ? 'ok' : source.state === 'needs_review' ? 'pending_review' : 'info', t, {
        label: t[`readingSourceState_${source.state}`] || source.state,
      }),
      source.rights?.automation_allowed ? esc(t.readingAutomationAllowed) : esc(t.readingAutomationNo),
      source.polling_enabled ? chip('ok', t, { label: t.readingPollingOn }) : esc(t.readingPollingOff),
      esc(source.last_checked_at ? dateTime(source.last_checked_at, ui) : '—'),
      `<div class="ac-actions">${source.state === 'active'
        ? `<button type="button" class="ac-button" data-ac-source="${esc(source.id)}" data-ac-state="paused">${esc(t.readingPause)}</button>`
        : `<button type="button" class="ac-button" data-ac-source="${esc(source.id)}" data-ac-state="active">${esc(t.readingApproveSource)}</button>`}</div>`,
    ],
  }));
}


export function submissionFrom(fields, kind) {
  const answer = fields.can_republish?.value || '';
  return {
    kind,
    text: fields.text?.value || '',
    url: fields.url?.value || '',
    title: fields.title?.value || '',
    author: fields.author?.value || '',
    language: fields.language?.value || '',
    ...(answer ? { can_republish: answer === 'allowed' } : {}),
    license_note: fields.license_note?.value || '',
  };
}

export function addForms(t) {
  return INPUT_KINDS.map((kind) => `<form class="ac-form" data-ac-add="${kind}">
      <h3>${esc(t[`readingAdd_${kind}`])}</h3>
      <p class="ac-note">${esc(t[`readingAddHint_${kind}`])}</p>
      ${kind === 'text' ? `<label class="ac-field"><span>${esc(t.readingText)}</span><textarea name="text" rows="8" required></textarea></label>` : ''}
      ${kind === 'url' ? `<label class="ac-field"><span>${esc(t.readingUrl)}</span><input type="url" name="url" required placeholder="https://"></label>` : ''}
      ${kind === 'file' ? `<label class="ac-field"><span>${esc(t.readingFile)}</span><input type="file" name="upload" accept=".txt,.md,.html,.htm" required></label>` : ''}
      <label class="ac-field"><span>${esc(t.readingTitle)}</span><input type="text" name="title" maxlength="240"></label>
      <label class="ac-field"><span>${esc(t.readingAuthor)}</span><input type="text" name="author" maxlength="120"></label>
      ${select({ name: 'language', label: t.readingLanguage, options: LANGUAGES.map((code) => [code, t[`lang_${code}`]]) })}
      ${select({ name: 'can_republish', label: t.readingRightsRepublish, options: [
        ['', t.readingRightsUnanswered], ['allowed', t.readingRightsAllowed], ['denied', t.readingRightsDenied],
      ] })}
      <label class="ac-field"><span>${esc(t.readingLicense)}</span><input type="text" name="license_note" maxlength="240" placeholder="${esc(t.readingLicenseHint)}"></label>
      <div class="ac-actions"><button type="submit" class="ac-button ac-button--primary">${esc(t.readingSubmit)}</button></div>
    </form>`).join('');
}

export function jobRows(jobs, t, ui) {
  return jobs.map((job) => ({
    cells: [
      esc(t[`readingJobType_${job.job_type}`] || job.job_type),
      chip(job.status === 'completed' ? 'ok' : job.status === 'failed' ? 'invalid' : 'info', t, {
        label: t[`readingJobStatus_${job.status}`] || job.status,
      }),
      esc(t[`readingStage_${job.stage}`] || job.stage),
      esc(`${job.attempt}/${job.max_attempts}`),
      job.last_error_code ? esc(t[`error_${job.last_error_code}`] || job.last_error_code) : '—',
      esc(dateTime(job.created_at, ui)),
      `<div class="ac-actions"><button type="button" class="ac-button" data-ac-job="${esc(job.id)}">${esc(t.actionPreview)}</button>${
        job.status === 'failed'
          ? `<button type="button" class="ac-button" data-ac-retry="${esc(job.id)}">${esc(t.readingRetry)}</button>`
          : ''
      }</div>`,
    ],
  }));
}

function articleTable(page, t, ui) {
  return table({
    head: [t.readingColTitle, t.colLanguage, t.readingColLevel, { label: t.readingColWords, numeric: true },
           t.readingColTime, t.colStatus, { label: t.colActions, hidden: true }],
    rows: articleRows(page.items || [], t, ui),
    empty: t.readingEmpty,
    caption: t.readingCaption,
  });
}


/* The job pane, opened from wherever a job is listed - the Reading section and
   Imports both show the same failure, so they open the same view of it. */
export async function openJob(api, jobId, { t, ui, onChange = null } = {}) {
  const drawer = openDrawer({ title: t.readingJobTitle, body: loadingBlock(t, { rows: 3 }), label: t.close });
  const paint = async () => {
    try {
      const job = await api.readingJob(jobId);
      drawer.set(jobDetailView(job, t, ui), jobDetailFooter(job, t));
    } catch (error) {
      const failure = failureDetail(error, t);
      drawer.set(errorBlock(t, { detail: failure.detail, reference: failure.reference, retry: false }), '');
    }
  };
  await paint();
  drawer.element.addEventListener('click', async (event) => {
    const retry = event.target.closest('[data-ac-retry]');
    if (!retry) return;
    await api.readingRetryJob(retry.dataset.acRetry);
    await paint();
    onChange?.();
  });
  return drawer;
}

export async function renderReading(host, env) {
  const { t, ui, alive, href } = env;
  const api = env.api || adminApi;
  const view = viewFrom(env.params);
  /* One page position per section render: the cursor being shown, and the
     cursors walked to get here so Previous can go back. Keyset pagination has
     no page numbers to jump to, and inventing some would mean counting the
     whole corpus to draw a list. */
  const page = { cursor: null, back: [] };
  /* Whether the last thing that happened in this view was a submission. It is
     what decides between the form and the confirmation that replaces it. */
  let queued = false;
  let timer = null;
  let stopWatching = () => {};
  const stop = () => {
    clearInterval(timer);
    timer = null;
  };

  const paint = (body) => {
    if (!alive() || !host) return;
    host.innerHTML = `${viewTabs({ view, t, href })}${body}`;
  };

  const openArticle = async (id) => {
    const drawer = openDrawer({ title: t.readingPreviewTitle, label: t.close });
    try {
      const article = await api.readingArticle(id);
      drawer.set(previewBody(article, t, ui));
      drawer.body.addEventListener('click', async (event) => {
        const target = event.target.closest('[data-ac-target]');
        const move = event.target.closest('[data-ac-move]');
        const action = event.target.closest('[data-ac-action]');
        if (move) {
          /* The whole order is sent, never a move: the server is told the
             arrangement the reviewer meant, so a second reviewer's drag cannot
             interleave with this one into an order neither of them chose. */
          const current = (await api.readingArticle(id)).targets.map((entry) => entry.id);
          const from = current.indexOf(move.dataset.acMove);
          const to = move.dataset.acDirection === 'up' ? from - 1 : from + 1;
          if (from < 0 || to < 0 || to >= current.length) return;
          current.splice(to, 0, ...current.splice(from, 1));
          await api.readingReorderTargets(id, current);
          drawer.set(previewBody(await api.readingArticle(id), t, ui));
          /* Keep the keyboard where it was. A target that reached an end has a
             disabled button there, so focus lands on the one that still works
             rather than falling back to the top of the drawer. */
          const moved = [...drawer.body.querySelectorAll(`[data-ac-move="${CSS.escape(move.dataset.acMove)}"]`)];
          (moved.find((button) => button.dataset.acDirection === move.dataset.acDirection && !button.disabled)
            || moved.find((button) => !button.disabled))?.focus();
          return;
        }
        if (target) {
          await api.readingDecideTarget(id, target.dataset.acTarget, target.dataset.acDecision === 'approve');
          drawer.set(previewBody(await api.readingArticle(id), t, ui));
          return;
        }
        if (!action || action.dataset.acAction === 'save') return;
        const form = drawer.body.querySelector('[data-ac-review]');
        const reason = form?.elements?.reason?.value?.trim() || '';
        if (action.dataset.acAction === 'rejected' && !reason) {
          env.notify(t.readingReasonRequired);
          return;
        }
        await api.readingSetStatus(id, action.dataset.acAction, reason);
        env.notify(t[`readingDone_${action.dataset.acAction}`] || t.readingDone);
        drawer.close();
        await loadOrExplain();
      });
      drawer.body.addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = event.target;
        await api.readingEditArticle(id, {
          reviewed_level: form.elements.reviewed_level.value || '',
          topic: form.elements.topic.value,
          reason: form.elements.reason.value,
        });
        env.notify(t.readingSaved);
        drawer.set(previewBody(await api.readingArticle(id), t, ui));
        await loadOrExplain();
      });
    } catch (error) {
      drawer.set(notice(error?.message || t.loadFailed, 'bad'));
    }
  };

  const load = async () => {
    if (view === 'sources') {
      const sources = await api.readingSources();
      paint(panel({
        title: t.readingSourcesTitle,
        note: t.readingSourcesNote,
        body: table({
          head: [t.readingColSource, t.readingColKind, t.colStatus, t.readingColAutomation, t.readingColPolling,
                 t.readingColChecked, { label: t.colActions, hidden: true }],
          rows: sourceRows(sources.items || [], t, ui),
          empty: t.readingNoSources,
        }),
      }));
      return;
    }
    if (view === 'add') {
      const jobs = await api.readingJobs({ limit: 10, cursor: page.cursor || '' });
      /* Study 04: the form is gone once the work is queued. What stands in its
         place says where the work went and offers the next submission - the
         tray in the console frame carries the progress from here, so nothing
         waits in front of the operator. */
      paint(`${queued
        ? panel({ title: t.readingAddTitle, body: `<div class="ac-state" data-state="success"><p class="ac-state__title">${esc(t.readingQueuedTitle)}</p><p class="ac-state__note">${esc(t.readingQueuedNote)}</p><div class="ac-state__actions"><button type="button" class="ac-button ac-button--primary" data-ac-add-another>${esc(t.readingAddAnother)}</button><a class="ac-link" href="${esc(href('imports'))}">${esc(t.readingTrayOpenImports)}</a></div></div>` })
        : panel({ title: t.readingAddTitle, note: t.readingAddNote, body: `<div class="ac-forms">${addForms(t)}</div>` })}
        ${panel({ title: t.readingJobsTitle, note: t.readingJobsNote, body: table({
          head: [t.readingColJob, t.colStatus, t.readingColStage, t.readingColAttempt, t.colError, t.colDate,
                 { label: t.colActions, hidden: true }],
          rows: jobRows(jobs.items || [], t, ui),
          empty: t.readingNoJobs,
        }) + cursorPager({ next: jobs.next_cursor, back: page.back.length > 0, t }) })}`);
      return;
    }
    const listed = await api.readingQueue({
      status: VIEW_STATUS[view],
      cursor: page.cursor || '',
    });
    paint(panel({
      title: t[`readingView_${view}`],
      note: t[`readingNote_${view}`],
      body: articleTable(listed, t, ui)
        + cursorPager({ next: listed.next_cursor, back: page.back.length > 0, t }),
    }));
  };

  /* A runtime where the reviewed schema is not applied answers 503 for every
     route here. That is a state, not a failure: the section keeps its views
     and says so, rather than collapsing into the shell's generic error. */
  const loadOrExplain = async () => {
    try {
      await load();
    } catch (error) {
      if (!isUnavailable(error)) throw error;
      paint(panel({ title: t.readingOpsTitle, body: notice(t.readingOpsUnavailable, 'neutral') }));
    }
  };

  await loadOrExplain();

  const onClick = async (event) => {
    const step = event.target.closest('[data-ac-page]');
    if (step) {
      if (step.dataset.acPage === 'next') {
        page.back.push(page.cursor);
        page.cursor = step.dataset.acCursor || null;
      } else {
        page.cursor = page.back.pop() ?? null;
      }
      await loadOrExplain();
      return;
    }
    const open = event.target.closest('[data-ac-open]');
    if (open) {
      await openArticle(open.dataset.acOpen);
      return;
    }
    const jobOpen = event.target.closest('[data-ac-job]');
    if (jobOpen) {
      await openJob(api, jobOpen.dataset.acJob, { t, ui, onChange: loadOrExplain });
      return;
    }
    const retry = event.target.closest('[data-ac-retry]');
    if (retry) {
      await api.readingRetryJob(retry.dataset.acRetry);
      env.notify(t.readingRetried);
      await loadOrExplain();
      return;
    }
    if (event.target.closest('[data-ac-add-another]')) {
      queued = false;
      await loadOrExplain();
      return;
    }
    const source = event.target.closest('[data-ac-source]');
    if (source) {
      await api.readingSetSourceState(source.dataset.acSource, source.dataset.acState);
      env.notify(t.readingSourceUpdated);
      await loadOrExplain();
    }
  };

  const onSubmit = async (event) => {
    const form = event.target.closest('[data-ac-add]');
    if (!form) return;
    event.preventDefault();
    const kind = form.dataset.acAdd;
    const fields = form.elements;
    const submitted = submissionFrom(fields, kind);
    const submit = form.querySelector('button[type="submit"]');
    pending(submit, t, 'running');
    try {
      const job = await api.readingSubmit(submitted, fields.upload?.files?.[0] || null);
      pending(submit, t, 'idle');
      env.notify(job.duplicate ? t.readingSubmitDuplicate : t.readingSubmitted);
      /* The form is done the moment the work is queued. The tray takes it from
         here and follows the operator out of this view, so what replaces the
         form is a confirmation and the way to submit another - not the form
         again, and not a modal to sit in front of. */
      watchJob({
        id: job.id,
        label: submitted.title || submitted.url || fields.upload?.files?.[0]?.name || '',
      });
      form.reset();
      queued = true;
      await loadOrExplain();
    } catch (error) {
      pending(submit, t, 'failed');
      env.notify(error?.message || t.readingSubmitFailed);
    }
  };

  host.addEventListener('click', onClick);
  host.addEventListener('submit', onSubmit);
  /* There is one clock in the console and it belongs to the tray. Add Content
     used to run a second interval over the same jobs; now it redraws when the
     tray learns something, so the server is asked once per round however many
     things are watching. */
  if (view === 'add') {
    stopWatching = onTrayChange(() => {
      if (!alive()) return;
      loadOrExplain().catch(() => {});
    });
  }

  return () => {
    stop();
    stopWatching();
    host.removeEventListener('click', onClick);
    host.removeEventListener('submit', onSubmit);
  };
}
