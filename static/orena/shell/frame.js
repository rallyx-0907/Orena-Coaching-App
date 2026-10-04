/* The frame of the new learner UI (Design Contract rules 35, 38, 47): desktop rail and top bar,
   phone header and bar, the main column and the overlay layer, as the pinned design draws them.
   The frame is drawn once; route changes repaint only the parts that follow the route (active
   place, breadcrumb, badges). */
import { html, mount, raw } from '../kit/html.js';
import { icon } from '../kit/icons.js';
import { brandChip, intelChip } from '../kit/brand.js';
import { shellCopy as t } from '../copy/shell.js';
import { href } from './routes.js';
import { orenaPresent, onOrenaPresence } from '../agent/presence.js';
import { probe } from '../agent/transport.js';

const RAIL = [
  { id: 'today', icon: 'house', label: 'today' },
  { id: 'discover', icon: 'compass', label: 'discover' },
  { id: 'practice', icon: 'graduation-cap', label: 'practiceHub', badge: 'inProgress' },
  { id: 'library', icon: 'library-big', label: 'myLibrary', badge: 'due' },
];

const BAR = [
  { id: 'today', icon: 'house', label: 'today' },
  { id: 'discover', icon: 'compass', label: 'discover' },
  { id: 'orena', orena: true },
  { id: 'practice', icon: 'graduation-cap', label: 'practiceShort', badge: 'inProgress' },
  { id: 'library', icon: 'library-big', label: 'libraryShort', badge: 'due' },
];

function current(active, id) {
  return active === id ? raw(' aria-current="page"') : '';
}

function badgeCount(context, key) {
  if (key === 'due') return context.due || 0;
  if (key === 'inProgress') return context.inProgress || 0;
  return 0;
}

function learningLabel(context) {
  const language = t(`lang_${context.language === 'zh' ? 'zh' : 'en'}`);
  return context.level ? t('learningLabel', { language, level: context.level }) : language;
}

function avatar(context, className = 'o-avatar') {
  return context.picture
    ? html`<span class="${className}"><img src="${context.picture}" alt=""></span>`
    : html`<span class="${className}" aria-hidden="true">${context.initial}</span>`;
}

function railMarkup(state) {
  const { active, context } = state;
  return html`
    <div class="o-rail__brand">${brandChip({ size: 36, mark: 27 })}<div class="o-wordmark">Orena</div></div>
    ${RAIL.map((item) => {
      const count = item.badge ? badgeCount(context, item.badge) : 0;
      return html`<a class="o-rail__item" href="${href(item.id)}"${current(active, item.id)}>${raw(icon(item.icon, { size: 19 }))}<span class="o-rail__label">${t(item.label)}</span>${
        count ? html`<span class="o-rail__badge">${count}</span>` : ''
      }</a>`;
    })}
    <div class="o-rail__spacer"></div>
    ${orenaPresent()
      ? html`<div class="o-ask" role="link" tabindex="0" data-go="${href('orena')}"${current(active, 'orena')}>
      <div class="o-ask__head">${intelChip({ size: 32, mark: 26 })}<div class="o-ask__headtext"><span>${t('askOrena')}</span><span class="o-ask__sub">${t('askOrenaSub')}</span></div></div>
      <div class="o-ask__row"><span class="o-ask__field">${t('askAnything')}</span><button type="button" class="o-ask__voice" data-voice="rail" aria-label="${t('talkToOrena')}" title="${t('talkToOrena')}">${raw(icon('mic', { size: 17 }))}</button></div>
    </div>`
      : ''}
    <a class="o-account" href="${href('profile')}"${current(active, 'profile')}>
      ${avatar(context)}
      <div style="flex:1;min-width:0"><div class="o-account__name">${context.name}</div><div class="o-account__meta">${learningLabel(context)}</div></div>
    </a>`;
}

function barMarkup(state) {
  const { active, context } = state;
  return html`${BAR.map((item) => {
    if (item.orena) {
      if (!orenaPresent()) return '';
      return html`<a class="o-bnav__orena" href="${href('orena')}"${current(active, 'orena')}><span class="o-bnav__disc">${raw(
        '<svg width="46" height="46" viewBox="0 0 100 100" style="display:block;flex:none;overflow:visible" aria-hidden="true"><use href="#ol-intel"></use></svg>',
      )}</span>${t('orena')}</a>`;
    }
    const count = item.badge ? badgeCount(context, item.badge) : 0;
    return html`<a class="o-bnav__item" href="${href(item.id)}"${current(active, item.id)}><span class="o-bnav__pill">${raw(icon(item.icon, { size: 22 }))}${
      count ? html`<span class="o-bnav__badge">${count}</span>` : ''
    }</span>${t(item.label)}</a>`;
  })}`;
}

function crumbMarkup(state) {
  const { crumb } = state;
  return html`${crumb.section ? html`<a class="o-crumb__section" href="${crumb.sectionHref}">${crumb.section}</a>${raw(icon('chevron-right', { size: 14 }))}` : ''}<span class="o-crumb__screen">${crumb.screen}</span>`;
}

function topbarMarkup(state) {
  const { context } = state;
  return html`
    <div class="o-crumb">${crumbMarkup(state)}</div>
    <a class="o-topsearch" href="${href('search')}">${raw(icon('search', { size: 17 }))}<span class="o-topsearch__label">${t('search')}</span><span class="o-topsearch__key">⌘K</span></a>
    <div class="o-tlpill">${learningLabel(context)}</div>
    <button type="button" class="o-bell" data-open="notifications" aria-label="${t('notifications')}">${raw(icon('bell', { size: 18 }))}${
      context.unread ? html`<span class="o-bell__dot"></span>` : ''
    }</button>`;
}

function mheadMarkup(state) {
  const { context } = state;
  return html`
    <div class="o-mhead__brand">${brandChip({ size: 28, mark: 22, round: true })}<span>Orena</span></div>
    <div class="o-mhead__actions">
      <a class="o-mhead__button" href="${href('search')}" aria-label="${t('search')}">${raw(icon('search', { size: 18 }))}</a>
      <button type="button" class="o-mhead__button" data-open="notifications" aria-label="${t('notifications')}">${raw(icon('bell', { size: 18 }))}${
        context.unread ? html`<span class="o-mhead__count">${context.unread}</span>` : ''
      }</button>
      <a href="${href('profile')}" aria-label="${t('profile')}">${avatar(context, 'o-avatar o-mhead__avatar')}</a>
    </div>`;
}

/* Draw the frame into `root` and return the handles the shell needs. */
export function drawFrame(root) {
  mount(
    root,
    html`<div class="o-frame">
      <nav class="o-rail" aria-label="${t('mainNavigation')}" data-part="rail"></nav>
      <div class="o-column">
        <div class="o-mhead" data-part="mhead"></div>
        <header class="o-topbar" data-part="topbar"></header>
        <main class="o-main" id="main" tabindex="-1"></main>
        <nav class="o-bnav" aria-label="${t('mainNavigation')}" data-part="bnav"></nav>
      </div>
      <div class="o-layer" data-part="layer"></div>
    </div>`,
  );
  const part = (name) => root.querySelector(`[data-part="${name}"]`);
  let lastState = null;
  const handles = {
    main: root.querySelector('#main'),
    layer: part('layer'),
    paint(state) {
      lastState = state;
      mount(part('rail'), railMarkup(state));
      mount(part('mhead'), mheadMarkup(state));
      mount(part('topbar'), topbarMarkup(state));
      mount(part('bnav'), barMarkup(state));
      // The rail's mic (desktop only - `.o-ask` is not drawn on mobile) opens the full-screen
      // voice mode (frame 56, E5 §7.1: this is the one place it is reached from). Rebound every
      // paint since railMarkup() replaces the rail's markup wholesale each time.
      part('rail')
        .querySelector('[data-voice="rail"]')
        ?.addEventListener('click', (event) => {
          event.stopPropagation();
          import('../screens/orena/voice.js')
            .then((module) => module.openVoiceFull())
            .catch((error) => console.error('[Orena] voice mode could not load', error));
        });
    },
    paintCrumb(state) {
      const crumb = part('topbar').querySelector('.o-crumb');
      if (crumb) mount(crumb, crumbMarkup(state));
    },
  };
  // §2.1: asked once when the UI starts; a server without the agent answers 404, which hides every
  // entry point via the `onOrenaPresence` repaint below.
  void probe();
  onOrenaPresence(() => {
    if (lastState) handles.paint(lastState);
  });
  return handles;
}
