import { esc } from './html.js';
import { pageIntro } from './patterns.js';

const alive = (ctx) => (typeof ctx.alive === 'function' ? ctx.alive() : true);

function valueLabel(c, value) {
  return c[`adminValue_${value}`] || value || '—';
}

function frame(c, body) {
  return `<div class="admin-room">${pageIntro({
    eyebrow: c.admin,
    title: c.adminTitle,
    note: c.adminNote,
    compact: true,
  })}<section class="thread-shelf admin-summary" aria-live="polite">${body}</section></div>`;
}

function loading(c) {
  return frame(c, `<p class="loading" role="status">${esc(c.adminLoading)}</p>`);
}

function empty(c) {
  return frame(c, `<p class="empty">${esc(c.adminEmpty)}</p>`);
}

function error(c) {
  return frame(c, `<div class="notice" role="alert"><p>${esc(c.adminUnavailable)}</p><button class="quiet" type="button" data-admin-retry>${esc(c.adminRetry)}</button></div>`);
}

function summary(c, payload) {
  const indicators = Array.isArray(payload.indicators) ? payload.indicators.filter((item) => item && typeof item === 'object') : [];
  const rows = indicators.map((item) => `<li><strong>${esc(c[`adminIndicator_${item.name}`] || item.name || '—')}</strong><span>${esc(valueLabel(c, item.state))}</span><small>${esc(c[`adminSource_${item.name}`] || item.source || '—')}</small>${item.detail ? `<p>${esc(item.detail)}</p>` : ''}</li>`).join('');
  return frame(c, `<div class="section-head"><div><h2>${esc(c.adminIndicators)}</h2><p>${esc(c.adminState)}: <strong>${esc(valueLabel(c, payload.evidence_state || payload.state))}</strong></p></div><p>${esc(c.adminApproval)}: <strong>${esc(valueLabel(c, payload.approval_state))}</strong></p></div><ul class="admin-indicators">${rows}</ul><p class="meta"><strong>${esc(c.adminRedaction)}:</strong> ${esc(payload.redaction || '—')}</p>`);
}

export async function renderAdmin(root, ctx) {
  const c = ctx.c;
  root.innerHTML = loading(c);
  try {
    const payload = await ctx.api.adminReadinessSummary();
    if (!alive(ctx)) return;
    if (!payload || payload.available === false) {
      root.innerHTML = empty(c);
      return;
    }
    const indicators = Array.isArray(payload.indicators) ? payload.indicators : [];
    root.innerHTML = indicators.length ? summary(c, payload) : empty(c);
  } catch {
    if (!alive(ctx)) return;
    root.innerHTML = error(c);
    root.querySelector('[data-admin-retry]')?.addEventListener('click', () => renderAdmin(root, ctx));
  }
}
