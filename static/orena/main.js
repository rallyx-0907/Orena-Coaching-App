/* Entry of the new learner UI (D-088, D-091), served at /next until it replaces the old UI at /.

   Boot: theme and device are already on the root (kit/boot.js); load the brand sprite, draw the
   frame, read who the learner is (shell/context.js), then hand over to the router. The old UI's
   internal-review gate is kept: the new product direction stays internal until the human release
   gate, so an account that is not an admin sees the same plain notice the old UI shows. */
import './kit/device.js';
import { onLanguageChange } from './copy/index.js';
import { shellCopy as t } from './copy/shell.js';
import { html, mount, raw } from './kit/html.js';
import { icon } from './kit/icons.js';
import { loadBrand } from './kit/brand.js';
import { setOverlayLayer } from './kit/overlay.js';
import { setToastLayer } from './kit/toast.js';
import { bannerMarkup } from './kit/states.js';
import { useStyles } from './kit/styles.js';
import { isAdminHash } from './shell/routes.js';
import { drawFrame } from './shell/frame.js';
import { createRouter } from './shell/router.js';
import { context, loadContext, onContext } from './shell/context.js';

const app = document.getElementById('app');

function offlineBanner(holder) {
  const paint = () => {
    if (navigator.onLine !== false) {
      holder.replaceChildren();
      return;
    }
    mount(holder, bannerMarkup({ kind: 'warn', title: t('offlineTitle'), dismissLabel: t('dismiss') }));
    holder.querySelector('[data-banner-close]')?.addEventListener('click', () => holder.replaceChildren());
  };
  window.addEventListener('online', paint);
  window.addEventListener('offline', paint);
  paint();
}

function failed(error) {
  console.error('[Orena] could not start', error);
  mount(
    app,
    html`<div class="o-error" role="alert"><div class="o-error__card">
      <div class="o-error__icon">${raw(icon('circle-alert', { size: 26 }))}</div>
      <div class="o-error__title">${t('cantOpen')}</div>
      <div class="o-error__text">${t(navigator.onLine === false ? 'errorOffline' : 'errorServer')}</div>
      <div class="o-error__actions"><button type="button" class="o-btn o-btn--secondary o-btn--sm" data-reload>${raw(icon('refresh-cw', { size: 16 }))}${t('retry')}</button></div>
    </div></div>`,
  );
  app.querySelector('[data-reload]').addEventListener('click', () => location.reload());
}

/* The legal pages are read before signing in: drawn with no learner frame and no request for who the
   learner is (legal/page.js). Moving to an address that is not a legal page starts the app as usual. */
async function legalPages() {
  const { legalAddress, renderLegal } = await import('./legal/page.js');
  const address = legalAddress(location.hash);
  if (!address) return false;
  await renderLegal(app, address);
  window.addEventListener('hashchange', () => {
    const next = legalAddress(location.hash);
    if (next) renderLegal(app, next);
    else location.reload();
  });
  return true;
}

async function boot() {
  if (/^#\/?legal\//.test(location.hash) && (await legalPages())) return;
  const brand = loadBrand();
  let learner;
  try {
    learner = await loadContext();
  } catch (error) {
    failed(error);
    return;
  }
  if (!learner.isAdmin) {
    /* An account that is not an admin, at an admin address: the design's No access frame, drawn
       before any admin request exists. Anywhere else the internal-review notice stands. */
    if (isAdminHash(location.hash)) {
      await brand;
      await useStyles('screens/admin/admin.css');
      const { renderNoAccess } = await import('./screens/admin/no-access.js');
      renderNoAccess(app, { email: learner.user?.email, name: learner.name, backHref: '/next' });
      return;
    }
    mount(app, html`<div class="o-error"><div class="o-error__card"><div class="o-error__text">${t('limited')}</div><a class="o-btn o-btn--secondary o-btn--sm" href="/account">${t('account')}</a></div></div>`);
    return;
  }
  await brand;
  const frame = drawFrame(app);
  setOverlayLayer(frame.layer);
  setToastLayer(frame.layer);
  const router = createRouter({ frame, getContext: context });
  onContext(() => router.repaint());
  onLanguageChange(() => {
    router.repaint();
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
  const banner = document.createElement('div');
  banner.dataset.part = 'banner';
  frame.main.before(banner);
  offlineBanner(banner);
  await router.start();
}

boot();
