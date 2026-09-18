/* Users: how many people have accounts, who is learning, and one account at
   a time when an operator needs it.

   Aggregates come from /api/admin/console/users/summary; the list from
   /api/admin/console/users, which masks every address and audits the read.
   The detail view is operational metadata and counts only - it never shows
   what a learner wrote, read, said or kept. Retention is shown only when the
   sample behind it is large enough to mean something. */
import { adminApi } from './api.js';
import { barList, bindCharts, columnChart } from './charts.js';
import { openDrawer } from './drawer.js';
import { chip, dateShort, dateTime, esc, fill, info, kv, languageName, notice, num, pager, panel, relative, select, table } from './format.js';

export const PAGE_SIZE = 25;

function tile(label, value, sub, hintText = '') {
  return `<div class="ac-kpi"><span class="ac-kpi__label">${esc(label)}${hintText ? info(hintText, label) : ''}</span><strong class="ac-kpi__value">${esc(value)}</strong><span class="ac-kpi__sub">${esc(sub)}</span></div>`;
}

export function retentionView(windows, t, ui) {
  return `<ul class="ac-retention">${(windows || [])
    .map((window) => `<li><span class="ac-retention__days">${esc(fill(t.retentionDays, { days: window.days }))}</span>${
      window.state === 'ready'
        ? `<strong>${esc(fill(t.retentionValue, { rate: num(window.rate_percent, ui), eligible: num(window.eligible_learners, ui) }))}</strong>`
        : chip('insufficient', t, { label: fill(t.retentionInsufficient, { eligible: num(window.eligible_learners, ui), minimum: num(window.minimum_sample, ui) }) })
    }</li>`)
    .join('')}</ul>`;
}

export function usersSummaryView(summary, t, ui) {
  if (!summary?.available) return notice(t.accountsUnavailable, 'neutral');
  const accounts = summary.accounts || {};
  const activity = summary.activity || {};
  const segments = summary.segments_30d || {};
  const strip = `<div class="ac-kpis ac-kpis--4">${[
    tile(t.summaryAccounts, num(accounts.total, ui), fill(t.summaryAccountsSub, { admins: num(accounts.admins, ui) })),
    tile(t.summaryNew, num(accounts.new_7d, ui), fill(t.summaryNewSub, { value: num(accounts.new_30d, ui) })),
    tile(t.summaryActive, num(activity.active_7d, ui), fill(t.summaryActiveSub, { value: num(activity.active_30d, ui) }), t.activeHint),
    tile(t.summarySegments, num(segments.active, ui), fill(t.summarySegmentsValue, { new: num(segments.new, ui), returning: num(segments.returning, ui) }), t.returningHint),
  ].join('')}</div>`;
  const charts = `<div class="ac-grid ac-grid--2">${panel({
    body: columnChart({ title: t.chartRegistrations, series: (accounts.registrations || []).map((point) => ({ date: point.date, value: point.count })), t, ui }),
  })}${panel({
    body: columnChart({ title: t.chartActive, series: (activity.daily || []).map((point) => ({ date: point.date, value: point.learners })), t, ui }),
  })}</div>`;
  const profiles = summary.languages?.profiles || [];
  const active = new Map((summary.languages?.active || []).map((row) => [row.language, row.learners]));
  const languages = panel({
    title: t.chartLanguages,
    body: barList({
      ui,
      rows: profiles.map((row) => ({
        label: languageName(row.language, t),
        value: row.learners,
        note: `${t.languagesActive}: ${num(active.get(row.language) || 0, ui)}`,
      })),
      empty: t.notAvailable,
    }),
  });
  const retention = panel({
    title: t.retentionTitle,
    actions: info(t.retentionHint, t.retentionTitle),
    body: retentionView(summary.retention, t, ui),
  });
  const level = panel({ title: t.levelTitle, body: `<p class="ac-note">${esc(t.levelNotRecorded)}</p>` });
  return `${strip}${charts}<div class="ac-grid ac-grid--3">${languages}${retention}${level}</div>`;
}

export function accountsToolbar(filters, languages, t) {
  const languageOptions = [['', t.all], ...languages.map((code) => [code, languageName(code, t)])];
  return `<form class="ac-toolbar" data-ac-filters role="search"><label class="ac-field ac-field--search"><span class="sr-only">${esc(t.searchAccounts)}</span><input type="search" name="q" value="${esc(filters.q || '')}" placeholder="${esc(t.searchAccounts)}" autocomplete="off"></label>${select({
    name: 'language', label: t.filterLanguage, options: languageOptions, value: filters.language || '',
  })}${select({
    name: 'activity', label: t.filterActivity, value: filters.activity || '',
    options: [['', t.all], ['active', t.activity_active], ['idle', t.activity_idle], ['never', t.activity_never]],
  })}${select({
    name: 'role', label: t.filterRole, value: filters.role || '',
    options: [['', t.all], ['admin', t.role_admin], ['user', t.role_user]],
  })}${select({
    name: 'sort', label: t.sortLabel, value: filters.sort || 'joined',
    options: [['joined', t.sort_joined], ['joined_asc', t.sort_joined_asc], ['active', t.sort_active], ['name', t.sort_name]],
  })}</form>`;
}

export function accountsTable(list, t, ui) {
  if (!list?.available) return notice(t.accountsUnavailable, 'neutral');
  const rows = (list.items || []).map((item) => ({
    attributes: ` data-account-row="${esc(item.id)}"`,
    cells: [
      `<div class="ac-cell-stack"><button type="button" class="ac-rowlink" data-account="${esc(item.id)}">${esc(item.display_name || t.unnamed)}</button>${item.role === 'admin' ? `<span class="ac-tag">${esc(t.role_admin)}</span>` : ''}<span class="ac-muted">${esc(item.email_masked || '')}</span></div>`,
      `<span title="${esc(dateTime(item.joined_at, ui))}">${esc(dateShort(item.joined_at, ui))}</span>`,
      esc((item.languages || []).map((code) => languageName(code, t)).join(t.enumSep) || '—'),
      `<span class="ac-muted">${esc(item.level || t.levelUnknown)}</span>`,
      item.last_active_at ? `<span title="${esc(dateTime(item.last_active_at, ui))}">${esc(relative(item.last_active_at, ui))}</span>` : '<span class="ac-muted">—</span>',
      chip(item.status, t),
    ],
  }));
  return `${table({
    head: [t.colAccount, t.colJoined, t.colLanguages, t.colLevel, t.colLastActive, t.colStatus],
    rows,
    empty: t.noAccounts,
    className: 'ac-table--accounts',
  })}${pager({ offset: list.offset || 0, limit: list.limit || PAGE_SIZE, total: list.total || 0 }, t, ui)}`;
}

export function accountDetailView(detail, t, ui) {
  const profiles = table({
    head: [t.colLanguage, t.colGoal, t.colStyle, t.colSupport, t.colUpdated],
    rows: (detail.profiles || []).map((profile) => [
      esc(languageName(profile.language, t)),
      esc(t[`goal_${profile.goal}`] || profile.goal || '—'),
      esc(t[`style_${profile.style}`] || profile.style || '—'),
      esc(languageName(profile.support_language, t)),
      esc(dateShort(profile.updated_at, ui)),
    ]),
    empty: t.detailNoProfiles,
  });
  const activity = table({
    head: [t.colMeasure, t.colLanguage, { label: t.colCount, numeric: true }, t.colLatest],
    rows: (detail.activity || []).map((row) => [
      esc(t[`measure_${row.measure}`] || row.measure),
      esc(languageName(row.language, t)),
      esc(num(row.count, ui)),
      esc(row.last_at ? relative(row.last_at, ui) : '—'),
    ]),
    empty: t.detailNoActivity,
  });
  return `<div class="ac-stack">${kv([
    [t.colAccount, `<strong>${esc(detail.display_name || t.unnamed)}</strong><br><span>${esc(detail.email || '')}</span>`],
    [t.filterRole, esc(detail.role === 'admin' ? t.role_admin : t.role_user)],
    [t.colStatus, chip(detail.status, t)],
    [t.colJoined, esc(dateTime(detail.joined_at, ui))],
    [t.detailLastLogin, esc(dateTime(detail.last_login_at, ui))],
    [t.colLastActive, esc(detail.last_active_at ? `${relative(detail.last_active_at, ui)} (${dateTime(detail.last_active_at, ui)})` : '—')],
    [t.colLevel, esc(t.levelUnknown)],
  ])}<section><h3>${esc(t.detailProfiles)}</h3>${profiles}</section><section><h3>${esc(t.detailActivity)}</h3>${activity}</section><section><h3>${esc(t.detailActions)}</h3><p class="ac-note">${esc(t.detailNoActions)}</p></section><p class="ac-footnote">${esc(t.detailPrivacy)} ${esc(t.detailAudited)}</p></div>`;
}

export async function renderUsers(container, env) {
  const { t, ui, alive } = env;
  const api = env.api || adminApi;
  const filters = { q: '', language: '', activity: '', role: '', sort: 'joined' };
  let offset = 0;
  let summary = null;
  let list = null;
  let timer = null;

  const [summaryData, listData] = await Promise.all([api.usersSummary(30), api.users({ ...filters, limit: PAGE_SIZE, offset })]);
  if (!alive()) return;
  summary = summaryData;
  list = listData;
  const languages = [...new Set((summary?.languages?.profiles || []).map((row) => row.language))].sort();

  container.innerHTML = `<div class="ac-stack">${usersSummaryView(summary, t, ui)}${panel({
    title: t.accountsTitle,
    body: `${accountsToolbar(filters, languages, t)}<div data-ac-accounts>${accountsTable(list, t, ui)}</div>`,
  })}</div>`;
  bindCharts(container, { ui });
  const results = container.querySelector('[data-ac-accounts]');

  const reload = async () => {
    results.setAttribute('aria-busy', 'true');
    try {
      list = await api.users({ ...filters, limit: PAGE_SIZE, offset });
    } catch {
      list = null;
    }
    if (!alive()) return;
    results.removeAttribute('aria-busy');
    results.innerHTML = list ? accountsTable(list, t, ui) : notice(t.loadFailed, 'bad');
  };

  const openAccount = async (id) => {
    const drawer = openDrawer({ title: t.colAccount, body: `<p class="ac-empty">${esc(t.loading)}</p>`, label: t.close });
    try {
      const detail = await api.user(id);
      if (!drawer.element.isConnected) return;
      drawer.set(accountDetailView(detail, t, ui));
    } catch (error) {
      if (drawer.element.isConnected) drawer.set(notice(error?.message || t.loadFailed, 'bad'));
    }
  };

  const form = container.querySelector('[data-ac-filters]');
  form?.addEventListener('submit', (event) => event.preventDefault());
  form?.addEventListener('input', (event) => {
    if (event.target.name !== 'q') return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      filters.q = event.target.value.trim();
      offset = 0;
      reload();
    }, 350);
  });
  form?.addEventListener('change', (event) => {
    if (!['language', 'activity', 'role', 'sort'].includes(event.target.name)) return;
    filters[event.target.name] = event.target.value;
    offset = 0;
    reload();
  });
  results?.addEventListener('click', (event) => {
    const page = event.target.closest('[data-page]');
    if (page) {
      offset = Math.max(0, offset + (page.dataset.page === 'next' ? PAGE_SIZE : -PAGE_SIZE));
      reload();
      return;
    }
    // The name is the keyboard target; the rest of the row is a larger
    // pointer target for the same action.
    const target = event.target.closest('[data-account]') || event.target.closest('[data-account-row]');
    if (target) openAccount(target.dataset.account || target.dataset.accountRow);
  });
  return () => clearTimeout(timer);
}
