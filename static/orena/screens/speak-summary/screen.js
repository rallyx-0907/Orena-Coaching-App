/* Speaking Summary (frame 42, `#/speak-summary`; D-091). A one-way "you're done" screen: no back
   button, no forward nav besides Practice Hub (confirmed against the source, D5/E2 §7). Reads
   this session's own speaking ledger (`product/speaking-session.js`) - real facts a measured take
   actually produced, never a formula (the source's own `xp = Math.max(5, score*0.4)` is not
   reproduced, matching `screens/lesson-complete`'s own precedent). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { readSpeakingSession } from '../../product/speaking-session.js';
import { shellCopy } from '../../copy/shell.js';
import { t } from './copy.js';
import { tasksFor, keyImprovement } from './model.js';

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

  const session = readSpeakingSession();
  const tasks = tasksFor(session);
  const improvement = keyImprovement(session);

  mount(
    element,
    html`<div class="s-spsummary-scroll" data-scroll-region>
      <div class="s-spsummary-hero">
        <span class="s-spsummary-hero__glow" aria-hidden="true"></span>
        <div class="s-spsummary-icon">${raw(icon('mic', { size: 28 }))}</div>
        <div class="s-spsummary-eyebrow">${t('eyebrow')}</div>
        <div class="s-spsummary-count">${tasks.length}<span> ${t('tasksSuffix')}</span></div>
        ${tasks.length ? html`<div class="s-spsummary-evidence">${t('recordedInProgress')}</div>` : ''}
      </div>
      <div class="s-spsummary-card">
        <div class="s-spsummary-label">${t('tasksCompleted')}</div>
        ${
          tasks.length
            ? html`<div class="s-spsummary-tasks">${tasks.map(
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
