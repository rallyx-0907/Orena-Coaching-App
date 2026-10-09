/* Attempt History (frame 41, `#/speak/:id/attempts`; D-091). Every attempt this tab knows of for
   one line (`product/take-store.js`, D-076), newest first, tap-through to Compare With Model scoped
   to that attempt. A pure review screen: no recording here, no "Finish" (confirmed against the
   source, D5 - the frame draws no forward exit). The frame draws no empty state either, so a line
   with no attempts shows the frame as it is with nothing in it: the three counts at 0 and no rows
   (rule 40), never a made-up empty visual. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { pageHeader } from '../../kit/components.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { loadSpeakingSource, segmentOf } from '../../product/speaking-source.js';
import { lineKey, listTakes, keepRecent, attemptIdOf } from '../../product/take-store.js';
import { loadLineAttempts, mergeAttempts } from '../../product/speaking-history.js';
import { t } from './copy.js';
import { statsFor, deltaLabel, rowsFor } from './model.js';

export default async function mountAttemptHistory(element, ctx) {
  await useStyles('screens/attempts/attempts.css');
  const language = ctx.context?.language || 'en';
  const support = languages().support;
  const segmentId = segmentOf(ctx.query);
  const lineQuery = segmentId ? { segment: segmentId } : {};

  mount(element, html`<div class="s-attempts-loading">${raw(icon('clock', { size: 22 }))}</div>`);
  element.classList.add('s-attempts-root');

  const source = await loadSpeakingSource(ctx.params.id, { api, support, language, owner: ctx.context.owner || 'local', segmentId });
  if (!ctx.isCurrent()) return undefined;
  ctx.setCrumb(t('title'));

  const key = lineKey(source.sourceId, source.line.lineId);
  /* This tab's takes AND what the account holds for this line (a fresh browser has no take of its own, the server
     still has every attempt): one list, never only the tab's. */
  const [tabTakes, serverRows] = await Promise.all([
    listTakes(key),
    loadLineAttempts(api, { assetId: source.assetId, segmentId: source.line.lineId }),
  ]);
  if (!ctx.isCurrent()) return undefined;
  if (serverRows === null) throw new Error('speaking_history_unavailable');
  const takes = mergeAttempts(tabTakes.map((take) => ({ ...take, attemptId: attemptIdOf(take.id) })), serverRows);

  const currentRef = ctx.query.get('attempt') || '';
  const stats = statsFor(takes);
  const countLabel = `${stats.count}${serverRows.length >= 50 ? '+' : ''}`;
  const rows = rowsFor(takes, currentRef);

  function rowMarkup(row) {
    const when = new Date(row.at).toLocaleString(languages().ui, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    const inner = html`<span class="s-attempts-tile" style="background:${row.tileBg};color:${row.tileColor}">${row.overall ?? '—'}</span>
      <span class="s-attempts-body">
        <span class="s-attempts-title">
          <span>${t('attemptLabel', { n: row.n })}</span>
          ${row.isBest ? html`<span class="s-attempts-badge">${t('bestBadge')}</span>` : ''}
          ${row.isCurrent ? html`<span class="s-attempts-badge s-attempts-badge--current">${t('currentBadge')}</span>` : ''}
        </span>
        <span class="s-attempts-meta">${t('metaLine', { when, acc: row.accuracy ?? '—', flu: row.hasFluency ? row.fluency : '—' })}</span>
      </span>`;
    // An attempt with no verified score has nothing to review: listed, not opened. Any other opens Compare
    // for that attempt - without its recording when only the account remembers it (audio is never kept, D-076).
    if (!row.reviewable) return html`<div class="s-attempts-row s-attempts-row--kept">${inner}</div>`;
    return html`<button type="button" class="s-attempts-row" data-open="${row.id}">${inner}<span class="s-attempts-chevron">${raw(icon('chevron-right', { size: 18 }))}</span></button>`;
  }

  mount(
    element,
    html`${pageHeader({ back: { label: shellCopy('back'), dataset: { back: '1' } }, title: t('title'), meta: t('subtitle'), compact: true })}
    <div class="s-attempts-scroll" data-scroll-region>
      <div class="s-attempts-stats">
        <div class="s-attempts-stat"><div class="s-attempts-stat__label">${t('statAttempts')}</div><div class="s-attempts-stat__value">${countLabel}</div></div>
        <div class="s-attempts-stat"><div class="s-attempts-stat__label">${t('statBest')}</div><div class="s-attempts-stat__value" style="color:var(--green)">${stats.best ?? '—'}</div></div>
        <div class="s-attempts-stat"><div class="s-attempts-stat__label">${t('statChange')}</div><div class="s-attempts-stat__value" style="color:var(--accent-on-photo, var(--accent))">${deltaLabel(stats.delta)}</div></div>
      </div>
      <div class="s-attempts-rows">${rows.map(rowMarkup)}</div>
      <p class="s-attempts-note">${t(keepRecent.value ? 'privacyNoteKept' : 'privacyNoteSession')}</p>
    </div>`,
  );

  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  element.querySelectorAll('[data-open]').forEach((button) => {
    button.addEventListener('click', () => ctx.go(ctx.href('compare', { id: ctx.params.id }, { ...lineQuery, attempt: button.dataset.open })));
  });

  return undefined;
}
