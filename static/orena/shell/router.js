/* Navigation of the new learner UI, following the design's own rules (the state script's nav(),
   back(), navFor() and crumbVals(); Design Contract rules 47, 49):

   - one hash route at a time (shell/routes.js); an unknown address goes to Today;
   - the place the learner came from (navOrigin: the last of the six primary places) stays lit in
     the rail and the phone bar while they work somewhere deeper, and names the breadcrumb's
     section;
   - a learning workspace (route.focus) sets :root[data-focus="1"]: no top bar, no phone header,
     no phone bar, and the main column never scrolls as a page;
   - Back, Forward and a reload return a browsing page to the place the learner left on it (shell/scroll-memory.js);
     a page opened from a link or a card starts at the top;
   - navigating closes every sheet, aborts the previous room's requests
     (infrastructure/navigation.js) and runs the previous room's cleanup;
   - a lesson route shows the design's loading skeleton while it loads, and its load error with
     Back / Retry when it fails;
   - a route whose screen is not built yet shows the design's Coming soon screen. */
import { setRouteView } from './view-context.js';
import { beginNavigation } from '../infrastructure/navigation.js';
import { mount } from '../kit/html.js';
import { closeSheet } from '../kit/overlay.js';
import { loadingMarkup, errorMarkup } from '../kit/states.js';
import { shellCopy as t } from '../copy/shell.js';
import { PRIMARY, DEFAULT_ROUTE, entryRoute, match, href, byId } from './routes.js';
import { SCREENS } from './screens.js';
import { formerAddress } from './former-addresses.js';
import { addressOf, createScrollMemory, restoreScrollWhenReady } from './scroll-memory.js';

const CRUMB_PRIMARY = ['today', 'discover', 'orena', 'practice', 'library', 'profile'];
const STORY_ROUTES = ['reader', 'listening', 'dictation', 'checku', 'rtransfer', 'feed'];
/* Speaking and Writing rooms belong to Practice Hub (rule 47): opened with no known origin (a direct
   load, a reload in a new tab), the rail lights Practice Hub, not Today or Discover. */
const PRACTICE_ROOMS = ['speak', 'compare', 'attempts', 'spsummary', 'freetalk', 'conv', 'situation', 'writing', 'writingDraft', 'wrcompare'];
const ORIGIN_KEY = 'orena.next.navOrigin';
const DEPTH_KEY = 'orena.next.depth';

function session(key, value) {
  try {
    if (value === undefined) return window.sessionStorage.getItem(key);
    window.sessionStorage.setItem(key, String(value));
  } catch {
    return null;
  }
  return null;
}

export function createRouter({ frame, getContext }) {
  const root = document.documentElement;
  const storedOrigin = session(ORIGIN_KEY);
  let origin = storedOrigin || DEFAULT_ROUTE;
  let depth = Number(session(DEPTH_KEY)) || 0;
  let originKnown = Boolean(storedOrigin);
  let cleanup = null;
  let generation = 0;
  let current = null;
  let crumbOverride = '';
  const memory = createScrollMemory();
  /* How the address being rendered was reached: 'push' and 'replace' are the app's own go(); anything else is the
     browser (Back, Forward, a reload) and returns to the remembered place. */
  let arrival = 'traverse';
  let settled = false;
  let stopRestore = null;

  function state() {
    const route = current?.route;
    // Profile is its own place (the avatar, the rail's account row): the bar lights nothing there, never the place the learner came from (LEX-080).
    const active = route && (PRIMARY.includes(route.id) || route.id === 'profile') ? route.id : origin;
    const section = route && !CRUMB_PRIMARY.includes(route.id) ? (route.id === 'progress' ? 'profile' : origin) : '';
    return {
      active,
      context: getContext(),
      crumb: {
        section: section ? t(sectionLabel(section)) : '',
        sectionHref: section ? href(section) : '',
        screen: crumbOverride || (route ? t(route.crumb) : ''),
      },
    };
  }

  function sectionLabel(id) {
    return { today: 'today', discover: 'discover', orena: 'orena', practice: 'practiceHub', library: 'myLibrary', progress: 'progress', profile: 'profile' }[id] || 'today';
  }

  function paint() {
    frame.paint(state());
    const title = state().crumb.screen;
    document.title = title ? `${title} · Orena` : 'Orena';
  }

  function go(target, { replace = false } = {}) {
    const hash = target.startsWith('#') ? target : `#${target.startsWith('/') ? target : `/${target}`}`;
    if (hash === location.hash) {
      arrival = 'push';
      return render();
    }
    arrival = replace ? 'replace' : 'push';
    if (replace) location.replace(hash);
    else {
      depth += 1;
      session(DEPTH_KEY, depth);
      location.hash = hash;
    }
    return null;
  }

  function back() {
    if (depth > 0) {
      depth -= 1;
      session(DEPTH_KEY, depth);
      history.back();
    } else go(href(origin), { replace: true });
  }

  function setCrumb(text) {
    crumbOverride = String(text || '');
    frame.paintCrumb(state());
    document.title = crumbOverride ? `${crumbOverride} · Orena` : document.title;
  }

  /* The browser's own wording when a dynamically imported module could not be fetched (Chromium, Firefox, Safari). */
  function moduleLoadFailed(error) {
    return error instanceof TypeError
      && /dynamically imported module|importing a module script failed|error loading dynamically imported module/i.test(String(error.message));
  }

  async function loadScreen(route) {
    const loader = SCREENS[route.screen];
    if (loader) return (await loader()).default;
    /* A screen that is not built yet: the design's Coming soon, titled with the place's name. */
    const coming = (await SCREENS.coming()).default;
    return (element, ctx) => coming(element, { ...ctx, params: { key: route.crumb }, placeholder: true });
  }

  async function render() {
    /* The empty address is an entry, not a place: it opens where `entryRoute` says (D-098). */
    if (!String(location.hash).replace(/^#\/?/, '').split('?')[0].replace(/\/+$/, '')) {
      go(href(entryRoute(getContext())), { replace: true });
      return;
    }
    // An address of the UI `/` served before the cutover opens the place that does its job now (D-143).
    const moved = formerAddress(location.hash);
    if (moved) {
      go(moved, { replace: true });
      return;
    }
    const found = match(location.hash);
    if (!found) {
      go(href(DEFAULT_ROUTE), { replace: true });
      return;
    }
    const mine = (generation += 1);
    const reached = arrival;
    arrival = 'traverse';
    const address = location.hash;
    settled = false;
    stopRestore?.();
    stopRestore = null;
    // An arrival through the app's own go() starts at the top, and an older position under this address is stale.
    if (reached !== 'traverse') memory.remember(address, 0);
    const signal = beginNavigation();
    closeSheet();
    try {
      cleanup?.();
    } catch (error) {
      console.error('[Orena] screen cleanup failed', error);
    }
    cleanup = null;
    crumbOverride = '';
    current = found;
    const { route } = found;
    if (!originKnown && PRACTICE_ROOMS.includes(route.id)) origin = 'practice';
    originKnown = true;
    // A Skill Hub is a page of Practice Hub, whichever way the learner reached it: it always lights Practice.
    if (route.id === 'skillhub') {
      origin = 'practice';
      session(ORIGIN_KEY, origin);
    }
    if (PRIMARY.includes(route.id)) {
      origin = route.id;
      session(ORIGIN_KEY, origin);
    }
    root.dataset.focus = route.focus ? '1' : '0';
    root.dataset.bare = route.bare ? '1' : '0';
    root.dataset.route = route.id;
    paint();

    const main = frame.main;
    main.scrollTop = 0;
    const element = document.createElement('section');
    element.className = 'o-screen';
    element.dataset.screen = route.id;
    main.replaceChildren(element);

    let skeleton = 0;
    let loadingLabel = t('loadingLesson');
    if (route.lesson) {
      skeleton = setTimeout(() => {
        if (mine !== generation) return;
        const holder = document.createElement('div');
        holder.dataset.state = 'loading';
        mount(holder, loadingMarkup(loadingLabel));
        main.append(holder);
      }, 150);
    }

    const ctx = {
      route,
      params: found.params,
      query: found.query,
      signal,
      context: getContext(),
      go,
      back,
      // Whether Back returns within the app (false when the room was opened directly, e.g. from a link).
      hasHistory: () => depth > 0,
      href,
      setCrumb,
      setLoadingLabel: (label) => { loadingLabel = String(label); },
      replace: (target) => go(target, { replace: true }),
      isCurrent: () => mine === generation,
    };

    try {
      const screen = await loadScreen(route);
      if (mine !== generation) return;
      // What a running Orena conversation is told the learner now sees: the route first, so what the screen
      // selects while it mounts (a remembered line) is added on top of it.
      setRouteView(route, found.params);
      const result = await screen(element, ctx);
      if (mine !== generation) {
        if (typeof result === 'function') result();
        return;
      }
      cleanup = typeof result === 'function' ? result : null;
      settled = true;
      // Back to a browsing page: the place the learner left on it, once its content is there to scroll.
      const place = reached === 'traverse' && !route.focus ? memory.recall(address) : 0;
      if (place > 0) stopRestore = restoreScrollWhenReady(main, place, element);
    } catch (error) {
      if (mine !== generation || error?.name === 'AbortError') return;
      console.error('[Orena] screen failed', route.id, error);
      // A room whose code failed to download stays failed for this page: the browser keeps a failed module for the
      // page's life, so only a fresh load can fetch it again (LEX-092). Its Retry reloads; anything else re-renders.
      const unloaded = moduleLoadFailed(error);
      showError(route, main, unloaded ? () => location.reload() : () => render(), { connection: unloaded });
    } finally {
      clearTimeout(skeleton);
      if (mine === generation) main.querySelector('[data-state="loading"]')?.remove();
    }
    if (mine === generation) main.focus({ preventScroll: true });
  }

  function showError(route, main, retry, { connection = false } = {}) {
    const offline = connection || navigator.onLine === false;
    const holder = document.createElement('div');
    holder.dataset.state = 'error';
    mount(
      holder,
      errorMarkup({
        // A browsing place is named for what it is (LEX-080); only a lesson-like route says "lesson" or "story".
        title: route.lesson ? t(STORY_ROUTES.includes(route.id) ? 'errorStory' : 'errorLesson') : t('errorPlace', { place: t(route.crumb) }),
        text: t(offline ? 'errorOffline' : 'errorServer'),
        backLabel: t('back'),
        retryLabel: t('retry'),
      }),
    );
    holder.querySelector('[data-error-back]').addEventListener('click', () => back());
    holder.querySelector('[data-error-retry]').addEventListener('click', () => retry());
    main.append(holder);
    // A page that failed for want of a connection loads itself again when the connection returns (LEX-080).
    if (offline) {
      window.addEventListener('online', () => {
        if (holder.isConnected) retry();
      }, { once: true });
    }
  }

  function onKey(event) {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      go(href('search'));
    }
  }

  function onClick(event) {
    const target = event.target.closest?.('[data-go]');
    if (target && !event.defaultPrevented) {
      if (event.target.closest('[data-voice]')) return;
      event.preventDefault();
      go(target.dataset.go);
    }
  }

  function onLinkClick(event) {
    const link = event.target.closest?.('a[href^="#/"]');
    if (!link || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || link.target) return;
    event.preventDefault();
    go(link.getAttribute('href'));
  }

  /* The bell (desktop top bar and phone header, shell/frame.js's two `[data-open="notifications"]`
     buttons): opens the design's notifications sheet (screens/notifications/sheet.js), loaded
     lazily so it never joins first paint - the same `import(...).then(...)` pattern every other
     shell-drawn sheet trigger already uses (e.g. discover/screen.js's Import button). */
  function onOpenClick(event) {
    const target = event.target.closest?.('[data-open]');
    if (!target || event.defaultPrevented) return;
    const which = target.dataset.open;
    if (which === 'notifications') {
      event.preventDefault();
      import('../screens/notifications/sheet.js')
        .then((module) => module.openNotifications({ context: getContext(), go }))
        .catch((error) => console.error('[Orena] Notifications is not available yet', error));
    }
  }

  return {
    start() {
      window.addEventListener('hashchange', (event) => {
        // The page being left is still on screen: its position goes under the address it had (a screen may have
        // rewritten it with replaceState, which is why the event's old address is the one to use).
        if (settled && frame.main) memory.remember(addressOf(event.oldURL), frame.main.scrollTop);
        render();
      });
      document.addEventListener('keydown', onKey);
      document.addEventListener('click', onClick);
      document.addEventListener('click', onLinkClick);
      document.addEventListener('click', onOpenClick);
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && event.target.matches?.('[data-go][role="link"]')) go(event.target.dataset.go);
      });
      return render();
    },
    go,
    back,
    repaint: paint,
    current: () => current,
    route: (id) => byId(id),
  };
}
