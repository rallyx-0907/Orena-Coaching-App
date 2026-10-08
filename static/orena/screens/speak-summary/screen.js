/* Speaking Summary (frame 42, `#/speak-summary`; D-091). A one-way "you're done" screen: no back
   button, no forward nav besides Practice Hub (confirmed against the source, D5/E2 §7). Reads
   this session's own speaking ledger (`product/speaking-session.js`) - real facts a measured take
   actually produced, never a formula (the source's own `xp = Math.max(5, score*0.4)` is not
   reproduced, matching `screens/lesson-complete`'s own precedent). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { readSpeakingSession } from '../../product/speaking-session.js';
import { loadAttemptsSince, loadCurrentSession } from '../../product/speaking-history.js';
import { api } from '../../infrastructure/api.js';
import { shellCopy } from '../../copy/shell.js';
import { t } from './copy.js';
import { tasksFor, tasksForServerSession, sessionScope, keyImprovement } from './model.js';

/* Every room that logs to the session ledger, by the kind it logs: Scripted Pronunciation's label
   is this screen's own; the other rooms are named as the shell names them. */
const TASK_LABEL = {
  scripted_pronunciation: () => t('taskScriptedPronunciation'),
  free_talk: () => shellCopy('freeTalk'),
  conversation: () => shellCopy('conversation'),
  situation_reaction: () => shellCopy('situationReaction'),
};

export default async function mountSpeakingSummary(element, ctx) {
  await useStyles('screens/speak-summary/speak-summary.css');
  element.classList.add('s-spsummary-root');

  /* This session (D-139 HD-8): the tasks this tab finished since it opened (`product/speaking-session.js`, a
     client session - no server notion of one exists). While it has any, only those are shown; with none, the
     last 7 days from the account, and the scope label says so. */
  const sessionTasks = readSpeakingSession();
  /* D-142: when the server keeps the practice session (ORENA_PRACTICE_SESSION on) and one is live, it is the session -
     the same on every tab and device. Otherwise (flag off, nothing live, unreadable) everything below is unchanged. */
  const current = await loadCurrentSession(api);
  if (!ctx.isCurrent()) return undefined;
  /* Feature on (`current` is not null): the server answer is authoritative, including `session: null` (none live). The
     tab ledger is then never read as the session, so it cannot revive an expired one; the seven-day view shows instead.
     Only the explicit feature-off answer (`current === null`) keeps the client ledger. */
  const { serverSession, useLedger } = sessionScope(current, sessionTasks);
  const inSession = serverSession ? true : useLedger;
  const since = useLedger ? Math.min(...sessionTasks.map((entry) => entry.at || Date.now())) - 60 * 1000 : Date.now() - 7 * 24 * 60 * 60 * 1000;
  const server = serverSession ? serverSession.rows : await loadAttemptsSince(api, new Date(since).toISOString());
  if (!ctx.isCurrent()) return undefined;
  if (server === null) throw new Error('speaking_history_unavailable');
  const labels = { accuracy: t('metricAccuracy'), fluency: t('metricFluency') };
  const tasks = serverSession
    ? tasksForServerSession(sessionTasks, serverSession, labels)
    : inSession
      ? tasksFor(sessionTasks, server || [], labels, { sessionOnly: true })
      : tasksFor([], server || [], labels);
  const improvement = keyImprovement(tasks);

  mount(
    element,
    html`<div class="s-spsummary-scroll" data-scroll-region>
      <div class="s-spsummary-hero">
        <span class="s-spsummary-hero__glow" aria-hidden="true"></span>
        <div class="s-spsummary-icon">${raw(icon('mic', { size: 28 }))}</div>
        <div class="s-spsummary-eyebrow">${t(inSession ? 'eyebrowSession' : 'eyebrow')}</div>
        <div class="s-spsummary-count">${tasks.length}${!inSession && server.length >= 100 ? '+' : ''}<span> ${t('tasksSuffix')}</span></div>
        ${tasks.length ? html`<div class="s-spsummary-evidence">${t('recordedInProgress')}</div>` : ''}
      </div>
      <div class="s-spsummary-card">
        <div class="s-spsummary-label">${t('tasksCompleted')}</div>
        ${
          tasks.length
            ? html`<div class="s-spsummary-tasks" data-scroll-region>${tasks.map(
                (task) => html`<div class="s-spsummary-task">
              <span class="s-spsummary-check">${raw(icon('check', { size: 14 }))}</span>
              <span class="s-spsummary-task__body"><span class="s-spsummary-task__label">${TASK_LABEL[task.kind] ? TASK_LABEL[task.kind]() : task.kind}</span>${task.note ? html`<span class="s-spsummary-task__note">${task.note}</span>` : ''}</span>
            </div>`,
              )}</div>`
            : html`<p class="s-spsummary-empty">${t('emptyTasks')}</p>`
        }
        ${improvement ? html`<div class="s-spsummary-improve"><b>${t('keyImprovementLabel')}</b> · ${t('keyImprovement', { label: improvement.label, value: improvement.value })}</div>` : ''}
        <div class="s-spsummary-actions">
          <button type="button" class="s-spsummary-primary" data-practice-more>${t('practiceMore')}</button>
          <button type="button" class="s-spsummary-secondary" data-practice-hub>${t('backToPracticeHub')}</button>
        </div>
      </div>
    </div>`,
  );

  element.querySelector('[data-practice-more]').addEventListener('click', () => ctx.go(ctx.href('skillhub', { skill: 'speak' })));
  element.querySelector('[data-practice-hub]').addEventListener('click', () => ctx.go(ctx.href('practice')));

  return undefined;
}
