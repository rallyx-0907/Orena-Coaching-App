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
   * **Polling belongs to the view that needs it.** Add Content watches its own
     jobs while it is open and stops the moment the section is left. A learner
     never polls anything here - none of this code is in their module graph.
   * **Nothing rendered here is trusted markup.** Every value from the server
     goes through `esc`; a title an admin pasted from a hostile page is text. */
import { adminApi } from './api.js';
import { openDrawer } from './drawer.js';
import { chip, dateTime, esc, fill, kv, mono, notice, num, panel, select, table } from './format.js';

export const VIEWS = ['queue', 'published', 'rejected', 'archived', 'sources', 'add'];
export const VIEW_STATUS = {
  queue: 'draft,processing,needs_review,ready',
  published: 'published',
  rejected: 'rejected',
  archived: 'archived,unpublished',
};
/* Job state is worth watching while an operator is looking at it, and worth
   nothing when they are not. Five seconds is slow enough to be polite and fast
   enough that a paste feels answered. */
export const JOB_POLL_MS = 5000;
const INPUT_KINDS = ['text', 'url', 'file'];
const LANGUAGES = ['en', 'zh'];

export function viewFrom(params) {
  const value = String(params?.view || '');
  return VIEWS.includes(value) ? value : 'queue';
}

export function viewTabs({ view, t, href }) {
  return `<nav class="ac-subtabs" aria-label="${esc(t.readingViewsLabel)}">${VIEWS.map((id) => {
    const target = href('reading', id === 'queue' ? {} : { view: id });
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

export function targetRows(targets, t) {
  return targets.map((target) => ({
    cells: [
      `<div class="ac-cell-stack"><strong>${esc(target.text)}</strong><span class="ac-muted">${esc(target.context || '')}</span></div>`,
      esc(t[`readingTargetType_${target.target_type}`] || target.target_type),
      target.admin_approved ? chip('ok', t, { label: t.readingTargetApproved })
        : target.admin_rejected ? chip('invalid', t, { label: t.readingTargetRejected })
        : chip('pending_review', t, { label: t.readingTargetSuggested }),
      `<div class="ac-actions"><button type="button" class="ac-button" data-ac-target="${esc(target.id)}" data-ac-decision="approve">${esc(t.readingApprove)}</button><button type="button" class="ac-button" data-ac-target="${esc(target.id)}" data-ac-decision="reject">${esc(t.readingReject)}</button></div>`,
    ],
  }));
}

export function qualityNote(analysis, t) {
  const issues = analysis?.quality_issues || [];
  if (!issues.length) return '';
  return notice(`${t.readingQualityTitle} ${issues.map((issue) => t[`readingIssue_${issue}`] || issue).join(', ')}`, 'warn');
}

export function previewBody(article, t, ui) {
  const source = article.source || {};
  const rights = source.rights || {};
  const facts = kv([
    [t.readingFactLevel, `${esc(article.effective_level || '—')}${article.reviewed_level ? ` <span class="ac-muted">${esc(fill(t.readingFactEstimated, { value: article.estimated_level || '—' }))}</span>` : ''}`],
    [t.readingFactWords, esc(num(article.word_count, ui))],
    [t.readingFactTime, esc(readingTime(article.reading_time_seconds, t))],
    [t.readingFactStatus, chip(article.status, t)],
    [t.readingFactSource, esc(source.canonical_url || source.metadata?.input_kind || t.readingSourcePasted)],
    [t.readingFactAuthor, esc(source.author || '—')],
    [t.readingFactRights, rights.can_republish ? esc(t.readingRightsGiven) : chip('pending_review', t, { label: t.readingRightsUnknown })],
    [t.readingFactHash, mono(String(source.content_hash || '').slice(0, 12))],
  ]);
  const duplicates = (article.duplicates || []).length
    ? notice(fill(t.readingDuplicateWarning, { count: article.duplicates.length }), 'warn')
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
    panel({ title: t.readingTargetsTitle, body: table({
      head: [t.readingTargetText, t.readingTargetKind, t.readingTargetState, { label: t.colActions, hidden: true }],
      rows: targetRows(article.targets || [], t),
      empty: t.readingNoTargets,
    }) }),
    panel({ title: t.readingBodyTitle, body: `<div class="ac-reading-body">${esc(article.body || '').split('\n\n').map((para) => `<p>${esc(para)}</p>`).join('')}</div>` }),
    panel({ title: t.readingHistoryTitle, body: events }),
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
      <label class="ac-check"><input type="checkbox" name="can_republish"> <span>${esc(t.readingRightsRepublish)}</span></label>
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
      job.status === 'failed'
        ? `<button type="button" class="ac-button" data-ac-retry="${esc(job.id)}">${esc(t.readingRetry)}</button>`
        : '',
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

export async function renderReading(host, env) {
  const { t, ui, alive, href } = env;
  const api = env.api || adminApi;
  const view = viewFrom(env.params);
  let timer = null;
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
        const action = event.target.closest('[data-ac-action]');
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
        await load();
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
        await load();
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
      const jobs = await api.readingJobs({ limit: 10 });
      paint(`${panel({ title: t.readingAddTitle, note: t.readingAddNote, body: `<div class="ac-forms">${addForms(t)}</div>` })}
        ${panel({ title: t.readingJobsTitle, note: t.readingJobsNote, body: table({
          head: [t.readingColJob, t.colStatus, t.readingColStage, t.readingColAttempt, t.colError, t.colDate,
                 { label: t.colActions, hidden: true }],
          rows: jobRows(jobs.items || [], t, ui),
          empty: t.readingNoJobs,
        }) })}`);
      return;
    }
    const page = view === 'queue'
      ? await api.readingQueue({ status: VIEW_STATUS.queue })
      : await api.readingQueue({ status: VIEW_STATUS[view] });
    paint(panel({ title: t[`readingView_${view}`], note: t[`readingNote_${view}`], body: articleTable(page, t, ui) }));
  };

  await load();

  const onClick = async (event) => {
    const open = event.target.closest('[data-ac-open]');
    if (open) {
      await openArticle(open.dataset.acOpen);
      return;
    }
    const retry = event.target.closest('[data-ac-retry]');
    if (retry) {
      await api.readingRetryJob(retry.dataset.acRetry);
      env.notify(t.readingRetried);
      await load();
      return;
    }
    const source = event.target.closest('[data-ac-source]');
    if (source) {
      await api.readingSetSourceState(source.dataset.acSource, source.dataset.acState);
      env.notify(t.readingSourceUpdated);
      await load();
    }
  };

  const onSubmit = async (event) => {
    const form = event.target.closest('[data-ac-add]');
    if (!form) return;
    event.preventDefault();
    const kind = form.dataset.acAdd;
    const fields = form.elements;
    const submitted = {
      kind,
      text: fields.text?.value || '',
      url: fields.url?.value || '',
      title: fields.title?.value || '',
      author: fields.author?.value || '',
      language: fields.language?.value || '',
      can_republish: Boolean(fields.can_republish?.checked),
      license_note: fields.license_note?.value || '',
    };
    try {
      const job = await api.readingSubmit(submitted, fields.upload?.files?.[0] || null);
      env.notify(job.duplicate ? t.readingSubmitDuplicate : t.readingSubmitted);
      form.reset();
      await load();
    } catch (error) {
      env.notify(error?.message || t.readingSubmitFailed);
    }
  };

  host.addEventListener('click', onClick);
  host.addEventListener('submit', onSubmit);
  /* Polling exists only here, only while Add Content is open, and stops with
     the section. Nothing else in Orena watches a job. */
  if (view === 'add' && typeof setInterval === 'function') {
    timer = setInterval(() => {
      if (!alive()) {
        stop();
        return;
      }
      load().catch(() => {});
    }, JOB_POLL_MS);
  }

  return () => {
    stop();
    host.removeEventListener('click', onClick);
    host.removeEventListener('submit', onSubmit);
  };
}
