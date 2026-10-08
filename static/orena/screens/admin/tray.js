/* The Admin's global progress tray (Orena-Admin.dc.html: fixed over the page, bottom right on a desk,
   full width on a phone). Submitting content hands the work to the engine and the form goes away; what
   is in flight follows the operator through every Admin place until it is done. The memory and the
   clock are capabilities/admin-tray.js; this draws them and owns the one interval that refreshes
   them while this shell is on screen. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { POLL_MS, inFlight, items, jobTone, progress, refresh, subscribe, ticking } from '../../capabilities/admin-tray.js';
import { t } from './copy.js';
import { pill } from './blocks.js';

function stageText(job) {
  if (job.status === 'failed') return t.has(`jobErr_${job.error}`) ? t(`jobErr_${job.error}`) : t('trayFailedText');
  if (job.status === 'completed') return job.resultKind === 'duplicate' ? t('trayDuplicate') : t('trayDone');
  return t.has(`impStage_${job.stage}`) ? t(`impStage_${job.stage}`) : t('trayWorking');
}

const TONE = { bad: 'err', ok: 'ok', info: 'info' };

export function trayMarkup({ open, href }) {
  const watched = items();
  if (!watched.length) return '';
  const busy = inFlight();
  const failed = watched.filter((job) => job.status === 'failed').length;
  const title = busy ? `${t('trayProcessing', { n: busy })}${failed ? ` · ${t('trayFailedN', { n: failed })}` : ''}` : failed ? t('trayFailedN', { n: failed }) : t('trayAllDone');
  return html`<section class="a-traybox" aria-label="${t('trayLabel')}">
    <button type="button" class="a-traybox__head" data-a="tray-toggle" aria-expanded="${open ? 'true' : 'false'}">${busy ? html`<span class="a-traybox__spin" aria-hidden="true"></span>` : ''}<span class="a-traybox__title">${title}</span>${raw(icon('chevron-down', { size: 18 }))}</button>
    ${open ? html`<div class="a-traybox__body" role="status" aria-live="polite">${watched.map((job) => html`<div class="a-trayitem" data-state="${job.status}">
      <div class="a-trayitem__top"><div class="a-trayitem__text"><div class="a-trayitem__title">${job.label || job.id.slice(0, 8)}</div><div class="a-trayitem__kind">${t('trayKind')} · ${stageText(job)}</div></div>${pill({ label: t(`jobStatusShort_${job.status}`), tone: TONE[jobTone(job)] })}</div>
      <div class="a-trayitem__bar"><span data-tone="${jobTone(job)}" style="width:${progress(job)}%"></span></div>
      <div class="a-actions">${job.articleId ? html`<button type="button" class="a-btn a-btn--xs a-btn--primary" data-go="${href('adminArticle', { id: job.articleId })}">${t('trayOpenReview')}</button>` : ''}<button type="button" class="a-btn a-btn--xs" data-go="${href('adminJob', { id: job.id })}">${t('trayViewJob')}</button></div>
    </div>`)}<div class="a-traybox__note">${t('trayNote')}</div></div>` : ''}
  </section>`;
}

/* Draw the tray into `host` and keep it current; returns the way out. */
export function mountTray(host, href, api = adminApi) {
  let open = true;
  let timer = 0;
  const paint = () => {
    mount(host, trayMarkup({ open, href }));
    schedule();
  };
  const schedule = () => {
    if (timer || !ticking()) return;
    timer = setInterval(async () => {
      if (!ticking()) {
        clearInterval(timer);
        timer = 0;
        return;
      }
      await refresh(api);
      paint();
    }, POLL_MS);
  };
  const onClick = (event) => {
    if (event.target.closest?.('[data-a="tray-toggle"]')) {
      open = !open;
      paint();
      event.stopPropagation();
    }
  };
  host.addEventListener('click', onClick);
  const unsubscribe = subscribe(paint);
  paint();
  return () => {
    clearInterval(timer);
    unsubscribe();
    host.removeEventListener('click', onClick);
  };
}
