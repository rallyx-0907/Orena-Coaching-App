import { api } from './infrastructure/api.js';
import { copy } from './ui/copy.js';
import { esc, dialog, status } from './ui/html.js';
import { route, link } from './product/intent.js';
import { learnerMemory } from './product/memory.js';
import { renderWorld } from './ui/world.js';
import { renderEncounter } from './ui/encounter.js';
import { renderSpeaking } from './ui/speaking.js';
import { renderConversation } from './ui/conversation.js';
import { referenceNavigation, navigationToggle, referenceCopy, experienceFor, renderContinue } from './ui/reference.js';
import { renderCollection } from './ui/collection.js';
import {
  renderExpression,
  renderLanguage,
  renderGrammar,
} from './ui/expression.js';
import { installHints } from './ui/patterns.js';
import { bindContentRails } from './ui/content-rail.js';
import { growthSummarySection } from './ui/growth-summary.js';
import { renderAdmin } from './ui/admin.js';

// Every hint in every room is one delegated behaviour, installed once.
installHints(document);

/* On a narrow screen the header retreats while the learner works.

   Expanded it orients - wordmark, bring and account actions, the control that
   names where the learner is. Scrolling down into a room collapses it to that
   control alone, and the header really gets shorter: the room reflows upward
   into the height it gives back rather than scrolling underneath a bar that
   only looks smaller. A deliberate scroll up, the top of the page, opening the
   destinations, or a new room brings it back.

   `--shell-offset` is the header's current height, written synchronously on
   every change so a sticky source strip or a result frame scrolled to in the
   same task already clears it. Shrinking the header moves the page by that
   difference; the scroll that follows is the browser keeping the learner's
   place, not the learner scrolling, so it is ignored. */
const header = (() => {
  const narrow = window.matchMedia('(max-width: 900px)');
  let compact = false,
    lastY = window.scrollY,
    travel = 0,
    quietUntil = 0;
  const shellEl = () => document.getElementById('shell');
  const measure = () => {
    const el = shellEl();
    if (!el) return;
    document.documentElement.style.setProperty(
      '--shell-offset',
      narrow.matches ? `${el.offsetHeight}px` : '0px',
    );
  };
  const set = (next) => {
    const el = shellEl();
    if (!el) return;
    next = Boolean(next) && narrow.matches;
    if (next === compact) return measure();
    compact = next;
    if (next) el.dataset.compact = '';
    else delete el.dataset.compact;
    measure();
    quietUntil = performance.now() + 350;
    travel = 0;
    lastY = window.scrollY;
  };
  window.addEventListener(
    'scroll',
    () => {
      const y = window.scrollY;
      const dy = y - lastY;
      lastY = y;
      if (!narrow.matches || performance.now() < quietUntil) return;
      if (shellEl()?.dataset.menu === 'open') return;
      if (y < 48) return set(false);
      travel = Math.sign(dy) === Math.sign(travel) ? travel + dy : dy;
      if (travel > 24 && y > 96) set(true);
      else if (travel < -72) set(false);
    },
    { passive: true },
  );
  narrow.addEventListener('change', () => set(false));
  window.addEventListener('resize', measure, { passive: true });
  /* A room that moves the learner to their work - a result frame, a practice
     opened below the source - asks for the working header first, so the place
     it scrolls to is computed against the height the header will have. */
  document.addEventListener('orena:work', () => set(true));
  return { set, measure };
})();

let generation = 0,
  cleanup = () => {},
  pendingWrites = 0,
  writeTail = Promise.resolve();
const root = document.getElementById('main');
const storage = (() => {
  try {
    return localStorage;
  } catch {
    return {
      getItem() {
        return null;
      },
      setItem() {
        throw Error('Storage unavailable');
      },
    };
  }
})();
/* The learner's support language owns everything Orena says.

   Orena has two learner language roles and only two: the learning language,
   which owns the material, and the support language, which owns every word the
   product itself speaks - navigation, controls, instructions, feedback,
   errors. A third, independently chosen "interface language" produced exactly
   what it sounds like: a learner studying English with Vietnamese support
   reading an English product. The stored preference is kept so nothing breaks,
   but it no longer decides this on its own.

   A locale with no copy pack falls back to English rather than showing keys. */
const uiLocale = (support) => (copy[String(support || '')] ? String(support) : 'en');
const ui = uiLocale(storage.getItem('orena.support') || storage.getItem('orena.interface'));
const ctx = {
  api,
  ui,
  c: copy[ui],
  language: 'en',
  profile: {},
  commerce: null,
  memory: null,
  location: route(location.hash),
  alive: () => true,
  go: (page, options) => {
    const next = link(page, options);
    // Assigning the hash it already has fires no hashchange, so re-entering
    // the route you are on would silently do nothing.
    if (location.hash === next) render();
    else location.hash = next;
  },
  settledWrites: () => writeTail,
  async mutate(action) {
    pendingWrites++;
    document
      .querySelectorAll('[data-preference]')
      .forEach((x) => (x.disabled = true));
    const write = writeTail.then(action);
    writeTail = write.catch(() => {});
    try {
      return await write;
    } finally {
      pendingWrites--;
      if (!pendingWrites)
        document
          .querySelectorAll('[data-preference]')
          .forEach((x) => (x.disabled = false));
    }
  },
  import: () => importContent(),
  message: status,
};
function shell() {
  const c = ctx.c;
  document.documentElement.lang = ctx.ui === 'zh' ? 'zh-Hans' : ctx.ui;
  document.documentElement.dataset.learning = ctx.language;
  // Shared plumbing such as a dialog's close control reads its label from the
  // interface language rather than carrying every language at once.
  document.documentElement.dataset.close = c.close;
  // The template names the skip link in both languages because it paints
  // before any language is known; once one is, it speaks only that one.
  const skip = document.querySelector('a.skip');
  if (skip) skip.textContent = c.skipToContent;
  document.getElementById('shell').innerHTML =
    `<div class="shell-identity"><a class="brand" href="#/" aria-label="Orena"><span class="brand-tail" aria-hidden="true"></span>orena</a><span class="shell-motto">${esc(referenceCopy[ctx.ui].fieldNote)}</span></div>${referenceNavigation(ctx)}${navigationToggle(ctx)}<div class="shell-actions"><button class="bring-button" aria-label="${c.bring}" data-bring>＋ <span>${c.bring}</span></button><button class="account-button" data-preference aria-label="${c.preferences}"><span class="language-seal">${ctx.language.toUpperCase()}</span> ${c.preferences}</button></div>`;
  document.querySelector('[data-bring]').onclick = importContent;
  document.querySelector('[data-preference]').onclick = () => preferences();
  /* The narrow-screen destination sheet. The shell is rebuilt on every route,
     so choosing a destination closes it without anything having to remember
     that it was open - and Escape closes it from the keyboard. */
  const shellEl = document.getElementById('shell');
  const toggle = shellEl.querySelector('[data-nav-toggle]');
  /* The curtain behind the sheet. A button rather than a div, so closing by
     tapping away is one thing to a pointer and to a keyboard both, and so it
     is announced as something that does something. */
  let backdrop = document.querySelector('.nav-backdrop');
  if (!backdrop) {
    backdrop = document.createElement('button');
    backdrop.className = 'nav-backdrop';
    backdrop.type = 'button';
    backdrop.tabIndex = -1;
    backdrop.setAttribute('aria-hidden', 'true');
    shellEl.insertAdjacentElement('afterend', backdrop);
  }
  const setMenu = (open) => {
    // Looking for somewhere else to go is navigating, not working.
    if (open) header.set(false);
    shellEl.dataset.menu = open ? 'open' : 'closed';
    toggle.setAttribute('aria-expanded', String(open));
  };
  setMenu(false);
  toggle.onclick = () => setMenu(shellEl.dataset.menu !== 'open');
  backdrop.onclick = () => setMenu(false);
  shellEl.onkeydown = (event) => {
    if (event.key !== 'Escape' || shellEl.dataset.menu !== 'open') return;
    setMenu(false);
    toggle.focus();
  };
  document.getElementById('footer').innerHTML =
    `<a href="#/" class="brand-small">orena</a><button class="quiet" data-account>${c.preferences} ↗</button>`;
  document
    .querySelector('[data-account]')
    ?.addEventListener('click', () => preferences());
}
/* Read-only account fact, never an access decision - accountCommerce() in
   writing_coach/product/commerce.py is the one server resolver this renders.
   billing_ready is false everywhere upstream, so no price, upgrade action or
   provider identifier belongs here (docs/product/ORENA_COMMERCE_ARCHITECTURE.md
   §2, §4: "read-only UI badges are not access enforcement"). Omitted from the
   onboarding sheet - a first-run welcome is not where usage numbers belong. */
function planUsageSection(scope) {
  const c = scope.c;
  const commerce = scope.commerce;
  if (!commerce || commerce.available === false || commerce.readiness === 'unavailable') {
    return `<section class="plan-usage"><h2>${c.planUsage}</h2><p>${c.planUsageUnavailable}</p></section>`;
  }
  const rows = Object.entries(commerce.features || {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, item]) => {
      const label = c['feature_' + key.replace(/\./g, '_')] || key;
      const value =
        item.entitlement_state === 'disabled'
          ? c.planNotIncluded
          : item.usage_state === 'unavailable'
            ? '—'
            : item.monthly_limit === null
              ? c.planUnlimited
              : `${item.used}/${item.monthly_limit} ${c.planUsed}`;
      return `<li><span>${esc(label)}</span><span>${esc(value)}</span></li>`;
    })
    .join('');
  return `<section class="plan-usage"><h2>${c.planUsage} — ${esc(commerce.plan?.name || '')}</h2><p>${c.planUsageNote}</p><ul>${rows}</ul></section>`;
}
function preferences(onboarding = false) {
  const c = ctx.c;
  const sheet = dialog({
    title: onboarding ? c.welcome : c.preferences,
    body: `<p>${onboarding ? c.welcomeNote : c.local}</p><form id="preferencesForm"><label>${c.learning}<select name="learning"><option value="en" ${ctx.language === 'en' ? 'selected' : ''}>English</option><option value="zh" ${ctx.language === 'zh' ? 'selected' : ''}>中文</option></select></label><label>${c.support}<select name="support">${ctx.supportLanguages.map(({ code, label: title }) => `<option value="${code}" ${ctx.support === code ? 'selected' : ''}>${title}</option>`).join('')}</select></label><label class="check-label"><input name="pinyin" type="checkbox" ${ctx.profile.pinyin !== 'off' ? 'checked' : ''}>${c.pinyin}</label><p role="alert" id="preferenceError"></p><button class="primary">${onboarding ? c.enterOrena : c.apply}</button></form>${onboarding ? '' : planUsageSection(ctx)}${onboarding ? '' : growthSummarySection(ctx)}<button class="quiet" id="themeButton">◐ ${c.theme}</button>`,
  });
  /* The theme chooser is built from the registry, so registering a theme is
     the whole of adding one - there is no list of themes written out a second
     time here. Each card carries `data-theme` itself, which means the sample
     inside it is painted by that theme's own tokens rather than by swatches
     copied into this file: a preview cannot drift from the theme it previews.

     Named themes rather than a light/dark switch, so the labels are read from
     copy like every other learner-facing string, in both interface languages. */
  const themeControl = document.createElement('fieldset');
  themeControl.className = 'theme-control';
  const choices = [
    { id: 'system', appearance: '' },
    ...window.orenaTheme.themes,
  ];
  themeControl.innerHTML = `<legend>${esc(c.theme)}</legend><div class="theme-choices">${choices
    .map(({ id }) => {
      const name = id === 'system' ? c.themesystem : c['theme_' + id];
      const note = id === 'system' ? c.themesystemNote : c['theme_' + id + 'Note'];
      // The sample is the theme's own canvas, surface, text and accent. A
      // theme that cannot paint this cannot paint a room either.
      const sample =
        id === 'system'
          ? ''
          : `<span class="theme-sample" data-theme="${esc(id)}" aria-hidden="true"><span class="theme-sample-card"><b></b><i></i></span><span class="theme-sample-accent"></span></span>`;
      return `<label class="theme-choice"><input type="radio" name="orenaTheme" value="${esc(id)}" ${window.orenaTheme.preference === id ? 'checked' : ''}>${sample}<span class="theme-choice-text"><strong>${esc(name)}</strong><span>${esc(note)}</span></span></label>`;
    })
    .join('')}</div>`;
  sheet.querySelector('#themeButton').replaceWith(themeControl);
  themeControl.onchange = (event) => {
    if (event.target.name === 'orenaTheme') window.orenaTheme.set(event.target.value);
  };
  sheet.querySelector('#preferencesForm').onsubmit = async (event) => {
    event.preventDefault();
    if (pendingWrites) return;
    const form = event.currentTarget,
      data = new FormData(form);
    const learningChanged = data.get('learning') !== ctx.language;
    form.inert = true;
    try {
      // Save full profile, preserving protected account settings. Language
      // changes wait for current evidence writes to finish.
      if (learningChanged) await api.setLanguage(data.get('learning'));
      ctx.language = String(data.get('learning'));
      /* Send the two settings this form owns, against the version that was
         read when it opened. Read-modify-writing the whole profile meant a
         second device saving a different preference lost whichever change
         landed first, silently; now the server refuses the stale write and the
         learner is told to reopen rather than being quietly overruled. */
      ctx.profile = await api.patchLearnerProfile({
        expected_version: ctx.profile.version ?? '',
        pinyin: data.has('pinyin') ? 'auto' : 'off',
        support_language: data.get('support'),
      });
      ctx.support = ctx.profile.support_language || ctx.profile.native_language;
      ctx.ui = uiLocale(data.get('support'));
      ctx.c = copy[ctx.ui];
      try {
        storage.setItem('orena.support', String(data.get('support') || ''));
      } catch {}
      ctx.memory = learnerMemory(storage, ctx.owner, ctx.language);
      sheet.close();
      // Content identities are language-scoped. A language switch returns to
      // a valid entry, never reopens an encounter from the previous language.
      if (learningChanged) history.replaceState(null, '', link());
      await render();
    } catch (error) {
      /* Somewhere else changed these first. Retrying automatically would
         overwrite whatever that was, which is the thing the version check
         exists to prevent - so the current values are fetched and shown, and
         applying again is the learner's decision. */
      if (error?.status === 409) {
        try {
          ctx.profile = await api.learnerProfile();
          ctx.support = ctx.profile.support_language || ctx.profile.native_language;
          form.elements.pinyin.checked = ctx.profile.pinyin !== 'off';
          form.elements.support.value = ctx.support;
        } catch {}
      }
      sheet.querySelector('#preferenceError').textContent =
        error?.status === 409 ? c.preferencesMoved : error.message;
      form.inert = false;
    }
  };
}
function validVideo(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.port)
      return false;
    if (url.hostname === 'youtu.be') return /^\/[\w-]{11}$/.test(url.pathname);
    return (
      ['youtube.com', 'www.youtube.com', 'm.youtube.com'].includes(
        url.hostname,
      ) &&
      ((url.pathname === '/watch' &&
        /^[\w-]{11}$/.test(url.searchParams.get('v') || '')) ||
        /^\/(shorts|embed)\/[\w-]{11}$/.test(url.pathname))
    );
  } catch {
    return false;
  }
}
function importContent() {
  const c = ctx.c;
  const sheet = dialog({
    title: c.bring,
    body: `<div class="import-choice"><button data-kind="text" aria-pressed="true">${c.textTab}</button><button data-kind="media" aria-pressed="false">${c.mediaTab}</button></div><form id="textImport"><label>${c.title}<input name="title" maxlength="120" required></label><label>${c.text}<textarea name="text" rows="7" maxlength="12000" required lang="${ctx.language}"></textarea></label><p>${c.textHelp}</p><p role="alert"></p><button class="primary">${c.importAction} ↗</button></form><form id="mediaImport" hidden><label>${c.url}<input name="url" type="url" inputmode="url" required></label><p>${c.mediaHelp}</p><p role="alert"></p><button class="primary">${c.importAction} ↗</button></form>`,
  });
  sheet.querySelectorAll('[data-kind]').forEach(
    (button) =>
      (button.onclick = () => {
        sheet
          .querySelectorAll('[data-kind]')
          .forEach((x) => x.setAttribute('aria-pressed', String(x === button)));
        sheet.querySelector('#textImport').hidden =
          button.dataset.kind !== 'text';
        sheet.querySelector('#mediaImport').hidden =
          button.dataset.kind !== 'media';
      }),
  );
  sheet.querySelector('#textImport').onsubmit = (event) => {
    event.preventDefault();
    try {
      const data = new FormData(event.currentTarget);
      const item = ctx.memory.add({
        title: data.get('title'),
        text: data.get('text'),
      });
      sheet.close();
      ctx.go('encounter', { id: item.id });
      if (!ctx.memory.available) status(c.memoryUnavailable);
    } catch {
      event.currentTarget.querySelector('[role=alert]').textContent =
        c.invalidText;
    }
  };
  sheet.querySelector('#mediaImport').onsubmit = (event) => {
    event.preventDefault();
    const url = String(new FormData(event.currentTarget).get('url')).trim();
    if (!validVideo(url)) {
      event.currentTarget.querySelector('[role=alert]').textContent =
        c.invalidUrl;
      return;
    }
    sheet.close();
    ctx.go('encounter', { id: `url:${url}` });
  };
}
/* The last twenty room failures, for the intermittent `#/language` report that
   has never reproduced under observation. `window.orenaRenderFailures()` reads
   them back. Nothing is sent anywhere. */
const renderFailures = [];
window.orenaRenderFailures = () => renderFailures.slice();

async function render() {
  const version = ++generation;
  const startedAt = performance.now();
  cleanup();
  cleanup = () => {};
  document.querySelectorAll('dialog').forEach((x) => x.close());
  ctx.location = route(location.hash);
  root.dataset.experience = experienceFor(ctx.location);
  ctx.alive = () => generation === version;
  const scope = { ...ctx, alive: ctx.alive };
  shell();
  window.scrollTo(0, 0);
  header.set(false);
  /* Announce loading only if there is actually a wait.

     This used to blank the room to a loading line before calling the renderer.
     Half the rooms render synchronously - Speaking, Continue, a conversation -
     so the line appeared and was replaced within the same frame, and choosing
     another starting point looked like the whole page reloading rather than
     one panel changing. A synchronous render has no latency to announce.

     The timer is a macrotask and a synchronous renderer finishes in a
     microtask, so it is always cleared before it can fire; a slow one leaves
     the previous room on screen for a moment and then says it is working,
     which is the honest order. */
  const announceLoading = setTimeout(() => {
    if (scope.alive())
      root.innerHTML = `<p class="loading" role="status">${ctx.c.loading}</p>`;
  }, 150);
  try {
    const page = ctx.location.page;
    const result =
      page === 'collection'
        ? renderCollection(root, scope)
        : page === 'admin'
          ? await renderAdmin(root, scope)
        : page === 'continue'
        ? (renderContinue(root, scope), bindContentRails(root))
        : page === 'encounter'
        ? await renderEncounter(root, scope)
        : page === 'conversation'
          ? renderConversation(root, scope)
          : page === 'expression'
            ? await renderExpression(root, scope)
            : page === 'language' || ctx.location.intent === 'recall'
              ? await renderLanguage(root, scope)
              : page === 'practice' && ctx.location.intent === 'speaking'
                ? renderSpeaking(root, scope)
                : page === 'practice' && ctx.location.intent === 'grammar'
                  ? await renderGrammar(root, scope)
                  : await renderWorld(root, scope);
    clearTimeout(announceLoading);
    if (!scope.alive()) {
      result?.();
      return;
    }
    cleanup = result || (() => {});
    root.querySelector('h1')?.setAttribute('tabindex', '-1');
    root.querySelector('h1')?.focus({ preventScroll: true });
  } catch (error) {
    clearTimeout(announceLoading);
    /* Keep what a room was doing when it failed.

       `#/language` has reported "temporarily unavailable" inside long
       multi-room sweeps and never once in isolation, so the next occurrence is
       the only chance to learn anything from it - and until now the screen said
       "unavailable" and the console said nothing at all. This records the route,
       the language, how long the render had been running, which render
       generation it was and whether that generation was still current, plus the
       error itself. It changes no behaviour and fixes nothing: there is no
       evidence yet for what to fix, and a guess would only make the next
       occurrence harder to read.

       Kept in memory and on the object, not sent anywhere: this is a device
       diagnostic, not telemetry. */
    const failure = {
      at: new Date().toISOString(),
      hash: location.hash,
      page: ctx.location.page,
      intent: ctx.location.intent,
      language: ctx.language,
      generation: version,
      stillCurrent: scope.alive(),
      elapsedMs: Math.round(performance.now() - startedAt),
      name: error?.name,
      status: error?.status,
      message: error?.message,
      stack: String(error?.stack || '').slice(0, 320),
    };
    renderFailures.push(failure);
    if (renderFailures.length > 20) renderFailures.shift();
    console.error('[orena] room failed to render', failure);
    if (scope.alive()) {
      // Retrying a route that is gone - the wrong language, a removed import,
      // an id that never existed - only fails again, so always offer the way
      // back out as well.
      /* Short, and in the room the learner was actually in.

         This used to open with the full "this part of your world" sentence as
         a page-sized heading and then print the same sentence again as the
         body, because that is what was thrown - and it offered "Discover",
         which does not say where it goes. It also had no idea which room had
         failed, so a Listening item that could not open showed a Reading page.
         The way back is now the room the learner came from (D-057 rule 13). */
      const r = referenceCopy[ctx.ui];
      const room = experienceFor(ctx.location);
      const back =
        room === 'listening'
          ? { href: link('practice', { intent: 'follow' }), label: r.listening }
          : room === 'reading'
            ? { href: link('practice', { intent: 'reading' }), label: r.reading }
            : { href: link(), label: r.discover };
      /* No technical detail on the page. Whatever was thrown is a developer's
         sentence - an English server message, an HTTP status - and printing it
         under a Chinese heading is how untranslated text reaches a learner.
         The failure itself is already recorded in `renderFailures` and the
         console, which is where a diagnostic belongs. */
      root.innerHTML = `<section class="room-failed"><h1>${esc(ctx.c.cantOpen)}</h1><div class="button-row"><button class="primary" id="retry">${esc(ctx.c.retry)}</button><a class="outline" href="${esc(back.href)}">${esc(String(ctx.c.backTo).replace('{room}', back.label))}</a></div></section>`;
      root.querySelector('#retry').onclick = render;
      root.querySelector('h1').setAttribute('tabindex', '-1');
      root.querySelector('h1').focus({ preventScroll: true });
    }
  }
}
async function boot() {
  try {
    const [user, languages, profile, commerce, growth] = await Promise.all([
      api.me(),
      api.languages(),
      api.learnerProfile(),
      // Best-effort: a learner's plan/usage read must never block boot or
      // stand for a real outage the way the other three awaits do.
      api.productCommerce().catch(() => null),
      // Same reasoning for the growth glance: `all` so an undated record
      // (grammar has no completion timestamp) is never silently excluded.
      api.learnerSummary('all').catch(() => null),
    ]);
    ctx.supportLanguages = languages.support_languages || [];
    ctx.languageProfiles = languages.languages || [];
    ctx.user = user;
    ctx.owner = user.email || user.mode || 'local';
    ctx.language = languages.active;
    ctx.profile = profile;
    ctx.commerce = commerce;
    ctx.growth = growth;
    ctx.support = profile.support_language || profile.native_language || 'en';
    ctx.ui = uiLocale(ctx.support);
    ctx.c = copy[ctx.ui];
    try {
      storage.setItem('orena.support', ctx.support);
    } catch {
      // A device that cannot keep it still honours it for this visit.
    }
    ctx.memory = learnerMemory(storage, ctx.owner, ctx.language);
    // New product direction remains internal until the human release gate.
    if (!user.is_admin) {
      root.innerHTML = `<section class="empty"><h1>orena</h1><p>${ctx.c.limited}</p><a href="/account">${ctx.c.account}</a></section>`;
      return;
    }
    // "Skip to content" is a fragment link, and letting it write #main into the
    // hash reads as a route change - the keyboard entry point would throw the
    // learner back to Discover. Move focus ourselves and leave the route alone.
    document.querySelector('a.skip')?.addEventListener('click', (event) => {
      event.preventDefault();
      root.focus({ preventScroll: true });
      root.scrollIntoView({ block: 'start' });
    });
    window.addEventListener('hashchange', render);
    await render();
    if (!profile.exists) preferences(true);
  } catch (error) {
    root.innerHTML = `<section class="room-failed"><h1>${esc(ctx.c.cantOpen)}</h1><button class="primary" onclick="location.reload()">${esc(ctx.c.retry)}</button></section>`;
  }
}
boot();
