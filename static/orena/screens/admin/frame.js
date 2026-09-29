/* The Platform Admin shell, as Orena-Admin.dc.html draws it: on a desk a 232px rail (brand, the
   areas, Back to learner app, the admin's account) beside a column with a 64px header (the page's
   title and a filter for the list on the page) over the scrolling main; on a phone the rail becomes
   a strip of section chips under the header. Not the learner rail (brief §3). The frame is drawn once
   per Admin place; the page it hosts is painted into `page`. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { brandChip } from '../../kit/brand.js';
import { t } from './copy.js';
import { AREAS } from './model.js';

function initial(name) {
  const letter = String(name || '').trim().charAt(0);
  return letter ? letter.toLocaleUpperCase() : 'A';
}

function railMarkup({ area, href, name }) {
  return html`
    <div class="a-rail__brand">${brandChip({ size: 36, mark: 28 })}<div><div class="a-rail__word">Orena</div><div class="a-rail__sub">${t('railSub')}</div></div></div>
    ${AREAS.map((item) => html`<a class="a-nav" href="${href(item.route)}"${item.id === area ? raw(' aria-current="page"') : ''}><span class="a-nav__dot" aria-hidden="true"></span><span class="a-nav__label">${t(item.label)}</span></a>`)}
    <div class="a-rail__spacer"></div>
    <a class="a-applink" href="${href('today')}">${raw(icon('arrow-left', { size: 16 }))}${t('backToLearner')}</a>
    <div class="a-account"><span class="a-account__avatar" aria-hidden="true">${initial(name)}</span><div class="a-account__text"><div class="a-account__name">${name ? t('adminName', { name }) : t('railSub')}</div><div class="a-account__sub">${t('accessFull')}</div></div></div>`;
}

function chipsMarkup({ area, href }) {
  return html`${AREAS.map((item) => html`<a class="a-chip" href="${href(item.route)}"${item.id === area ? raw(' aria-current="page"') : ''}>${t(item.label)}</a>`)}`;
}

/* Draw the shell into `element` and return the handles a page needs. */
export function drawAdminShell(element, { area, href, name }) {
  mount(
    element,
    html`<div class="a-shell" data-area="${area}">
      <nav class="a-rail" aria-label="${t('navLabel')}" data-part="rail"></nav>
      <div class="a-col">
        <header class="a-top"><a class="a-topback" href="${href('today')}" aria-label="${t('backToLearner')}" title="${t('backToLearner')}">${raw(icon('arrow-left', { size: 18 }))}</a><div class="a-top__title" data-part="title"></div><input class="a-filter" type="search" data-part="filter" placeholder="${t('filterPlaceholder')}" aria-label="${t('filterPlaceholder')}" title="${t('filterTip')}" autocomplete="off"></header>
        <nav class="a-mnav" aria-label="${t('navLabel')}" data-part="chips"></nav>
        <main class="a-main" id="admin-main" tabindex="-1"><div class="a-main__inner" data-part="page"></div></main>
      </div>
      <div class="a-layer" data-part="layer"></div>
      <div class="a-tray" data-part="tray"></div>
    </div>`,
  );
  const part = (key) => element.querySelector(`[data-part="${key}"]`);
  mount(part('rail'), railMarkup({ area, href, name }));
  mount(part('chips'), chipsMarkup({ area, href }));
  const filter = part('filter');
  return {
    root: element.querySelector('.a-shell'),
    main: element.querySelector('.a-main'),
    page: part('page'),
    layer: part('layer'),
    tray: part('tray'),
    filter,
    setTitle(text) {
      part('title').textContent = text;
    },
    /* The header filter narrows the list on the page; where the page has none it is off. */
    setFilter({ enabled, value = '' }) {
      filter.disabled = !enabled;
      if (filter.value !== value) filter.value = value;
    },
  };
}
