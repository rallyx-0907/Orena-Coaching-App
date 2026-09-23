/* The Platform Admin console frame.

   Six sections behind one route: `#/admin` is the Overview and
   `#/admin?id=<section>` is every other section, so the router needs nothing
   new and every section can be linked to. The frame is operator tooling: a
   small heading, the runtime facts an operator checks first, the sections,
   and a status line for the result of an action. No hero, no artwork.

   The console's stylesheet is loaded when the console is first opened, so a
   learner's page never downloads admin styling. */
import { link } from '../product/intent.js';
import { adminApi } from './api.js';
import { adminText } from './copy.js';
import { chip, esc, fill, notice } from './format.js';
import { renderOverview } from './overview.js';
import { renderAi } from './ai.js';
import { renderUsers } from './users.js';
import { renderContent } from './content.js';
import { renderImports } from './imports.js';
import { renderOperations } from './operations.js';

export const SECTIONS = ['overview', 'ai', 'users', 'content', 'imports', 'operations'];
/* Reading is a Content view, not a seventh area (canonical design). It briefly
   had its own tab; links to it stay valid rather than 404-ing an operator's
   bookmark. */
const LEGACY_SECTIONS = { reading: { section: 'content', params: { kind: 'reading' } } };
const RENDERERS = {
  overview: renderOverview,
  ai: renderAi,
  users: renderUsers,
  content: renderContent,
  imports: renderImports,
  operations: renderOperations,
};
const STYLESHEET = '/orena-assets/admin/admin.css';

/* What the console remembers between sections within one visit: the last
   attention list (for the section badges) and the runtime facts. */
const memory = { attention: null, runtime: null, runtimeAt: 0 };

export function sectionFrom(location) {
  const id = String(location?.id || '');
  if (LEGACY_SECTIONS[id]) return LEGACY_SECTIONS[id].section;
  return SECTIONS.includes(id) ? id : 'overview';
}

/* What a legacy id carried with it - `?id=reading` means Content, scoped to
   Reading, not Content's first tab. */
export function legacyParams(location) {
  return LEGACY_SECTIONS[String(location?.id || '')]?.params || null;
}

export function sectionHref(section, params = {}) {
  const base = link('admin', { id: section === 'overview' ? '' : section });
  const extra = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) if (value) extra.set(key, String(value));
  if (!extra.size) return base;
  return `${base}${base.includes('?') ? '&' : '?'}${extra}`;
}

export function hashParams(hash) {
  const query = String(hash || '').split('?')[1] || '';
  return Object.fromEntries(new URLSearchParams(query));
}

export function badgeCounts(attention) {
  const counts = {};
  for (const item of attention || []) counts[item.section] = (counts[item.section] || 0) + 1;
  return counts;
}

export function tabsView({ section, t, attention = null }) {
  const badges = badgeCounts(attention);
  const tabs = SECTIONS.map((id) => {
    const count = id === 'overview' ? 0 : badges[id] || 0;
    return `<a class="ac-tab" href="${esc(sectionHref(id))}"${id === section ? ' aria-current="page"' : ''}>${esc(t[`section_${id}`])}${count ? `<span class="ac-tab__badge">${count}</span>` : ''}</a>`;
  }).join('');
  return `<nav class="ac-tabs" aria-label="${esc(t.sectionsLabel)}">${tabs}</nav>`;
}

export function frameView({ section, t, attention = null }) {
  return `<div class="ac-console" data-section="${esc(section)}"><header class="ac-head"><div class="ac-head__title"><h1>${esc(t.title)}</h1><div class="ac-head__env" data-ac-env></div></div>${tabsView({ section, t, attention })}<p class="ac-toast" role="status" aria-live="polite" data-ac-toast></p></header><div class="ac-body" data-ac-section><p class="ac-empty" role="status">${esc(t.loading)}</p></div></div>`;
}

export function envView(runtime, t) {
  if (!runtime) return '';
  const mode = runtime.ai?.learner_runtime_mode;
  return [
    chip(runtime.persistence_backend === 'postgresql' ? 'ok' : 'invalid', t, { label: fill(t.envBackend, { value: runtime.persistence_backend || '—' }) }),
    chip(mode === 'capability' ? 'ok' : 'info', t, { label: fill(t.envRuntime, { value: t[`status_${mode}`] || mode || '—' }) }),
    `<span class="ac-muted">${esc(fill(t.envVersion, { value: runtime.app_version || '—' }))}</span>`,
  ].join('');
}

function ensureStylesheet() {
  if (typeof document === 'undefined') return Promise.resolve();
  if (document.querySelector(`link[href="${STYLESHEET}"]`)) return Promise.resolve();
  return new Promise((resolve) => {
    const sheet = document.createElement('link');
    sheet.rel = 'stylesheet';
    sheet.href = STYLESHEET;
    sheet.onload = resolve;
    sheet.onerror = resolve;
    document.head.append(sheet);
    // Never block the console on a slow stylesheet; it is operable unstyled.
    setTimeout(resolve, 1500);
  });
}

export async function renderConsole(root, ctx) {
  const t = adminText(ctx.ui);
  const section = sectionFrom(ctx.location);
  const alive = typeof ctx.alive === 'function' ? ctx.alive : () => true;
  const api = ctx.adminApi || adminApi;
  await ensureStylesheet();
  if (!alive()) return undefined;
  /* Built off-document and attached once its section is ready. The router
     writes a loading line into the room when a render takes a moment; a frame
     attached early would be overwritten by it, and the section would then
     paint into a node that is no longer on the page. */
  const detached = typeof document !== 'undefined';
  const frame = detached ? document.createElement('div') : root;
  frame.innerHTML = frameView({ section, t, attention: memory.attention });
  const scope = detached ? frame.firstElementChild : root;
  const host = scope.querySelector?.('[data-ac-section]');
  const toast = scope.querySelector?.('[data-ac-toast]');
  const envHost = scope.querySelector?.('[data-ac-env]');
  let toastTimer = null;

  const fresh = memory.runtime && Date.now() - memory.runtimeAt < 60000;
  (fresh ? Promise.resolve(memory.runtime) : api.runtime())
    .then((runtime) => {
      memory.runtime = runtime;
      memory.runtimeAt = Date.now();
      if (alive() && envHost) envHost.innerHTML = envView(runtime, t);
    })
    .catch(() => {});

  const env = {
    t,
    ui: ctx.ui,
    api,
    ctx,
    alive,
    params: { ...(typeof location === 'undefined' ? {} : hashParams(location.hash)), ...(legacyParams(ctx.location) || {}) },
    href: sectionHref,
    remember: (facts) => {
      memory.attention = facts.attention;
      if (!alive()) return;
      const nav = scope.querySelector?.('.ac-tabs');
      if (nav) nav.outerHTML = tabsView({ section, t, attention: memory.attention });
    },
    notify: (message) => {
      if (!toast) return;
      clearTimeout(toastTimer);
      toast.textContent = message;
      toastTimer = setTimeout(() => {
        toast.textContent = '';
      }, 6000);
    },
  };

  let cleanup = () => {};
  const run = async () => {
    try {
      const result = await RENDERERS[section](host, env);
      cleanup = typeof result === 'function' ? result : () => {};
    } catch (error) {
      if (!alive() || !host) return;
      host.innerHTML = `${notice(error?.message ? `${t.loadFailed} ${error.message}` : t.loadFailed, 'bad')}<button type="button" class="ac-button" data-ac-retry>${esc(t.retry)}</button>`;
      host.querySelector('[data-ac-retry]')?.addEventListener('click', run, { once: true });
    }
  };
  if (host) await run();
  if (detached) {
    if (!alive()) return () => cleanup();
    root.replaceChildren(scope);
  }
  return () => {
    clearTimeout(toastTimer);
    cleanup();
  };
}
