import { api } from './infrastructure/api.js';
import { copy } from './ui/copy.js';
import { esc, dialog, status } from './ui/html.js';
import { route, link } from './product/intent.js';
import { learnerMemory } from './product/memory.js';
import { renderWorld } from './ui/world.js';
import { renderEncounter } from './ui/encounter.js';
import {
  renderExpression,
  renderLanguage,
  renderGrammar,
} from './ui/expression.js';

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
const ui = storage.getItem('orena.interface') === 'zh' ? 'zh' : 'en';
const ctx = {
  api,
  ui,
  c: copy[ui],
  language: 'en',
  profile: {},
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
  const c = ctx.c,
    current = ctx.location.page;
  document.documentElement.lang = ctx.ui === 'zh' ? 'zh-Hans' : 'en';
  document.documentElement.dataset.learning = ctx.language;
  document.getElementById('shell').innerHTML =
    `<a class="brand" href="#/" aria-label="Orena"><span class="brand-tail" aria-hidden="true"></span>orena</a><nav aria-label="Orena">${[
      ['discover', c.discover],
      ['practice', c.practice],
      ['content', c.content],
      ['language', c.language],
    ]
      .map(
        ([page, title]) =>
          `<a href="${link(page)}" ${current === page ? 'aria-current="page"' : ''}>${title}</a>`,
      )
      .join(
        '',
      )}</nav><div class="shell-actions"><button class="bring-button" aria-label="${c.bring}" data-bring>＋ <span>${c.bring}</span></button><button class="account-button" data-preference aria-label="${c.preferences}">${ctx.language.toUpperCase()} <span aria-hidden="true">☰</span></button></div>`;
  document.querySelector('[data-bring]').onclick = importContent;
  document.querySelector('[data-preference]').onclick = () => preferences();
  document.getElementById('footer').innerHTML =
    `<a href="#/" class="brand-small">orena</a><span>${c.internal}</span><button class="quiet" data-account>${c.preferences} ↗</button>`;
  document
    .querySelector('[data-account]')
    ?.addEventListener('click', () => preferences());
}
function preferences(onboarding = false) {
  const c = ctx.c;
  const sheet = dialog({
    title: onboarding ? c.welcome : c.preferences,
    body: `<p>${onboarding ? c.welcomeNote : c.local}</p><form id="preferencesForm"><label>${c.learning}<select name="learning"><option value="en" ${ctx.language === 'en' ? 'selected' : ''}>English</option><option value="zh" ${ctx.language === 'zh' ? 'selected' : ''}>中文</option></select></label><label>${c.interface}<select name="interface"><option value="en" ${ctx.ui === 'en' ? 'selected' : ''}>English</option><option value="zh" ${ctx.ui === 'zh' ? 'selected' : ''}>中文</option></select></label><label>${c.support}<select name="support">${ctx.supportLanguages.map(({ code, label: title }) => `<option value="${code}" ${ctx.support === code ? 'selected' : ''}>${title}</option>`).join('')}</select></label><label class="check-label"><input name="pinyin" type="checkbox" ${ctx.profile.pinyin !== 'off' ? 'checked' : ''}>${c.pinyin}</label><p role="alert" id="preferenceError"></p><button class="primary">${onboarding ? c.enterOrena : c.apply}</button></form><button class="quiet" id="themeButton">◐ ${c.theme}</button>`,
  });
  sheet.querySelector('#themeButton').onclick = () => {
    const theme =
      document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    try {
      storage.setItem('orena.theme', theme);
    } catch {}
  };
  sheet.querySelector('#preferencesForm').onsubmit = async (event) => {
    event.preventDefault();
    if (pendingWrites) return;
    const form = event.currentTarget,
      data = new FormData(form);
    form.inert = true;
    try {
      // Save full profile, preserving protected account settings. Language
      // changes wait for current evidence writes to finish.
      if (data.get('learning') !== ctx.language)
        await api.setLanguage(data.get('learning'));
      ctx.language = String(data.get('learning'));
      const prior = await api.learnerProfile();
      ctx.profile = await api.saveLearnerProfile({
        goal: prior.goal || 'everyday',
        style: prior.style || 'guided',
        pinyin: data.has('pinyin') ? 'auto' : 'off',
        native_language: data.get('support'),
        theme_preset: prior.theme_preset || 'editorial',
      });
      ctx.support = ctx.profile.support_language || ctx.profile.native_language;
      ctx.ui = String(data.get('interface'));
      ctx.c = copy[ctx.ui];
      try {
        storage.setItem('orena.interface', ctx.ui);
      } catch {}
      ctx.memory = learnerMemory(storage, ctx.owner, ctx.language);
      sheet.close();
      // Content identities are language-scoped. A language switch returns to
      // a valid entry, never reopens an encounter from the previous language.
      history.replaceState(null, '', link());
      await render();
    } catch (error) {
      sheet.querySelector('#preferenceError').textContent = error.message;
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
async function render() {
  const version = ++generation;
  cleanup();
  cleanup = () => {};
  document.querySelectorAll('dialog').forEach((x) => x.close());
  ctx.location = route(location.hash);
  ctx.alive = () => generation === version;
  const scope = { ...ctx, alive: ctx.alive };
  shell();
  root.innerHTML = `<p class="loading" role="status">${ctx.c.loading}</p>`;
  window.scrollTo(0, 0);
  try {
    const page = ctx.location.page;
    const result =
      page === 'encounter'
        ? await renderEncounter(root, scope)
        : page === 'expression'
          ? await renderExpression(root, scope)
          : page === 'language' || ctx.location.intent === 'recall'
            ? await renderLanguage(root, scope)
            : page === 'practice' && ctx.location.intent === 'grammar'
              ? await renderGrammar(root, scope)
              : await renderWorld(root, scope);
    if (!scope.alive()) {
      result?.();
      return;
    }
    cleanup = result || (() => {});
    root.querySelector('h1')?.setAttribute('tabindex', '-1');
    root.querySelector('h1')?.focus({ preventScroll: true });
  } catch (error) {
    if (scope.alive()) {
      // Retrying a route that is gone - the wrong language, a removed import,
      // an id that never existed - only fails again, so always offer the way
      // back out as well.
      root.innerHTML = `<section class="empty"><h1>${ctx.c.unavailable}</h1><p>${esc(error.message)}</p><div class="button-row"><button class="primary" id="retry">${ctx.c.retry}</button><a class="outline" href="${link()}">${ctx.c.discover} ↗</a></div></section>`;
      root.querySelector('#retry').onclick = render;
      root.querySelector('h1').setAttribute('tabindex', '-1');
      root.querySelector('h1').focus({ preventScroll: true });
    }
  }
}
async function boot() {
  try {
    document.documentElement.dataset.theme =
      storage.getItem('orena.theme') === 'dark' ? 'dark' : 'light';
    const [user, languages, profile] = await Promise.all([
      api.me(),
      api.languages(),
      api.learnerProfile(),
    ]);
    ctx.supportLanguages = languages.support_languages || [];
    ctx.user = user;
    ctx.owner = user.email || user.mode || 'local';
    ctx.language = languages.active;
    ctx.profile = profile;
    ctx.support = profile.support_language || profile.native_language || 'en';
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
    root.innerHTML = `<section class="empty"><h1>${ctx.c.unavailable}</h1><p>${esc(error.message)}</p><button onclick="location.reload()">${ctx.c.retry}</button></section>`;
  }
}
boot();
